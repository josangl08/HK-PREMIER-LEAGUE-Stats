"""
Configuración global para la aplicación Sports Dashboard.
Versión optimizada que lee máximo del archivo .env para evitar duplicaciones.
"""

import os
from dotenv import load_dotenv
from typing import Dict, List

# Cargar variables de entorno
load_dotenv()

def get_env_bool(key: str, default: bool = False) -> bool:
    """Convierte variable de entorno a booleano."""
    return os.getenv(key, str(default)).lower() in ('true', '1', 'yes', 'on')

def get_env_int(key: str, default: int = 0) -> int:
    """Convierte variable de entorno a entero."""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

def get_env_float(key: str, default: float = 0.0) -> float:
    """Convierte variable de entorno a flotante."""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default

class AppConfig:
    """Configuración principal de la aplicación."""
    
    # Información básica (desde .env)
    APP_NAME = os.getenv("APP_NAME", "Sports Dashboard - Liga de Hong Kong")
    APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
    
    # Configuración de servidor (desde .env)
    DEBUG = get_env_bool("DEBUG", True)
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = get_env_int("PORT", 8050)
    
    # Configuración de autenticación (desde .env)
    SECRET_KEY = os.getenv("SECRET_KEY")
    ADMIN_USER = os.getenv("ADMIN_USER")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
    
    # Configuración de cache (desde .env)
    CACHE_TYPE = os.getenv("CACHE_TYPE", "filesystem")
    CACHE_DIR = os.getenv("CACHE_DIR", "./cache")
    CACHE_DEFAULT_TIMEOUT = get_env_int("CACHE_DEFAULT_TIMEOUT", 300)
    
    # Directorios (calculados dinámicamente)
    DATA_DIR = "data"
    CACHE_DATA_DIR = "data/cache"
    EXPORTS_DIR = "data/exports"
    LOGS_DIR = "logs"
    ASSETS_DIR = "assets"

class DataConfig:
    """Configuración relacionada con datos."""
 
    # Configuración desde .env
    DEFAULT_SEASON = os.getenv("DEFAULT_SEASON", "2024-25")
    MIN_TEAMS_EXPECTED = get_env_int("MIN_TEAMS_EXPECTED", 8)
    MAX_TEAMS_EXPECTED = get_env_int("MAX_TEAMS_EXPECTED", 12)
    MAX_PLAYERS_PER_TEAM = get_env_int("MAX_PLAYERS_PER_TEAM", 30)
    
    # Equipos esperados en la Liga de Hong Kong (estático - para validación)
    EXPECTED_HK_TEAMS = [
        "Lee Man", "Eastern", "Kitchee", "Rangers", 
        "Southern District", "Tai Po", "Kowloon City", 
        "North District", "Hong Kong Football Club"
    ]

# Funciones auxiliares
def create_directories():
    """
    Crea los directorios esenciales para el funcionamiento de la aplicación.
    Versión simplificada que solo crea directorios realmente utilizados.
    """
    essential_dirs = [
        'cache',          # Para el sistema de caché
        'data/cache',     # Para datos procesados
        'data/exports',   # Para exportación de reportes
        'logs'            # Para logs
    ]
    
    for directory in essential_dirs:
        os.makedirs(directory, exist_ok=True)
