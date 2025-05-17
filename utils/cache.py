from flask_caching import Cache
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración del caché basada en variables de entorno
cache_config = {
    'CACHE_TYPE': os.getenv('CACHE_TYPE', 'filesystem'),
    'CACHE_DIR': os.getenv('CACHE_DIR', './cache'),
    'CACHE_DEFAULT_TIMEOUT': 300  # 5 minutos en segundos
}

# Inicializar el objeto de caché
cache = Cache(config=cache_config)

#  Inicializa el caché con la aplicación Flask
def init_cache(flask_app):
    
    # Si recibimos una aplicación Dash, usamos su server
    if hasattr(flask_app, 'server'):
        flask_app = flask_app.server
    
    # Inicializar el caché
    cache.init_app(flask_app)
    return cache