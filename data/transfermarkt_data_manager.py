"""
Gestor integrado de datos de lesiones desde Transfermarkt - VERSIÓN CORREGIDA.
Combina extracción, procesamiento y cache en una interfaz unificada.
"""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import json
from pathlib import Path

# Importar nuestros módulos
from data.extractors.transfermarkt_extractor import TransfermarktExtractor
from data.processors.transfermarkt_processor import TransfermarktProcessor
from data.aggregators.transfermarkt_aggregator import TransfermarktStatsAggregator

class TransfermarktDataManager:
    """
    Gestor integral para datos de lesiones de Transfermarkt - VERSIÓN CORREGIDA.
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
        self.aggregator = None  # Agregador similar a Performance
        self.last_update = None
        
        # Configurar logging
        self.logger = logging.getLogger(__name__)
        
        # Cache de datos procesados
        self.cache_dir = Path(cache_dir)
        self.processed_cache_file = self.cache_dir / "transfermarkt_processed.json"
        
        if auto_load:
            self.refresh_data()
    def should_update_data(self) -> bool:
        """
        Determina si los datos deben actualizarse basado en la programación (lunes por la mañana).
        
        Returns:
            True si se debe realizar una actualización
        """
        # Si no hay última actualización, siempre actualizar
        if self.last_update is None:
            self.logger.info("No hay actualización previa, actualizando datos...")
            return True
        
        # Obtener fecha y hora actual
        now = datetime.now()
        
        # Verificar si es lunes
        is_monday = now.weekday() == 0
        
        # Verificar si es por la mañana (antes de las 12:00)
        is_morning = now.hour < 12
        
        # Verificar si ya se actualizó este lunes
        last_update_date = self.last_update.date()
        is_different_day = last_update_date < now.date()
        
        # Actualizar solo si:
        # 1. Es lunes por la mañana
        # 2. No se ha actualizado hoy todavía
        should_update = is_monday and is_morning and is_different_day
        
        if should_update:
            self.logger.info("Es lunes por la mañana, programando actualización automática...")
        
        return should_update
    
    def refresh_data(self, force_scraping: bool = False) -> bool:
        """
        Refresca todos los datos (extrae, procesa y cachea).
        
        Args:
            force_scraping: Forzar scraping desde web ignorando cache
            
        Returns:
            True si la operación fue exitosa
        """
        try:
            self.logger.info("Verificando si se deben actualizar datos de lesiones...")
            
            # NUEVO: Solo actualizar si:
            # 1. Es forzado manualmente
            # 2. Es lunes por la mañana y no se ha actualizado hoy
            if not force_scraping and not self.should_update_data():
                # Verificar si tenemos datos procesados recientes
                if self._has_recent_processed_cache():
                    self.logger.info("Usando datos procesados desde cache (no es lunes o ya se actualizó hoy)")
                    return self._load_from_processed_cache()
            
            # 2. Extraer datos crudos
            self.logger.info("Extrayendo datos desde Transfermarkt...")
            self.raw_injuries = self.extractor.extract_all_injuries(force_refresh=force_scraping)
            
            if not self.raw_injuries:
                self.logger.error("No se pudieron extraer datos de lesiones")
                return False
            
            self.logger.info(f"Extraídas {len(self.raw_injuries)} lesiones crudas")
            
            # 3. Procesar datos
            self.logger.info("Procesando datos...")
            try:
                df_processed = self.processor.process_injuries_data(self.raw_injuries)
                
                if df_processed.empty:
                    self.logger.error("No se pudieron procesar los datos - DataFrame vacío")
                    return False
                
                self.logger.info(f"Procesadas {len(df_processed)} lesiones exitosamente")
                
                # Debug: mostrar columnas disponibles
                self.logger.debug(f"Columnas en DataFrame procesado: {list(df_processed.columns)}")
                
                # 4. Convertir a formato compatible con el dashboard
                self.logger.info("Convirtiendo a formato dashboard...")
                self.processed_injuries = self._convert_to_dashboard_format(df_processed)
                
                # Inicializar el agregador después de procesar los datos
                if self.processed_injuries:
                    self.aggregator = TransfermarktStatsAggregator(self.processed_injuries)

                if not self.processed_injuries:
                    self.logger.error("Error convirtiendo a formato dashboard")
                    return False
                
                self.logger.info(f"Convertidas {len(self.processed_injuries)} lesiones al formato dashboard")
                
                # 5. Guardar en cache procesado
                self._save_to_processed_cache()
                
                # 6. Actualizar timestamp
                self.last_update = datetime.now()
                
                self.logger.info("Actualización de datos completada exitosamente")
                return True
                
            except Exception as processing_error:
                self.logger.error(f"Error durante el procesamiento: {processing_error}")
                # Log de debug más detallado
                self.logger.debug(f"Tipo de error: {type(processing_error)}")
                if self.raw_injuries:
                    self.logger.debug(f"Muestra de datos crudos: {self.raw_injuries[0] if self.raw_injuries else 'Vacío'}")
                raise processing_error
            
        except Exception as e:
            self.logger.error(f"Error actualizando datos: {e}")
            self.logger.debug(f"Detalles del error: {type(e).__name__}: {str(e)}")
            import traceback
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            return False
    
    def get_injuries_data(self) -> List[Dict]:
        """
        Obtiene los datos de lesiones en formato compatible con el dashboard.
        
        Returns:
            Lista de diccionarios con datos de lesiones
        """
        if self.processed_injuries is None:
            self.logger.warning("No hay datos disponibles, intentando cargar desde cache...")
            if not self._load_from_processed_cache():
                self.logger.warning("No se pudo cargar desde cache, retornando lista vacía")
                return []
        
        return self.processed_injuries if self.processed_injuries is not None else []
    
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
            status: Estado de la lesión ('En tratamiento', 'Recuperado', 'Crónico')
            
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
        
        # Convertir a DataFrame para cálculos
        df = pd.DataFrame(injuries)
        
        # Calcular estadísticas
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
        
        Returns:
            Diccionario con información de actualizaciones
        """
        # Verificar cache del extractor
        cache_info = self.extractor.get_cache_info()
        
        # Determinar si necesita actualización
        needs_update = False
        message = "Datos actualizados"
        
        # Si no hay cache o es muy antiguo (más de 6 horas)
        if not cache_info['injuries_cache_exists']:
            needs_update = True
            message = "No hay datos en cache"
        elif cache_info['injuries_cache_modified']:
            cache_time = datetime.fromisoformat(cache_info['injuries_cache_modified'])
            if datetime.now() - cache_time > timedelta(hours=6):
                needs_update = True
                message = "Cache antiguo, actualizaciones disponibles"
        
        return {
            'needs_update': needs_update,
            'message': message,
            'cache_info': cache_info,
            'last_update': self.last_update.isoformat() if self.last_update else None
        }
    
    def clear_all_cache(self):
        """Limpia todos los caches."""
        self.extractor.clear_cache()
        
        if self.processed_cache_file.exists():
            self.processed_cache_file.unlink()
            self.logger.info("Cache de datos procesados eliminado")
        
        # Limpiar estado interno
        self.raw_injuries = None
        self.processed_injuries = None
        self.last_update = None
    
    def _convert_to_dashboard_format(self, df: pd.DataFrame) -> List[Dict]:
        """
        Convierte DataFrame procesado al formato esperado por el dashboard.
        VERSIÓN CORREGIDA - Maneja columnas faltantes sin errores.
        
        Args:
            df: DataFrame procesado
            
        Returns:
            Lista de diccionarios compatible con el dashboard
        """
        injuries = []
        
        for i, row in df.iterrows():
            injury = {}
            
            # Procesar cada campo con manejo de errores
            try:
                # ID único
                injury['id'] = str(i)
                
                # Información básica del jugador
                injury['player_name'] = str(row.get('player_name', 'Desconocido'))
                injury['team'] = str(row.get('team', 'Desconocido'))
                injury['position'] = str(row.get('position', 'Desconocida'))
                injury['age'] = int(row.get('age', 0)) if pd.notna(row.get('age')) else 0
                
                # Información de la lesión
                injury['injury_type'] = str(row.get('injury_type', 'Desconocida'))
                injury['body_part'] = str(row.get('body_part', 'Otros'))
                injury['severity'] = str(row.get('severity', 'Moderada'))
                injury['status'] = str(row.get('status', 'En tratamiento'))
                
                # Fechas (manejar diferentes tipos)
                injury_date = row.get('injury_date')
                if pd.notna(injury_date):
                    if hasattr(injury_date, 'strftime'):
                        injury['injury_date'] = injury_date.strftime('%Y-%m-%d')
                    else:
                        try:
                            injury['injury_date'] = pd.to_datetime(injury_date).strftime('%Y-%m-%d')
                        except:
                            injury['injury_date'] = None
                else:
                    injury['injury_date'] = None
                
                return_date = row.get('return_date')
                if pd.notna(return_date):
                    if hasattr(return_date, 'strftime'):
                        injury['return_date'] = return_date.strftime('%Y-%m-%d')
                    else:
                        try:
                            injury['return_date'] = pd.to_datetime(return_date).strftime('%Y-%m-%d')
                        except:
                            injury['return_date'] = None
                else:
                    injury['return_date'] = None
                
                # Datos numéricos
                injury['recovery_days'] = int(row.get('recovery_days', 0)) if pd.notna(row.get('recovery_days')) else 0
                injury['market_value'] = int(row.get('market_value', 0)) if pd.notna(row.get('market_value')) else 0
                
                # Matches missed - verificar si la columna existe
                if 'matches_missed' in df.columns:
                    injury['matches_missed'] = int(row.get('matches_missed', 0)) if pd.notna(row.get('matches_missed')) else 0
                else:
                    # Si no existe, calcular una estimación basada en días de recuperación
                    recovery_days = injury['recovery_days']
                    if recovery_days > 0:
                        # Estimación: 1 partido cada 7 días aproximadamente
                        injury['matches_missed'] = max(1, recovery_days // 7)
                    else:
                        injury['matches_missed'] = 0
                
                injuries.append(injury)
                
            except Exception as e:
                self.logger.warning(f"Error procesando lesión {i}: {e}")
                # Continuar con la siguiente lesión
                continue
        
        self.logger.info(f"Convertidas {len(injuries)} lesiones al formato dashboard")
        return injuries
    
    def _has_recent_processed_cache(self, max_age_hours: int = 4) -> bool:
        """Verifica si hay cache procesado reciente."""
        if not self.processed_cache_file.exists():
            return False
        
        try:
            with open(self.processed_cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                cache_time = datetime.fromisoformat(cache_data.get('timestamp', '2000-01-01'))
                return datetime.now() - cache_time < timedelta(hours=max_age_hours)
        except:
            return False
    
    def _load_from_processed_cache(self) -> bool:
        """Carga datos desde cache procesado."""
        try:
            with open(self.processed_cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                self.processed_injuries = cache_data['injuries']
                self.last_update = datetime.fromisoformat(cache_data['timestamp'])
                self.logger.info(f"Cargadas {len(self.processed_injuries)} lesiones desde cache procesado")
                return True
        except Exception as e:
            self.logger.warning(f"Error cargando cache procesado: {e}")
            return False
    
    def _save_to_processed_cache(self):
        """Guarda datos procesados en cache."""
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'total_injuries': len(self.processed_injuries) if self.processed_injuries is not None else 0,
                'injuries': self.processed_injuries
            }
            
            # Crear directorio si no existe
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.processed_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info("Datos procesados guardados en cache")
            
        except Exception as e:
            self.logger.warning(f"Error guardando cache procesado: {e}")
    
    def get_status_info(self) -> Dict:
        """Obtiene información del estado actual del gestor."""
        return {
            'raw_injuries_count': len(self.raw_injuries) if self.raw_injuries else 0,
            'processed_injuries_count': len(self.processed_injuries) if self.processed_injuries else 0,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'has_data': self.processed_injuries is not None,
            'cache_info': self.extractor.get_cache_info()
        }