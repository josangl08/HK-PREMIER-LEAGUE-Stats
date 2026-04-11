# ABOUTME: Intelligence refresh script for BeSoccer and Sofascore data.
# ABOUTME: Populates the database with match-level and season-level ratings.
# ABOUTME: Strict HK-only filter, 2018-2026 window, AFC/ACL prioritization for Sofascore.

import logging
import sys
import os
import re
from datetime import datetime, timedelta
from typing import Set

# Add root to path
sys.path.append(os.getcwd())

from utils.db_engine import SessionFactory
from models.db_models import Player, PlayerSeasonStat, MatchHistory, Team
from data.extractors.besoccer_extractor import BeSoccerExtractor
from data.extractors.sofascore_extractor import SofascoreExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Period constants
START_DATE = datetime(2018, 7, 1)
END_DATE = datetime(2026, 6, 30)

def get_hk_team_names(session) -> Set[str]:
    """Returns a set of normalized HK team names from the DB."""
    # Based on the system's known HK professional teams
    hk_core = {
        "lee man", "kitchee", "eastern", "tai po", "southern district", 
        "rangers", "bc rangers", "hong kong fc", "hkfc", "north district", 
        "north dt.", "kowloon city", "resources capital", "rcfc", "hk u23", 
        "happy valley", "yuen long", "pegasus", "r&f", "dreams fc", "hoi king"
    }
    # Add names from the Teams table that are likely HK (this is an extra safety layer)
    db_teams = session.query(Team.name).all()
    for (name,) in db_teams:
        n_lower = name.lower()
        if any(token in n_lower for token in ["district", "dt.", " u23", "hong kong"]):
            hk_core.add(n_lower)
    return hk_core

def is_hk_team(team_name: str, hk_names: Set[str]) -> bool:
    """Checks if a team name matches our HK database."""
    if not team_name: return False
    n = team_name.lower().strip()
    # Direct match or partial match
    if n in hk_names: return True
    for hk in hk_names:
        if hk in n or n in hk: return True
    return False

def refresh_player_intelligence(player_id: str, force: bool = False):
    """
    Fetches and saves BeSoccer and Sofascore intelligence for a specific player.
    Filtros: Periodo 2018-2026, Solo Equipos HK, Solo AFC/ACL en Sofascore.
    """
    session = SessionFactory()
    besoccer = BeSoccerExtractor()
    sofascore = SofascoreExtractor()
    
    hk_team_names = get_hk_team_names(session)
    # window for SS (approx 2 seasons)
    two_seasons_ago = datetime.now() - timedelta(days=365 * 2)
    
    try:
        player = session.get(Player, player_id)
        if not player:
            logger.error(f"Player {player_id} not found.")
            return

        logger.info(f"--- REFRESHING INTELLIGENCE: {player.name} ({player_id}) ---")

        # --- 1. BeSoccer: Ratings por Partido y Temporada ---
        if player.besoccer_id:
            logger.info(f"  [BeSoccer] Fetching matches for {player.besoccer_id}...")
            match_ratings = besoccer.get_player_ratings(player.besoccer_id)
            
            if match_ratings:
                matches = session.query(MatchHistory).filter(MatchHistory.player_id == player_id).all()
                matches_updated = 0
                for match in matches:
                    if not (START_DATE <= match.date <= END_DATE):
                        continue
                    
                    match_date_str = match.date.strftime("%Y-%m-%d")
                    if match_date_str in match_ratings:
                        current_raw = dict(match.raw_data or {})
                        current_raw["besoccer_rating"] = match_ratings[match_date_str]
                        match.raw_data = current_raw
                        matches_updated += 1
                logger.info(f"  ✓ Updated {matches_updated} match ratings from BeSoccer.")

            logger.info(f"  [BeSoccer] Fetching career path...")
            season_ratings = besoccer.get_season_ratings(player.besoccer_id)
            if season_ratings:
                stats = session.query(PlayerSeasonStat).filter(PlayerSeasonStat.player_id == player_id).all()
                for stat in stats:
                    bs_key = stat.season_id.replace("-", "/")
                    if bs_key in season_ratings:
                        current_adv = dict(stat.advanced_stats or {})
                        current_adv["besoccer_season_rating"] = season_ratings[bs_key]
                        stat.advanced_stats = current_adv
                        logger.info(f"  ✓ Updated season rating {stat.season_id}: {season_ratings[bs_key]}")

        # --- 2. Sofascore: Career Rating + Continental Stats (Last 2 Seasons) ---
        ss_ids = [player.sofascore_id] if player.sofascore_id else []
        # Manuel Bleda special case
        if player_id == "125040" and 835213 not in ss_ids:
            ss_ids.append(835213)

        for ss_id in ss_ids:
            logger.info(f"  [Sofascore] Refreshing ID: {ss_id}...")
            
            # A. Career Rating / Attributes
            attr_data = sofascore.get_player_attribute_overviews(ss_id)
            if attr_data:
                # Update player profile_data if available or meta
                pass 

            # B. Continental Matches (Full Window 2018-2026)
            ss_events = sofascore.get_all_player_events(ss_id, max_pages=15)
            if ss_events:
                db_matches = session.query(MatchHistory).filter(MatchHistory.player_id == player_id).all()
                ss_updated = 0
                
                for event in ss_events:
                    ts = event.get("startTimestamp")
                    if not ts: continue
                    event_dt = datetime.fromtimestamp(ts)
                    
                    # Filtro 1: Periodo 2018-2026
                    if not (START_DATE <= event_dt <= END_DATE):
                        continue
                    
                    # Filtro 2: Solo AFC/ACL/ACL2/Champions/Elite
                    comp_name = event.get("tournament", {}).get("name", "").upper()
                    is_continental = any(x in comp_name for x in ["AFC", "CHAMPIONS", "ACL"])
                    if not is_continental:
                        continue
                        
                    # Filtro 3: Solo si jugaba en equipo de HK
                    home_team = event.get("homeTeam", {}).get("name", "")
                    away_team = event.get("awayTeam", {}).get("name", "")
                    
                    if not (is_hk_team(home_team, hk_team_names) or is_hk_team(away_team, hk_team_names)):
                        continue

                    # Match with DB record
                    date_str = event_dt.strftime("%Y-%m-%d")
                    match_id = event.get("id")
                    
                    for m in db_matches:
                        if m.date.strftime("%Y-%m-%d") == date_str:
                            # Update if missing or forced
                            if not m.raw_data or "sofascore_intelligence" not in m.raw_data or force:
                                logger.info(f"    Fetching stats for match on {date_str} ({comp_name})...")
                                stats = sofascore.get_match_player_stats(match_id, ss_id)
                                hmap = sofascore.get_player_heatmap(match_id, ss_id)
                                if stats:
                                    stats["heatmap"] = hmap
                                    current_raw = dict(m.raw_data or {})
                                    current_raw["sofascore_intelligence"] = stats
                                    if stats.get("rating"):
                                        current_raw["sofascore_rating"] = stats.get("rating")
                                    m.raw_data = current_raw
                                    ss_updated += 1
                                break
                logger.info(f"  ✓ Updated {ss_updated} continental matches from Sofascore.")

        session.commit()
        logger.info(f"✓ Completed: {player.name}")
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error refreshing {player_id}: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        refresh_player_intelligence(sys.argv[1])
    else:
        print("Usage: python scripts/refresh_intelligence.py <player_id>")
