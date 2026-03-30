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

logger = logging.getLogger(__name__)

class HKPLSyncManager:
    """
    Manager to sync HKPL data from GitHub to SQL.
    """
    
    def __init__(self):
        self.extractor = HongKongDataExtractor()
        self.processor = HongKongDataProcessor()

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
                player_slug = self._get_slug(player_name)
                player = session.get(Player, player_slug)
                
                # Update basic player info
                if not player:
                    player = Player(
                        id=player_slug,
                        name=player_name,
                        current_team_id=team.id,
                        position_main=row.get('Position_Group', 'Unknown'),
                        age=int(row.get('Age', 0)) if pd.notna(row.get('Age')) else 0
                    )
                    session.add(player)
                    session.flush()
                else:
                    player.current_team_id = team.id
                    player.position_main = row.get('Position_Group', 'Unknown')
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
