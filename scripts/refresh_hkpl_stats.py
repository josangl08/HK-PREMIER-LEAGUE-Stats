# ABOUTME: Script to refresh HK Premier League stats in the SQL database from GitHub.
# ABOUTME: Uses HKPLSyncManager to handle download, processing, and SQL upsert.

import sys
import os
# Añadir el directorio raíz al path para que encuentre los paquetes locales
sys.path.append(os.getcwd())

import logging
import argparse
from data.managers.hkpl_sync_manager import HKPLSyncManager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Refresh HKPL stats from GitHub to SQL.")
    parser.add_argument("--season", type=str, help="Season to sync (e.g. 2024-25). If not provided, syncs current season.")
    parser.add_argument("--all", action="store_true", help="Sync all available seasons.")
    
    args = parser.parse_args()
    
    manager = HKPLSyncManager()
    
    try:
        if args.all:
            logger.info("Starting full refresh of ALL seasons...")
            manager.sync_all_seasons()
        else:
            season = args.season
            logger.info(f"Starting refresh of HKPL stats for season: {season or 'current'}...")
            manager.sync_season(season)
            
        logger.info("✓ HKPL stats refresh completed successfully.")
    except Exception as e:
        logger.error(f"❌ Error during HKPL stats refresh: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
