"""
Módulo de extractores de datos.

Proporciona clases para descargar datos de diferentes fuentes,
principalmente desde repositorios de GitHub.
"""

from .hong_kong_extractor import HongKongDataExtractor

# Exportar las clases principales
__all__ = [
    'HongKongDataExtractor',
]

# Metadatos del módulo
__version__ = "1.0.0"