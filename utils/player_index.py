# ABOUTME: Interface for player identity resolution using the SQL database.
# ABOUTME: Replaces the old JSON-based index with direct SQLAlchemy queries for better performance and consistency.

import logging
import re
from typing import Dict, List, Optional
from sqlalchemy import func, select
from models.db_models import Player, PlayerSeasonStat
from utils.db_engine import SessionFactory

logger = logging.getLogger(__name__)


def _normalize_team_token(value: Optional[str]) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    raw = raw.replace("&", " and ")
    raw = raw.replace("fc", " ")
    raw = raw.replace("-", " ")
    raw = raw.replace(".", " ")
    raw = re.sub(r"[^a-z0-9]+", " ", raw)
    return " ".join(raw.split())

class PlayerIndex:
    """
    Maintains a virtual player ID index backed by SQL.
    Provides backward compatibility with the old JSON-based PlayerIndex API.
    """

    def __init__(self):
        self._loaded = True # Always considered loaded as it proxies to SQL

    # ------------------------------------------------------------------
    # Public API (Backward Compatible)
    # ------------------------------------------------------------------

    def get_player_id(
        self,
        name: str,
        team_id: Optional[str] = None,
        team_name: Optional[str] = None,
    ) -> Optional[str]:
        """Returns the best canonical player ID for a given player name from SQL."""
        session = SessionFactory()
        try:
            stmt = select(Player).where(Player.name == name)
            candidates = session.execute(stmt).scalars().all()
            if not candidates:
                return None
            if len(candidates) == 1:
                return str(candidates[0].id)

            team_token = _normalize_team_token(team_name)
            best_player = None
            best_score = -1
            for player in candidates:
                score = 0
                if team_id and player.current_team_id == team_id:
                    score += 100
                if team_token and _normalize_team_token(player.current_team_id) == team_token:
                    score += 80
                if player.current_team_id:
                    score += 10
                if player.tm_id:
                    score += 6
                if player.position_main:
                    score += 4

                season_count = session.execute(
                    select(func.count()).select_from(PlayerSeasonStat).where(PlayerSeasonStat.player_id == player.id)
                ).scalar_one()
                score += int(season_count)

                if score > best_score:
                    best_score = score
                    best_player = player

            if best_player:
                logger.debug(
                    "Resolved duplicate player name '%s' to id=%s using team_id=%s team_name=%s",
                    name,
                    best_player.id,
                    team_id,
                    team_name,
                )
                return str(best_player.id)
            return None
        finally:
            session.close()

    def get_player_info(self, player_id: str) -> Optional[Dict]:
        """Returns player metadata and active seasons from SQL."""
        session = SessionFactory()
        try:
            player = session.get(Player, str(player_id))
            if not player:
                return None
            
            # Fetch active seasons from player_season_stats
            stmt = select(PlayerSeasonStat.season_id).where(PlayerSeasonStat.player_id == player_id)
            seasons = session.execute(stmt).scalars().all()

            return {
                "canonical_name": player.name,
                "id_type": "wyscout" if not str(player_id).startswith("hk_") else "generated",
                "seasons": list(seasons),
                "fingerprint": {
                    "birth_country": player.birth_country or "",
                    "foot": player.foot or "",
                    "height": str(player.height) if player.height else "0",
                }
            }
        finally:
            session.close()

    def get_all_player_names(self) -> List[str]:
        """Returns all player names stored in the database."""
        session = SessionFactory()
        try:
            stmt = select(Player.name).order_by(Player.name)
            return list(session.execute(stmt).scalars().all())
        finally:
            session.close()

    def build(self, force: bool = False) -> bool:
        """
        No-op for backward compatibility. 
        In the new system, building is handled by the ETL/Migration process.
        """
        logger.debug("PlayerIndex.build() is now a no-op (data managed in SQL).")
        return True

# Module-level singleton for backward compatibility
_player_index = PlayerIndex()

def get_player_index() -> PlayerIndex:
    """Returns the module-level PlayerIndex singleton."""
    return _player_index
