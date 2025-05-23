import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)
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
            
            # 7. Validación final
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
        
        # Limpiar nombres de jugadores manualmente
        df['Player'] = df['Player'].apply(lambda x: str(x).strip() if pd.notna(x) else 'Unknown')
        
        # Eliminar jugadores sin nombre válido
        mask = (df['Player'] != 'Unknown') & (df['Player'] != '') & (df['Player'] != 'nan')
        df = df[mask].copy()
        
        return df
    
    def _process_teams(self, df: pd.DataFrame) -> pd.DataFrame:
        """Procesa información de equipos."""
        # Buscar columna de equipo principal
        team_column = None
        if 'Team within selected timeframe' in df.columns:
            team_column = 'Team within selected timeframe'
        elif 'Team' in df.columns:
            team_column = 'Team'
        
        if team_column is None:
            df['Team'] = 'Unknown Team'
            return df
        
        # Limpiar nombres de equipos manualmente
        df['Team'] = df[team_column].apply(lambda x: str(x).strip() if pd.notna(x) else 'Unknown Team')
        
        # Eliminar equipos inválidos
        invalid_teams = ['Unknown Team', 'nan', 'None', '']
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
        
        # Si no se encuentra, buscar cualquier columna con "position" en el nombre
        if position_column is None:
            position_column = next((col for col in df.columns if 'position' in col.lower()), None)
        
        # Si no se encuentra ninguna columna de posición
        if position_column is None:
            df['Position_Clean'] = 'Unknown'
            df['Position_Group'] = 'Unknown'
            return df
        
        # Limpiar posiciones
        df['Position_Clean'] = df[position_column].apply(lambda x: str(x).strip() if pd.notna(x) else 'Unknown')
        
        # Asignar grupo de posición
        df['Position_Group'] = df['Position_Clean'].apply(self._get_position_group)
        
        # Manejar Unknown con posiciones secundarias
        unknown_mask = df['Position_Group'] == 'Unknown'
        unknown_count = unknown_mask.sum()
        
        if unknown_count > 0.3 * len(df):  # Si más del 30% son desconocidas
            # Buscar columnas de posición secundaria por orden de prioridad
            secondary_columns = ['Secondary position', 'Position_Secondary', 'Second Position']
            
            for col in secondary_columns:
                if col in df.columns:
                    # Actualizar solo las filas con posición desconocida
                    df.loc[unknown_mask, 'Position_Clean'] = df.loc[unknown_mask, col].apply(
                        lambda x: str(x).strip() if pd.notna(x) else 'Unknown'
                    )
                    df.loc[unknown_mask, 'Position_Group'] = df.loc[unknown_mask, 'Position_Clean'].apply(
                        self._get_position_group
                    )
                    break
        
        return df

    def _get_position_group(self, position):
        """Determina el grupo de posición con mejor manejo de variaciones."""
        if not position or position == 'Unknown':
            return 'Unknown'
        
        position = str(position).strip()
        
        # Si hay múltiples posiciones separadas por comas, usar la primera
        if ',' in position:
            positions = [pos.strip() for pos in position.split(',')]
            position = positions[0]
        
        # Mapeo completo de posiciones a grupos
        position_mapping = {
            'Goalkeeper': ['GK', 'Goalkeeper', 'Goalie', 'Keeper', 'Portero', 'Porter'],
            'Defender': ['CB', 'RCB', 'LCB', 'RCB3', 'LCB3', 'RB', 'LB', 'RWB', 'LWB', 
                        'Defender', 'Defense', 'Centre-Back', 'Right-Back', 'Left-Back',
                        'Centre Back', 'Right Back', 'Left Back', 'Wing Back',
                        'Central Defender', 'Lateral', 'Stopper'],
            'Midfielder': ['DM', 'CM', 'AM', 'RM', 'LM', 
                            'Midfielder', 'Midfield', 'Central Midfielder',
                            'Defensive Midfielder', 'Attacking Midfielder',
                            'Central Medio', 'Medio', 'Medio Campo', 'Pivot', 'Pivote'],
            'Winger': ['RW', 'LW', 'RWF', 'LWF', 
                    'Winger', 'Wing', 'Wide Midfielder', 'Wide Man',
                    'Outside Midfielder', 'Extremo', 'Interior'],
            'Forward': ['CF', 'ST', 'SS', 
                        'Forward', 'Striker', 'Centre-Forward', 'Center Forward',
                        'Attacker', 'Second Striker', 'False 9', 'Delantero', 'Punta']
        }
        
        # Verificar en cuál grupo encaja la posición (case-insensitive)
        position_lower = position.lower()
        for group, variations in position_mapping.items():
            if any(variation.lower() == position_lower or 
                variation.lower() in position_lower 
                for variation in variations):
                return group
        
        # Si no hay coincidencia, verificar con el mapeo original
        for group, positions in self.position_groups.items():
            if position in positions:
                return group
        
        return 'Unknown'
    
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