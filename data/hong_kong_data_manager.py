"""
Gestor integral de datos de Hong Kong.
Combina extractor, procesador y agregador en una interfaz unificada.
Versión corregida para manejar equipos y posiciones correctamente.
"""

import pandas as pd
from typing import Dict, List, Optional, Union
from datetime import datetime
import logging
import threading
import json
from pathlib import Path


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
    Versión corregida para mejor manejo de equipos y temporadas.
    """
    
    def __init__(self, auto_load: bool = True, background_preload: bool = False):
        """
        Inicializa el gestor de datos.
        
        Args:
            auto_load: Si debe cargar automáticamente los datos al inicializar
            background_preload: Si debe pre-cargar otras temporadas en background
        """
        
        self.extractor = HongKongDataExtractor()
        self.processor = HongKongDataProcessor()
        self.aggregator = None
        
        # Estado interno - mejorado para múltiples temporadas
        self.data_cache = {}  # Cache por temporada
        self.current_season = "2024-25"
        self.last_update = {}  # Última actualización por temporada
        
        # Datos actuales
        self.raw_data = None
        self.processed_data = None

        # Cargar timestamps desde archivo
        self._load_update_timestamps()
        
        if auto_load:
            # Verificar si ya hay datos en caché para la temporada actual
            timestamp_file = Path(self.extractor.cache_dir) / "update_timestamps.json"
            if "2024-25" in self.last_update and timestamp_file.exists():
                # Cargar desde caché sin actualizar timestamps
                logger.info("Using cached data from previous session")
                cached_file = self.extractor._get_cached_file_path("2024-25")
                if cached_file.exists():
                    try:
                        self.raw_data = pd.read_csv(cached_file)
                        self.processed_data = self.processor.process_season_data(self.raw_data, "2024-25")
                        self.aggregator = HongKongStatsAggregator(self.processed_data.copy())
                        logger.info("Loaded data from cache successfully")
                    except Exception as e:
                        logger.error(f"Error loading cached data: {e}")
                        self.refresh_data()
                else:
                    self.refresh_data()
            else:
                self.refresh_data()

            # Iniciar pre-carga en background después de cargar la principal
            if background_preload:
                self.start_background_preload()

    def _load_update_timestamps(self):
        """Carga timestamps de últimas actualizaciones desde un archivo."""
        timestamp_file = Path(self.extractor.cache_dir) / "update_timestamps.json"
        if timestamp_file.exists():
            try:
                with open(timestamp_file, 'r') as f:
                    timestamps_json = json.load(f)
                    # Convertir strings a datetime
                    self.last_update = {}
                    for season, timestamp in timestamps_json.items():
                        try:
                            self.last_update[season] = datetime.fromisoformat(timestamp)
                        except:
                            # Si hay error al parsear, ignorar esta entrada
                            pass
                    logger.info(f"Loaded update timestamps for {len(self.last_update)} seasons")
            except Exception as e:
                logger.warning(f"Failed to load timestamps: {e}")
                self.last_update = {}
        else:
            self.last_update = {}

    def _save_update_timestamps(self):
        """Guarda timestamps de últimas actualizaciones en un archivo."""
        timestamp_file = Path(self.extractor.cache_dir) / "update_timestamps.json"
        try:
            # Convertir datetime a strings
            timestamps = {}
            for season, timestamp in self.last_update.items():
                if isinstance(timestamp, datetime):
                    timestamps[season] = timestamp.isoformat()

            with open(timestamp_file, 'w') as f:
                json.dump(timestamps, f, indent=2)
            logger.info(f"Saved update timestamps for {len(self.last_update)} seasons")
        except Exception as e:
            logger.warning(f"Failed to save timestamps: {e}")                                   
            
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
            target_season = season or self.current_season
            current_season = "2024-25"  # Temporada actual
            
            logger.info(f"Refreshing data for season {target_season}")

            # Variable para rastrear si se descargaron nuevos datos
            data_was_downloaded = False
            
            # Si hay forzado manual, registrarlo
            if force_download:
                self.last_update[f"{target_season}_manual"] = datetime.now()
                self._save_update_timestamps()
            
            # SOLO para temporadas anteriores, usar caché siempre
            if target_season != current_season and target_season in self.data_cache:
                cached_data = self.data_cache[target_season]
                if cached_data.get('processed_data') is not None:
                    logger.info(f"Using cached data for previous season {target_season}")
                    
                    # Actualizar datos actuales
                    self.current_season = target_season
                    self.raw_data = cached_data['raw_data']
                    self.processed_data = cached_data['processed_data']
                    self.aggregator = cached_data['aggregator']
                    
                    return True
            
            # Para temporada actual
            if target_season == current_season:
                # Verificar si se debe buscar actualizaciones
                should_check = self.should_check_for_updates(target_season) or force_download
                
                # Si no es momento de verificar Y tenemos datos en caché, usar caché
                if not should_check and target_season in self.data_cache:
                    cached_data = self.data_cache[target_season]
                    if cached_data.get('processed_data') is not None:
                        logger.info(f"No es momento de verificar actualizaciones, usando caché para {target_season}")
                        
                        # Actualizar datos actuales
                        self.current_season = target_season
                        self.raw_data = cached_data['raw_data']
                        self.processed_data = cached_data['processed_data']
                        self.aggregator = cached_data['aggregator']
                        
                        return True
                
                # Si es momento de verificar Y tenemos datos en caché, verificar actualizaciones
                if should_check and target_season in self.data_cache:
                    needs_update, message = self.extractor.check_for_updates(target_season)
                    if not needs_update and not force_download:
                        cached_data = self.data_cache[target_season]
                        logger.info(f"No hay cambios en GitHub para {target_season}: {message}")
                        
                        # Actualizar datos actuales
                        self.current_season = target_season
                        self.raw_data = cached_data['raw_data']
                        self.processed_data = cached_data['processed_data']
                        self.aggregator = cached_data['aggregator']
                        
                        return True
                    else:
                        logger.info(f"Se detectaron cambios en GitHub para {target_season}: {message}")
            
            # Si llegamos aquí, necesitamos descargar/actualizar los datos
            
            # 1. Extraer datos
            logger.info(f"Downloading data for {target_season}...")
            raw_data = self.extractor.download_season_data(target_season, force_download)
            
            # Marcar que se descargaron datos si no usamos caché
            if force_download or not (target_season in self.data_cache):
                data_was_downloaded = True

            if raw_data is None:
                logger.error(f"Failed to extract data for {target_season}")
                return False
            
            logger.info(f"Extracted {len(raw_data)} player records")
            
            # 2. Procesar datos
            logger.info("Processing data...")
            processed_data = self.processor.process_season_data(raw_data, target_season)
            
            if processed_data.empty:
                logger.error("Failed to process data")
                return False
            
            logger.info(f"Processed {len(processed_data)} player records")
            
            # 3. Inicializar agregador
            logger.info("Initializing aggregator...")
            if not isinstance(processed_data, pd.DataFrame):
                logger.error("processed_data is not a DataFrame")
                return False
            
            try:
                aggregator = HongKongStatsAggregator(processed_data.copy())
            except Exception as e:
                logger.error(f"Failed to initialize aggregator: {str(e)}")
                return False
            
            # 4. Almacenar en cache
            self.data_cache[target_season] = {
                'raw_data': raw_data,
                'processed_data': processed_data,
                'aggregator': aggregator,
                'last_update': datetime.now()
            }
            
            # 5. Actualizar datos actuales
            self.current_season = target_season
            self.raw_data = raw_data
            self.processed_data = processed_data
            self.aggregator = aggregator
            
            # Actualizar timestamp y guardar
            if data_was_downloaded or force_download:
                self.last_update[target_season] = datetime.now()
                self._save_update_timestamps()
                logger.info(f"Updated timestamp for {target_season} - new data downloaded/processed")
            else:
                logger.info(f"Using cached data for {target_season}, main timestamp not updated")
                    
            logger.info("Data refresh completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error refreshing data: {str(e)}")
            return False
    
    def get_league_overview(self, position_filter: Optional[str] = None, age_range: Optional[List[int]] = None) -> Dict:
        """
        Obtiene overview completo de la liga con filtros aplicados.
        
        Args:
            position_filter: Filtro de posición ('all', 'Goalkeeper', etc.)
            age_range: Rango de edad [min, max]
            
        Returns:
            Diccionario con estadísticas de la liga
        """
        if not self._check_data_availability():
            return {"error": "No data available"}
            
        try:
            if self.aggregator is None:
                if not isinstance(self.processed_data, pd.DataFrame):
                    return {"error": "No processed data available"}
                self.aggregator = HongKongStatsAggregator(self.processed_data)
            
            return self.aggregator.get_league_statistics(position_filter, age_range)
        except Exception as e:
            logger.error(f"Error getting league statistics: {str(e)}")
            return {"error": str(e)}
    
    def get_team_overview(self, team_name: str, position_filter: Optional[str] = None, age_range: Optional[List[int]] = None) -> Dict:
        """
        Obtiene overview completo de un equipo con filtros aplicados.
        
        Args:
            team_name: Nombre del equipo
            position_filter: Filtro de posición
            age_range: Rango de edad [min, max]
            
        Returns:
            Diccionario con estadísticas del equipo
        """
        if not self._check_data_availability():
            return {"error": "No data available"}
            
        try:
            if self.aggregator is None:
                if not isinstance(self.processed_data, pd.DataFrame):
                    return {"error": "No processed data available"}
                self.aggregator = HongKongStatsAggregator(self.processed_data)
            
            return self.aggregator.get_team_statistics(team_name, position_filter, age_range)
        except Exception as e:
            logger.error(f"Error getting team statistics: {str(e)}")
            return {"error": str(e)}
    
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
            
        try:
            if self.aggregator is None:
                if not isinstance(self.processed_data, pd.DataFrame):
                    return {"error": "No processed data available"}
                self.aggregator = HongKongStatsAggregator(self.processed_data)
            
            return self.aggregator.get_player_statistics(player_name, team_name)
        except Exception as e:
            logger.error(f"Error getting player statistics: {str(e)}")
            return {"error": str(e)}
    
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
            
        try:
            if self.aggregator is None:
                if not isinstance(self.processed_data, pd.DataFrame):
                    return {"error": "No processed data available"}
                self.aggregator = HongKongStatsAggregator(self.processed_data)
            
            return self.aggregator.get_comparative_data_for_charts(level, identifier)
        except Exception as e:
            logger.error(f"Error getting chart data: {str(e)}")
            return {"error": str(e)}
    
    def get_available_teams(self) -> List[str]:
        """Retorna lista de equipos disponibles para la temporada actual."""
        if not self._check_data_availability():
            return []
            
        if self.aggregator is None:
            if not isinstance(self.processed_data, pd.DataFrame):
                return []
            self.aggregator = HongKongStatsAggregator(self.processed_data)
        
        return self.aggregator.get_available_teams()
    
    def get_available_players(self, team_name: Optional[str] = None) -> List[str]:
        """
        Retorna lista de jugadores disponibles ordenada alfabéticamente.
        
        Args:
            team_name: Filtrar por equipo específico
            
        Returns:
            Lista de nombres de jugadores ordenada alfabéticamente
        """
        if not self._check_data_availability():
            return []
            
        if self.aggregator is None:
            if not isinstance(self.processed_data, pd.DataFrame):
                return []
            self.aggregator = HongKongStatsAggregator(self.processed_data)
        
        return self.aggregator.get_available_players(team_name)
    
    def get_available_seasons(self) -> List[str]:
        """Retorna lista de temporadas disponibles."""
        return self.extractor.get_available_seasons()
    
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
            # Usar la posición más relevante
            position = (player.get('Position_Group') or 
                player.get('Position_Primary_Group') or 
                player.get('Position_Clean') or 
                'Unknown')
            
            results.append({
                'name': player['Player'],
                'team': player['Team'],
                'position': position,
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
        # Verificar fecha real del archivo para la temporada actual
        cached_file = self.extractor._get_cached_file_path(self.current_season)
        file_timestamp = None
        if cached_file.exists():
            file_timestamp = datetime.fromtimestamp(cached_file.stat().st_mtime)
        
        # Usar la fecha del archivo como último timestamp si existe y es más reciente
        last_update = None
        if file_timestamp and self.current_season in self.last_update:
            # Usar el timestamp más reciente
            last_update = max(file_timestamp, self.last_update[self.current_season])
        elif file_timestamp:
            last_update = file_timestamp
        else:
            last_update = self.last_update.get(self.current_season)

        # Estado de los datos actuales
        data_status = {
            'current_season': self.current_season,
            'available_seasons': self.get_available_seasons(),
            'last_update': last_update,
            'raw_data_available': self.raw_data is not None,
            'processed_data_available': self.processed_data is not None,
            'aggregator_available': self.aggregator is not None,
            'extractor_cache_info': self.extractor.get_cache_info(),
            'cached_seasons': list(self.data_cache.keys()) # Esto debería incluir todas las temporadas cacheadas
    }
        
        # Estadísticas de datos si están disponibles
        if self.processed_data is not None:
            data_status['data_stats'] = {
                'total_players': len(self.processed_data),
                'total_teams': self.processed_data['Team'].nunique() if 'Team' in self.processed_data.columns else 0,
                'columns_count': len(self.processed_data.columns)
            }
            
            # Listar equipos de Hong Kong
            if 'Team' in self.processed_data.columns:
                teams_list = sorted(self.processed_data['Team'].unique())
                data_status['hong_kong_teams'] = teams_list
                data_status['teams_count'] = len(teams_list)
        
        return data_status
    
    def check_for_updates(self, season: Optional[str] = None) -> Dict:
        """
        Verifica si hay actualizaciones disponibles.
        
        Args:
            season: Temporada a verificar (por defecto actual)
            
        Returns:
            Diccionario con información de actualizaciones
        """
        target_season = season or self.current_season
        needs_update, message = self.extractor.check_for_updates(target_season)
        
        # Para probar - descomentar esta línea:
        # needs_update = True
        # message = "Simulando actualización disponible para pruebas"

        return {
            'needs_update': needs_update,
            'message': message,
            'season': target_season,
            'last_update': self.last_update[target_season].isoformat() if target_season in self.last_update else None
        }
    
    def should_check_for_updates(self, season: Optional[str] = None) -> bool:
        """
        Determina si se debe verificar actualizaciones para una temporada.
        Para la temporada actual, solo verificar los lunes por la mañana.
        Para temporadas anteriores, nunca verificar.
        
        Args:
            season: Temporada a verificar (por defecto la actual)
            
        Returns:
            True si se debe verificar actualizaciones
        """
        target_season = season or self.current_season
        current_season = "2024-25"
        
        # Para temporadas anteriores, nunca verificar
        if target_season != current_season:
            logger.info(f"No se verifican actualizaciones para temporada anterior: {target_season}")
            return False
        
        # Para temporada actual, verificar solo los lunes por la mañana
        now = datetime.now()
        is_monday = now.weekday() == 0  # 0 = Lunes
        is_morning = now.hour < 12  # Antes de mediodía
        
        # Si hay forzado manual (desde UI), siempre verificar
        last_manual_check = self.last_update.get(f"{target_season}_manual", None)
        is_manual_check = False
        
        if last_manual_check:
            # Si ha pasado menos de 5 minutos desde la última verificación manual
            time_since_manual = datetime.now() - last_manual_check
            is_manual_check = time_since_manual.total_seconds() < 300  # 5 minutos
        
        if is_monday and is_morning:
            # Verificar si ya se comprobó hoy
            last_update = self.last_update.get(target_season)
            if last_update and last_update.date() == now.date():
                logger.info(f"Ya se verificaron actualizaciones hoy para {target_season}")
                return False
            
            logger.info(f"Verificando actualizaciones para {target_season} (lunes por la mañana)")
            return True
        elif is_manual_check:
            logger.info(f"Verificando actualizaciones para {target_season} (solicitud manual)")
            return True
        else:
            logger.info(f"No es momento de verificar actualizaciones automáticas para {target_season}")
            return False
        
    def export_data(self, format: str = 'csv', level: str = 'processed', season: Optional[str] = None) -> Optional[str]:
        """
        Exporta datos en diferentes formatos.
        
        Args:
            format: 'csv', 'json', 'excel'
            level: 'raw', 'processed'
            season: Temporada específica (opcional)
            
        Returns:
            Path del archivo exportado o None si hay error
        """
        try:
            # Usar temporada especificada o actual
            target_season = season or self.current_season
            
            # Seleccionar datos a exportar
            if target_season in self.data_cache:
                cache_data = self.data_cache[target_season]
                if level == 'raw' and cache_data['raw_data'] is not None:
                    data = cache_data['raw_data']
                elif level == 'processed' and cache_data['processed_data'] is not None:
                    data = cache_data['processed_data']
                else:
                    logger.error(f"No {level} data available for season {target_season}")
                    return None
            else:
                # Datos actuales
                if level == 'raw' and self.raw_data is not None:
                    data = self.raw_data
                elif level == 'processed' and self.processed_data is not None:
                    data = self.processed_data
                else:
                    logger.error(f"No {level} data available")
                    return None
            
            # Generar nombre de archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hong_kong_{level}_{target_season}_{timestamp}"
            
            # Crear directorio si no existe
            import os
            export_dir = "data/exports"
            os.makedirs(export_dir, exist_ok=True)
            
            # Exportar según formato
            if format == 'csv':
                filepath = f"{export_dir}/{filename}.csv"
                data.to_csv(filepath, index=False)
            elif format == 'json':
                filepath = f"{export_dir}/{filename}.json"
                data.to_json(filepath, orient='records', indent=2)
            elif format == 'excel':
                filepath = f"{export_dir}/{filename}.xlsx"
                data.to_excel(filepath, index=False)
            else:
                logger.error(f"Unsupported format: {format}")
                return None
            
            logger.info(f"Data exported to: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error exporting data: {str(e)}")
            return None
    
    def get_performance_summary(self, level: str, identifier: Optional[str] = None, **filters) -> Dict:
        """
        Obtiene un resumen de performance para dashboard con filtros aplicados.
        
        Args:
            level: 'league', 'team', o 'player'
            identifier: team_name para 'team', player_name para 'player'
            **filters: Filtros adicionales (position_filter, age_range)
            
        Returns:
            Diccionario con métricas clave para dashboard
        """
        if not self._check_data_availability():
            return {"error": "No data available"}
        
        try:
            # Extraer filtros
            position_filter = filters.get('position_filter')
            age_range = filters.get('age_range')
            
            if level == 'league':
                if self.aggregator is None:
                    if not isinstance(self.processed_data, pd.DataFrame):
                        return {"error": "No processed data available"}
                    self.aggregator = HongKongStatsAggregator(self.processed_data)
                stats = self.aggregator.get_league_statistics(position_filter, age_range)
                return {
                    'title': f'Liga de Hong Kong - {self.current_season}',
                    'overview': stats['overview'],
                    'top_scorers': stats['top_performers']['top_scorers'][:10] if 'top_performers' in stats else [],
                    'top_assisters': stats['top_performers']['top_assisters'][:10] if 'top_performers' in stats else [],
                    'position_breakdown': stats['position_analysis'] if 'position_analysis' in stats else {}
                }
            
            elif level == 'team' and identifier:
                if self.aggregator is None:
                    if not isinstance(self.processed_data, pd.DataFrame):
                        return {"error": "No processed data available"}
                    self.aggregator = HongKongStatsAggregator(self.processed_data)
                stats = self.aggregator.get_team_statistics(identifier, position_filter, age_range)
                return {
                    'title': f'{identifier} - {self.current_season}',
                    'overview': stats['overview'],
                    'top_players': stats['top_players'] if 'top_players' in stats else {},
                    'squad_analysis': stats['squad_analysis'] if 'squad_analysis' in stats else {}
                }
            
            elif level == 'player' and identifier:
                if self.aggregator is None:
                    if not isinstance(self.processed_data, pd.DataFrame):
                        return {"error": "No processed data available"}
                    self.aggregator = HongKongStatsAggregator(self.processed_data)
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
        """Verifica si hay datos disponibles para la temporada actual."""
        if self.processed_data is None or self.aggregator is None:
            logger.warning(f"Data not available for season {self.current_season}. Run refresh_data() first")
            return False
        return True
    
    def clear_all_cache(self):
        """Limpia todos los caches."""
        try:
            # Limpiar cache del extractor
            self.extractor.clear_cache()
            
            # Limpiar cache interno de temporadas
            self.data_cache.clear()
            self.last_update.clear()
            
            # Limpiar datos actuales
            self.raw_data = None
            self.processed_data = None
            self.aggregator = None
            
            logger.info("All caches cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
    
    def clear_season_cache(self, season: str):
        """
        Limpia el cache de una temporada específica.
        
        Args:
            season: Temporada a limpiar
        """
        try:
            if season in self.data_cache:
                del self.data_cache[season]
            
            if season in self.last_update:
                del self.last_update[season]
            
            # Si es la temporada actual, limpiar también los datos actuales
            if season == self.current_season:
                self.raw_data = None
                self.processed_data = None
                self.aggregator = None
            
            logger.info(f"Cache cleared for season {season}")
        except Exception as e:
            logger.error(f"Error clearing cache for season {season}: {str(e)}")
    
    def start_background_preload(self):
        """Inicia la pre-carga de temporadas en background."""
        def background_preload():
            available_seasons = self.get_available_seasons()
            # Excluir la temporada actual que ya está cargada
            seasons_to_load = [s for s in available_seasons if s != self.current_season]
            
            logger.info(f"🔄 Iniciando pre-carga en background de {len(seasons_to_load)} temporadas...")
            
            for i, season in enumerate(seasons_to_load, 1):
                try:
                    # NUEVO: Verificar si ya existe en caché y tiene datos
                    cached_file = self.extractor._get_cached_file_path(season)
                    timestamp_file = Path(self.extractor.cache_dir) / "update_timestamps.json"
                    timestamp_exists = False
                    
                    # Verificar si existe en timestamps guardados
                    if timestamp_file.exists():
                        try:
                            with open(timestamp_file, 'r') as f:
                                timestamps = json.load(f)
                                timestamp_exists = season in timestamps
                        except:
                            pass
                    
                    # Si el archivo CSV existe y hay un timestamp guardado, saltarlo
                    if cached_file.exists() and timestamp_exists:
                        logger.info(f"✅ Background: {season} ya está en caché, saltando...")
                        
                        # Añadir esta temporada a data_cache si no está
                        if season not in self.data_cache:
                            try:
                                # Cargar datos de caché directamente
                                raw_data = pd.read_csv(cached_file)
                                processed_data = self.processor.process_season_data(raw_data, season)
                                aggregator = HongKongStatsAggregator(processed_data)
                                
                                self.data_cache[season] = {
                                    'raw_data': raw_data,
                                    'processed_data': processed_data,
                                    'aggregator': aggregator,
                                    'last_update': datetime.now()  # Timestamp solo para caché interno
                                }
                                logger.info(f"✅ Background: {season} cargada desde caché existente")
                            except Exception as e:
                                logger.warning(f"⚠️ Error cargando {season} desde caché: {e}")
                        
                        continue
                    
                    # Si no está en caché, cargar normalmente
                    logger.info(f"📥 Cargando en background: {season} ({i}/{len(seasons_to_load)})")
                    success = self.refresh_data(season)
                    if success:
                        logger.info(f"✅ Background: {season} cargada exitosamente")
                    else:
                        logger.warning(f"⚠️ Background: Error cargando {season}")
                except Exception as e:
                    logger.warning(f"❌ Background: Error cargando {season}: {e}")
            
            logger.info(f"🎉 Pre-carga en background completada. {len(self.data_cache)} temporadas disponibles.")
        
        # Iniciar en un hilo separado
        thread = threading.Thread(target=background_preload, daemon=True, name="SeasonPreloader")
        thread.start()
        logger.info("🚀 Pre-carga en background iniciada...")
    
    def get_teams_summary(self) -> Dict:
        """
        Obtiene un resumen de todos los equipos de Hong Kong.
        
        Returns:
            Diccionario con información resumida de equipos
        """
        if not self._check_data_availability():
            return {"error": "No data available"}
        
        teams_info = {}
        available_teams = self.get_available_teams()
        
        if self.aggregator is None and isinstance(self.processed_data, pd.DataFrame):
            self.aggregator = HongKongStatsAggregator(self.processed_data)
            
        for team in available_teams:
            if self.aggregator is None:
                return {"error": "Aggregator not initialized"}
            team_stats = self.aggregator.get_team_statistics(team)
            if 'overview' in team_stats:
                overview = team_stats['overview']
                teams_info[team] = {
                    'players': overview.get('total_players', 0),
                    'goals': overview.get('total_goals', 0),
                    'assists': overview.get('total_assists', 0),
                    'avg_age': overview.get('avg_age', 0)
                }
        
        return {
            'season': self.current_season,
            'total_teams': len(available_teams),
            'teams': teams_info
        }