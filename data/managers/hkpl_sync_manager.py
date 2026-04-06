# ABOUTME: Manager to synchronize HK Premier League data from GitHub to SQL.
# ABOUTME: Handles download, normalization, and persistence in SQLAlchemy database.

import logging
import pandas as pd
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_

from data.extractors.hong_kong_extractor import HongKongDataExtractor
from data.processors.hong_kong_processor import HongKongDataProcessor
from models.db_models import Player, Team, Season, PlayerSeasonStat, SystemSyncLog
from utils.db_engine import SessionFactory
from utils.common import get_current_season
from utils.player_index import get_player_index

logger = logging.getLogger(__name__)

_TM_TEXT_TO_ABBR = {
    'goalkeeper': 'GK', 'portero': 'GK',
    'centre-back': 'CB', 'central': 'CB', 'central defender': 'CB', 'defensa central': 'CB', 'defensa': 'CB',
    'right-back': 'RB', 'lateral derecho': 'RB',
    'left-back': 'LB', 'lateral izquierdo': 'LB',
    'right wing-back': 'RWB', 'left wing-back': 'LWB',
    'defensive midfield': 'DM', 'central midfield': 'CM', 'centrocampista': 'CM',
    'attacking midfield': 'AMF', 'mediapunta': 'AMF', 'centrocampista ofensivo': 'AMF',
    'right midfield': 'RM', 'left midfield': 'LM',
    'interior derecho': 'RM', 'interior izquierdo': 'LM',
    'right winger': 'RW', 'left winger': 'LW',
    'right wing forward': 'RWF', 'left wing forward': 'LWF',
    'centre-forward': 'CF', 'centre forward': 'CF', 'delantero centro': 'CF',
    'striker': 'ST', 'second striker': 'SS',
}

_KNOWN_POSITION_CODES = {
    "GK", "CB", "LCB", "RCB", "CB3", "LCB3", "RCB3",
    "LB", "RB", "LWB", "RWB", "LB5", "RB5",
    "DM", "DMF", "LDMF", "RDMF",
    "CM", "LCMF", "RCMF", "CMF",
    "AMF", "LAMF", "RAMF", "MCO",
    "LM", "RM", "LW", "RW", "LWF", "RWF", "EI", "ED", "ID", "II",
    "ST", "CF", "SS",
}

