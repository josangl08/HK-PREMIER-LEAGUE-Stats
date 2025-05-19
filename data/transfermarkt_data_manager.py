"""
Gestor integrado de datos de lesiones desde Transfermarkt.
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

class TransfermarktDataManager:
    """
    Gestor integral para datos de lesiones de Transfermarkt.
    """
    
    def __init__(self, cache_dir: str = "data/cache", auto_load: bool = False):
        """
        Inicializa el gestor de datos.
        
        Args:
            cache_dir: Directorio para cache de datos
            auto_load: Si debe cargar datos automáticamente al inicializar
        """
        self.extractor = TransfermarktExtractor(cache_dir)
        self.processor = TransfermarktProcessor()
        
        # Estado interno
        self.raw_injuries = None
        self.processed_injuries = None
        self.last_update = None
        
        # Configurar logging
        self.logger = logging.getLogger(__name__)
        
        # Cache de datos procesados
        self.cache_dir = Path(cache_dir)
        self.processed_cache_file = self.cache_dir / "transfermarkt_processed.json"
        
        if auto_load:
            self.refresh_data()
    
    def refresh_data(self, force_scraping: bool = False) -> bool:
        """
        Refresca todos los datos (extrae, procesa y cachea).
        
        Args:
            force_scraping: Forzar scraping desde web ignorando cache
            
        Returns:
            True si la operación fue exitosa
        """
        try:
            self.logger.info("Iniciando actualización de datos de lesiones...")
            
            # 1. Verificar cache procesado primero
            if not force_scraping and self._has_recent_processed_cache():
                self.logger.info("Usando datos procesados desde cache")
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
            df_processed = self.processor.process_injuries_data(self.raw_injuries)
            
            if df_processed.empty:
                self.logger.error("No se pudieron procesar los datos")
                return False
            
            # Convertir a formato compatible con el dashboard existente
            self.processed_injuries = self._convert_to_dashboard_format(df_processed)
            
            self.logger.info(f"Procesadas {len(self.processed_injuries)} lesiones")
            
            # 4. Guardar en cache procesado
            self._save_to_processed_cache()
            
            # 5. Actualizar timestamp
            self.last_update = datetime.now()
            
            self.logger.info("Actualización de datos completada exitosamente")
            return True
            
        except Exception as e:
            self.logger.error(f"Error actualizando datos: {e}")
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
            'avg_recovery_days': df['recovery_days'].mean(),
            'most_common_injury': df['injury_type'].mode().iloc[0] if len(df) > 0 else 'N/A',
            'most_affected_part': df['body_part'].mode().iloc[0] if len(df) > 0 else 'N/A',
            'teams_with_injuries': df['team'].nunique(),
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
        
        Args:
            df: DataFrame procesado
            
        Returns:
            Lista de diccionarios compatible con el dashboard
        """
        injuries = []
        
        for _, row in df.iterrows():
            injury = {
                'id': str(row.name),  # Usar índice como ID
                'player_name': row['player_name'],
                'team': row['team'],
                'injury_type': row['injury_type'],
                'body_part': row['body_part'],
                'severity': row['severity'],
                'injury_date': row['injury_date'].strftime('%Y-%m-%d') if pd.notna(row['injury_date']) else None,
                'return_date': row['return_date'].strftime('%Y-%m-%d') if pd.notna(row['return_date']) else None,
                'recovery_days': int(row['recovery_days']) if pd.notna(row['recovery_days']) else 0,
                'status': row['status'],
                'position': row['position'],
                'age': int(row['age']) if pd.notna(row['age']) else 0,
                'matches_missed': int(row['matches_missed']) if pd.notna(row['matches_missed']) else 0,
                'market_value': int(row['market_value']) if pd.notna(row['market_value']) else 0
            }
            injuries.append(injury)
        
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