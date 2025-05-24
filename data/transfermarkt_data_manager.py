"""
Gestor simplificado de datos de lesiones desde Transfermarkt.
Actualización automática solo los lunes por la mañana.
"""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import json
from pathlib import Path

# Importar componentes
from data.extractors.transfermarkt_extractor import TransfermarktExtractor
from data.processors.transfermarkt_processor import TransfermarktProcessor
from data.aggregators.transfermarkt_aggregator import TransfermarktStatsAggregator

# Configurar logging básico
logger = logging.getLogger(__name__)

class TransfermarktDataManager:
    """
    Gestor simplificado para datos de lesiones de Transfermarkt.
    Actualización automática solo los lunes por la mañana.
    """
    
    def __init__(self, cache_dir: str = "data/cache", auto_load: bool = False):
        """
        Inicializa el gestor de datos.
        
        Args:
            cache_dir: Directorio para cache de datos
            auto_load: Si debe cargar automáticamente al inicializar
        """
        self.extractor = TransfermarktExtractor(cache_dir)
        self.processor = TransfermarktProcessor()
        
        # Estado interno
        self.raw_injuries = None
        self.processed_injuries = None
        self.aggregator = None
        self.last_update = None
        
        # Cache simple
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
       
        
        # Cargar timestamp de última actualización
        self._load_last_update()
        
        if auto_load:
            self.refresh_data()
    
    def _save_manual_update_timestamp(self, update_time: datetime):
        """
        Guarda timestamp de actualización manual en update_timestamps.json.
        Mantiene el timestamp original y crea uno manual separado.
        
        Args:
            update_time: Tiempo de la actualización manual
        """
        timestamp_file = self.cache_dir / "update_timestamps.json"
        try:
            # PASO 1: Cargar timestamps existentes (incluyendo Hong Kong)
            existing_timestamps = {}
            if timestamp_file.exists():
                with open(timestamp_file, 'r', encoding='utf-8') as f:
                    existing_timestamps = json.load(f)
            
            # PASO 2: Crear timestamp manual separado
            existing_timestamps['transfermarkt_manual'] = update_time.isoformat()
            
            # PASO 3: Crear timestamp principal solo si no existe
            if 'transfermarkt' not in existing_timestamps:
                existing_timestamps['transfermarkt'] = update_time.isoformat()
                logger.info("Creando timestamp principal de transfermarkt")
            else:
                logger.info("Manteniendo timestamp principal de transfermarkt existente")
            
            # PASO 4: Guardar archivo completo (preservando Hong Kong)
            with open(timestamp_file, 'w', encoding='utf-8') as f:
                json.dump(existing_timestamps, f, indent=2)
                
            logger.info(f"Timestamp manual de Transfermarkt guardado (preservando otros sistemas)")
            
        except Exception as e:
            logger.warning(f"Error guardando timestamp manual de Transfermarkt: {e}")

    def _load_last_update(self):
        """Carga el timestamp de la última actualización desde update_timestamps.json."""
        timestamp_file = self.cache_dir / "update_timestamps.json"
        try:
            if timestamp_file.exists():
                with open(timestamp_file, 'r', encoding='utf-8') as f:
                    timestamps_data = json.load(f)
                    
                    # Buscar timestamp de transfermarkt
                    if 'transfermarkt' in timestamps_data:
                        self.last_update = datetime.fromisoformat(timestamps_data['transfermarkt'])
                        logger.info(f"Transfermarkt - Última actualización: {self.last_update}")
                    else:
                        logger.info("Transfermarkt - No hay timestamp previo")
            else:
                logger.info("Archivo update_timestamps.json no existe")
        except Exception as e:
            logger.warning(f"Error cargando timestamp de Transfermarkt: {e}")
            self.last_update = None

    def _save_last_update(self):
        """Guarda el timestamp de la última actualización en update_timestamps.json compartido."""
        timestamp_file = self.cache_dir / "update_timestamps.json"
        try:
            # PASO 1: Cargar timestamps existentes (incluyendo Hong Kong)
            existing_timestamps = {}
            if timestamp_file.exists():
                with open(timestamp_file, 'r', encoding='utf-8') as f:
                    existing_timestamps = json.load(f)
            
            # PASO 2: Actualizar solo el timestamp principal de transfermarkt
            if self.last_update:
                existing_timestamps['transfermarkt'] = self.last_update.isoformat()
                
                # PASO 3: Guardar archivo completo (preservando Hong Kong)
                with open(timestamp_file, 'w', encoding='utf-8') as f:
                    json.dump(existing_timestamps, f, indent=2)
                    
                logger.info(f"Transfermarkt timestamp guardado (preservando otros sistemas)")
            
        except Exception as e:
            logger.warning(f"Error guardando timestamp de Transfermarkt: {e}")
    
    def _should_update_data(self) -> bool:
        """
        Determina si los datos deben actualizarse.
        Solo los lunes por la mañana y si no se ha actualizado hoy.
        
        Returns:
            True si se debe realizar una actualización
        """
        # Si no hay última actualización, siempre actualizar
        if self.last_update is None:
            logger.info("No hay actualización previa, actualizando datos...")
            return True
        
        now = datetime.now()
        
        # Verificar si es lunes (0 = lunes)
        is_monday = now.weekday() == 0
        
        # Verificar si es por la mañana (antes de las 12:00)
        is_morning = now.hour < 12
        
        # Verificar si ya se actualizó hoy
        last_update_date = self.last_update.date()
        is_different_day = last_update_date < now.date()
        
        # Actualizar solo si es lunes por la mañana y no se ha actualizado hoy
        should_update = is_monday and is_morning and is_different_day
        
        if should_update:
            logger.info("Es lunes por la mañana, programando actualización automática...")
        else:
            logger.info("No es momento de actualización automática (solo lunes por la mañana)")
        
        return should_update
    
    def refresh_data(self, force_scraping: bool = False) -> bool:
        """
        Actualiza los datos (extrae, procesa y cachea).
        
        Args:
            force_scraping: Forzar scraping ignorando la lógica de lunes
            
        Returns:
            True si la operación fue exitosa
        """
        try:
            # Verificar si debe actualizar (excepto si es forzado)
            if not force_scraping and not self._should_update_data():
                # Intentar cargar desde cache del extractor
                if self._load_from_cache():
                    logger.info("Usando datos desde cache existente")
                    return True
                else:
                    logger.info("No hay cache válido, pero no es momento de actualizar")
                    return False
            
            logger.info("Actualizando datos de lesiones desde Transfermarkt...")
            
            # 1. Extraer datos
            self.raw_injuries = self.extractor.extract_all_injuries(force_refresh=force_scraping)
            
            if not self.raw_injuries:
                logger.warning("No se pudieron extraer datos de lesiones")
                return False
            
            # 2. Procesar datos
            df_processed = self.processor.process_injuries_data(self.raw_injuries)
            
            if df_processed.empty:
                logger.warning("No se pudieron procesar los datos")
                return False
            
            # 3. Convertir a formato dashboard
            self.processed_injuries = self._convert_to_dashboard_format(df_processed)
            
            if not self.processed_injuries:
                logger.warning("Error convirtiendo a formato dashboard")
                return False
            
            # 4. Inicializar agregador
            self.aggregator = TransfermarktStatsAggregator(self.processed_injuries)
            
            # 5. Actualizar timestamp solo si fue actualización real
            if force_scraping:
                # Actualización MANUAL - crear timestamp separado
                self._save_manual_update_timestamp(datetime.now())
                logger.info("Timestamp de actualización MANUAL guardado")
            elif self._should_update_data():
                # Actualización AUTOMÁTICA - timestamp regular
                self.last_update = datetime.now()
                self._save_last_update()
                logger.info("Timestamp de actualización AUTOMÁTICA guardado")
            
            logger.info(f"✅ Datos actualizados: {len(self.processed_injuries)} lesiones")
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando datos: {e}")
            # Intentar cargar desde cache como fallback
            return self._load_from_cache()
    
    def _load_from_cache(self) -> bool:
        """
        Intenta cargar datos desde el cache del extractor.
        
        Returns:
            True si se cargaron datos válidos desde cache
        """
        try:
            # Intentar usar el cache del extractor
            cache_info = self.extractor.get_cache_info()
            
            if cache_info.get('injuries_cache_exists', False):
                logger.info("Intentando cargar desde cache del extractor...")
                self.raw_injuries = self.extractor.extract_all_injuries(force_refresh=False)
                
                if self.raw_injuries:
                    # Procesar datos del cache
                    df_processed = self.processor.process_injuries_data(self.raw_injuries)
                    self.processed_injuries = self._convert_to_dashboard_format(df_processed)
                    
                    if self.processed_injuries:
                        self.aggregator = TransfermarktStatsAggregator(self.processed_injuries)
                        logger.info(f"✅ Datos cargados desde cache: {len(self.processed_injuries)} lesiones")
                        return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error cargando desde cache: {e}")
            return False
    
    def get_injuries_data(self) -> List[Dict]:
        """
        Obtiene los datos de lesiones en formato compatible con el dashboard.
        
        Returns:
            Lista de diccionarios con datos de lesiones
        """
        if self.processed_injuries is None:
            logger.info("No hay datos disponibles, intentando cargar...")
            if not self.refresh_data():
                logger.warning("No se pudieron cargar datos")
                return []
        
        return self.processed_injuries or []
    
    def get_teams_with_injuries(self) -> List[str]:
        """Obtiene lista de equipos que tienen lesiones."""
        injuries = self.get_injuries_data()
        if not injuries:
            return []
        
        teams = list(set(injury['team'] for injury in injuries))
        return sorted(teams)
    
    def get_injuries_by_team(self, team_name: str) -> List[Dict]:
        """
        Obtiene lesiones filtradas por equipo.
        
        Args:
            team_name: Nombre del equipo
            
        Returns:
            Lista de lesiones del equipo
        """
        injuries = self.get_injuries_data()
        return [injury for injury in injuries if injury['team'] == team_name]
    
    def get_injuries_by_status(self, status: str = 'En tratamiento') -> List[Dict]:
        """
        Obtiene lesiones filtradas por estado.
        
        Args:
            status: Estado de la lesión
            
        Returns:
            Lista de lesiones con el estado especificado
        """
        injuries = self.get_injuries_data()
        return [injury for injury in injuries if injury['status'] == status]
    
    def get_statistics_summary(self) -> Dict:
        """
        Obtiene resumen estadístico de las lesiones.
        
        Returns:
            Diccionario con estadísticas resumidas
        """
        injuries = self.get_injuries_data()
        
        if not injuries:
            return {
                'total_injuries': 0,
                'active_injuries': 0,
                'avg_recovery_days': 0,
                'most_common_injury': 'N/A',
                'most_affected_part': 'N/A'
            }
        
        # Calcular estadísticas básicas
        df = pd.DataFrame(injuries)
        
        stats = {
            'total_injuries': len(injuries),
            'active_injuries': len(df[df['status'] == 'En tratamiento']),
            'recovered_injuries': len(df[df['status'] == 'Recuperado']),
            'chronic_injuries': len(df[df['status'] == 'Crónico']),
            'avg_recovery_days': float(df['recovery_days'].mean()) if 'recovery_days' in df.columns else 0,
            'most_common_injury': df['injury_type'].mode().iloc[0] if len(df) > 0 and 'injury_type' in df.columns else 'N/A',
            'most_affected_part': df['body_part'].mode().iloc[0] if len(df) > 0 and 'body_part' in df.columns else 'N/A',
            'teams_with_injuries': df['team'].nunique() if 'team' in df.columns else 0,
            'last_update': self.last_update.isoformat() if self.last_update else None
        }
        
        return stats
    
    def check_for_updates(self) -> Dict:
        """
        Verifica si hay actualizaciones disponibles.
        Versión de producción.
        
        Returns:
            Diccionario con información de actualizaciones
        """
        # Verificar si hay actualización manual reciente (últimos 5 minutos)
        if self.last_update:
            time_since_update = datetime.now() - self.last_update
            
            # Si la última actualización fue hace menos de 5 minutos, considerar actualizado
            if time_since_update.total_seconds() < 300:  # 5 minutos
                logger.info(f"Transfermarkt actualización manual reciente ({time_since_update.total_seconds():.0f}s)")
                return {
                    'needs_update': False,
                    'message': "Datos actualizados recientemente (manual)",
                    'last_update': self.last_update.isoformat(),
                    'next_auto_update': "Próximo lunes antes de las 12:00"
                }
        
        # Verificar si debe actualizar según la lógica de lunes por la mañana
        needs_update = self._should_update_data()
        
        if needs_update:
            message = "Actualización programada disponible (lunes por la mañana)"
        else:
            message = "Próxima actualización automática: próximo lunes por la mañana"
        
        return {
            'needs_update': needs_update,
            'message': message,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'next_auto_update': "Próximo lunes antes de las 12:00"
        }
    
    def clear_all_cache(self):
        """Limpia todos los caches."""
        self.extractor.clear_cache()
        
        # Limpiar solo el timestamp de transfermarkt del archivo compartido
        timestamp_file = self.cache_dir / "update_timestamps.json"
        try:
            if timestamp_file.exists():
                with open(timestamp_file, 'r', encoding='utf-8') as f:
                    timestamps_data = json.load(f)
                
                # Eliminar solo el timestamp de transfermarkt
                if 'transfermarkt' in timestamps_data:
                    del timestamps_data['transfermarkt']
                    
                    # Guardar archivo actualizado
                    with open(timestamp_file, 'w', encoding='utf-8') as f:
                        json.dump(timestamps_data, f, indent=2)
                        
                    logger.info("Timestamp de Transfermarkt eliminado de update_timestamps.json")
        except Exception as e:
            logger.warning(f"Error eliminando timestamp de Transfermarkt: {e}")
        
        self.raw_injuries = None
        self.processed_injuries = None
        self.aggregator = None
        self.last_update = None
        logger.info("Cache de Transfermarkt eliminado")
    
    def _convert_to_dashboard_format(self, df: pd.DataFrame) -> List[Dict]:
        """
        Convierte DataFrame procesado al formato esperado por el dashboard.
        Versión simplificada.
        
        Args:
            df: DataFrame procesado
            
        Returns:
            Lista de diccionarios compatible con el dashboard
        """
        injuries = []
        
        for i, row in df.iterrows():
            try:
                injury = {
                    'id': str(i),
                    'player_name': str(row.get('player_name', 'Desconocido')),
                    'team': str(row.get('team', 'Desconocido')),
                    'position': str(row.get('position', 'Desconocida')),
                    'age': int(row.get('age', 0)) if pd.notna(row.get('age')) else 0,
                    'injury_type': str(row.get('injury_type', 'Desconocida')),
                    'body_part': str(row.get('body_part', 'Otros')),
                    'severity': str(row.get('severity', 'Moderada')),
                    'status': str(row.get('status', 'En tratamiento')),
                    'recovery_days': int(row.get('recovery_days', 0)) if pd.notna(row.get('recovery_days')) else 0,
                    'market_value': int(row.get('market_value', 0)) if pd.notna(row.get('market_value')) else 0,
                    'matches_missed': int(row.get('matches_missed', 0)) if pd.notna(row.get('matches_missed')) else 0
                }
                
                # Procesar fechas de forma simple
                injury_date = row.get('injury_date')
                if pd.notna(injury_date):
                    try:
                        if hasattr(injury_date, 'strftime'):
                            injury['injury_date'] = injury_date.strftime('%Y-%m-%d')
                        else:
                            injury['injury_date'] = pd.to_datetime(injury_date).strftime('%Y-%m-%d')
                    except:
                        injury['injury_date'] = None
                else:
                    injury['injury_date'] = None
                
                return_date = row.get('return_date')
                if pd.notna(return_date):
                    try:
                        if hasattr(return_date, 'strftime'):
                            injury['return_date'] = return_date.strftime('%Y-%m-%d')
                        else:
                            injury['return_date'] = pd.to_datetime(return_date).strftime('%Y-%m-%d')
                    except:
                        injury['return_date'] = None
                else:
                    injury['return_date'] = None
                
                injuries.append(injury)
                
            except Exception as e:
                logger.debug(f"Error procesando lesión {i}: {e}")
                continue
        
        logger.info(f"Convertidas {len(injuries)} lesiones al formato dashboard")
        return injuries
    
    def get_status_info(self) -> Dict:
        """Obtiene información del estado actual del gestor."""
        return {
            'raw_injuries_count': len(self.raw_injuries) if self.raw_injuries else 0,
            'processed_injuries_count': len(self.processed_injuries) if self.processed_injuries else 0,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'has_data': self.processed_injuries is not None,
            'cache_info': self.extractor.get_cache_info(),
            'next_auto_update': "Próximo lunes antes de las 12:00"
        }