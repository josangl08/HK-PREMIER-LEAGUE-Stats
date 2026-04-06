# ABOUTME: Simple script to initialize the database tables (idempotent).
import sys
import os
import logging

# Add root to path
sys.path.append(os.getcwd())

from utils.db_engine import init_db

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    print("Verificando e inicializando tablas de base de datos...")
    init_db()
    print("✓ Proceso completado.")
