"""
Procesador de datos de lesiones extraídos de Transfermarkt.
Limpia, normaliza y transforma los datos para uso en el dashboard.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import re

class TransfermarktProcessor:
    """
    Procesador de datos de lesiones de Transfermarkt.
    """
    
    def __init__(self):
        """Inicializa el procesador."""
        self.logger = logging.getLogger(__name__)
        
        # Mapeos de normalización
        self.position_mapping = {
            'defensa central': 'Defensor',
            'lateral derecho': 'Defensor',
            'lateral izquierdo': 'Defensor',
            'pivote': 'Mediocampista',
            'mediocentro': 'Mediocampista',
            'mediocentro ofensivo': 'Mediocampista',
            'mediocentro defensivo': 'Mediocampista',
            'extremo izquierdo': 'Extremo',
            'extremo derecho': 'Extremo',
            'delantero centro': 'Delantero',
            'segundo delantero': 'Delantero',
            'portero': 'Portero'
        }
        
        self.injury_severity = {
            'contusión': 'Leve',
            'esguince': 'Leve',
            'sobrecarga': 'Leve',
            'lesión muscular': 'Moderada',
            'desgarro': 'Moderada',
            'tendinitis': 'Moderada',
            'lesión de rodilla': 'Moderada',
            'fractura': 'Grave',
            'rotura de ligamento': 'Grave',
            'rotura del ligamento': 'Grave',
            'rotura fibrilar': 'Grave'
        }
        
        # Mapeo de partes del cuerpo
        self.body_part_mapping = {
            'rodilla': 'Rodilla',
            'tobillo': 'Tobillo',
            'muslo': 'Isquiotibiales',
            'gemelo': 'Gemelo',
            'isquiotibiales': 'Isquiotibiales',
            'cuádriceps': 'Cuádriceps',
            'pie': 'Pie',
            'cadera': 'Cadera',
            'espalda': 'Espalda baja',
            'hombro': 'Hombro',
            'muñeca': 'Muñeca',
            'cabeza': 'Cabeza',
            'costilla': 'Costillas',
            'abductor': 'Cadera',
            'aductor': 'Cadera'
        }
    
    def process_injuries_data(self, raw_injuries: List[Dict]) -> pd.DataFrame:
        """
        Procesa los datos crudos de lesiones y los convierte en DataFrame limpio.
        
        Args:
            raw_injuries: Lista de diccionarios con datos crudos de lesiones
            
        Returns:
            DataFrame procesado con lesiones
        """
        if not raw_injuries:
            self.logger.warning("No hay datos de lesiones para procesar")
            return pd.DataFrame()
        
        self.logger.info(f"Procesando {len(raw_injuries)} lesiones...")
        
        # Convertir a DataFrame
        df = pd.DataFrame(raw_injuries)
        
        # Limpieza inicial
        df = self._initial_cleaning(df)
        
        # Procesamiento específico de campos
        df = self._process_dates(df)
        df = self._process_injury_types(df)
        df = self._process_positions(df)
        df = self._calculate_derived_fields(df)
        df = self._add_status_field(df)
        
        # Validación final
        df = self._final_validation(df)
        
        self.logger.info(f"Procesamiento completado: {len(df)} lesiones válidas")
        
        return df
    
    def _initial_cleaning(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpieza inicial del DataFrame."""
        
        # Eliminar filas con jugadores desconocidos
        initial_count = len(df)
        df = df[df['player_name'].notna() & (df['player_name'] != 'Desconocido')]
        
        if len(df) < initial_count:
            self.logger.info(f"Eliminadas {initial_count - len(df)} lesiones con jugadores desconocidos")
        
        # Limpiar nombres de jugadores
        df['player_name'] = df['player_name'].str.strip()
        
        # Limpiar nombres de equipos
        df['team'] = df['team'].str.strip()
        
        # Resetear índice
        df = df.reset_index(drop=True)
        
        return df
    
    def _process_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Procesa las fechas de lesiones."""
        
        # Convertir fechas
        df['injury_date'] = pd.to_datetime(df['date_from'], errors='coerce')
        df['expected_return_date'] = pd.to_datetime(df['date_until'], errors='coerce')
        
        # Calcular fecha de retorno actual si no existe
        df['return_date'] = df['expected_return_date'].copy()
        
        # Para lesiones sin fecha de retorno, estimar basado en días
        missing_return = df['return_date'].isna() & df['days'].notna() & (df['days'] > 0)
        if missing_return.any():
            df.loc[missing_return, 'return_date'] = (
                df.loc[missing_return, 'injury_date'] + 
                pd.to_timedelta(df.loc[missing_return, 'days'], unit='D')
            )
        
        # Calcular días de recuperación reales si no existe
        df['recovery_days'] = df['days'].copy()
        
        # Para lesiones con fechas pero sin días, calcular
        missing_days = df['recovery_days'].isna() & df['injury_date'].notna() & df['return_date'].notna()
        if missing_days.any():
            df.loc[missing_days, 'recovery_days'] = (
                df.loc[missing_days, 'return_date'] - df.loc[missing_days, 'injury_date']
            ).dt.days
        
        # Limpiar columnas auxiliares
        df = df.drop(['date_from', 'date_until', 'days'], axis=1)
        
        return df
    
    def _process_injury_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Procesa y normaliza los tipos de lesión."""
        
        # Limpiar tipos de lesión
        df['injury_type_clean'] = df['injury_type'].str.lower().str.strip()
        
        # Determinar severidad basada en el tipo
        df['severity'] = df['injury_type_clean'].apply(self._determine_severity)
        
        # Determinar parte del cuerpo afectada
        df['body_part'] = df['injury_type_clean'].apply(self._determine_body_part)
        
        # Mantener el tipo original también
        df['injury_type'] = df['injury_type'].str.strip()
        
        return df
    
    def _process_positions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Procesa y normaliza las posiciones."""
        
        # Limpiar posiciones
        df['position_clean'] = df['position'].str.lower().str.strip()
        
        # Mapear a grupos de posición
        df['position_group'] = df['position_clean'].apply(self._map_position_group)
        
        return df
    
    def _calculate_derived_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula campos derivados."""
        
        # Asegurar que recovery_days sea numérico
        df['recovery_days'] = pd.to_numeric(df['recovery_days'], errors='coerce').fillna(0)
        
        # Calcular días desde la lesión
        current_date = pd.Timestamp.now()
        df['days_since_injury'] = (current_date - pd.to_datetime(df['injury_date'])).dt.days
        df['days_since_injury'] = df['days_since_injury'].fillna(0)
        
        # Calcular si la lesión está activa
        df['is_active'] = (
            (df['return_date'].isna()) |  # Sin fecha de retorno
            (df['return_date'] > current_date)  # Fecha de retorno en el futuro
        )
        
        # Calcular edad de la lesión en categorías
        df['injury_age_category'] = df['days_since_injury'].apply(self._categorize_injury_age)
        
        return df
    
    def _add_status_field(self, df: pd.DataFrame) -> pd.DataFrame:
        """Añade campo de estado de la lesión."""
        
        current_date = datetime.now()
        
        def determine_status(row):
            if pd.isna(row['return_date']):
                # Sin fecha de retorno definida
                if row['days_since_injury'] > 365:
                    return 'Crónico'
                else:
                    return 'En tratamiento'
            elif row['return_date'] > current_date:
                # Fecha de retorno en el futuro
                return 'En tratamiento'
            else:
                # Fecha de retorno en el pasado
                return 'Recuperado'
        
        df['status'] = df.apply(determine_status, axis=1)
        
        return df
    
    def _final_validation(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validación final de los datos."""
        
        # Asegurar que los campos numéricos sean válidos
        numeric_fields = ['age', 'recovery_days', 'matches_missed', 'market_value', 'days_since_injury']
        for field in numeric_fields:
            if field in df.columns:
                df[field] = pd.to_numeric(df[field], errors='coerce').fillna(0)
        
        # Eliminar lesiones con fechas inválidas
        initial_count = len(df)
        df = df[df['injury_date'].notna()]
        
        if len(df) < initial_count:
            self.logger.info(f"Eliminadas {initial_count - len(df)} lesiones con fechas inválidas")
        
        # Ordenar por fecha de lesión (más recientes primero)
        df = df.sort_values('injury_date', ascending=False).reset_index(drop=True)
        
        # Validar rangos
        df = df[df['age'].between(15, 50)]  # Edad razonable
        df = df[df['recovery_days'].between(0, 500)]  # Días de recuperación razonables
        
        return df
    
    def _determine_severity(self, injury_type: str) -> str:
        """Determina la severidad basada en el tipo de lesión."""
        if not injury_type:
            return 'Leve'
        
        injury_lower = injury_type.lower()
        
        for keyword, severity in self.injury_severity.items():
            if keyword in injury_lower:
                return severity
        
        # Por defecto, si no se encuentra coincidencia
        return 'Moderada'
    
    def _determine_body_part(self, injury_type: str) -> str:
        """Determina la parte del cuerpo afectada basada en el tipo de lesión."""
        if not injury_type:
            return 'Desconocida'
        
        injury_lower = injury_type.lower()
        
        for keyword, body_part in self.body_part_mapping.items():
            if keyword in injury_lower:
                return body_part
        
        # Si no encuentra coincidencia específica
        return 'Otros'
    
    def _map_position_group(self, position: str) -> str:
        """Mapea la posición a un grupo de posición."""
        if not position:
            return 'Desconocida'
        
        position_lower = position.lower()
        
        for keyword, group in self.position_mapping.items():
            if keyword in position_lower:
                return group
        
        # Si no encuentra coincidencia
        return 'Otros'
    
    def _categorize_injury_age(self, days_since_injury: float) -> str:
        """Categoriza la edad de la lesión."""
        if pd.isna(days_since_injury):
            return 'Desconocida'
        
        if days_since_injury <= 7:
            return 'Reciente'
        elif days_since_injury <= 30:
            return 'Este mes'
        elif days_since_injury <= 90:
            return 'Últimos 3 meses'
        elif days_since_injury <= 365:
            return 'Este año'
        else:
            return 'Antigua'
    
    def get_processing_summary(self, df: pd.DataFrame) -> Dict:
        """Genera un resumen del procesamiento de datos."""
        
        if df.empty:
            return {'error': 'No hay datos para analizar'}
        
        summary = {
            'total_injuries': len(df),
            'active_injuries': len(df[df['status'] == 'En tratamiento']),
            'recovered_injuries': len(df[df['status'] == 'Recuperado']),
            'chronic_injuries': len(df[df['status'] == 'Crónico']),
            'teams_with_injuries': df['team'].nunique(),
            'avg_recovery_days': df['recovery_days'].mean(),
            'most_common_injury': df['injury_type'].mode().iloc[0] if len(df) > 0 else 'N/A',
            'most_affected_body_part': df['body_part'].mode().iloc[0] if len(df) > 0 else 'N/A',
            'severity_distribution': df['severity'].value_counts().to_dict(),
            'position_distribution': df['position_group'].value_counts().to_dict(),
            'date_range': {
                'earliest': df['injury_date'].min().strftime('%Y-%m-%d') if df['injury_date'].notna().any() else None,
                'latest': df['injury_date'].max().strftime('%Y-%m-%d') if df['injury_date'].notna().any() else None
            }
        }
        
        return summary
    
    def export_processed_data(self, df: pd.DataFrame, export_path: str, format: str = 'csv') -> bool:
        """
        Exporta los datos procesados.
        
        Args:
            df: DataFrame procesado
            export_path: Ruta de exportación
            format: Formato de exportación ('csv', 'json', 'excel')
            
        Returns:
            True si la exportación fue exitosa
        """
        try:
            if format == 'csv':
                df.to_csv(export_path, index=False, encoding='utf-8')
            elif format == 'json':
                df.to_json(export_path, orient='records', indent=2, date_format='iso')
            elif format == 'excel':
                df.to_excel(export_path, index=False)
            else:
                raise ValueError(f"Formato no soportado: {format}")
            
            self.logger.info(f"Datos exportados exitosamente a {export_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exportando datos: {e}")
            return False