class HKPLSyncManager:
    """
    Manager to sync HKPL data from GitHub to SQL.
    """
    
    def __init__(self):
        self.extractor = HongKongDataExtractor()
        self.processor = HongKongDataProcessor()
        self.player_index = get_player_index()

    def sync_season(self, season_id: str = None):
        """
        Synchronizes a specific season's data from GitHub to SQL.
        """
        target_season = season_id or get_current_season()
        logger.info(f"Syncing HKPL data for season {target_season}...")
        
        # 1. Download
        df_raw = self.extractor.download_season_data(target_season, force_update=True)
        if df_raw is None or df_raw.empty:
            logger.warning(f"No data found for season {target_season}")
            return
            
        # 2. Process (Normalización)
        df_processed = self.processor.process_season_data(df_raw, target_season)
        
        # 3. Save to SQL (Upsert)
        self._upsert_to_sql(df_processed, target_season)
        
        # 4. Update Sync Log
        self._update_sync_log(f"hkpl_sync_{target_season}")

    def sync_all_seasons(self):
        """
        Synchronizes all available seasons.
        """
        seasons = self.extractor.get_available_seasons()
        logger.info(f"Syncing all {len(seasons)} available seasons...")
        for season in seasons:
            self.sync_season(season)

    def _upsert_to_sql(self, df: pd.DataFrame, season_id: str):
        """
        Inserts or updates player, team and stats in SQL.
        """
        session = SessionFactory()
        try:
            # Ensure season exists
            season = session.get(Season, season_id)
            if not season:
                season = Season(id=season_id, name=f"Season {season_id}")
                session.add(season)
                session.flush()

            count_stats = 0
            affected_player_ids = set()
            for _, row in df.iterrows():
                # 1. Team (Upsert)
                team_name = str(row.get('Team', 'Unknown'))
                team_slug = self._get_slug(team_name)
                team = session.get(Team, team_slug)
                if not team:
                    team = Team(id=team_slug, name=team_name)
                    session.add(team)
                    session.flush()

                # 2. Player (Upsert)
                player_name = str(row.get('Player'))
                
                # USE PLAYER INDEX FOR CONSISTENT IDs
                # Player names are already Title Case from processor
                player_id = self.player_index.get_player_id(
                    player_name,
                    team_id=team.id,
                    team_name=team_name,
                )
                
                if not player_id:
                    logger.warning(f"Player '{player_name}' not found in index during sync. Rebuilding index...")
                    self.player_index.build(force=True)
                    player_id = self.player_index.get_player_id(
                        player_name,
                        team_id=team.id,
                        team_name=team_name,
                    )
                    
                if not player_id:
                    # Fallback to name-based slug only if index failed, but log it as an error
                    logger.error(f"CRITICAL: Player '{player_name}' still missing ID after index rebuild.")
                    player_id = self._get_slug(player_name)

                player = session.get(Player, player_id)
                
                # Update basic player info
                if not player:
                    player = Player(
                        id=player_id,
                        name=player_name,
                        current_team_id=team.id,
                        position_main=None,
                        age=int(row.get('Age', 0)) if pd.notna(row.get('Age')) else 0
                    )
                    session.add(player)
                    session.flush()
                else:
                    player.current_team_id = team.id
                    if pd.notna(row.get('Age')):
                        player.age = int(row.get('Age'))

                # 3. Stats (Upsert)
                # Lookup by player_id and season_id
                stmt_stat = select(PlayerSeasonStat).where(
                    and_(
                        PlayerSeasonStat.player_id == player.id,
                        PlayerSeasonStat.season_id == season_id
                    )
                )
                stat = session.execute(stmt_stat).scalar_one_or_none()
                
                # Extract core metrics
                matches = int(row.get('Matches played', 0))
                minutes = int(row.get('Minutes played', 0))
                goals = int(row.get('Goals', 0))
                assists = int(row.get('Assists', 0))
                yellow = int(row.get('Yellow cards', 0))
                red = int(row.get('Red cards', 0))

                # Extract advanced metrics as JSON
                exclude_keys = {
                    'Player', 'Team', 'Matches played', 'Minutes played', 
                    'Goals', 'Assists', 'Yellow cards', 'Red cards', 
                    'Season', 'Age', 'Position_Group', 'Position_Clean'
                }
                advanced = {k: v for k, v in row.to_dict().items() if k not in exclude_keys and pd.notna(v)}

                if not stat:
                    stat = PlayerSeasonStat(
                        player_id=player.id,
                        season_id=season_id,
                        matches_played=matches,
                        minutes_played=minutes,
                        goals=goals,
                        assists=assists,
                        yellow_cards=yellow,
                        red_cards=red,
                        advanced_stats=advanced
                    )
                    session.add(stat)
                else:
                    stat.matches_played = matches
                    stat.minutes_played = minutes
                    stat.goals = goals
                    stat.assists = assists
                    stat.yellow_cards = yellow
                    stat.red_cards = red
                    stat.advanced_stats = advanced
                
                count_stats += 1
                affected_player_ids.add(player.id)

            for player_id in affected_player_ids:
                self._reconcile_player_position(session, player_id, prefer_transfermarkt=False)

            session.commit()
            logger.info(f"✓ {season_id}: {count_stats} player stats synchronized.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error upserting season {season_id}: {e}")
            raise
        finally:
            session.close()

    def _get_slug(self, name: str) -> str:
        """Simple slug generator."""
        return re.sub(r"[^a-z0-9]", "_", str(name).lower()).strip("_")

    def _update_sync_log(self, task: str):
        session = SessionFactory()
        try:
            log = session.get(SystemSyncLog, task)
            if not log:
                log = SystemSyncLog(task_name=task, last_run=datetime.now(), status="SUCCESS")
                session.add(log)
            else:
                log.last_run = datetime.now()
                log.status = "SUCCESS"
            session.commit()
        finally:
            session.close()

    def resolve_player_tm_data(self, player_id: str, player_name: str, team: str = "") -> None:
        """
        Background-safe method to resolve Transfermarkt data for a newly created player.

        Steps:
        1. If player.tm_id is None, search TM by name+team and persist the result.
        2. If tm_id resolved, fetch and store the profile photo as a DB blob.
        3. If player.position_main is None, fetch TM position and persist it.

        Safe to call from a daemon thread — opens its own DB session.
        """
        from data.managers.transfermarkt_refresh_manager import TransfermarktRefreshManager

        try:
            manager = TransfermarktRefreshManager()
            ok = manager.refresh_player(
                player_id,
                mode="new_user_bootstrap",
                player_name=player_name,
                team=team,
                fetch_photo=True,
                reconcile_position=self._reconcile_player_position,
            )
            if ok:
                logger.info(f"resolve_player_tm_data: unified TM bootstrap completed for {player_name!r}")
            else:
                logger.warning(f"resolve_player_tm_data: no TM history synced for {player_name!r}")
        except Exception as e:
            logger.error(f"resolve_player_tm_data error for {player_name!r}: {e}", exc_info=True)

    def reconcile_all_player_positions(self, prefer_transfermarkt: bool = True) -> Dict[str, int]:
        """Recomputes canonical player positions across the whole DB."""
        from data.extractors.transfermarkt_extractor import TransfermarktExtractor

        session = SessionFactory()
        extractor = TransfermarktExtractor() if prefer_transfermarkt else None
        updated = 0
        scanned = 0
        try:
            players = session.execute(select(Player)).scalars().all()
            for player in players:
                scanned += 1
                previous = player.position_main
                resolved = self._reconcile_player_position(
                    session,
                    player.id,
                    prefer_transfermarkt=prefer_transfermarkt,
                    extractor=extractor,
                )
                if resolved and resolved != previous:
                    updated += 1
            session.commit()
            return {"scanned": scanned, "updated": updated}
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _reconcile_player_position(
        self,
        session,
        player_id: str,
        prefer_transfermarkt: bool = False,
        extractor=None,
    ) -> Optional[str]:
        player = session.get(Player, player_id)
        if not player:
            return None

        resolved = self._resolve_position_from_latest_stats(session, player_id)

        if not resolved and prefer_transfermarkt and player.tm_id:
            resolved = self._resolve_position_from_transfermarkt(player.tm_id, extractor)

        if not resolved:
            resolved = self._resolve_position_from_match_history(session, player_id)

        if resolved:
            player.position_main = resolved
        return resolved

    def _resolve_position_from_latest_stats(self, session, player_id: str) -> Optional[str]:
        stmt = (
            select(PlayerSeasonStat)
            .where(PlayerSeasonStat.player_id == player_id)
            .order_by(PlayerSeasonStat.season_id.desc())
        )
        stats = session.execute(stmt).scalars().all()
        for stat in stats:
            advanced = stat.advanced_stats or {}
            raw_primary = str(advanced.get("Primary position") or "").strip()
            raw_position = str(advanced.get("Position_Clean") or advanced.get("Position") or "").strip()

            # If the latest available season lists multiple roles, treat it as ambiguous
            # and delegate the tie-break to Transfermarkt / recent match history.
            if raw_primary and "," in raw_primary:
                return None
            if raw_position and "," in raw_position:
                return None

            primary = self._normalize_position_text(raw_primary)
            if primary:
                return primary

            clean = self._normalize_position_text(raw_position)
            if clean:
                return clean

            # If the most recent season exists but is not resolvable, stop here so older
            # seasons do not overwrite the player with stale historical roles.
            return None
        return None

    def _resolve_position_from_match_history(self, session, player_id: str) -> Optional[str]:
        from models.db_models import MatchHistory

        stmt = (
            select(MatchHistory)
            .where(MatchHistory.player_id == player_id)
            .order_by(MatchHistory.date.desc())
            .limit(12)
        )
        matches = session.execute(stmt).scalars().all()
        weighted: Dict[str, int] = {}
        for idx, match in enumerate(matches):
            code = self._normalize_position_text(getattr(match, "position", None))
            if not code:
                continue
            minutes = int(getattr(match, "minutes_played", 0) or 0)
            weight = max(minutes, 1) + max(0, 12 - idx)
            weighted[code] = weighted.get(code, 0) + weight
        if not weighted:
            return None
        return max(weighted.items(), key=lambda item: item[1])[0]

    def _resolve_position_from_transfermarkt(self, tm_id: int, extractor=None) -> Optional[str]:
        from data.extractors.transfermarkt_extractor import TransfermarktExtractor

        extractor = extractor or TransfermarktExtractor()
        tm_pos = extractor.get_player_main_position(str(tm_id))
        return self._normalize_position_text(tm_pos)

    def _normalize_position_text(self, raw: Any) -> Optional[str]:
        value = str(raw or "").strip()
        if not value or value.lower() in {"unknown", "nan", "none", "0.0"}:
            return None

        if "," in value:
            return None

        upper = value.upper()
        if upper in _KNOWN_POSITION_CODES:
            mapped = {
                "ED": "RW",
                "EI": "LW",
                "ID": "RM",
                "II": "LM",
                "MCO": "AMF",
                "CMF": "CM",
                "DMF": "DM",
            }
            return mapped.get(upper, upper)

        key = value.lower()
        if key in _TM_TEXT_TO_ABBR:
            return _TM_TEXT_TO_ABBR[key]
        for pattern, code in _TM_TEXT_TO_ABBR.items():
            if pattern in key:
                return code
        return None
