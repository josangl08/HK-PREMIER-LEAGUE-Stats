"""
Gestor simplificado de datos de Hong Kong.
Versión limpia y optimizada que mantiene funcionalidad esencial.
"""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import json
from pathlib import Path

# Importar componentes
from data.extractors.hong_kong_extractor import HongKongDataExtractor
from data.processors.hong_kong_processor import HongKongDataProcessor
from data.aggregators.hong_kong_aggregator import HongKongStatsAggregator
from data.managers.fixture_manager import get_fixture_manager
from utils.cache_manager import (
    AdvancedCacheManager,
    invalidate_cache_for_season
)

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

        # Estado interno - AUTO-DETECTAR temporada actual
        self.current_season = self._get_current_season_with_fallback()
        self.raw_data: Optional[pd.DataFrame] = None
        self.processed_data: Optional[pd.DataFrame] = None

        # Advanced cache with TTL (replaces simple dict)
        self.advanced_cache = AdvancedCacheManager()
        self.data_cache: Dict = {}  # Legacy cache for file-based storage
        self.last_update: Dict = {}

        # Cache TTL configuration (in seconds)
        self.cache_ttl = {
            'season_data': 3600,      # 1 hour for season data
            'league_stats': 1800,     # 30 min for league stats
            'team_stats': 1800,       # 30 min for team stats
            'player_stats': 1800,     # 30 min for player stats
            'chart_data': 900,        # 15 min for chart data
            'tactical_data': 1800,    # 30 min for tactical analysis
        }

        # Cargar timestamps PRIMERO
        self._load_update_timestamps()

        # Descarga inicial: verificar y descargar todas las temporadas
        # disponibles si cache está vacío
        self._ensure_all_seasons_downloaded()

        if auto_load:
            self._load_current_season()

    def _get_current_season_with_fallback(self) -> str:
        """
        Obtiene la temporada actual usando auto-detección con fallback.

        Si la temporada actual detectada no tiene datos disponibles
        (pre-temporada), usa la temporada anterior.

        Returns:
            str: Temporada a usar (actual o fallback)
        """
        season, is_fallback, message = (
            self.extractor._get_season_with_fallback()
        )

        if is_fallback:
            logger.warning(
                f"Pre-temporada detectada - usando fallback: {message}"
            )
        else:
            logger.info(f"Temporada actual detectada: {season}")

        return season

    def _ensure_all_seasons_downloaded(self):
        """
        Descarga inicial de todas las temporadas disponibles si no existen
        en cache.

        Estrategia:
        - Temporadas finalizadas: Descarga única (nunca se actualizarán)
        - Temporada actual: Se descarga y verificará updates en cada refresh
        """
        available_seasons = self.extractor.get_available_seasons()
        current_season = self.extractor._detect_current_season()
        finished_seasons = self.extractor._get_finished_seasons(current_season)

        logger.info(
            f"Verificando disponibilidad de {len(available_seasons)} "
            f"temporadas..."
        )

        seasons_to_download = []

        # Identificar qué temporadas faltan en cache
        for season in available_seasons:
            cached_file = self.extractor._get_cached_file_path(season)

            if not cached_file.exists():
                seasons_to_download.append(season)

        if not seasons_to_download:
            logger.info(
                f"Todas las temporadas ya están en cache "
                f"({len(available_seasons)} temporadas)"
            )
            return

        # Descargar temporadas faltantes
        logger.info(
            f"Descargando {len(seasons_to_download)} temporadas faltantes: "
            f"{', '.join(seasons_to_download)}"
        )

        for season in seasons_to_download:
            status = "ACTUAL" if season == current_season else "FINALIZADA"
            logger.info(f"Descargando {season} ({status})...")

            try:
                # Descargar sin forzar update (respeta check_for_updates)
                data = self.extractor.download_season_data(
                    season, force_update=False
                )

                if data is not None:
                    logger.info(
                        f"✓ {season} descargada exitosamente "
                        f"({len(data)} registros)"
                    )
                    # Actualizar timestamp de descarga
                    self.last_update[season] = datetime.now()
                else:
                    logger.warning(f"⚠️ No se pudo descargar {season}")

            except Exception as e:
                logger.error(f"Error descargando {season}: {e}")

        # Guardar todos los timestamps de una vez
        if seasons_to_download:
            self._save_update_timestamps()

        logger.info(
            f"Descarga inicial completada. "
            f"Temporadas finalizadas: {len(finished_seasons)}, "
            f"Temporada actual: {current_season}"
        )

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
        Refresca datos para una temporada específica, centralizando la lógica de actualización.
        """
        try:
            target_season = season or self.current_season
            
            # 1. VERIFICACIÓN TEMPRANA: Si los datos ya están en memoria, no hacer nada.
            if not force_download and target_season == self.current_season and self._check_data_availability():
                logger.debug(f"Datos para {target_season} ya en memoria.")
                return True

            logger.info(f"Iniciando refresco de datos para la temporada: {target_season}")

            # 2. CENTRALIZAR LÓGICA DE ACTUALIZACIÓN
            needs_update, message = self.extractor.check_for_updates(target_season)
            logger.info(f"Verificación de actualizaciones para {target_season}: {message}")

            # Determinar si se debe forzar la descarga
            should_force_download = force_download or needs_update
            
            # Si no se requiere descarga, intentar cargar desde el cache
            if not should_force_download:
                if self._load_from_cache(target_season):
                    logger.info(f"Datos para {target_season} cargados desde cache.")
                    return True
            
            # 3. EXTRAER DATOS (descargar si es necesario)
            raw_data = self.extractor.download_season_data(target_season, force_update=should_force_download)
            if raw_data is None:
                logger.error(f"No se pudieron extraer los datos para {target_season}.")
                return self._load_from_cache(target_season) # Fallback al cache

            # 4. PROCESAR Y AGREGAR DATOS
            processed_data = self.processor.process_season_data(raw_data, target_season)
            aggregator = HongKongStatsAggregator(processed_data.copy())
            
            # 5. ACTUALIZAR ESTADO INTERNO
            self.current_season = target_season
            self.raw_data = raw_data
            self.processed_data = processed_data
            self.aggregator = aggregator
            self._add_to_cache(target_season, raw_data, processed_data, aggregator)

            # 6. GESTIONAR TIMESTAMPS SOLO SI HUBO CAMBIOS
            if should_force_download:
                current_time = datetime.now()
                self.last_update[target_season] = current_time
                if force_download:  # Solicitud manual
                    self.last_update[f"{target_season}_manual"] = current_time
                self._save_update_timestamps()
                logger.info(f"Timestamps actualizados para {target_season}.")

            # 7. INVALIDATE CACHE for this season (new data loaded)
            invalidated = invalidate_cache_for_season(target_season)
            logger.info(
                f"Cache invalidated for {target_season}: "
                f"{invalidated} entries"
            )

            # 8. BUILD PLAYER INDEX (cross-season ID resolution)
            try:
                from utils.player_index import get_player_index
                get_player_index().build()
            except Exception as e:
                logger.warning(f"Player index build failed (non-critical): {e}")

            logger.info(
                f"Refresco de datos para {target_season} "
                f"completado exitosamente."
            )
            return True

        except Exception as e:
            logger.error(f"Error crítico refrescando datos para {target_season}: {e}", exc_info=True)
            return False
    
    def get_league_overview(
        self,
        position_filter: Optional[str] = None,
        age_range: Optional[List[int]] = None
    ) -> Dict:
        """
        Obtiene overview de la liga con filtros aplicados.

        Uses advanced caching with TTL for performance optimization.
        """
        if not self._check_data_availability():
            return {"error": "No hay datos disponibles"}

        # Verificación explícita para Pylance
        if self.aggregator is None:
            return {"error": "Aggregator no inicializado"}

        # Generate cache key
        cache_key = (
            f"league_stats_{self.current_season}_"
            f"{position_filter}_{age_range}"
        )

        # Try to get from cache
        cached_result = self.advanced_cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit for league overview")
            return cached_result

        try:
            # Compute result
            result = self.aggregator.get_league_statistics(
                position_filter,
                age_range
            )

            # Store in cache with TTL
            self.advanced_cache.set(
                cache_key,
                result,
                self.cache_ttl['league_stats']
            )

            return result
        except Exception as e:
            logger.error(f"Error obteniendo overview de liga: {str(e)}")
            return {"error": str(e)}
    
    def get_team_overview(
        self,
        team_name: str,
        position_filter: Optional[str] = None,
        age_range: Optional[List[int]] = None
    ) -> Dict:
        """
        Obtiene overview de un equipo con filtros aplicados.

        Uses advanced caching with TTL for performance optimization.
        """
        if not self._check_data_availability():
            return {"error": "No hay datos disponibles"}

        # Verificación explícita para Pylance
        if self.aggregator is None:
            return {"error": "Aggregator no inicializado"}

        # Generate cache key
        cache_key = (
            f"team_stats_{self.current_season}_{team_name}_"
            f"{position_filter}_{age_range}"
        )

        # Try to get from cache
        cached_result = self.advanced_cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit for team overview: {team_name}")
            return cached_result

        try:
            # Compute result
            result = self.aggregator.get_team_statistics(
                team_name,
                position_filter,
                age_range
            )

            # Store in cache with TTL
            self.advanced_cache.set(
                cache_key,
                result,
                self.cache_ttl['team_stats']
            )

            return result
        except Exception as e:
            logger.error(f"Error obteniendo overview de equipo: {str(e)}")
            return {"error": str(e)}
    
    def get_player_overview(
        self,
        player_name: str,
        team_name: Optional[str] = None
    ) -> Dict:
        """
        Obtiene overview de un jugador.

        Uses advanced caching with TTL for performance optimization.
        """
        if not self._check_data_availability():
            return {"error": "No hay datos disponibles"}

        # Verificación explícita para Pylance
        if self.aggregator is None:
            return {"error": "Aggregator no inicializado"}

        # Generate cache key
        cache_key = (
            f"player_stats_{self.current_season}_{player_name}_"
            f"{team_name}"
        )

        # Try to get from cache
        cached_result = self.advanced_cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit for player overview: {player_name}")
            return cached_result

        try:
            # Compute result
            result = self.aggregator.get_player_statistics(
                player_name,
                team_name
            )

            # Store in cache with TTL
            self.advanced_cache.set(
                cache_key,
                result,
                self.cache_ttl['player_stats']
            )

            return result
        except Exception as e:
            logger.error(f"Error obteniendo overview de jugador: {str(e)}")
            return {"error": str(e)}
    
    def get_chart_data(
        self,
        level: str,
        identifier: Optional[str] = None
    ) -> Dict:
        """
        Obtiene datos formateados para gráficos.

        Uses advanced caching with shorter TTL for chart data.
        """
        if not self._check_data_availability():
            return {"error": "No hay datos disponibles"}

        # Verificación explícita para Pylance
        if self.aggregator is None:
            return {"error": "Aggregator no inicializado"}

        # Generate cache key
        cache_key = (
            f"chart_data_{self.current_season}_{level}_{identifier}"
        )

        # Try to get from cache
        cached_result = self.advanced_cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit for chart data: {level}/{identifier}")
            return cached_result

        try:
            # Compute result
            result = self.aggregator.get_comparative_data_for_charts(
                level,
                identifier
            )

            # Store in cache with shorter TTL (charts update more frequently)
            self.advanced_cache.set(
                cache_key,
                result,
                self.cache_ttl['chart_data']
            )

            return result
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
        """Verifica si hay datos disponibles en memoria."""
        if self.processed_data is None or self.aggregator is None:
            logger.info(f"Buscando datos para temporada {self.current_season}...")
            return False
        return True
    
    
    def clear_all_cache(self):
        """Limpia todos los caches (file-based y advanced)."""
        try:
            # Clear file-based cache
            self.extractor.clear_cache()
            self.data_cache.clear()
            self.last_update.clear()

            # Clear advanced cache
            self.advanced_cache.clear()

            # Clear data in memory
            self.raw_data = None
            self.processed_data = None
            self.aggregator = None

            logger.info("Todos los caches eliminados (file + advanced)")
        except Exception as e:
            logger.error(f"Error limpiando cache: {str(e)}")

    def get_cache_stats(self) -> Dict:
        """
        Obtiene estadísticas del cache avanzado.

        Returns:
            Dictionary con estadísticas de cache
        """
        stats = self.advanced_cache.get_stats()

        # Add cache size breakdown
        stats['cache_breakdown'] = {
            'total_keys': len(self.advanced_cache.get_all_keys()),
            'league_stats': len([
                k for k in self.advanced_cache.get_all_keys()
                if 'league_stats' in k
            ]),
            'team_stats': len([
                k for k in self.advanced_cache.get_all_keys()
                if 'team_stats' in k
            ]),
            'player_stats': len([
                k for k in self.advanced_cache.get_all_keys()
                if 'player_stats' in k
            ]),
            'chart_data': len([
                k for k in self.advanced_cache.get_all_keys()
                if 'chart_data' in k
            ])
        }

        return stats

    def cleanup_expired_cache(self) -> int:
        """
        Limpia entradas de cache expiradas.

        Returns:
            Número de entradas eliminadas
        """
        return self.advanced_cache.cleanup_expired()

    def get_next_fixture(self, team: str) -> Optional[dict]:
        """
        Returns the soonest upcoming HKFA fixture for the given team (English name).
        Delegates to FixtureManager singleton. Returns None if no fixture found.
        """
        return get_fixture_manager().get_next_fixture(team)
