import pandas as pd
import numpy as np
from typing import Dict, Any
import logging
import re

from data.processors.ml_preprocessor import MLPreprocessor

logger = logging.getLogger(__name__)

# Maps Wyscout/internal position abbreviations to human-readable full names.
POSITION_FULL_NAMES: Dict[str, str] = {
    'GK':   'Goalkeeper',
    'CB':   'Centre-Back',     'RCB':  'Right Centre-Back',  'LCB':  'Left Centre-Back',
    'RCB3': 'Right Centre-Back (3)',                          'LCB3': 'Left Centre-Back (3)',
    'RB':   'Right Back',      'LB':   'Left Back',
    'RWB':  'Right Wing-Back',                                'LWB':  'Left Wing-Back',
    'DM':   'Defensive Midfielder',                           'CM':   'Central Midfielder',
    'AM':   'Attacking Midfielder',                           'AMF':  'Attacking Midfielder',
    'RAMF': 'Right Attacking Midfielder',                     'LAMF': 'Left Attacking Midfielder',
    'RM':   'Right Midfielder',                               'LM':   'Left Midfielder',
    'RW':   'Right Winger',                                   'LW':   'Left Winger',
    'RWF':  'Right Wing-Forward',                             'LWF':  'Left Wing-Forward',
    'CF':   'Centre Forward',
    'ST':   'Striker',
    'SS':   'Second Striker',
}

