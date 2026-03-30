# ABOUTME: Script to refresh fixtures in the SQL database from official ICS.
# ABOUTME: Replaces the legacy JSON persistence with SQLAlchemy sync.

import sys
import os
# Añadir el directorio raíz al path para que encuentre los paquetes locales
sys.path.append(os.getcwd())

import logging
from data.managers.fixture_manager import get_fixture_manager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    fm = get_fixture_manager()
    logger.info("Starting manual refresh of fixtures from official ICS to SQL...")
    
    try:
        fm.sync_from_ics()
        logger.info("✓ Fixtures refresh completed successfully.")
    except Exception as e:
        logger.error(f"❌ Error during fixtures refresh: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
