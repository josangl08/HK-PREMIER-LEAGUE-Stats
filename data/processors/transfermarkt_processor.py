"""
Procesador de datos de lesiones extraídos de Transfermarkt - VERSIÓN FINAL CORREGIDA.
Limpia, normaliza y transforma los datos para uso en el dashboard.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import re
from pathlib import Path

class TransfermarktProcessor:
    """
    Procesador de datos de lesiones de Transfermarkt - VERSIÓN FINAL CORREGIDA.
    Maneja mejor el parsing de fechas, tipos de datos y validación.
    """
    
    def __init__(self):
        """Inicializa el procesador."""
        self.logger = logging.getLogger(__name__)
        
        # Mapeos de normalización mejorados
        self.position_mapping = {
            'defensa central': 'Defensor',
            'lateral derecho': 'Defensor', 
            'lateral izquierdo': 'Defensor',
            'defensor': 'Defensor',
            'pivote': 'Mediocampista',
            'mediocentro': 'Mediocampista',
            'mediocampista': 'Mediocampista',
            'mediocentro ofensivo': 'Mediocampista',
            'mediocentro defensivo': 'Mediocampista',
            'medio': 'Mediocampista',
            'extremo izquierdo': 'Extremo',
            'extremo derecho': 'Extremo',
            'extremo': 'Extremo',
            'delantero centro': 'Delantero',
            'delantero': 'Delantero',
            'segundo delantero': 'Delantero',
            'portero': 'Portero',
            'arquero': 'Portero'
        }
        
        self.injury_severity = {
            'contusión': 'Leve',
            'esguince': 'Leve',
            'sobrecarga': 'Leve',
            'molestias': 'Leve',
            'lesión muscular': 'Moderada',
            'desgarro': 'Moderada',
            'tendinitis': 'Moderada',
            'lesión de rodilla': 'Moderada',
            'lesión en la rodilla': 'Moderada',
            'fractura': 'Grave',
            'rotura de ligamento': 'Grave',
            'rotura del ligamento': 'Grave',
            'rotura fibrilar': 'Grave',
            'cirugía': 'Grave'
        }
        
        # Mapeo de partes del cuerpo mejorado
        self.body_part_mapping = {
            'rodilla': 'Rodilla',
            'tobillo': 'Tobillo',
            'muslo': 'Isquiotibiales',
            'gemelo': 'Gemelo',
            'pantorrilla': 'Gemelo',
            'isquiotibiales': 'Isquiotibiales',
            'cuádriceps': 'Cuádriceps',
            'pie': 'Pie',
            'cadera': 'Cadera',
            'espalda': 'Espalda baja',
            'columna': 'Espalda baja',
            'hombro': 'Hombro',
            'muñeca': 'Muñeca',
            'codo': 'Codo',
            'cabeza': 'Cabeza',
            'cara': 'Cabeza',
            'costilla': 'Costillas',
            'tórax': 'Pecho',
            'abductor': 'Cadera',
            'aductor': 'Cadera',
            'ingle': 'Cadera',
            'tendón': 'Tendones',
            'ligamento': 'Ligamentos',
            'menisco': 'Rodilla'
        }
    
    def process_injuries_data(self, raw_injuries: List[Dict]) -> pd.DataFrame:
        """
        Procesa los datos crudos de lesiones y los convierte en DataFrame limpio.
        VERSIÓN FINAL CORREGIDA - Mejor manejo de fechas y tipos de datos.
        
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
        
        # Análisis inicial de los datos para debugging
        self.logger.info(f"Columnas disponibles: {list(df.columns)}")
        
        # Limpieza inicial
        df = self._initial_cleaning(df)
        
        # Procesamiento específico de campos
        df = self._process_dates_improved(df)
        df = self._process_injury_types(df)
        df = self._process_positions(df)
        df = self._calculate_derived_fields(df)
        df = self._add_status_field(df)
        
        # Validación final mejorada
        df = self._final_validation_improved(df)
        
        self.logger.info(f"Procesamiento completado: {len(df)} lesiones válidas")
        
        return df
    
    def _initial_cleaning(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpieza inicial del DataFrame."""
        
        # Eliminar filas con jugadores desconocidos
        initial_count = len(df)
        
        # Limpiar nombres de jugadores
        if 'player_name' in df.columns:
            df = df[df['player_name'].notna() & 
            (df['player_name'] != 'Desconocido') &
            (df['player_name'].str.strip() != '')]
            df['player_name'] = df['player_name'].str.strip()
        
        if len(df) < initial_count:
            self.logger.info(f"Eliminadas {initial_count - len(df)} lesiones sin jugador válido")
        
        # Limpiar nombres de equipos
        if 'team' in df.columns:
            df['team'] = df['team'].str.strip()
        
        # Resetear índice
        df = df.reset_index(drop=True)
        
        return df
    
    def _process_dates_improved(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Procesa las fechas de lesiones - VERSIÓN FINAL MEJORADA.
        Maneja diferentes formatos de fecha y casos especiales.
        """
        self.logger.info("Procesando fechas de lesiones...")
        
        # Verificar que las columnas existan
        date_columns = ['date_from', 'date_until']
        available_columns = [col for col in date_columns if col in df.columns]
        
        if not available_columns:
            self.logger.warning("No se encontraron columnas de fecha")
            # Crear fechas por defecto
            df['injury_date'] = pd.NaT
            df['return_date'] = pd.NaT
            df['recovery_days'] = 0
            return df
        
        # Procesar fecha de inicio (injury_date)
        if 'date_from' in df.columns:
            df['injury_date'] = df['date_from'].apply(self._parse_date_robust)
            # Log del parsing de fechas
            valid_dates = df['injury_date'].notna().sum()
            self.logger.info(f"Fechas de inicio válidas: {valid_dates}/{len(df)}")
        else:
            df['injury_date'] = pd.NaT
        
        # Procesar fecha de retorno (return_date)
        if 'date_until' in df.columns:
            df['return_date'] = df['date_until'].apply(self._parse_date_robust)
            valid_returns = df['return_date'].notna().sum()
            self.logger.info(f"Fechas de retorno válidas: {valid_returns}/{len(df)}")
        else:
            df['return_date'] = pd.NaT
        
        # Calcular días de recuperación
        df['recovery_days'] = df['days'].copy() if 'days' in df.columns else 0
        df['recovery_days'] = pd.to_numeric(df['recovery_days'], errors='coerce').fillna(0)
        
        # Para lesiones con fechas pero sin días, calcular
        missing_days_mask = (
            (df['recovery_days'] == 0) & 
            df['injury_date'].notna() & 
            df['return_date'].notna()
        )
        
        if missing_days_mask.any():
            calculated_days = (df.loc[missing_days_mask, 'return_date'] - 
                df.loc[missing_days_mask, 'injury_date']).dt.days
            df.loc[missing_days_mask, 'recovery_days'] = calculated_days.fillna(0)
            self.logger.info(f"Días calculados para {missing_days_mask.sum()} lesiones")
        
        # Para lesiones sin fecha de retorno, estimar basado en días
        missing_return_mask = (
            df['return_date'].isna() & 
            df['injury_date'].notna() & 
            (df['recovery_days'] > 0)
        )
        
        if missing_return_mask.any():
            df.loc[missing_return_mask, 'return_date'] = (
                df.loc[missing_return_mask, 'injury_date'] + 
                pd.to_timedelta(df.loc[missing_return_mask, 'recovery_days'], unit='D')
            )
            self.logger.info(f"Fechas de retorno estimadas para {missing_return_mask.sum()} lesiones")
        
        # Para lesiones sin fechas, asignar fecha reciente por defecto
        no_date_mask = df['injury_date'].isna()
        if no_date_mask.any():
            # Asignar fechas en el último mes
            recent_date = datetime.now() - timedelta(days=30)
            df.loc[no_date_mask, 'injury_date'] = pd.Timestamp(recent_date)
            self.logger.info(f"Fechas por defecto asignadas a {no_date_mask.sum()} lesiones")
        
        # Limpiar columnas auxiliares
        columns_to_drop = ['date_from', 'date_until', 'days']
        for col in columns_to_drop:
            if col in df.columns:
                df = df.drop(col, axis=1)
        
        return df
    
    def _parse_date_robust(self, date_str) -> Optional[pd.Timestamp]:
        """
        Parsea fechas de forma robusta manejando diferentes formatos.
        
        Args:
            date_str: String de fecha en diferentes formatos
            
        Returns:
            Timestamp de pandas o None si no se puede parsear
        """
        if pd.isna(date_str) or not str(date_str).strip():
            return None
        
        date_str = str(date_str).strip()
        
        # Lista de formatos a probar
        formats_to_try = [
            '%d/%m/%Y',      # 15/03/2024
            '%d-%m-%Y',      # 15-03-2024
            '%Y-%m-%d',      # 2024-03-15
            '%d.%m.%Y',      # 15.03.2024
            '%d/%m/%y',      # 15/03/24
            '%d-%m-%y',      # 15-03-24
            '%Y/%m/%d',      # 2024/03/15
            '%m/%d/%Y',      # 03/15/2024 (formato americano)
        ]
        
        # Intentar cada formato
        for fmt in formats_to_try:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                # Validar que la fecha es razonable (últimos 5 años)
                if (datetime.now() - timedelta(days=5*365) <= parsed_date <= 
                    datetime.now() + timedelta(days=365)):
                    return pd.Timestamp(parsed_date)
            except ValueError:
                continue
        
        # Intentar parsing automático de pandas
        try:
            parsed_date = pd.to_datetime(date_str, dayfirst=True, errors='coerce')
            if not pd.isna(parsed_date):
                # Validar rango razonable
                if (datetime.now() - timedelta(days=5*365) <= parsed_date <= 
                    datetime.now() + timedelta(days=365)):
                    return parsed_date
        except:
            pass
        
        # Si nada funciona, intentar extraer números y crear fecha
        try:
            numbers = re.findall(r'\d+', date_str)
            if len(numbers) >= 3:
                # Asumir DD/MM/YYYY
                day, month, year = map(int, numbers[:3])
                
                # Ajustar año si es de 2 dígitos
                if year < 100:
                    year += 2000 if year < 50 else 1900
                
                # Validar rangos
                if 1 <= month <= 12 and 1 <= day <= 31 and 2000 <= year <= 2030:
                    parsed_date = datetime(year, month, day)
                    return pd.Timestamp(parsed_date)
        except:
            pass
        
        self.logger.debug(f"No se pudo parsear fecha: '{date_str}'")
        return None
    
    def _process_injury_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Procesa y normaliza los tipos de lesión."""
        
        # Limpiar tipos de lesión
        if 'injury_type' in df.columns:
            df['injury_type_clean'] = df['injury_type'].str.lower().str.strip()
            
            # Determinar severidad basada en el tipo
            df['severity'] = df['injury_type_clean'].apply(self._determine_severity)
            
            # Determinar parte del cuerpo afectada
            df['body_part'] = df['injury_type_clean'].apply(self._determine_body_part)
            
            # Mantener el tipo original también
            df['injury_type'] = df['injury_type'].str.strip()
        else:
            # Valores por defecto si no hay tipo de lesión
            df['injury_type'] = 'Desconocida'
            df['injury_type_clean'] = 'desconocida'
            df['severity'] = 'Moderada'
            df['body_part'] = 'Otros'
        
        return df
    
    def _process_positions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Procesa y normaliza las posiciones."""
        
        if 'position' in df.columns:
            # Limpiar posiciones
            df['position_clean'] = df['position'].str.lower().str.strip()
            
            # Mapear a grupos de posición
            df['position_group'] = df['position_clean'].apply(self._map_position_group)
        else:
            # Valores por defecto
            df['position'] = 'Desconocida'
            df['position_clean'] = 'desconocida'
            df['position_group'] = 'Otros'
        
        return df
    
    def _calculate_derived_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula campos derivados - VERSIÓN FINAL CON MATCHES_MISSED."""
        
        # Asegurar que recovery_days sea numérico
        if 'recovery_days' in df.columns:
            df['recovery_days'] = pd.to_numeric(df['recovery_days'], errors='coerce').fillna(0)
        else:
            df['recovery_days'] = 0
        
        # Calcular días desde la lesión - CORREGIDO
        current_date = pd.Timestamp.now()
        
        if 'injury_date' in df.columns:
            # Asegurar que injury_date sea datetime
            df['injury_date'] = pd.to_datetime(df['injury_date'], errors='coerce')
            
            # Calcular días desde la lesión (siempre positivo)
            df['days_since_injury'] = (pd.Series([current_date] * len(df)) - df['injury_date']).dt.days
            
            # Manejar valores NaN y negativos
            df['days_since_injury'] = df['days_since_injury'].fillna(0)
            df['days_since_injury'] = df['days_since_injury'].clip(lower=0)
        else:
            df['days_since_injury'] = 0
        
        # Calcular si la lesión está activa
        if 'return_date' in df.columns:
            # Asegurar que return_date sea datetime
            df['return_date'] = pd.to_datetime(df['return_date'], errors='coerce')
            
            df['is_active'] = (
                (df['return_date'].isna()) |  # Sin fecha de retorno
                (df['return_date'] > current_date)  # Fecha de retorno en el futuro
            )
        else:
            df['is_active'] = True  # Asumir activa si no hay fecha
        
        # Calcular matches_missed basado en recovery_days
        # Estimación: promedio de 1 partido cada 7 días
        df['matches_missed'] = (df['recovery_days'] / 7).round().astype(int)
        df['matches_missed'] = df['matches_missed'].clip(lower=0)  # No negativos
        
        # Para lesiones activas sin recovery_days definidos, estimar basado en días transcurridos
        active_no_recovery = (df['is_active'] == True) & (df['recovery_days'] == 0)
        if active_no_recovery.any():
            df.loc[active_no_recovery, 'matches_missed'] = (df.loc[active_no_recovery, 'days_since_injury'] / 7).round().astype(int)
        
        # Calcular edad de la lesión en categorías
        df['injury_age_category'] = df['days_since_injury'].apply(self._categorize_injury_age)
        
        return df
    
    def _add_status_field(self, df: pd.DataFrame) -> pd.DataFrame:
        """Añade campo de estado de la lesión - VERSIÓN FINAL CORREGIDA."""
        
        current_date = pd.Timestamp.now()
        
        def determine_status(row):
            # Verificar si existe la columna return_date
            if 'return_date' not in row.index or pd.isna(row['return_date']):
                # Sin fecha de retorno definida
                days_since = row.get('days_since_injury', 0)
                if pd.isna(days_since):
                    days_since = 0
                    
                if days_since > 365:
                    return 'Crónico'
                else:
                    return 'En tratamiento'
            else:
                # Convertir return_date a Timestamp si no lo es
                return_date = row['return_date']
                if not isinstance(return_date, pd.Timestamp):
                    try:
                        return_date = pd.to_datetime(return_date)
                    except:
                        return 'En tratamiento'
                
                if pd.isna(return_date):
                    return 'En tratamiento'
                elif return_date > current_date:
                    # Fecha de retorno en el futuro
                    return 'En tratamiento'
                else:
                    # Fecha de retorno en el pasado
                    return 'Recuperado'
        
        df['status'] = df.apply(determine_status, axis=1)
        
        return df
    
    def _final_validation_improved(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validación final de los datos - VERSIÓN MEJORADA.
        Menos restrictiva para conservar más datos.
        """
        initial_count = len(df)
        
        # Asegurar que los campos numéricos sean válidos
        numeric_fields = ['age', 'recovery_days', 'market_value', 'days_since_injury']
        for field in numeric_fields:
            if field in df.columns:
                df[field] = pd.to_numeric(df[field], errors='coerce').fillna(0)
        
        # Solo eliminar lesiones con datos claramente inválidos
        # Mantener lesiones incluso sin fechas perfectas
        valid_mask = (
            df['player_name'].notna() & 
            (df['player_name'] != 'Desconocido') &
            (df['player_name'].str.strip() != '')
        )
        
        df = df[valid_mask]
        
        if len(df) < initial_count:
            eliminated = initial_count - len(df)
            self.logger.info(f"Eliminadas {eliminated} lesiones por datos inválidos")
        
        # Ordenar por fecha de lesión (más recientes primero)
        if 'injury_date' in df.columns and df['injury_date'].notna().any():
            df = df.sort_values('injury_date', ascending=False, na_position='last')
        
        df = df.reset_index(drop=True)
        
        # Validar rangos solo para campos críticos
        if 'age' in df.columns:
            df = df[df['age'].between(0, 50) | (df['age'] == 0)]  # Permitir edad 0 (desconocida)
        
        if 'recovery_days' in df.columns:
            df = df[df['recovery_days'].between(0, 1000)]  # Rango más amplio
        
        final_count = len(df)
        self.logger.info(f"Validación final: {final_count} lesiones conservadas de {initial_count} iniciales")
        
        return df
    
    # Métodos auxiliares (sin cambios significativos)
    
    def _determine_severity(self, injury_type: str) -> str:
        """Determina la severidad basada en el tipo de lesión."""
        if not injury_type:
            return 'Moderada'
        
        injury_lower = str(injury_type).lower()
        
        for keyword, severity in self.injury_severity.items():
            if keyword in injury_lower:
                return severity
        
        # Por defecto
        return 'Moderada'
    
    def _determine_body_part(self, injury_type: str) -> str:
        """Determina la parte del cuerpo afectada basada en el tipo de lesión."""
        if not injury_type:
            return 'Otros'
        
        injury_lower = str(injury_type).lower()
        
        for keyword, body_part in self.body_part_mapping.items():
            if keyword in injury_lower:
                return body_part
        
        # Si no encuentra coincidencia específica
        return 'Otros'
    
    def _map_position_group(self, position: str) -> str:
        """Mapea la posición a un grupo de posición."""
        if not position:
            return 'Otros'
        
        position_lower = str(position).lower()
        
        for keyword, group in self.position_mapping.items():
            if keyword in position_lower:
                return group
        
        # Si no encuentra coincidencia
        return 'Otros'
    
    def _categorize_injury_age(self, days_since_injury: float) -> str:
        """Categoriza la edad de la lesión."""
        if pd.isna(days_since_injury) or days_since_injury < 0:
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
        
        # Análisis de fechas
        date_analysis = {}
        if 'injury_date' in df.columns:
            valid_injury_dates = df['injury_date'].notna().sum()
            date_analysis['valid_injury_dates'] = int(valid_injury_dates)
            date_analysis['invalid_injury_dates'] = len(df) - int(valid_injury_dates)
            
            if valid_injury_dates > 0:
                date_analysis['date_range'] = {
                    'earliest': df['injury_date'].min().strftime('%Y-%m-%d'),
                    'latest': df['injury_date'].max().strftime('%Y-%m-%d')
                }
        
        if 'return_date' in df.columns:
            valid_return_dates = df['return_date'].notna().sum()
            date_analysis['valid_return_dates'] = int(valid_return_dates)
        
        summary = {
            'total_injuries': len(df),
            'active_injuries': len(df[df['status'] == 'En tratamiento']) if 'status' in df.columns else 0,
            'recovered_injuries': len(df[df['status'] == 'Recuperado']) if 'status' in df.columns else 0,
            'chronic_injuries': len(df[df['status'] == 'Crónico']) if 'status' in df.columns else 0,
            'teams_with_injuries': df['team'].nunique() if 'team' in df.columns else 0,
            'avg_recovery_days': float(df['recovery_days'].mean()) if 'recovery_days' in df.columns else 0,
            'most_common_injury': df['injury_type'].mode().iloc[0] if 'injury_type' in df.columns and len(df) > 0 else 'N/A',
            'most_affected_body_part': df['body_part'].mode().iloc[0] if 'body_part' in df.columns and len(df) > 0 else 'N/A',
            'severity_distribution': df['severity'].value_counts().to_dict() if 'severity' in df.columns else {},
            'position_distribution': df['position_group'].value_counts().to_dict() if 'position_group' in df.columns else {},
            'status_distribution': df['status'].value_counts().to_dict() if 'status' in df.columns else {},
            'date_analysis': date_analysis
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
            # Crear directorio si no existe
            path = Path(export_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            if format == 'csv':
                df.to_csv(str(path), index=False, encoding='utf-8')
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