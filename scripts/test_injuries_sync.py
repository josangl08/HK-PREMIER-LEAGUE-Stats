# ABOUTME: Script de prueba para validar la sincronización de lesiones desde Transfermarkt a SQL.
# ABOUTME: Ejecuta el proceso ETL y verifica que los datos se persistan correctamente.

import logging
import sys
import os
from pathlib import Path

# Añadir el directorio raíz al path para importar módulos del proyecto
sys.path.append(str(Path(__file__).parent.parent))

from data.transfermarkt_data_manager import TransfermarktDataManager
from utils.db_engine import SessionFactory
from models.db_models import Injury, Player
from sqlalchemy import select

# Configurar logging para ver qué está pasando
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_sync(historical=False):
    logger.info(f"Iniciando prueba de sincronización de lesiones (histórico={historical})...")
    
    # Inicializar el manager
    manager = TransfermarktDataManager(use_playwright=True)
    
    # Ejecutar el refresco forzado (esto dispara el scraping)
    logger.info("Ejecutando manager.refresh_data(force_scraping=True)...")
    success = manager.refresh_data(force_scraping=True, sync_history=False, historical=historical)
    
    if success:
        logger.info("✅ Proceso ETL completado con éxito.")
    else:
        logger.error("❌ El proceso de refresco falló.")
        
    # Verificar resultados en la base de datos
    session = SessionFactory()
    try:
        # Consulta para obtener lesiones y nombres de jugadores
        stmt = select(Injury, Player).join(Player, Injury.player_id == Player.id)
        results = session.execute(stmt).all()
        
        logger.info(f"📊 Total de lesiones en base de datos: {len(results)}")
        
        if len(results) > 0:
            logger.info("Muestra de lesiones encontradas:")
            for i, row in enumerate(results[:10]):
                injury = row[0]
                player = row[1]
                logger.info(f"  {i+1}. {player.name}: {injury.injury_type} ({injury.body_part}) - {injury.start_date} -> {injury.return_date}")
        else:
            logger.warning("⚠️ No hay lesiones en la base de datos.")
            
    finally:
        session.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Prueba de sincronización de lesiones")
    parser.add_argument("--historical", action="store_true", help="Extraer también datos históricos")
    args = parser.parse_args()
    
    test_sync(historical=args.historical)
