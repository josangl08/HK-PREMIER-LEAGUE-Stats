# ABOUTME: Database engine configuration for SQLAlchemy, supporting SQLite and PostgreSQL via DATABASE_URL.

import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from models.db_models import Base
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Obtener URL de la base de datos, por defecto usar SQLite local
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/database.db")

# Crear el motor de SQLAlchemy
# check_same_thread=False es necesario para SQLite en Flask/Dash si hay hilos
engine_args = {}
if DATABASE_URL.startswith("sqlite"):
    engine_args["connect_args"] = {"check_same_thread": False}
    # Asegurar que el directorio de la base de datos existe
    db_path = DATABASE_URL.replace("sqlite:///", "")
    if db_path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

engine = create_engine(DATABASE_URL, **engine_args)

# Crear un SessionFactory
SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Crear un scoped_session para entornos web (Flask/Dash)
Session = scoped_session(SessionFactory)

def init_db():
    """
    Inicializa la base de datos creando todas las tablas.
    Debe llamarse al arrancar la aplicación o mediante scripts de migración.
    """
    logger.info(f"Inicializando base de datos en: {DATABASE_URL}")
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas creadas/verificadas exitosamente.")

def get_session():
    """
    Generador para obtener una sesión de base de datos.
    Útil para el uso con Context Managers o inyección de dependencias.
    """
    session = Session()
    try:
        yield session
    finally:
        session.close()
