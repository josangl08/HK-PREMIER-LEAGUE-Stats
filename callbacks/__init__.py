"""
Paquete de manejo de datos para la Liga de Hong Kong.

Este paquete proporciona herramientas para extraer, procesar y agregar
estadísticas de jugadores de la Liga Premier de Hong Kong y datos de 
lesiones desde Transfermarkt.

Uso principal:
    from data import HongKongDataManager
    from data import TransfermarktDataManager
"""

# Managers principales - más fáciles de importar
from data.hong_kong_data_manager import HongKongDataManager
from data.transfermarkt_data_manager import TransfermarktDataManager

# Extractors, processors y aggregators disponibles para uso avanzado
from data.extractors import HongKongDataExtractor, TransfermarktExtractor
from data.processors import HongKongDataProcessor, TransfermarktProcessor  
from data.aggregators import HongKongStatsAggregator, TransfermarktStatsAggregator

__version__ = "1.0.0"
__author__ = "Sports Dashboard Team"

# Exportar solo lo más importante para uso normal
__all__ = [
    # Managers principales (uso común)
    'HongKongDataManager',
    'TransfermarktDataManager',
    
    # Componentes individuales (uso avanzado)
    'HongKongDataExtractor',
    'TransfermarktExtractor', 
    'HongKongDataProcessor',
    'TransfermarktProcessor',
    'HongKongStatsAggregator',
    'TransfermarktStatsAggregator'
]