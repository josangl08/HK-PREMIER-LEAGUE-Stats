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
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    ADMIN_USER = os.getenv("ADMIN_USER", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
    
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
    
    # Temporadas disponibles (estático - raramente cambia)
    AVAILABLE_SEASONS = [
        "2024-25", "2023-24", "2022-23", "2021-22", 
        "2020-21", "2019-20", "2018-19"
    ]
    
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
    
    # URLs de GitHub (estático - raramente cambia)
    GITHUB_BASE_URL = os.getenv(
        "GITHUB_BASE_URL",
        "https://raw.githubusercontent.com/griffisben/Wyscout_Prospect_Research/adabd2a3f30e739aa8a048aaf51c08cda248e5fe/Main%20App"
    )
    GITHUB_API_BASE = os.getenv(
        "GITHUB_API_BASE",
        "https://api.github.com/repos/griffisben/Wyscout_Prospect_Research/contents/Main%20App"
    )
    
    # Archivos por temporada (estático)
    SEASON_FILES = {
        "2024-25": "Hong Kong Premier League 24-25.csv",
        "2023-24": "Hong Kong Premier League 23-24.csv", 
        "2022-23": "Hong Kong Premier League 22-23.csv",
        "2021-22": "Hong Kong Premier League 21-22.csv",
        "2020-21": "Hong Kong Premier League 20-21.csv",
        "2019-20": "Hong Kong Premier League 19-20.csv",
        "2018-19": "Hong Kong Premier League 18-19.csv"
    }

class UIConfig:
    """Configuración de interfaz de usuario."""
    
    # Configuración desde .env
    TOP_PERFORMERS_COUNT = get_env_int("TOP_PERFORMERS_COUNT", 10)
    DEFAULT_CHART_HEIGHT = get_env_int("DEFAULT_CHART_HEIGHT", 400)
    TABLE_PAGE_SIZE = get_env_int("TABLE_PAGE_SIZE", 10)
    
    # Colores del tema (estático - parte del diseño)
    COLORS = {
        'primary': '#6ea4da',
        'secondary': '#3498db',
        'success': '#27ae60',
        'danger': '#e74c3c',
        'warning': '#f39c12',
        'info': '#17a2b8',
        'light': '#2d3748',
        'dark': '#343a40',
        'background': '#313131'
    }
    
    # Configuración de gráficos (derivada)
    CHART_CONFIG = {
        'default_height': DEFAULT_CHART_HEIGHT,
        'color_scales': {
            'default': 'Blues',
            'performance': 'Viridis',
            'injury': 'Reds'
        }
    }
    
    # Filtros por defecto (derivados)
    DEFAULT_FILTERS = {
        'position': 'all',
        'age_range': [15, 45],
        'season': DataConfig.DEFAULT_SEASON
    }
    
    # Configuración de tablas (derivada)
    TABLE_CONFIG = {
        'default_page_size': TABLE_PAGE_SIZE,
        'max_page_size': TABLE_PAGE_SIZE * 5,
        'style_cell': {
            'textAlign': 'left',
            'padding': '10px',
            'fontFamily': 'Arial',
            'fontSize': 14
        },
        'style_header': {
            'backgroundColor': COLORS['primary'],
            'color': 'white',
            'fontWeight': 'bold',
            'textAlign': 'center'
        }
    }

class PerformanceConfig:
    """Configuración específica del dashboard de performance."""
    
    # Métricas por posición (estático - lógica de negocio)
    POSITION_METRICS = {
        'Goalkeeper': [
            'Clean sheets', 'Save rate, %', 'Conceded goals', 'xG against'
        ],
        'Defender': [
            'Defensive duels won, %', 'Aerial duels won, %', 
            'Interceptions per 90', 'Fouls per 90'
        ],
        'Midfielder': [
            'Accurate passes, %', 'Key passes per 90', 
            'Progressive passes per 90', 'Assists'
        ],
        'Winger': [
            'Successful dribbles, %', 'Crosses per 90', 
            'Assists', 'Goals'
        ],
        'Forward': [
            'Goals', 'xG', 'Goal conversion, %', 'Shots on target, %'
        ]
    }
    
    # Filtros de posición disponibles (estático)
    POSITION_FILTERS = [
        {"label": "Todas las posiciones", "value": "all"},
        {"label": "Portero", "value": "Goalkeeper"},
        {"label": "Defensor", "value": "Defender"},
        {"label": "Mediocampista", "value": "Midfielder"},
        {"label": "Extremo", "value": "Winger"},
        {"label": "Delantero", "value": "Forward"}
    ]

class InjuryConfig:
    """Configuración específica del dashboard de lesiones."""
    
    # Tipos de análisis (estático)
    ANALYSIS_TYPES = [
        {"label": "🏥 Lesiones Generales", "value": "general"},
        {"label": "🦵 Lesiones por Región", "value": "body_part"},
        {"label": "📅 Tendencias Temporales", "value": "temporal"},
        {"label": "⚽ Lesiones por Equipo", "value": "team"}
    ]
    
    # Períodos de análisis (estático)
    ANALYSIS_PERIODS = [
        {"label": "Último mes", "value": "1m"},
        {"label": "Últimos 3 meses", "value": "3m"},
        {"label": "Últimos 6 meses", "value": "6m"},
        {"label": "Última temporada", "value": "season"},
        {"label": "Todo el historial", "value": "all"}
    ]
    
    # Severidades y estados de lesión (estático)
    INJURY_SEVERITIES = ['Leve', 'Moderada', 'Grave']
    INJURY_STATUSES = ['En tratamiento', 'Recuperado', 'Crónico']

class LoggingConfig:
    """Configuración de logging."""
    
    # Configuración desde .env
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    MAX_LOG_SIZE = get_env_int("MAX_LOG_SIZE", 10 * 1024 * 1024)  # 10MB
    BACKUP_COUNT = get_env_int("BACKUP_COUNT", 5)
    
    # Formato y archivos (estático)
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILES = {
        'app': 'logs/app.log',
        'data': 'logs/data.log',
        'errors': 'logs/errors.log'
    }

# Funciones auxiliares
def create_directories():
    """Crea todos los directorios necesarios para la aplicación."""
    directories = [
        AppConfig.DATA_DIR,
        AppConfig.CACHE_DATA_DIR,
        AppConfig.EXPORTS_DIR,
        AppConfig.LOGS_DIR,
        AppConfig.ASSETS_DIR,
        AppConfig.CACHE_DIR
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def validate_config() -> List[str]:
    """
    Valida la configuración básica de la aplicación.
    
    Returns:
        Lista de errores encontrados
    """
    errors = []
    
    # Verificar variables de entorno críticas
    if not AppConfig.ADMIN_USER:
        errors.append("ADMIN_USER no está configurado en .env")
    
    if not AppConfig.ADMIN_PASSWORD:
        errors.append("ADMIN_PASSWORD no está configurado en .env")
    
    if not AppConfig.SECRET_KEY or AppConfig.SECRET_KEY == "dev-secret-key-change-in-production":
        if not AppConfig.DEBUG:
            errors.append("SECRET_KEY debe cambiarse en producción")
    
    # Verificar puertos
    if not (1024 <= AppConfig.PORT <= 65535):
        errors.append(f"PORT debe estar entre 1024-65535, actual: {AppConfig.PORT}")
    
    # Verificar temporada por defecto
    if DataConfig.DEFAULT_SEASON not in DataConfig.AVAILABLE_SEASONS:
        errors.append(f"DEFAULT_SEASON '{DataConfig.DEFAULT_SEASON}' no está en AVAILABLE_SEASONS")
    
    # Verificar directorios
    try:
        create_directories()
    except Exception as e:
        errors.append(f"No se pudieron crear directorios: {e}")
    
    return errors

def get_config_summary() -> Dict:
    """
    Obtiene un resumen de la configuración actual.
    
    Returns:
        Diccionario con resumen de configuración
    """
    return {
        'app': {
            'name': AppConfig.APP_NAME,
            'version': AppConfig.APP_VERSION,
            'debug': AppConfig.DEBUG,
            'host': AppConfig.HOST,
            'port': AppConfig.PORT
        },
        'data': {
            'default_season': DataConfig.DEFAULT_SEASON,
            'available_seasons': len(DataConfig.AVAILABLE_SEASONS),
            'expected_teams': len(DataConfig.EXPECTED_HK_TEAMS)
        },
        'ui': {
            'top_performers': UIConfig.TOP_PERFORMERS_COUNT,
            'chart_height': UIConfig.DEFAULT_CHART_HEIGHT,
            'table_page_size': UIConfig.TABLE_PAGE_SIZE
        },
        'validation_errors': validate_config()
    }

# Configuración automática basada en entorno
if AppConfig.DEBUG:
    # Configuraciones adicionales para desarrollo
    LoggingConfig.LOG_LEVEL = "DEBUG"
    # Crear directorios automáticamente en desarrollo
    create_directories()
else:
    # Configuraciones para producción
    LoggingConfig.LOG_LEVEL = "INFO"