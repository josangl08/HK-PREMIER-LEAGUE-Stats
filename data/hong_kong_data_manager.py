"""
Gestor integral de datos de Hong Kong.
Combina extractor, procesador y agregador en una interfaz unificada.
"""

import pandas as pd
from typing import Dict, List, Optional, Union
from datetime import datetime
import logging

 # Importar componentes
from data.extractors.hong_kong_extractor import HongKongDataExtractor
from data.processors.hong_kong_processor import HongKongDataProcessor
from data.aggregators.hong_kong_aggregator import HongKongStatsAggregator

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HongKongDataManager:
    """
    Gestor integral que combina extracción, procesamiento y agregación
    de datos de la Liga de Hong Kong.
    """
    
    def __init__(self, auto_load: bool = True):
        """
        Inicializa el gestor de datos.
        
        Args:
            auto_load: Si debe cargar automáticamente los datos al inicializar
        """
        
        self.extractor = HongKongDataExtractor()
        self.processor = HongKongDataProcessor()
        self.aggregator = None
        
        # Estado interno
        self.raw_data = None
        self.processed_data = None
        self.current_season = "2024-25"
        self.last_update = None
        
        if auto_load:
            self.refresh_data()
    
    def refresh_data(self, season: Optional[str] = None, force_download: bool = False) -> bool:
        """
        Refresca todos los datos (extrae, procesa y prepara agregador).
        
        Args:
            season: Temporada a cargar (por defecto actual)
            force_download: Forzar descarga desde GitHub
            
        Returns:
            True si la operación fue exitosa
        """
        try:
            # Usar temporada especificada o actual
            season = season or self.current_season
            
            logger.info(f"Refreshing data for season {season}")
            
            # 1. Extraer datos
            logger.info("Extracting raw data...")
            self.raw_data = self.extractor.download_season_data(season, force_download)
            
            if self.raw_data is None:
                logger.error("Failed to extract data")
                return False
            
            logger.info(f"Extracted {len(self.raw_data)} player records")
            
            # 2. Procesar datos
            logger.info("Processing data...")
            self.processed_data = self.processor.process_season_data(self.raw_data, season)
            
            if self.processed_data.empty:
                logger.error("Failed to process data")
                return False
            
            logger.info(f"Processed {len(self.processed_data)} player records")
            
            # 3. Inicializar agregador
            logger.info("Initializing aggregator...")
            self.aggregator = HongKongStatsAggregator(self.processed_data)
            
            # Actualizar estado
            self.current_season = season
            self.last_update = datetime.now()
            
            logger.info("Data refresh completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error refreshing data: {str(e)}")
            return False
    
    def get_league_overview(self) -> Dict:
        """
        Obtiene overview completo de la liga.
        
        Returns:
            Diccionario con estadísticas de la liga
        """
        if not self._check_data_availability():
            return {"error": "No data available"}
        
        if self.aggregator is None:
            return {"error": "Aggregator not initialized"}
        return self.aggregator.get_league_statistics()
    
    def get_team_overview(self, team_name: str) -> Dict:
        """
        Obtiene overview completo de un equipo.
        
        Args:
            team_name: Nombre del equipo
            
        Returns:
            Diccionario con estadísticas del equipo
        """
        if not self._check_data_availability():
            return {"error": "No data available"}
        
        if self.aggregator is None:
            return {"error": "Aggregator not initialized"}
        return self.aggregator.get_team_statistics(team_name)
    
    def get_player_overview(self, player_name: str, team_name: Optional[str] = None) -> Dict:
        """
        Obtiene overview completo de un jugador.
        
        Args:
            player_name: Nombre del jugador
            team_name: Nombre del equipo (opcional)
            
        Returns:
            Diccionario con estadísticas del jugador
        """
        if not self._check_data_availability():
            return {"error": "No data available"}
        
        if self.aggregator is None:
            return {"error": "Aggregator not initialized"}
        return self.aggregator.get_player_statistics(player_name, team_name)
    
    def get_chart_data(self, level: str, identifier: Optional[str] = None) -> Dict:
        """
        Obtiene datos formateados para gráficos.
        
        Args:
            level: 'league', 'team', o 'player'
            identifier: team_name para 'team', player_name para 'player'
            
        Returns:
            Diccionario con datos para gráficos
        """
        if not self._check_data_availability():
            return {"error": "No data available"}
        
        if self.aggregator is None:
            return {"error": "Aggregator not initialized"}
        return self.aggregator.get_comparative_data_for_charts(level, identifier)
    
    def get_available_teams(self) -> List[str]:
        """Retorna lista de equipos disponibles."""
        if not self._check_data_availability() or self.aggregator is None:
            return []
        
        return self.aggregator.get_available_teams()
    
    def get_available_players(self, team_name: Optional[str] = None) -> List[str]:
        """
        Retorna lista de jugadores disponibles.
        
        Args:
            team_name: Filtrar por equipo específico
            
        Returns:
            Lista de nombres de jugadores
        """
        if not self._check_data_availability() or self.aggregator is None:
            return []
        
        return self.aggregator.get_available_players(team_name)
    
    def search_players(self, query: str, team_name: Optional[str] = None) -> List[Dict]:
        """
        Busca jugadores por nombre.
        
        Args:
            query: Término de búsqueda
            team_name: Filtrar por equipo específico
            
        Returns:
            Lista de diccionarios con información de jugadores
        """
        if not self._check_data_availability():
            return []
        
        # Filtrar datos
        data = self.processed_data
        if data is None:
            return []
        if team_name:
            data = data[data['Team'] == team_name]
        
        # Buscar por nombre (case insensitive)
        matches = data[data['Player'].str.contains(query, case=False, na=False)]
        
        # Formatear resultados
        results = []
        for _, player in matches.iterrows():
            results.append({
                'name': player['Player'],
                'team': player['Team'],
                'position': player.get('Position_Group', 'Unknown'),
                'age': player.get('Age', 0),
                'goals': player.get('Goals', 0),
                'assists': player.get('Assists', 0)
            })
        
        return sorted(results, key=lambda x: x['name'])
    
    def get_data_status(self) -> Dict:
        """
        Obtiene el estado actual de los datos.
        
        Returns:
            Diccionario con información del estado
        """
        # Información de cache
        cache_info = self.extractor.get_cache_info()
        
        # Estado de los datos
        data_status = {
            'current_season': self.current_season,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'raw_data_available': self.raw_data is not None,
            'processed_data_available': self.processed_data is not None,
            'aggregator_available': self.aggregator is not None,
            'cache_info': cache_info
        }
        
        # Estadísticas de datos si están disponibles
        if self.processed_data is not None:
            data_status['data_stats'] = {
                'total_players': len(self.processed_data),
                'total_teams': self.processed_data['Team'].nunique() if 'Team' in self.processed_data.columns else 0,
                'columns_count': len(self.processed_data.columns)
            }
        
        return data_status
    
    def check_for_updates(self) -> Dict:
        """
        Verifica si hay actualizaciones disponibles.
        
        Returns:
            Diccionario con información de actualizaciones
        """
        needs_update, message = self.extractor.check_for_updates(self.current_season)
        
        return {
            'needs_update': needs_update,
            'message': message,
            'current_season': self.current_season,
            'last_update': self.last_update.isoformat() if self.last_update else None
        }
    
    def export_data(self, format: str = 'csv', level: str = 'processed') -> Optional[str]:
        """
        Exporta datos en diferentes formatos.
        
        Args:
            format: 'csv', 'json', 'excel'
            level: 'raw', 'processed'
            
        Returns:
            Path del archivo exportado o None si hay error
        """
        try:
            # Seleccionar datos a exportar
            if level == 'raw' and self.raw_data is not None:
                data = self.raw_data
            elif level == 'processed' and self.processed_data is not None:
                data = self.processed_data
            else:
                logger.error(f"No data available for level: {level}")
                return None
            
            # Generar nombre de archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hong_kong_{level}_{self.current_season}_{timestamp}"
            
            # Exportar según formato
            if format == 'csv':
                filepath = f"data/exports/{filename}.csv"
                data.to_csv(filepath, index=False)
            elif format == 'json':
                filepath = f"data/exports/{filename}.json"
                data.to_json(filepath, orient='records', indent=2)
            elif format == 'excel':
                filepath = f"data/exports/{filename}.xlsx"
                data.to_excel(filepath, index=False)
            else:
                logger.error(f"Unsupported format: {format}")
                return None
            
            logger.info(f"Data exported to: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error exporting data: {str(e)}")
            return None
    
    def get_performance_summary(self, level: str, identifier: Optional[str] = None) -> Dict:
        """
        Obtiene un resumen de performance para dashboard.
        
        Args:
            level: 'league', 'team', o 'player'
            identifier: team_name para 'team', player_name para 'player'
            
        Returns:
            Diccionario con métricas clave para dashboard
        """
        if not self._check_data_availability():
            return {"error": "No data available"}
        
        try:
            if level == 'league':
                if self.aggregator is None:
                    return {"error": "Aggregator not initialized"}
                stats = self.aggregator.get_league_statistics()
                return {
                    'title': f'Liga de Hong Kong - {self.current_season}',
                    'overview': stats['overview'],
                    'top_scorers': stats['top_performers']['top_scorers'][:5] if 'top_performers' in stats else [],
                    'position_breakdown': stats['position_analysis'] if 'position_analysis' in stats else {}
                }
            
            elif level == 'team' and identifier:
                if self.aggregator is None:
                    return {"error": "Aggregator not initialized"}
                stats = self.aggregator.get_team_statistics(identifier)
                return {
                    'title': f'{identifier} - {self.current_season}',
                    'overview': stats['overview'],
                    'top_players': stats['top_players'] if 'top_players' in stats else {},
                    'squad_analysis': stats['squad_analysis'] if 'squad_analysis' in stats else {}
                }
            
            elif level == 'player' and identifier:
                if self.aggregator is None:
                    return {"error": "Aggregator not initialized"}
                stats = self.aggregator.get_player_statistics(identifier)
                return {
                    'title': f'{identifier} - {self.current_season}',
                    'basic_info': stats['basic_info'],
                    'performance': stats['performance_stats'] if 'performance_stats' in stats else {},
                    'comparisons': stats['comparisons'] if 'comparisons' in stats else {}
                }
            
            else:
                return {"error": "Invalid parameters"}
                
        except Exception as e:
            logger.error(f"Error getting performance summary: {str(e)}")
            return {"error": str(e)}
    
    def _check_data_availability(self) -> bool:
        """Verifica si hay datos disponibles."""
        if self.processed_data is None or self.aggregator is None:
            logger.warning("Data not available. Run refresh_data() first")
            return False
        return True
    
    def clear_all_cache(self):
        """Limpia todos los caches."""
        try:
            # Limpiar cache del extractor
            self.extractor.clear_cache()
            
            # Limpiar cache del agregador si existe
            if self.aggregator:
                self.aggregator.clear_cache()
            
            logger.info("All caches cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")