# ABOUTME: Unified orchestration layer for Transfermarkt identity resolution and scoped player refresh policies.

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select

from data.extractors.transfermarkt_extractor import TransfermarktExtractor
from data.extractors.transfermarkt_playwright_extractor import TransfermarktPlaywrightExtractor
from data.managers.transfermarkt_runtime_manager import TransfermarktRuntimeManager
from data.transfermarkt_data_manager import TransfermarktDataManager
from models.db_models import Player, Season
from utils.common import get_current_season
from utils.db_engine import SessionFactory
from utils.proxy_manager import ProxyManager


logger = logging.getLogger(__name__)

MIN_TM_SEASON_START = 2018


def _build_extractor(proxy_manager: ProxyManager) -> TransfermarktExtractor:
    """Return a Playwright extractor if dependencies are available, otherwise CloudScraper."""
    try:
        import playwright  # noqa: F401
        import playwright_stealth  # noqa: F401
        logger.info("TransfermarktRefreshManager: using Playwright+stealth extractor.")
        return TransfermarktPlaywrightExtractor(proxy_manager=proxy_manager)
    except ImportError as exc:
        logger.warning("Playwright unavailable (%s); falling back to CloudScraper extractor.", exc)
        return TransfermarktExtractor(proxy_manager=proxy_manager)


class TransfermarktRefreshManager:
    def __init__(self):
        self.runtime = TransfermarktRuntimeManager()
        self.proxy_manager = ProxyManager()
        self.extractor = _build_extractor(self.proxy_manager)
        self.tm_manager = TransfermarktDataManager(auto_load=False)
        self.last_http_status: Optional[int] = None
        self.last_block_type: Optional[str] = None
        self.last_block_reason: Optional[str] = None
        self.last_result_source: Optional[str] = None
        self.last_cache_fresh: bool = False
        self._load_assisted_cookies()

    def _load_assisted_cookies(self) -> None:
        cookie_jar = self.runtime.get_cookie_jar()
        if not cookie_jar:
            return
        self.extractor.load_cookie_jar(cookie_jar)
        self.tm_manager.extractor.load_cookie_jar(cookie_jar)

    def _season_start_year(self, season_id: str) -> Optional[int]:
        match = re.match(r"^(\d{4})-\d{2}$", str(season_id or ""))
        if not match:
            return None
        return int(match.group(1))

    def get_valid_season_ids(self) -> List[str]:
        current_start = self._season_start_year(get_current_season()) or datetime.now().year
        upper_bound = current_start + 1
        with SessionFactory() as session:
            season_ids = session.execute(select(Season.id)).scalars().all()
        valid = []
        for season_id in season_ids:
            start = self._season_start_year(season_id)
            if start is None:
                continue
            if MIN_TM_SEASON_START <= start <= upper_bound:
                valid.append(season_id)
        return sorted(set(valid))

    def season_ids_for_mode(self, mode: str) -> List[str]:
        valid = self.get_valid_season_ids()
        current = get_current_season()
        current_start = self._season_start_year(current)
        previous = f"{current_start - 1}-{str(current_start)[-2:]}" if current_start else None

        if mode == "new_user_bootstrap":
            return valid
        if mode in {"user_priority_refresh", "current_season_bootstrap"}:
            return [s for s in [current, previous] if s in valid]
        return [s for s in [current] if s in valid]

    def resolve_tm_identity(self, player_id: str, player_name: str = "", team: str = "") -> Optional[int]:
        with SessionFactory() as session:
            player = session.get(Player, player_id)
            if not player:
                return None
            if player.tm_id:
                return int(player.tm_id)
            birth_year = player.birth_date.year if player.birth_date else ((datetime.now().year - player.age) if player.age else None)
            found = self.extractor.search_player_by_name(
                player_name or player.name,
                team=team or getattr(getattr(player, "current_team", None), "name", "") or "",
                nationality=player.nationality or player.birth_country or "",
                birth_year=birth_year,
                position=player.position_main or "",
            )
            if found:
                player.tm_id = found
                session.commit()
                return int(found)
            return None

    def refresh_player(
        self,
        player_id: str,
        *,
        mode: str,
        player_name: str = "",
        team: str = "",
        fetch_photo: bool = False,
        reconcile_position=None,
    ) -> bool:
        tm_id = self.resolve_tm_identity(player_id, player_name=player_name, team=team)
        if not tm_id:
            logger.warning(f"TransfermarktRefreshManager: no tm_id for player {player_id}")
            return False

        seasons = self.season_ids_for_mode(mode)
        if not seasons:
            logger.warning(f"TransfermarktRefreshManager: no valid seasons for mode={mode}")
            return False

        any_updated = False
        for season_id in seasons:
            raw_matches = self.extractor.get_match_history(str(tm_id), season_id)
            self.last_http_status = self.extractor.last_http_status
            self.last_block_type = self.extractor.last_block_type
            self.last_block_reason = self.extractor.last_block_reason
            self.last_result_source = self.extractor.last_result_source
            self.last_cache_fresh = self.extractor.last_cache_fresh
            if self.last_http_status == 405:
                logger.warning(
                    "TransfermarktRefreshManager: 405 for player=%s tm_id=%s season=%s; stopping refresh early.",
                    player_id,
                    tm_id,
                    season_id,
                )
                break
            if raw_matches:
                self.tm_manager._upsert_history_to_sql(player_id, raw_matches)
                any_updated = True

        if fetch_photo:
            with SessionFactory() as session:
                try:
                    self.extractor.fetch_and_store_player_photo(player_id, str(tm_id), session)
                except Exception as exc:
                    logger.warning(f"TransfermarktRefreshManager: photo fetch failed for {player_id}: {exc}")

        if reconcile_position is not None:
            with SessionFactory() as session:
                try:
                    reconcile_position(session, player_id, prefer_transfermarkt=True, extractor=self.extractor)
                    session.commit()
                except Exception as exc:
                    session.rollback()
                    logger.warning(f"TransfermarktRefreshManager: position reconcile failed for {player_id}: {exc}")

        return any_updated
