"""
Módulo de procesadores de datos.

Proporciona clases para limpiar, transformar y estandarizar
datos crudos de jugadores.
"""

from .hong_kong_processor import HongKongDataProcessor
from .transfermarkt_processor import TransfermarktProcessor

# Exportar las clases principales
__all__ = [
'HongKongDataProcessor',
'TransfermarktProcessor'
]

# Metadatos del módulo
__version__ = "1.0.0"