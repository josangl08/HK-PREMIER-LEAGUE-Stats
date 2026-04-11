# ABOUTME: Helper script to refresh match history for a single player from Transfermarkt.
# ABOUTME: Useful for targeted updates of specific platform players.

import logging
import sys
import os

# Add root to path
sys.path.append(os.getcwd())

from data.transfermarkt_data_manager import TransfermarktDataManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def refresh_single_player(player_id: str):
    manager = TransfermarktDataManager(auto_load=False)
    
    # We want to cover the requested range 2018-2026
    seasons = [
        "2018-19", "2019-20", "2020-21", "2021-22", 
        "2022-23", "2023-24", "2024-25", "2025-26"
    ]
    
    logger.info(f"Starting targeted refresh for Player ID: {player_id}")
    success = manager.refresh_player_data_for_seasons(player_id, seasons)
    
    if success:
        logger.info(f"✓ Match history refreshed for {player_id}")
    else:
        logger.error(f"Failed to refresh match history for {player_id}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_id = sys.argv[1]
        refresh_single_player(target_id)
    else:
        print("Usage: python scripts/refresh_player_match_history.py <player_id>")
