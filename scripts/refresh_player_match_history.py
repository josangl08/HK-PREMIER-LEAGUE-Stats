# ABOUTME: Helper script to refresh match history for a single player from Transfermarkt.
# ABOUTME: Supports full-history and recent-window refresh modes for targeted player updates.

import argparse
import logging
import sys
import os

# Add root to path
sys.path.append(os.getcwd())

from data.managers.transfermarkt_refresh_manager import TransfermarktRefreshManager
from data.transfermarkt_data_manager import TransfermarktDataManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def refresh_single_player_full(player_id: str):
    manager = TransfermarktDataManager(auto_load=False)
    
    # We want to cover the requested range 2018-2026
    seasons = [
        "2018-19", "2019-20", "2020-21", "2021-22", 
        "2022-23", "2023-24", "2024-25", "2025-26"
    ]
    
    logger.info(f"Starting full-history refresh for Player ID: {player_id}")
    success = manager.refresh_player_data_for_seasons(player_id, seasons)
    
    if success:
        logger.info(f"✓ Full match history refreshed for {player_id}")
    else:
        logger.error(f"Failed to refresh full match history for {player_id}")


def refresh_single_player_recent(player_id: str):
    manager = TransfermarktRefreshManager()
    logger.info(f"Starting recent-window refresh for Player ID: {player_id}")
    success = manager.refresh_player(player_id, mode="user_priority_refresh")

    if success:
        logger.info(f"✓ Recent match history refreshed for {player_id}")
    else:
        logger.error(f"Failed to refresh recent match history for {player_id}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh Transfermarkt match history for a single player.")
    parser.add_argument("player_id", help="Internal player ID")
    parser.add_argument(
        "--mode",
        choices=["recent", "full"],
        default="recent",
        help="Refresh only current+previous season (recent) or the full tracked history (full). Default: recent",
    )
    args = parser.parse_args()

    if args.mode == "full":
        refresh_single_player_full(args.player_id)
    else:
        refresh_single_player_recent(args.player_id)
