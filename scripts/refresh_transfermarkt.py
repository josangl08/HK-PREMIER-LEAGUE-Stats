# ABOUTME: Script to refresh Transfermarkt data (Match History) in the SQL database.
# ABOUTME: Uses TransfermarktDataManager to handle scraping, processing, and SQL upsert.

import sys
import os
# Añadir el directorio raíz al path para que encuentre los paquetes locales
sys.path.append(os.getcwd())

import logging
from data.transfermarkt_data_manager import TransfermarktDataManager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting refresh of Transfermarkt data (Match History) to SQL...")
    
    # auto_load=False to avoid loading twice
    manager = TransfermarktDataManager(auto_load=False)
    
    try:
        # force_scraping=True will trigger ETL and save to SQL
        success = manager.refresh_data(force_scraping=True)
        
        if success:
            logger.info("✓ Transfermarkt data refresh completed successfully.")
        else:
            logger.warning("Transfermarkt data refresh finished with warnings (check logs).")
            
    except Exception as e:
        logger.error(f"❌ Error during Transfermarkt refresh: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
