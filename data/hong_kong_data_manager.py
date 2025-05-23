"""
Gestor simplificado de datos de Hong Kong.
Versión limpia y optimizada que mantiene funcionalidad esencial.
"""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
import logging
import json
from pathlib import Path

# Importar componentes
from data.extractors.hong_kong_extractor import HongKongDataExtractor
from data.processors.hong_kong_processor import HongKongDataProcessor
from data.aggregators.hong_kong_aggregator import HongKongStatsAggregator

# Configurar logging
logger = logging.getLogger(__name__)

class HongKongDataManager:
    """
    Gestor simplificado de datos de la Liga de Hong Kong.
    Versión optimizada con responsabilidades claras.
    """
    
    def __init__(self, auto_load: bool = True):
        """
        Inicializa el gestor de datos.
        
        Args:
            auto_load: Si debe cargar automáticamente los datos al inicializar
        """
        self.extractor = HongKongDataExtractor()
        self.processor = HongKongDataProcessor()
        self.aggregator: Optional[HongKongStatsAggregator] = None
        
        # Estado interno
        self.current_season = "2024-25"
        self.raw_data: Optional[pd.DataFrame] = None
        self.processed_data: Optional[pd.DataFrame] = None
        self.data_cache: Dict = {}  # Cache simple por temporada
        self.last_update: Dict = {}
        
        # Cargar timestamps
        self._load_update_timestamps()
        
        if auto_load:
            self._load_current_season()
    
    def _load_update_timestamps(self):
        """Carga timestamps de últimas actualizaciones desde un archivo."""
        timestamp_file = Path(self.extractor.cache_dir) / "update_timestamps.json"
        if timestamp_file.exists():
            try:
                with open(timestamp_file, 'r') as f:
                    timestamps_json = json.load(f)
                    
                    # Convertir strings a datetime SOLO para temporadas de Hong Kong
                    self.last_update = {}
                    for season, timestamp in timestamps_json.items():
                        # Solo procesar temporadas de Hong Kong (ignorar transfermarkt)
                        if season not in ['transfermarkt', 'transfermarkt_manual']:
                            try:
                                self.last_update[season] = datetime.fromisoformat(timestamp)
                            except:
                                # Si hay error al parsear, ignorar esta entrada
                                pass
                                
                    logger.info(f"Loaded Hong Kong timestamps for {len(self.last_update)} seasons")
            except Exception as e:
                logger.warning(f"Failed to load Hong Kong timestamps: {e}")
                self.last_update = {}
        else:
            self.last_update = {}
    
    def _save_update_timestamps(self):
        """Guarda timestamps de últimas actualizaciones en un archivo compartido."""
        timestamp_file = Path(self.extractor.cache_dir) / "update_timestamps.json"
        try:
            # PASO 1: Cargar timestamps existentes (incluyendo transfermarkt)
            existing_timestamps = {}
            if timestamp_file.exists():
                with open(timestamp_file, 'r') as f:
                    existing_timestamps = json.load(f)
            
            # PASO 2: Actualizar solo los timestamps de Hong Kong
            for season, timestamp in self.last_update.items():
                if isinstance(timestamp, datetime):
                    existing_timestamps[season] = timestamp.isoformat()
            
            # PASO 3: Guardar archivo completo (preservando transfermarkt)
            with open(timestamp_file, 'w') as f:
                json.dump(existing_timestamps, f, indent=2)
                
            logger.info(f"Hong Kong timestamps guardados (preservando otros sistemas)")
            
        except Exception as e:
            logger.warning(f"Error guardando timestamps de Hong Kong: {e}")
    
    def _load_current_season(self):
        """Carga datos de la temporada actual desde cache si existe."""
        cached_file = self.extractor._get_cached_file_path(self.current_season)
        if cached_file.exists():
            try:
                self.raw_data = pd.read_csv(cached_file)
                self.processed_data = self.processor.process_season_data(self.raw_data, self.current_season)
                self.aggregator = HongKongStatsAggregator(self.processed_data.copy())
                
                # Agregar al cache
                self._add_to_cache(self.current_season, self.raw_data, self.processed_data, self.aggregator)
                
                logger.info(f"Datos cargados desde cache para {self.current_season}")
            except Exception as e:
                logger.error(f"Error cargando desde cache: {e}")
                self.refresh_data()
        else:
            self.refresh_data()
    
    def _add_to_cache(self, season: str, raw_data: pd.DataFrame, processed_data: pd.DataFrame, aggregator: HongKongStatsAggregator):
        """Agrega datos al cache."""
        self.data_cache[season] = {
            'raw_data': raw_data,
            'processed_data': processed_data,
            'aggregator': aggregator,
            'last_update': datetime.now()
        }
    
    def _load_from_cache(self, season: str) -> bool:
        """
        Carga datos desde cache si existe.
        
        Returns:
            True si se cargó exitosamente desde cache
        """
        if season in self.data_cache:
            cache_data = self.data_cache[season]
            self.current_season = season
            self.raw_data = cache_data['raw_data']
            self.processed_data = cache_data['processed_data']
            self.aggregator = cache_data['aggregator']
            logger.info(f"Datos cargados desde cache interno para {season}")
            return True
        
        # Intentar cargar desde archivo cache
        cached_file = self.extractor._get_cached_file_path(season)
        if cached_file.exists():
            try:
                raw_data = pd.read_csv(cached_file)
                processed_data = self.processor.process_season_data(raw_data, season)
                aggregator = HongKongStatsAggregator(processed_data.copy())
                
                # Actualizar estado actual
                self.current_season = season
                self.raw_data = raw_data
                self.processed_data = processed_data
                self.aggregator = aggregator
                
                # Agregar al cache interno
                self._add_to_cache(season, raw_data, processed_data, aggregator)
                
                logger.info(f"Datos cargados desde archivo cache para {season}")
                return True
            except Exception as e:
                logger.error(f"Error cargando desde archivo cache para {season}: {e}")
        
        return False
    
    def refresh_data(self, season: Optional[str] = None, force_download: bool = False) -> bool:
        """
        Refresca datos para una temporada específica.
        
        Args:
            season: Temporada a cargar (por defecto actual)
            force_download: Forzar descarga desde GitHub
            
        Returns:
            True si la operación fue exitosa
        """
        try:
            target_season = season or self.current_season
            logger.info(f"Refrescando datos para temporada {target_season}")
            
            # Si no es forzado y la temporada ya existe en cache, usar cache
            if not force_download and target_season != self.current_season:
                if self._load_from_cache(target_season):
                    return True
            
            # 1. Extraer datos
            raw_data = self.extractor.download_season_data(target_season, force_download)
            if raw_data is None:
                logger.error(f"Error extrayendo datos para {target_season}")
                return False
            
            # 2. Procesar datos
            processed_data = self.processor.process_season_data(raw_data, target_season)
            if processed_data.empty:
                logger.error("Error procesando datos")
                return False
            
            # 3. Crear agregador
            aggregator = HongKongStatsAggregator(processed_data.copy())
            
            # 4. SIEMPRE actualizar estado actual (ESTE ERA EL PROBLEMA)
            self.current_season = target_season
            self.raw_data = raw_data
            self.processed_data = processed_data
            self.aggregator = aggregator
            
            # 5. Actualizar cache y timestamps
            self._add_to_cache(target_season, raw_data, processed_data, aggregator)
            self.last_update[target_season] = datetime.now()
            self._save_update_timestamps()
            
            logger.info(f"Datos refrescados exitosamente para {target_season}")
            return True
            
        except Exception as e:
            logger.error(f"Error refrescando datos: {str(e)}")
            return False
    
    def get_league_overview(self, position_filter: Optional[str] = None, age_range: Optional[List[int]] = None) -> Dict:
        """Obtiene overview de la liga con filtros aplicados."""
        if not self._check_data_availability():
            return {"error": "No hay datos disponibles"}
        
        # Verificación explícita para Pylance
        if self.aggregator is None:
            return {"error": "Aggregator no inicializado"}
        
        try:
            return self.aggregator.get_league_statistics(position_filter, age_range)
        except Exception as e:
            logger.error(f"Error obteniendo overview de liga: {str(e)}")
            return {"error": str(e)}
    
    def get_team_overview(self, team_name: str, position_filter: Optional[str] = None, age_range: Optional[List[int]] = None) -> Dict:
        """Obtiene overview de un equipo con filtros aplicados."""
        if not self._check_data_availability():
            return {"error": "No hay datos disponibles"}
        
        # Verificación explícita para Pylance
        if self.aggregator is None:
            return {"error": "Aggregator no inicializado"}
        
        try:
            return self.aggregator.get_team_statistics(team_name, position_filter, age_range)
        except Exception as e:
            logger.error(f"Error obteniendo overview de equipo: {str(e)}")
            return {"error": str(e)}
    
    def get_player_overview(self, player_name: str, team_name: Optional[str] = None) -> Dict:
        """Obtiene overview de un jugador."""
        if not self._check_data_availability():
            return {"error": "No hay datos disponibles"}
        
        # Verificación explícita para Pylance
        if self.aggregator is None:
            return {"error": "Aggregator no inicializado"}
        
        try:
            return self.aggregator.get_player_statistics(player_name, team_name)
        except Exception as e:
            logger.error(f"Error obteniendo overview de jugador: {str(e)}")
            return {"error": str(e)}
    
    def get_chart_data(self, level: str, identifier: Optional[str] = None) -> Dict:
        """Obtiene datos formateados para gráficos."""
        if not self._check_data_availability():
            return {"error": "No hay datos disponibles"}
        
        # Verificación explícita para Pylance
        if self.aggregator is None:
            return {"error": "Aggregator no inicializado"}
        
        try:
            return self.aggregator.get_comparative_data_for_charts(level, identifier)
        except Exception as e:
            logger.error(f"Error obteniendo datos de gráficos: {str(e)}")
            return {"error": str(e)}
    
    def get_available_teams(self) -> List[str]:
        """Retorna lista de equipos disponibles."""
        if not self._check_data_availability():
            return []
        
        # Verificación explícita para Pylance
        if self.aggregator is None:
            return []
        
        return self.aggregator.get_available_teams()
    
    def get_available_players(self, team_name: Optional[str] = None) -> List[str]:
        """Retorna lista de jugadores disponibles."""
        if not self._check_data_availability():
            return []
        
        # Verificación explícita para Pylance
        if self.aggregator is None:
            return []
        
        return self.aggregator.get_available_players(team_name)
    
    def get_available_seasons(self) -> List[str]:
        """Retorna lista de temporadas disponibles."""
        return self.extractor.get_available_seasons()
    
    def get_data_status(self) -> Dict:
        """Obtiene el estado actual de los datos."""
        cached_file = self.extractor._get_cached_file_path(self.current_season)
        file_timestamp = None
        if cached_file.exists():
            file_timestamp = datetime.fromtimestamp(cached_file.stat().st_mtime)
        
        last_update = None
        if file_timestamp and self.current_season in self.last_update:
            last_update = max(file_timestamp, self.last_update[self.current_season])
        elif file_timestamp:
            last_update = file_timestamp
        else:
            last_update = self.last_update.get(self.current_season)
        
        # Obtener todas las temporadas disponibles en cache (archivos + cache interno)
        all_cached_seasons = set(self.data_cache.keys())
        
        # Agregar temporadas que tienen archivos cache
        for season in self.get_available_seasons():
            cached_file = self.extractor._get_cached_file_path(season)
            if cached_file.exists():
                all_cached_seasons.add(season)
        
        status = {
            'current_season': self.current_season,
            'available_seasons': self.get_available_seasons(),
            'last_update': last_update,
            'raw_data_available': self.raw_data is not None,
            'processed_data_available': self.processed_data is not None,
            'aggregator_available': self.aggregator is not None,
            'extractor_cache_info': self.extractor.get_cache_info(),
            'cached_seasons': sorted(list(all_cached_seasons))  # Mostrar todas las temporadas en cache
        }
        
        if self.processed_data is not None:
            status['data_stats'] = {
                'total_players': len(self.processed_data),
                'total_teams': self.processed_data['Team'].nunique() if 'Team' in self.processed_data.columns else 0,
                'columns_count': len(self.processed_data.columns)
            }
            
            if 'Team' in self.processed_data.columns:
                teams_list = sorted(self.processed_data['Team'].unique())
                status['hong_kong_teams'] = teams_list
                status['teams_count'] = len(teams_list)
        
        return status
    
    def check_for_updates(self, season: Optional[str] = None) -> Dict:
        """Verifica si hay actualizaciones disponibles."""
        target_season = season or self.current_season
        needs_update, message = self.extractor.check_for_updates(target_season)
        
        return {
            'needs_update': needs_update,
            'message': message,
            'season': target_season,
            'last_update': self.last_update[target_season].isoformat() if target_season in self.last_update else None
        }
    
    def _check_data_availability(self) -> bool:
        """Verifica si hay datos disponibles."""
        if self.processed_data is None or self.aggregator is None:
            logger.warning(f"Datos no disponibles para temporada {self.current_season}")
            return False
        return True
    
    def clear_all_cache(self):
        """Limpia todos los caches."""
        try:
            self.extractor.clear_cache()
            self.data_cache.clear()
            self.last_update.clear()
            self.raw_data = None
            self.processed_data = None
            self.aggregator = None
            logger.info("Todos los caches eliminados")
        except Exception as e:
            logger.error(f"Error limpiando cache: {str(e)}")