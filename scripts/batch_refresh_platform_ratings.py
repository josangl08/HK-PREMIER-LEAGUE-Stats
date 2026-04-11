# ABOUTME: Batch refresh script specifically for players associated with platform users.
# ABOUTME: Downloads BeSoccer and Sofascore ratings by season and match (last 2 seasons SS).

import logging
import sys
import os
from datetime import datetime
from sqlalchemy import select

# Add root to path
sys.path.append(os.getcwd())

from utils.db_engine import SessionFactory
from models.db_models import Player, UserPlayerLink, agent_player_links
from scripts.refresh_intelligence import refresh_player_intelligence

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def refresh_platform_users_players():
    """
    Identifies all players linked to users (direct accounts or agent rosters) 
    and refreshes their intelligence data.
    """
    session = SessionFactory()
    try:
        player_ids = set()
        
        # 1. Get players with direct user accounts (Player role)
        direct_links = session.query(UserPlayerLink).all()
        for link in direct_links:
            player_ids.add(link.player_id)
            
        # 2. Get players managed by agents in the platform
        agent_rosters = session.execute(select(agent_player_links.c.player_id)).all()
        for row in agent_rosters:
            player_ids.add(row[0])
            
        logger.info(f"Targeting {len(player_ids)} unique players associated with platform users.")
        
        if not player_ids:
            logger.warning("No players found linked to users in the database.")
            return

        sorted_ids = sorted(list(player_ids))
        for i, player_id in enumerate(sorted_ids):
            player = session.get(Player, player_id)
            player_name = player.name if player else "Unknown"
            
            # Skip players without external IDs
            if not player or (not player.besoccer_id and not player.sofascore_id):
                logger.info(f"[{i+1}/{len(player_ids)}] Skipping {player_name} (No external IDs).")
                continue

            logger.info(f"[{i+1}/{len(player_ids)}] Refreshing intelligence for {player_name} (ID: {player_id})...")
            
            try:
                # Use the existing robust refresh function
                # This handles BeSoccer (matches/seasons) and Sofascore (2-season continental)
                refresh_player_intelligence(player_id)
            except Exception as e:
                logger.error(f"Failed to refresh {player_name}: {e}")
                
        logger.info("Platform-user intelligence refresh completed.")
        
    except Exception as e:
        logger.error(f"Error in batch refresh: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    refresh_platform_users_players()
