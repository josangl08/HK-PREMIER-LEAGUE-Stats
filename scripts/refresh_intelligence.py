# ABOUTME: Intelligence refresh script for BeSoccer and Sofascore data.
# ABOUTME: Populates the database with match-level and season-level ratings.

import logging
import sys
import os
from datetime import datetime
from sqlalchemy import inspect

# Add root to path
sys.path.append(os.getcwd())

from utils.db_engine import SessionFactory, engine
from models.db_models import Player, PlayerSeasonStat, MatchHistory
from data.extractors.besoccer_extractor import BeSoccerExtractor
from data.extractors.sofascore_extractor import SofascoreExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def refresh_player_intelligence(player_id: str, force: bool = False):
    """
    Fetches and saves BeSoccer and Sofascore intelligence for a specific player.
    """
    session = SessionFactory()
    besoccer = BeSoccerExtractor()
    sofascore = SofascoreExtractor()
    
    try:
        logger.info(f"Database Engine URL: {engine.url}")
        
        player = session.get(Player, player_id)
        if not player:
            logger.error(f"Player {player_id} not found.")
            return

        # --- 1. BeSoccer Match Ratings ---
        if player.besoccer_id:
            logger.info(f"Refreshing BeSoccer Match Ratings for {player.name}...")
            match_ratings = besoccer.get_player_ratings(player.besoccer_id)
            
            if match_ratings:
                # Find MatchHistory records for this player
                matches = session.query(MatchHistory).filter(MatchHistory.player_id == player_id).all()
                logger.info(f"Found {len(matches)} match history records in DB for {player.name}.")
                
                matches_updated = 0
                for match in matches:
                    match_date_str = match.date.strftime("%Y-%m-%d")
                    if match_date_str in match_ratings:
                        # Merge into raw_data
                        # Crucial: SQLAlchemy needs to know the JSON column changed
                        current_raw = dict(match.raw_data or {})
                        current_raw["besoccer_rating"] = match_ratings[match_date_str]
                        match.raw_data = current_raw
                        matches_updated += 1
                
                logger.info(f"✓ Updated {matches_updated} match ratings from BeSoccer.")

            # --- 2. BeSoccer Season Ratings ---
            logger.info(f"Refreshing BeSoccer Season Ratings for {player.name}...")
            season_ratings = besoccer.get_season_ratings(player.besoccer_id)
            if season_ratings:
                stats = session.query(PlayerSeasonStat).filter(PlayerSeasonStat.player_id == player_id).all()
                for stat in stats:
                    bs_key = stat.season_id.replace("-", "/")
                    if bs_key in season_ratings:
                        current_adv = dict(stat.advanced_stats or {})
                        current_adv["besoccer_season_rating"] = season_ratings[bs_key]
                        stat.advanced_stats = current_adv
                        logger.info(f"✓ Updated season rating for {stat.season_id}: {season_ratings[bs_key]}")

        # --- 3. Sofascore Intelligence (Heatmaps/Granular) ---
        # Note: Bleda has two IDs (835213, 112880). We'll handle multiple IDs if found.
        ss_ids = [player.sofascore_id] if player.sofascore_id else []
        if player_id == "125040" and 112880 not in ss_ids:
            ss_ids.append(112880) # Add the second ID for Manuel Bleda specifically

        for ss_id in ss_ids:
            logger.info(f"Refreshing Sofascore Intelligence for {player.name} (ID: {ss_id})...")
            # Fetch ALL events using the new paginated method
            ss_matches = sofascore.get_all_player_events(ss_id, max_pages=10)
            
            if ss_matches:
                matches = session.query(MatchHistory).filter(MatchHistory.player_id == player_id).all()
                matches_updated = 0
                for ss_event in ss_matches:
                    start_ts = ss_event.get("startTimestamp")
                    if not start_ts: continue
                    
                    ss_date_str = datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d")
                    ss_match_id = ss_event.get("id")
                    
                    for match in matches:
                        # Match by date
                        if match.date.strftime("%Y-%m-%d") == ss_date_str:
                            # CRITICAL: Only extract Sofascore stats for AFC/Continental competitions
                            comp_name = (match.competition_name or "").upper()
                            is_afc = "AFC" in comp_name or "CHAMPIONS" in comp_name
                            
                            if not is_afc:
                                continue # Skip league/local matches for Sofascore

                            # Only update if not already high-fidelity
                            if match.raw_data and "sofascore_intelligence" in match.raw_data:
                                existing_ss = match.raw_data.get("sofascore_intelligence", {})
                                if existing_ss.get("statistics", {}).get("accuratePasses"):
                                    continue

                            logger.info(f"  Fetching AFC SS stats for match on {ss_date_str} (ID: {ss_match_id})...")
                            ss_stats = sofascore.get_match_player_stats(ss_match_id, ss_id)
                            ss_heatmap = sofascore.get_player_heatmap(ss_match_id, ss_id)
                            
                            if ss_stats:
                                # Add heatmap to the intelligence payload
                                ss_stats["heatmap"] = ss_heatmap
                                current_raw = dict(match.raw_data or {})
                                current_raw["sofascore_intelligence"] = ss_stats
                                match.raw_data = current_raw
                                matches_updated += 1
                                break
                
                logger.info(f"✓ Updated {matches_updated} AFC matches with Sofascore intelligence (SS ID: {ss_id}).")

        session.commit()
        logger.info(f"✓ Intelligence refresh committed for {player.name}.")
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error refreshing intelligence for {player_id}: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    target_id = "125040" 
    refresh_player_intelligence(target_id)
