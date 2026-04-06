# ABOUTME: Database engine configuration for SQLAlchemy, supporting SQLite and PostgreSQL via DATABASE_URL.

import os
import logging
from sqlalchemy import create_engine, text
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
    # Migración idempotente: añadir photo_data si no existe
    if DATABASE_URL.startswith("sqlite"):
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE player_photos ADD COLUMN photo_data BLOB"))
                conn.commit()
                logger.info("Migración: columna photo_data añadida a player_photos.")
            except Exception:
                pass  # La columna ya existe

            # Migración: hacer original_path nullable (SQLite no soporta ALTER COLUMN)
            cols = conn.execute(text("PRAGMA table_info(player_photos)")).fetchall()
            original_path_col = next((c for c in cols if c[1] == "original_path"), None)
            if original_path_col and original_path_col[3] == 1:  # notnull == 1
                logger.info("Migración: reconstruyendo player_photos con original_path nullable.")
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS player_photos_new (
                        id INTEGER NOT NULL PRIMARY KEY,
                        player_id VARCHAR(100) NOT NULL,
                        original_path VARCHAR(255),
                        cutout_path VARCHAR(255),
                        is_primary BOOLEAN NOT NULL,
                        upload_date DATETIME NOT NULL,
                        photo_data BLOB
                    )
                """))
                conn.execute(text("""
                    INSERT INTO player_photos_new
                        SELECT id, player_id, original_path, cutout_path, is_primary, upload_date, photo_data
                        FROM player_photos
                """))
                conn.execute(text("DROP TABLE player_photos"))
                conn.execute(text("ALTER TABLE player_photos_new RENAME TO player_photos"))
                conn.commit()
                logger.info("Migración: columna original_path ahora permite NULL.")

            # Migración: modernizar match_update_queue a la cola unificada de refresh TM
            try:
                queue_cols = conn.execute(text("PRAGMA table_info(match_update_queue)")).fetchall()
                if queue_cols:
                    col_names = {c[1] for c in queue_cols}
                    fixture_col = next((c for c in queue_cols if c[1] == "fixture_id"), None)
                    requires_rebuild = (
                        "job_type" not in col_names
                        or "priority" not in col_names
                        or "source" not in col_names
                        or "reason" not in col_names
                        or "season_id" not in col_names
                        or "details" not in col_names
                        or "tm_status" not in col_names
                        or "retry_after" not in col_names
                        or (fixture_col is not None and fixture_col[3] == 1)
                    )
                    if requires_rebuild:
                        logger.info("Migración: reconstruyendo match_update_queue con esquema unificado.")
                        conn.execute(text("""
                            CREATE TABLE IF NOT EXISTS match_update_queue_new (
                                id INTEGER NOT NULL PRIMARY KEY,
                                fixture_id INTEGER,
                                player_id VARCHAR(100) NOT NULL,
                                job_type VARCHAR(40) NOT NULL DEFAULT 'post_match_history',
                                priority INTEGER NOT NULL DEFAULT 100,
                                source VARCHAR(40),
                                reason VARCHAR(255),
                                season_id VARCHAR(20),
                                details JSON,
                                status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
                                tm_status VARCHAR(30),
                                attempt_count INTEGER NOT NULL DEFAULT 0,
                                last_attempt DATETIME,
                                next_attempt DATETIME NOT NULL,
                                retry_after DATETIME,
                                created_at DATETIME NOT NULL
                            )
                        """))
                        conn.execute(text("""
                            INSERT INTO match_update_queue_new (
                                id, fixture_id, player_id, job_type, priority, source, reason, season_id, details,
                                status, tm_status, attempt_count, last_attempt, next_attempt, retry_after, created_at
                            )
                            SELECT
                                id,
                                fixture_id,
                                player_id,
                                'post_match_history',
                                100,
                                'watcher',
                                NULL,
                                NULL,
                                NULL,
                                status,
                                NULL,
                                attempt_count,
                                last_attempt,
                                next_attempt,
                                NULL,
                                created_at
                            FROM match_update_queue
                        """))
                        conn.execute(text("DROP TABLE match_update_queue"))
                        conn.execute(text("ALTER TABLE match_update_queue_new RENAME TO match_update_queue"))
                        conn.commit()
                        logger.info("Migración: match_update_queue actualizado.")
            except Exception as exc:
                logger.warning(f"⚠️ No se pudo migrar match_update_queue: {exc}")

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
