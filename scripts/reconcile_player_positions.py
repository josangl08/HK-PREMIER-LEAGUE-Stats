# ABOUTME: Recomputes canonical player positions across the SQL database.
# ABOUTME: Prefers Transfermarkt when available, then falls back to latest season stats and recent match history.

import os
import sys
import logging

sys.path.append(os.getcwd())

from data.managers.hkpl_sync_manager import HKPLSyncManager


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    prefer_transfermarkt = True
    if len(sys.argv) > 1 and sys.argv[1] == "--no-transfermarkt":
        prefer_transfermarkt = False

    manager = HKPLSyncManager()
    logger.info("Reconciling player positions across the database...")
    result = manager.reconcile_all_player_positions(prefer_transfermarkt=prefer_transfermarkt)
    logger.info(
        "✓ Position reconciliation complete. scanned=%s updated=%s prefer_transfermarkt=%s",
        result["scanned"],
        result["updated"],
        prefer_transfermarkt,
    )


if __name__ == "__main__":
    main()
