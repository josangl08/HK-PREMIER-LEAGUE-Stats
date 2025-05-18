"""
Paquete de manejo de datos para la Liga de Hong Kong.

Este paquete proporciona herramientas para extraer, procesar y agregar
estadísticas de jugadores de la Liga Premier de Hong Kong.

Módulos principales:
- extractors: Descarga de datos desde GitHub
- processors: Limpieza y transformación de datos
- aggregators: Generación de estadísticas agregadas
- hong_kong_data_manager: Gestor integral de todos los componentes
"""

# Versión del paquete
__version__ = "1.0.0"

# Metadatos
__author__ = "Tu Nombre"
__email__ = "tu.email@example.com"

# Importaciones principales para facilitar el uso
from .hong_kong_data_manager import HongKongDataManager

# Definir qué se exporta cuando se usa "from data import *"
__all__ = [
    'HongKongDataManager',
    # Los otros módulos se importan explícitamente si se necesitan
]