# ABOUTME: Migration script to add BeSoccer and Sofascore IDs to the players table.
# ABOUTME: Updates the SQL database schema to support external match intelligence integration.
import sys
import os
import logging
from sqlalchemy import text

# Add root to path
sys.path.append(os.getcwd())

from utils.db_engine import engine, DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    logger.info(f"Iniciando migración en: {DATABASE_URL}")
    
    if DATABASE_URL.startswith("sqlite"):
        with engine.connect() as conn:
            # Añadir besoccer_id a la tabla players
            try:
                conn.execute(text("ALTER TABLE players ADD COLUMN besoccer_id VARCHAR(100)"))
                conn.commit()
                logger.info("Migración: columna besoccer_id añadida a la tabla players.")
            except Exception as e:
                logger.warning(f"⚠️ No se pudo añadir besoccer_id (puede que ya exista): {e}")

            # Añadir sofascore_id a la tabla players
            try:
                conn.execute(text("ALTER TABLE players ADD COLUMN sofascore_id INTEGER"))
                conn.commit()
                logger.info("Migración: columna sofascore_id añadida a la tabla players.")
            except Exception as e:
                logger.warning(f"⚠️ No se pudo añadir sofascore_id (puede que ya exista): {e}")

    logger.info("✓ Proceso de migración completado.")

if __name__ == "__main__":
    migrate()
