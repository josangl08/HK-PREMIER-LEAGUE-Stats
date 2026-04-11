# ABOUTME: Auto-resolver for missing external IDs of platform players.
# ABOUTME: Attempts to find BeSoccer and Sofascore IDs before intelligence refresh.

import logging
import sys
import os
from sqlalchemy import select

# Add root to path
sys.path.append(os.getcwd())

from utils.db_engine import SessionFactory
from models.db_models import Player, UserPlayerLink, agent_player_links
from utils.player_index import IdentityResolver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def resolve_ids():
    session = SessionFactory()
    resolver = IdentityResolver()
    
    try:
        # Identify targeted players
        player_ids = set()
        direct_links = session.query(UserPlayerLink).all()
        for link in direct_links:
            player_ids.add(link.player_id)
        agent_rosters = session.execute(select(agent_player_links.c.player_id)).all()
        for row in agent_rosters:
            player_ids.add(row[0])
            
        logger.info(f"Checking IDs for {len(player_ids)} platform players...")
        
        for player_id in sorted(list(player_ids)):
            player = session.get(Player, player_id)
            if not player: continue
            
            missing_bs = not player.besoccer_id
            missing_ss = not player.sofascore_id
            
            if missing_bs or missing_ss:
                logger.info(f"Resolving missing IDs for {player.name}...")
                resolver.resolve_external_ids(player_id)
            else:
                logger.info(f"✓ {player.name} already has all IDs.")
                
    except Exception as e:
        logger.error(f"Error in resolution: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    resolve_ids()
