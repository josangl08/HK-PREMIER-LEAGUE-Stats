"""
Módulo de agregadores de estadísticas.

Proporciona clases para generar estadísticas agregadas
a nivel de liga, equipo y jugador.
"""

from .hong_kong_aggregator import HongKongStatsAggregator
from .transfermarkt_aggregator import TransfermarktStatsAggregator

# Exportar las clases principales
__all__ = [
    'HongKongStatsAggregator',
    'TransfermarktStatsAggregator',
]

# Metadatos del módulo
__version__ = "1.0.0"