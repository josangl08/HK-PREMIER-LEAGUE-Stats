"""
Módulo de caché para la aplicación.
Proporciona funciones para inicializar y usar el sistema de caché,
mejorando el rendimiento mediante el almacenamiento de resultados de operaciones costosas.
"""

from flask_caching import Cache
import os
from dotenv import load_dotenv
import logging

# Configurar logging
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Obtener configuración de caché desde variables de entorno
CACHE_TYPE = os.getenv('CACHE_TYPE', 'filesystem')
CACHE_DIR = os.getenv('CACHE_DIR', './cache')
CACHE_DEFAULT_TIMEOUT = int(os.getenv('CACHE_DEFAULT_TIMEOUT', '300'))  # Ahora configurable

# Configuración adicional basada en el tipo de caché
cache_config = {
    'CACHE_TYPE': CACHE_TYPE,
    'CACHE_DEFAULT_TIMEOUT': CACHE_DEFAULT_TIMEOUT
}

# Añadir configuración específica según el tipo de caché
if CACHE_TYPE == 'filesystem':
    cache_config['CACHE_DIR'] = CACHE_DIR
elif CACHE_TYPE == 'redis':
    cache_config['CACHE_REDIS_URL'] = os.getenv('CACHE_REDIS_URL', 'redis://localhost:6379/0')
elif CACHE_TYPE == 'memcached':
    cache_config['CACHE_MEMCACHED_SERVERS'] = os.getenv('CACHE_MEMCACHED_SERVERS', ['127.0.0.1:11211'])

# Inicializar el objeto de caché
cache = Cache(config=cache_config)

def init_cache(flask_app):
    """
    Inicializa el caché con la aplicación Flask o Dash.
    
    Args:
        flask_app: Aplicación Flask o Dash
        
    Returns:
        Objeto cache inicializado
    
    """
    # Si recibimos una aplicación Dash, usamos su server
    if hasattr(flask_app, 'server'):
        flask_app = flask_app.server
    
    # Inicializar el caché
    cache.init_app(flask_app)
    logger.info(f"Cache inicializado con tipo: {CACHE_TYPE}, timeout: {CACHE_DEFAULT_TIMEOUT}s")
    
    return cache