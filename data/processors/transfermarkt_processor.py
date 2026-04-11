# ABOUTME: Process data from Transfermarkt (injuries and match history).
# ABOUTME: Normalizes dates, injury types, and handles data validation for SQL storage.

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import re
from pathlib import Path

class TransfermarktProcessor:
    """
    Procesador de datos de lesiones de Transfermarkt.
    Maneja el parsing de fechas, tipos de datos y validación.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        self.severity_levels = {
            'Leve': ['contusión', 'esguince', 'sobrecarga', 'molestias', 'minor', 'knock', 'bruise', 'strain'],
            'Moderada': ['lesión muscular', 'desgarro', 'tendinitis', 'lesión de rodilla', 'muscle', 'torn', 'ligament', 'hamstring'],
            'Grave': ['fractura', 'rotura de ligamento', 'cirugía', 'fracture', 'rupture', 'surgery', 'cruciate', 'acl']
        }
        
        self.body_regions = {
            'Cabeza': ['cabeza', 'cara', 'conmoción', 'head', 'face', 'concussion', 'nose', 'nariz', 'eye'],
            'Tronco': ['espalda', 'costilla', 'back', 'rib', 'chest', 'pecho', 'abdominal'],
            'Cadera': ['cadera', 'pubis', 'ingle', 'hip', 'groin', 'adductor', 'abductor'],
            'Rodilla': ['rodilla', 'menisco', 'cruzado', 'knee', 'meniscus', 'cruciate', 'acl'],
            'Muslo': ['isquiotibiales', 'muslo', 'cuádriceps', 'hamstring', 'thigh', 'quadriceps'],
            'Pierna/Pie': ['peroné', 'tibia', 'gemelo', 'tobillo', 'pie', 'fibula', 'tibia', 'calf', 'ankle', 'foot', 'shin'],
            'Brazo': ['hombro', 'codo', 'muñeca', 'shoulder', 'elbow', 'wrist', 'arm'],
            'General': ['músculo', 'tendón', 'ligamento', 'muscle', 'tendon', 'ligament']
        }

    def process_injuries_data(self, raw_injuries: List[Dict]) -> pd.DataFrame:
        if not raw_injuries: return pd.DataFrame()
        
        df = pd.DataFrame(raw_injuries)
        
        # Limpieza inicial
        if 'player_name' in df.columns:
            df = df[df['player_name'].notna() & (df['player_name'] != '')]
        
        # Procesar fechas
        df = self._process_dates_improved(df)
        
        # Procesar tipos y severidad
        df['injury_type'] = df['injury_type'].fillna('Desconocida').str.strip()
        df['severity'] = df['injury_type'].apply(self._determine_severity)
        df['body_part'] = df['injury_type'].apply(self._determine_body_part)
        
        # Normalizar missed_matches y recovery_days
        df['missed_matches'] = pd.to_numeric(df.get('missed_matches', 0), errors='coerce').fillna(0).astype(int)
        df['recovery_days'] = pd.to_numeric(df.get('days_out', 0), errors='coerce').fillna(0).astype(int)
        
        # Campo status
        current_date = datetime.now()
        df['status'] = df['return_date'].apply(lambda x: 'Recuperado' if pd.notna(x) and x < current_date else 'En tratamiento')
        
        return df.reset_index(drop=True)

    def _process_dates_improved(self, df: pd.DataFrame) -> pd.DataFrame:
        df['injury_date'] = pd.to_datetime(df['date_from'].apply(self._parse_date_robust) if 'date_from' in df.columns else pd.NaT)
        df['return_date'] = pd.to_datetime(df['date_until'].apply(self._parse_date_robust) if 'date_until' in df.columns else pd.NaT)
        
        # Inicializar days_out si no existe
        if 'days_out' not in df.columns:
            df['days_out'] = 0

        # Cálculo seguro de días de recuperación
        mask = df['injury_date'].notna() & df['return_date'].notna()
        if mask.any():
            # Realizar la resta solo en las filas válidas y convertir a días
            diff = df.loc[mask, 'return_date'] - df.loc[mask, 'injury_date']
            df.loc[mask, 'days_out'] = diff.dt.days
        
        # Asegurar que days_out es entero
        df['days_out'] = pd.to_numeric(df['days_out'], errors='coerce').fillna(0).astype(int)
        
        return df

    def _parse_date_robust(self, date_str) -> Optional[datetime]:
        if pd.isna(date_str) or not str(date_str).strip(): return None
        
        s = str(date_str).strip()
        # Regex para DD/MM/YYYY
        match = re.search(r'(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})', s)
        if match:
            try:
                d, m, y = map(int, match.groups())
                if y < 100: y += 2000 if y < 50 else 1900
                return datetime(y, m, d)
            except: pass
            
        return None

    def _determine_severity(self, txt: str) -> str:
        txt = txt.lower()
        for sev, keywords in self.severity_levels.items():
            if any(k in txt for k in keywords): return sev
        return 'Moderada'

    def _determine_body_part(self, txt: str) -> str:
        txt = txt.lower()
        for part, keywords in self.body_regions.items():
            if any(k in txt for k in keywords): return part
        return 'Otros'

    def process_match_history(self, raw_history: List[Dict], player_id: str) -> pd.DataFrame:
        """Procesa historial de partidos para SQL."""
        if not raw_history: return pd.DataFrame()
        df = pd.DataFrame(raw_history)
        df['player_id'] = player_id
        df['date'] = df['date'].apply(self._parse_date_robust)
        return df