class HongKongDataProcessor:
    """
    Procesador específico para datos de jugadores de la Liga de Hong Kong.
    """
    
    def __init__(self):
        # Grupos de posiciones para análisis
        self.position_groups = {
            'Goalkeeper': ['GK'],
            'Defender': ['CB', 'RCB', 'LCB', 'RCB3', 'LCB3', 'RB', 'LB', 'RWB', 'LWB'],
            'Midfielder': ['DM', 'CM', 'AM', 'RM', 'LM'],
            'Winger': ['RW', 'LW', 'RWF', 'LWF'],
            'Forward': ['CF', 'ST', 'SS']
        }
    
    def process_season_data(self, df: pd.DataFrame, season: str) -> pd.DataFrame:
        """
        Procesa datos de jugadores de una temporada.
        """
        if df.empty:
            logger.info("DataFrame vacío, no hay datos para procesar")
            return df
        
        logger.info(f"Procesando datos de jugadores {season}...")
        logger.info(f"Datos originales: {len(df)} jugadores, {len(df.columns)} columnas")
        
        # Hacer una copia para no modificar el original
        processed_df = df.copy()
        
        try:
            # 1. Limpieza básica
            processed_df = self._basic_cleaning(processed_df)
            
            # 2. Procesar jugadores
            processed_df = self._process_players(processed_df)
            
            # 3. Procesar equipos
            processed_df = self._process_teams(processed_df)
            
            # 4. Procesar posiciones
            processed_df = self._process_positions(processed_df)
            
            # 5. Procesar datos numéricos
            processed_df = self._process_numbers(processed_df)
            
            # 6. Agregar columnas calculadas
            processed_df = self._add_calculated_fields(processed_df, season)

            # 7. Preprocesamiento táctico para nuevas métricas
            processed_df = self._tactical_preprocessing(processed_df)

            # 8. Validación final
            processed_df = self._final_cleanup(processed_df)
            
            logger.info(f"Datos procesados: {len(processed_df)} jugadores, {len(processed_df.columns)} columnas")
            logger.info(f"Jugadores eliminados: {len(df) - len(processed_df)}")
            
            return processed_df
            
        except Exception as e:
            logger.error(f"Error procesando datos: {e}")
            # En caso de error, devolver al menos una versión básica
            return self._create_minimal_dataset(df, season)
    
    def _basic_cleaning(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpieza básica del DataFrame."""
        # Eliminar filas y columnas completamente vacías
        df = df.dropna(how='all')
        df = df.dropna(axis=1, how='all')
        
        # Resetear índice
        df = df.reset_index(drop=True)
        
        # Limpiar nombres de columnas manualmente
        new_columns = []
        for col in df.columns:
            clean_col = str(col).strip()
            new_columns.append(clean_col)
        df.columns = new_columns
        
        # Eliminar columnas duplicadas por nombre
        df = df.loc[:, ~df.columns.duplicated()]
        
        return df
    
    def _process_players(self, df: pd.DataFrame) -> pd.DataFrame:
        """Procesa información de jugadores."""
        if 'Player' not in df.columns:
            return df
        
        def clean_name(name):
            if pd.isna(name): return 'Unknown'
            n = str(name).strip()
            # Eliminar múltiples espacios y convertir a Title Case
            n = re.sub(r'\s+', ' ', n)
            return n.title() if n else 'Unknown'
            
        df['Player'] = df['Player'].apply(clean_name)
        
        # Eliminar jugadores sin nombre válido
        mask = (df['Player'] != 'Unknown') & (df['Player'] != 'Nan')
        df = df[mask].copy()
        
        return df
    
    def _process_teams(self, df: pd.DataFrame) -> pd.DataFrame:
        """Procesa información de equipos."""
        # Buscar columna de equipo principal - Priorizamos 'Team' que viene resuelta de la DB
        team_column = None
        if 'Team' in df.columns:
            team_column = 'Team'
        elif 'Team within selected timeframe' in df.columns:
            team_column = 'Team within selected timeframe'
        
        if team_column is None:
            df['Team'] = 'Unknown Team'
            return df
        
        def clean_team(name):
            if pd.isna(name): return 'Unknown Team'
            n = str(name).strip()
            n = re.sub(r'\s+', ' ', n)
            return n.title() if n else 'Unknown Team'
            
        df['Team'] = df[team_column].apply(clean_team)
        
        # Eliminar equipos inválidos (ahora permitimos Unknown Team)
        invalid_teams = ['Nan', 'None', '0.0', '0']
        df = df[~df['Team'].isin(invalid_teams)].copy()
        
        return df
    
    def _process_positions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Procesa información de posiciones con manejo mejorado de múltiples formatos."""
        # Buscar columnas relacionadas con posiciones - orden de prioridad
        position_columns = [
            'Primary position', 'Position', 'Primary Position', 'position', 
            'Position_Primary', 'Position Primary', 'Main Position'
        ]
        
        # Encontrar la primera columna disponible
        position_column = next((col for col in position_columns if col in df.columns), None)
        
        # Determinar Position_Clean inicial
        if position_column:
            df['Position_Clean'] = df[position_column].apply(lambda x: str(x).strip() if pd.notna(x) else 'Unknown')
        else:
            # Si no hay columna de posición, intentar usar la confirmada si existe
            if 'Position_Confirmed' in df.columns:
                df['Position_Clean'] = df['Position_Confirmed'].fillna('Unknown')
            else:
                df['Position_Clean'] = 'Unknown'

        # Determinar Position_Group prioritariamente desde Position_Confirmed (DB/TM)
        def _resolve_group(row) -> str:
            # 1. Prioridad Máxima: Posición confirmada en DB (Transfermarkt/Manual)
            confirmed = str(row.get('Position_Confirmed', '') or '').strip()
            if confirmed and confirmed not in ('Unknown', 'nan', '0.0', ''):
                # Si la confirmada es una lista, usamos la lógica multi-posición
                if ',' in confirmed:
                    return self._get_position_group(confirmed)
                return self._get_position_group_single(confirmed)
            
            # 2. Segunda opción: Valor crudo del CSV de la temporada
            raw = row.get('Position_Clean', 'Unknown')
            return self._get_position_group(raw)

        df['Position_Group'] = df.apply(_resolve_group, axis=1)
        
        # Manejar Unknown con posiciones secundarias (solo para los que siguen como Unknown)
        unknown_mask = (df['Position_Group'] == 'Unknown') | (df['Position_Group'].isna())
        unknown_count = unknown_mask.sum()
        
        if unknown_count > 0:
            # Buscar columnas de posición secundaria
            secondary_columns = ['Secondary position', 'Position_Secondary', 'Second Position']
            
            for col in secondary_columns:
                if col in df.columns:
                    # Actualizar solo las filas que siguen siendo Unknown
                    df.loc[unknown_mask, 'Position_Group'] = df.loc[unknown_mask, col].apply(
                        lambda x: self._get_position_group(str(x)) if pd.notna(x) else 'Unknown'
                    )
                    # Actualizar mask para el siguiente intento
                    unknown_mask = (df['Position_Group'] == 'Unknown') | (df['Position_Group'].isna())
                    if unknown_mask.sum() == 0: break
        
        return df

    # Priority order when a player has multiple positions: attack roles take precedence.
    _POSITION_GROUP_PRIORITY = ['Forward', 'Winger', 'Defender', 'Midfielder', 'Goalkeeper']

    # Full position-to-group mapping used by _get_position_group_single.
    _POSITION_MAPPING = {
        'Goalkeeper': ['GK', 'Goalkeeper', 'Goalie', 'Keeper', 'Portero', 'Porter'],
        'Defender': ['CB', 'RCB', 'LCB', 'RCB3', 'LCB3', 'RB', 'LB', 'RWB', 'LWB',
                     'Defender', 'Defense', 'Centre-Back', 'Right-Back', 'Left-Back',
                     'Centre Back', 'Right Back', 'Left Back', 'Wing Back',
                     'Central Defender', 'Lateral', 'Stopper'],
        'Midfielder': ['DM', 'CM', 'AM', 'AMF', 'RAMF', 'LAMF', 'RM', 'LM',
                       'Midfielder', 'Midfield', 'Central Midfielder',
                       'Defensive Midfielder', 'Attacking Midfielder',
                       'Central Medio', 'Medio', 'Medio Campo', 'Pivot', 'Pivote'],
        'Winger': ['RW', 'LW', 'RWF', 'LWF',
                   'Winger', 'Wing', 'Wide Midfielder', 'Wide Man',
                   'Outside Midfielder', 'Extremo', 'Interior'],
        'Forward': ['CF', 'ST', 'SS',
                    'Forward', 'Striker', 'Centre-Forward', 'Center Forward',
                    'Attacker', 'Second Striker', 'False 9', 'Delantero', 'Punta'],
    }

    def _get_position_group_single(self, position: str) -> str:
        """Maps a single position token (no commas) to a position group."""
        if not position or position == 'Unknown':
            return 'Unknown'
        position = str(position).strip()
        position_lower = position.lower()

        # CF / ST have absolute forward priority (guards against substring false-matches)
        if position_lower in ('cf', 'st'):
            return 'Forward'

        for group, variations in self._POSITION_MAPPING.items():
            if any(v.lower() == position_lower for v in variations):
                return group

        # Substring fallback (last resort — exact match preferred above)
        for group, variations in self._POSITION_MAPPING.items():
            if any(v.lower() in position_lower for v in variations):
                return group

        for group, positions in self.position_groups.items():
            if position in positions:
                return group

        return 'Unknown'

    def _get_position_group(self, position):
        """Determina el grupo de posición con mejor manejo de variaciones.

        When a player has multiple comma-separated positions, evaluates all of them
        and returns the highest-priority group (Forward > Winger > Defender > Midfielder).
        """
        if not position or position == 'Unknown':
            return 'Unknown'

        position = str(position).strip()

        if ',' in position:
            tokens = [p.strip() for p in position.split(',')]
            # Forward priority: if any token is CF or ST, player is a Forward
            for tok in tokens:
                if tok.upper() in ('CF', 'ST'):
                    return 'Forward'
            # Evaluate all tokens and return the highest-priority group found
            found_groups = {self._get_position_group_single(tok) for tok in tokens} - {'Unknown'}
            for group in self._POSITION_GROUP_PRIORITY:
                if group in found_groups:
                    return group
            return 'Unknown'

        return self._get_position_group_single(position)
    
    def _process_numbers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Procesa columnas numéricas importantes."""
        # Columnas numéricas críticas
        numeric_columns = {
            'Age': 'Age',
            'Matches played': 'Matches played',
            'Minutes played': 'Minutes played',
            'Goals': 'Goals',
            'Assists': 'Assists'
        }
        
        for new_col, orig_col in numeric_columns.items():
            if orig_col in df.columns:
                # Convertir a numérico de forma segura
                df[new_col] = pd.to_numeric(df[orig_col], errors='coerce').fillna(0)
                # Asegurar que no sean negativos
                df[new_col] = df[new_col].clip(lower=0)
        
        return df
    
    def _add_calculated_fields(self, df: pd.DataFrame, season: str) -> pd.DataFrame:
        """Agrega campos calculados esenciales."""
        df['Season'] = season
        
        # Minutos por partido
        if 'Minutes played' in df.columns and 'Matches played' in df.columns:
            df['Minutes_per_Match'] = np.where(
                df['Matches played'] > 0,
                df['Minutes played'] / df['Matches played'],
                0
            )
        
        # Categoría de edad
        if 'Age' in df.columns:
            df['Age_Category'] = df['Age'].apply(self._categorize_age)
        
        return df
    
    def _categorize_age(self, age):
        """Categoriza la edad."""
        try:
            age = float(age)
            if age < 21:
                return 'Young'
            elif age < 25:
                return 'Developing'
            elif age < 30:
                return 'Prime'
            elif age < 35:
                return 'Experienced'
            else:
                return 'Veteran'
        except:
            return 'Unknown'
    
    def _final_cleanup(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpieza final del DataFrame."""
        # Eliminar duplicados basados en jugador y equipo
        if 'Player' in df.columns and 'Team' in df.columns:
            initial_count = len(df)
            df = df.drop_duplicates(subset=['Player', 'Team'], keep='first')
            if len(df) < initial_count:
                logger.info(f"Eliminados {initial_count - len(df)} registros duplicados")
        
        # Resetear índice final
        df = df.reset_index(drop=True)
        
        # Ordenar por equipo y luego por jugador
        if 'Team' in df.columns and 'Player' in df.columns:
            df = df.sort_values(['Team', 'Player'])
        
        return df
    
    def _tactical_preprocessing(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Realiza preprocesamiento específico para métricas tácticas y de eficiencia.
        Asegura que las columnas existan y tengan el tipo de dato correcto.
        """
        logger.info("Realizando preprocesamiento táctico profesional...")

        # Inject composite metrics (efficiency_index, defensive_wall)
        try:
            ml_pre = MLPreprocessor()
            df = ml_pre.inject_composite_metrics(df)
            logger.info("✓ Métricas compuestas inyectadas correctamente")
        except Exception as e:
            logger.error(f"Error inyectando métricas compuestas: {e}")

        # Convertir a numérico TODAS las columnas excepto las de texto conocidas
        text_columns = ['Player', 'Team', 'Position', 'Position_Clean', 'Position_Group', 
                        'Season', 'Age_Category', 'Birth country', 'Passport country', 
                        'Foot', 'On loan']
        
        for col in df.columns:
            if col not in text_columns and df[col].dtype == 'object':
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Control de rangos: Limitar TODAS las columnas que sean porcentajes a un máximo de 100
        for col in df.columns:
            if '%' in col or 'rate' in col.lower():
                df[col] = self._validate_metric_range(df[col], 0, 100)
            elif pd.api.types.is_numeric_dtype(df[col]) and col not in ['Age', 'Height', 'Weight', 'Matches played', 'Minutes played']:
                # Ninguna métrica deportiva (pases, xg, etc) puede ser negativa
                df[col] = self._validate_metric_range(df[col], 0, float('inf'))

        # Lógica de relleno de Nulos (Inteligente)
        # Si tiene 0 minutos jugados, NO rellenamos con ceros las métricas avanzadas, 
        # dejamos NaN para que los modelos estadísticos y de IA no se contaminen.
        if 'Minutes played' in df.columns:
            played_mask = df['Minutes played'] > 0
            
            # Solo rellenamos con 0 a los que sí han jugado (es decir, tuvieron la oportunidad 
            # de hacer una acción y no la hicieron)
            for col in df.columns:
                if pd.api.types.is_numeric_dtype(df[col]) and col not in ['Age', 'Height', 'Weight', 'Matches played', 'Minutes played']:
                    df.loc[played_mask, col] = df.loc[played_mask, col].fillna(0)

        # Tratar nulos en columnas de texto
        for col in text_columns:
            if col in df.columns:
                df[col] = df[col].fillna('Unknown')

        return df

    def _validate_metric_range(self, series: pd.Series, lower_bound=0, upper_bound=100) -> pd.Series:
        """Valida que los valores de una serie estén dentro de un rango específico."""
        return series.clip(lower=lower_bound, upper=upper_bound)

    def _create_minimal_dataset(self, df: pd.DataFrame, season: str) -> pd.DataFrame:
        """Crea un dataset mínimo en caso de error total."""
        logger.warning("Creando dataset mínimo debido a errores en el procesamiento")
        
        minimal_df = pd.DataFrame({
            'Player': ['Sample Player 1', 'Sample Player 2'],
            'Team': ['Sample Team A', 'Sample Team B'],
            'Position_Clean': ['ST', 'GK'],
            'Position_Group': ['Forward', 'Goalkeeper'],
            'Age': [25, 30],
            'Matches played': [10, 15],
            'Minutes played': [900, 1350],
            'Goals': [5, 0],
            'Assists': [2, 0],
            'Season': [season, season],
            'Age_Category': ['Developing', 'Prime'],
            'Minutes_per_Match': [90, 90]
        })
        
        return minimal_df
    
    def get_player_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Genera resumen estadístico detallado de los jugadores procesados.
        
        Args:
            df: DataFrame procesado
            
        Returns:
            Diccionario con resumen estadístico
        """
        if df.empty:
            return {"error": "No hay datos para resumir"}
        
        summary = {
            'basic_info': {
                'total_players': len(df),
                'total_teams': df['Team'].nunique() if 'Team' in df.columns else 0,
                'season': df['Season'].iloc[0] if 'Season' in df.columns else 'N/A',
                'positions_distribution': df['Position_Group'].value_counts().to_dict() 
                    if 'Position_Group' in df.columns else {}
            }
        }
        
        # Estadísticas de edad
        if 'Age' in df.columns:
            summary['age_stats'] = {
                'average_age': round(df['Age'].mean(), 1),
                'median_age': round(df['Age'].median(), 1),
                'youngest_player': {
                    'age': int(df['Age'].min()),
                    'player': df.loc[df['Age'].idxmin(), 'Player'] if 'Player' in df.columns else 'N/A'
                },
                'oldest_player': {
                    'age': int(df['Age'].max()),
                    'player': df.loc[df['Age'].idxmax(), 'Player'] if 'Player' in df.columns else 'N/A'
                },
                'age_distribution': df['Age_Category'].value_counts().to_dict() 
                    if 'Age_Category' in df.columns else {}
            }
        
        # Performance stats
        performance_stats = {}
        if 'Goals' in df.columns:
            performance_stats['goals'] = {
                'total': int(df['Goals'].sum()),
                'average_per_player': round(df['Goals'].mean(), 2)
            }
            # Top scorers
            top_scorers = df.nlargest(5, 'Goals')[['Player', 'Team', 'Goals']]
            performance_stats['top_scorers'] = top_scorers.to_dict('records')
        
        if 'Assists' in df.columns:
            performance_stats['assists'] = {
                'total': int(df['Assists'].sum()),
                'average_per_player': round(df['Assists'].mean(), 2)
            }
            # Top assisters
            top_assisters = df.nlargest(5, 'Assists')[['Player', 'Team', 'Assists']]
            performance_stats['top_assisters'] = top_assisters.to_dict('records')
        
        # Añadir performance stats al resumen
        if performance_stats:
            summary['performance_stats'] = performance_stats
        
        # Team stats
        if 'Team' in df.columns:
            team_stats = {}
            for team in df['Team'].unique():
                team_df = df[df['Team'] == team]
                team_stats[team] = {
                    'players_count': len(team_df),
                    'avg_age': round(team_df['Age'].mean(), 1) if 'Age' in team_df.columns else 0,
                    'goals': int(team_df['Goals'].sum()) if 'Goals' in team_df.columns else 0,
                    'assists': int(team_df['Assists'].sum()) if 'Assists' in team_df.columns else 0
                }
            summary['team_stats'] = team_stats
        
        return summary
