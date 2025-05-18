import pandas as pd
import numpy as np
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class HongKongDataProcessor:
    """
    Procesador específico para datos de jugadores de la Liga de Hong Kong.
    Limpia y transforma estadísticas individuales de jugadores.
    """
    
    def __init__(self):
        # Mapeo de posiciones para estandarización
        self.position_mapping = {
            'GK': 'Goalkeeper',
            'CB': 'Centre-Back',
            'RCB': 'Right Centre-Back',
            'LCB': 'Left Centre-Back',
            'RCB3': 'Right Centre-Back (3-5-2)',
            'LCB3': 'Left Centre-Back (3-5-2)',
            'RB': 'Right-Back',
            'LB': 'Left-Back',
            'RWB': 'Right Wing-Back',
            'LWB': 'Left Wing-Back',
            'DM': 'Defensive Midfielder',
            'CM': 'Central Midfielder',
            'AM': 'Attacking Midfielder',
            'RM': 'Right Midfielder',
            'LM': 'Left Midfielder',
            'RW': 'Right Winger',
            'LW': 'Left Winger',
            'CF': 'Centre Forward',
            'ST': 'Striker',
            'RWF': 'Right Wing Forward',
            'LWF': 'Left Wing Forward',
            'SS': 'Second Striker'
        }
        
        # Grupos de posiciones para análisis
        self.position_groups = {
            'Goalkeeper': ['GK'],
            'Defender': ['CB', 'RCB', 'LCB', 'RCB3', 'LCB3', 'RB', 'LB', 'RWB', 'LWB'],
            'Midfielder': ['DM', 'CM', 'AM', 'RM', 'LM'],
            'Winger': ['RW', 'LW', 'RWF', 'LWF'],
            'Forward': ['CF', 'ST', 'SS']
        }
        
        # Columnas críticas que deben estar presentes
        self.required_columns = [
            'Player', 'Team', 'Position', 'Age', 'Matches played'
        ]
        
        # Columnas numéricas para convertir
        self.numeric_columns = [
            'Age', 'Matches played', 'Minutes played', 'Goals', 'xG', 'Assists', 'xA',
            'Height', 'Weight', 'Yellow cards', 'Red cards', 'Market value'
        ]
        
        # Columnas de porcentaje para limpiar
        self.percentage_columns = [
            'Primary position, %', 'Secondary position, %', 'Third position, %',
            'Duels won, %', 'Shots on target, %', 'Goal conversion, %',
            'Accurate crosses, %', 'Successful dribbles, %', 'Accurate passes, %'
        ]
    
    def process_season_data(self, df: pd.DataFrame, season: str) -> pd.DataFrame:
        """
        Procesa datos de jugadores de una temporada.
        
        Args:
            df: DataFrame crudo con datos de jugadores
            season: Temporada (ej: "2024-25")
            
        Returns:
            DataFrame procesado y limpio
        """
        if df.empty:
            print("DataFrame vacío, no hay datos para procesar")
            return df
        
        print(f"Procesando datos de jugadores {season}...")
        print(f"Datos originales: {len(df)} jugadores, {len(df.columns)} columnas")
        
        # Hacer una copia profunda para evitar warnings
        df_clean = df.copy(deep=True)
        
        # 1. Limpieza inicial
        df_clean = self._initial_cleaning(df_clean)
        
        # 2. Limpiar y validar columnas críticas
        df_clean = self._clean_critical_columns(df_clean)
        
        # 3. Procesar datos numéricos
        df_clean = self._process_numeric_data(df_clean)
        
        # 4. Limpiar posiciones
        df_clean = self._process_positions(df_clean)
        
        # 5. Limpiar información personal
        df_clean = self._process_personal_info(df_clean)
        
        # 6. Agregar columnas calculadas (crear un nuevo DataFrame para evitar fragmentación)
        df_clean = self._add_calculated_columns(df_clean, season)
        
        # 7. Validación final
        df_clean = self._final_validation(df_clean)
        
        print(f"Datos procesados: {len(df_clean)} jugadores, {len(df_clean.columns)} columnas")
        print(f"Jugadores eliminados: {len(df) - len(df_clean)}")
        
        return df_clean
    
    def _initial_cleaning(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpieza inicial básica del DataFrame."""
        
        # Eliminar filas completamente vacías
        df = df.dropna(how='all')
        
        # Eliminar columnas completamente vacías
        df = df.dropna(axis=1, how='all')
        
        # Resetear índice
        df = df.reset_index(drop=True)
        
        # Limpiar nombres de columnas (remover espacios extra)
        df.columns = df.columns.str.strip()
        
        return df
    
    def _clean_critical_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpia y valida las columnas críticas."""
        
        # Verificar columnas requeridas
        missing_columns = [col for col in self.required_columns if col not in df.columns]
        if missing_columns:
            print(f"Advertencia: Columnas faltantes: {missing_columns}")
        
        # Limpiar nombres de jugadores solo si la columna existe
        if 'Player' in df.columns:
            # Convertir a string y limpiar - crear nueva serie para evitar warnings
            player_clean = df['Player'].astype(str).str.strip()
            # Crear DataFrame nuevo para evitar warnings de copia
            df = df.copy()
            df['Player'] = player_clean
            
            # Eliminar jugadores sin nombre válido
            initial_count = len(df)
            mask = (
                df['Player'].notna() & 
                (df['Player'] != '') & 
                (df['Player'] != 'nan') & 
                (df['Player'] != 'None')
            )
            df = df[mask].copy()
            
            if len(df) < initial_count:
                print(f"Eliminados {initial_count - len(df)} jugadores sin nombre válido")
        
        # Limpiar nombres de equipos solo si la columna existe
        if 'Team' in df.columns:
            # Convertir a string y limpiar - crear nueva serie para evitar warnings
            team_clean = df['Team'].astype(str).str.strip()
            df['Team'] = team_clean
            
            # Eliminar jugadores sin equipo válido
            initial_count = len(df)
            mask = (
                df['Team'].notna() & 
                (df['Team'] != '') & 
                (df['Team'] != 'nan') & 
                (df['Team'] != 'None')
            )
            df = df[mask].copy()
            
            if len(df) < initial_count:
                print(f"Eliminados {initial_count - len(df)} jugadores sin equipo válido")
        
        return df
    
    def _process_numeric_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Procesa y limpia datos numéricos."""
        
        # Convertir columnas numéricas básicas
        for col in self.numeric_columns:
            if col in df.columns:
                # Limpiar valores especiales - no modificar inplace
                series_clean = df[col].astype(str).str.replace(',', '')
                
                # Manejar Market value especial (puede tener 'K', 'M')
                if col == 'Market value':
                    series_clean = series_clean.apply(self._parse_market_value)
                
                # Convertir a numérico
                series_numeric = pd.to_numeric(series_clean, errors='coerce')
                
                # Para columnas críticas, eliminar NaN
                if col in ['Age', 'Matches played']:
                    mask = series_numeric.notna()
                    df = df[mask].copy()
                    series_numeric = series_numeric[mask]
                else:
                    # Para otras, llenar con 0
                    series_numeric = series_numeric.fillna(0)
                
                # Asegurar que no sean negativos (excepto algunas estadísticas defensivas avanzadas)
                if col not in ['xG against', 'Prevented goals', 'Prevented goals per 90']:
                    series_numeric = series_numeric.clip(lower=0)
                
                # Asignar de vuelta al DataFrame
                df[col] = series_numeric
        
        # Limpiar columnas de porcentaje
        for col in self.percentage_columns:
            if col in df.columns:
                # Convertir porcentajes a decimal (ej: "50.0" -> 0.5)
                series_numeric = pd.to_numeric(df[col], errors='coerce')
                series_numeric = series_numeric.fillna(0)
                # Asegurar que estén entre 0 y 100
                series_numeric = series_numeric.clip(0, 100)
                df[col] = series_numeric
        
        # Limpiar todas las columnas "per 90"
        per_90_columns = [col for col in df.columns if 'per 90' in col]
        for col in per_90_columns:
            series_numeric = pd.to_numeric(df[col], errors='coerce')
            series_numeric = series_numeric.fillna(0)
            # Las estadísticas per 90 no pueden ser negativas en su mayoría
            if col not in ['Conceded goals per 90', 'xG against per 90']:
                series_numeric = series_numeric.clip(lower=0)
            df[col] = series_numeric
        
        return df
    
    def _parse_market_value(self, value):
        """Convierte valores de mercado en formato texto a números."""
        if pd.isna(value) or value == '' or value == '0':
            return 0
        
        value = str(value).strip().upper()
        
        # Remover símbolos de moneda
        value = re.sub(r'[€$£]', '', value)
        
        # Convertir K y M a números
        if 'K' in value:
            try:
                return float(value.replace('K', '')) * 1000
            except:
                return 0
        elif 'M' in value:
            try:
                return float(value.replace('M', '')) * 1000000
            except:
                return 0
        else:
            try:
                return float(value)
            except:
                return 0
    
    def _process_positions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Procesa y estandariza información de posiciones."""
        
        # Crear diccionario para las nuevas columnas de posición
        position_columns = {}
        
        # Limpiar posición principal
        if 'Position' in df.columns:
            # Extraer primera posición si hay múltiples
            position_clean = df['Position'].astype(str).str.split(',').str[0].str.strip()
            
            # Remover caracteres extra y normalizar
            position_clean = position_clean.str.replace('"', '').str.strip()
            
            # Mapear a nombres completos
            position_full = position_clean.map(self.position_mapping)
            position_full = position_full.fillna(position_clean)
            
            position_columns['Position_Clean'] = position_clean
            position_columns['Position_Full'] = position_full
            position_columns['Position_Group'] = position_clean.apply(self._get_position_group)
        
        # Procesar Primary position
        if 'Primary position' in df.columns:
            primary_clean = df['Primary position'].astype(str).str.strip()
            primary_full = primary_clean.map(self.position_mapping)
            primary_full = primary_full.fillna(primary_clean)
            position_columns['Primary_Position_Full'] = primary_full
        
        # Agregar todas las columnas de posición de una vez usando pd.concat
        if position_columns:
            new_df = pd.concat([df, pd.DataFrame(position_columns, index=df.index)], axis=1)
            return new_df
        else:
            return df
    
    def _get_position_group(self, position):
        """Determina el grupo de posición (Goalkeeper, Defender, etc.)."""
        for group, positions in self.position_groups.items():
            if position in positions:
                return group
        return 'Unknown'
    
    def _process_personal_info(self, df: pd.DataFrame) -> pd.DataFrame:
        """Procesa información personal de los jugadores."""
        
        # Crear diccionario para las nuevas columnas
        personal_columns = {}
        
        # Procesar fecha de nacimiento
        if 'Birthday' in df.columns:
            df['Birthday'] = pd.to_datetime(df['Birthday'], errors='coerce')
            
            # Calcular edad si no está disponible o es inconsistente
            if 'Age' in df.columns:
                current_year = datetime.now().year
                age_calculated = current_year - df['Birthday'].dt.year
                personal_columns['Age_Calculated'] = age_calculated
                
                # Verificar consistencia de edad
                age_diff = abs(df['Age'] - age_calculated)
                inconsistent_ages = age_diff > 1  # Diferencia mayor a 1 año
                if inconsistent_ages.sum() > 0:
                    print(f"Advertencia: {inconsistent_ages.sum()} jugadores con edades inconsistentes")
        
        # Procesar país
        if 'Birth country' in df.columns:
            df['Birth country'] = df['Birth country'].astype(str).str.strip()
        
        if 'Passport country' in df.columns:
            # Limpiar formato de lista en string
            passport_clean = df['Passport country'].astype(str)
            passport_clean = passport_clean.str.replace(r"[\[\]']", '', regex=True)
            df['Passport country'] = passport_clean.str.strip()
        
        # Procesar información física - manejar ceros y valores faltantes
        if 'Height' in df.columns and 'Weight' in df.columns:
            # Asegurar que los datos sean numéricos primero
            height_numeric = pd.to_numeric(df['Height'], errors='coerce')
            weight_numeric = pd.to_numeric(df['Weight'], errors='coerce')
            
            # Calcular BMI solo donde ambos valores son válidos y mayores a 0
            bmi_values = np.full(len(df), np.nan)  # Inicializar con NaN
            
            # Crear máscara para valores válidos
            valid_mask = (
                height_numeric.notna() & 
                weight_numeric.notna() & 
                (height_numeric > 0) & 
                (weight_numeric > 0)
            )
            
            # Calcular BMI solo para valores válidos
            if valid_mask.any():
                valid_height = height_numeric[valid_mask]
                valid_weight = weight_numeric[valid_mask]
                bmi_values[valid_mask] = valid_weight / ((valid_height / 100) ** 2)
            
            personal_columns['BMI'] = bmi_values
        
        # Procesar pie dominante
        if 'Foot' in df.columns:
            foot_clean = df['Foot'].astype(str).str.lower().str.strip()
            df['Foot'] = foot_clean.replace({'nan': 'unknown', '': 'unknown'})
        
        # Agregar todas las columnas personales de una vez
        if personal_columns:
            new_df = pd.concat([df, pd.DataFrame(personal_columns, index=df.index)], axis=1)
            return new_df
        else:
            return df
    
    def _add_calculated_columns(self, df: pd.DataFrame, season: str) -> pd.DataFrame:
        """Agrega columnas calculadas útiles para análisis."""
        
        # Crear diccionario con todas las nuevas columnas para evitar fragmentación
        new_columns = {}
        
        # Información de temporada
        new_columns['Season'] = season
        
        # Calcular minutos por partido
        if all(col in df.columns for col in ['Minutes played', 'Matches played']):
            new_columns['Minutes_per_Match'] = np.where(
                df['Matches played'] > 0,
                df['Minutes played'] / df['Matches played'],
                0
            )
        
        # Categorizar experiencia
        if 'Age' in df.columns:
            def categorize_age(age):
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
            
            new_columns['Age_Category'] = df['Age'].apply(categorize_age)
        
        # Categorizar actividad de juego
        if 'Matches played' in df.columns:
            # Asumiendo máximo de 30 partidos en la temporada
            max_matches = df['Matches played'].max()
            new_columns['Playing_Time_Category'] = pd.cut(
                df['Matches played'],
                bins=[0, max_matches*0.25, max_matches*0.5, max_matches*0.75, max_matches],
                labels=['Rarely plays', 'Occasional', 'Regular', 'Key player'],
                include_lowest=True
            )
        
        # Calcular eficiencia de gol
        if all(col in df.columns for col in ['Goals', 'Shots']):
            new_columns['Goal_Efficiency'] = np.where(
                df['Shots'] > 0,
                (df['Goals'] / df['Shots'] * 100).round(2),
                0
            )
        
        # Indicador de versatilidad (si juega múltiples posiciones)
        position_cols = ['Primary position', 'Secondary position', 'Third position']
        available_pos_cols = [col for col in position_cols if col in df.columns]
        
        if len(available_pos_cols) > 1:
            # Contar posiciones no vacías
            versatility_count = 0
            for col in available_pos_cols:
                versatility_count += (
                    df[col].notna() & 
                    (df[col] != '') & 
                    (df[col] != '0') & 
                    (df[col] != 'nan')
                ).astype(int)
            new_columns['Position_Versatility'] = versatility_count
        
        # Indicador de juventud del equipo (para análisis posterior)
        if 'Team' in df.columns and 'Age' in df.columns:
            team_avg_age = df.groupby('Team')['Age'].mean()
            new_columns['Team_Avg_Age'] = df['Team'].map(team_avg_age)
            new_columns['Above_Team_Avg_Age'] = df['Age'] > new_columns['Team_Avg_Age']
        
        # Clasificación por valor de mercado
        if 'Market value' in df.columns:
            new_columns['Market_Value_Category'] = pd.cut(
                df['Market value'],
                bins=[0, 50000, 200000, 500000, float('inf')],
                labels=['Low', 'Medium', 'High', 'Premium'],
                include_lowest=True
            )
        
        # Agregar todas las columnas nuevas de una vez usando pd.concat
        new_df = pd.concat([df, pd.DataFrame(new_columns, index=df.index)], axis=1)
        
        return new_df
    
    def _final_validation(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validación final de datos procesados."""
        
        # Eliminar duplicados basados en jugador y equipo
        initial_count = len(df)
        df = df.drop_duplicates(subset=['Player', 'Team'], keep='first')
        if len(df) < initial_count:
            print(f"Eliminados {initial_count - len(df)} jugadores duplicados")
        
        # Verificar datos básicos
        if 'Age' in df.columns:
            invalid_ages = df[(df['Age'] < 15) | (df['Age'] > 50)]
            if len(invalid_ages) > 0:
                print(f"Advertencia: {len(invalid_ages)} jugadores con edades inusuales")
        
        if 'Minutes played' in df.columns and 'Matches played' in df.columns:
            # Verificar que los minutos no excedan el máximo posible
            max_minutes_possible = df['Matches played'] * 90
            excessive_minutes = df[df['Minutes played'] > max_minutes_possible]
            if len(excessive_minutes) > 0:
                print(f"Advertencia: {len(excessive_minutes)} jugadores con minutos excesivos")
        
        # Ordenar por equipo y luego por nombre
        if all(col in df.columns for col in ['Team', 'Player']):
            df = df.sort_values(['Team', 'Player']).reset_index(drop=True)
        
        return df
    
    def get_player_summary(self, df: pd.DataFrame) -> Dict:
        """Genera resumen estadístico de los jugadores."""
        
        if df.empty:
            return {"error": "No hay datos para resumir"}
        
        summary = {
            'basic_info': {
                'total_players': len(df),
                'total_teams': df['Team'].nunique() if 'Team' in df.columns else 'N/A',
                'season': df['Season'].iloc[0] if 'Season' in df.columns else 'N/A'
            }
        }
        
        # Distribución por posición
        if 'Position_Group' in df.columns:
            position_dist = df['Position_Group'].value_counts().to_dict()
            summary['position_distribution'] = position_dist
        
        # Estadísticas de edad
        if 'Age' in df.columns:
            summary['age_stats'] = {
                'average_age': round(df['Age'].mean(), 1),
                'youngest_player': int(df['Age'].min()),
                'oldest_player': int(df['Age'].max()),
                'players_under_23': int((df['Age'] < 23).sum())
            }
        
        # Top performers (solo si las columnas necesarias existen)
        if all(col in df.columns for col in ['Goals', 'Player', 'Team']) and len(df) > 0:
            top_scorers_df = df.nlargest(5, 'Goals')[['Player', 'Team', 'Goals']]
            # Convertir explícitamente a lista de diccionarios
            top_scorers_list = []
            for _, row in top_scorers_df.iterrows():
                top_scorers_list.append({
                    'Player': str(row['Player']),
                    'Team': str(row['Team']),
                    'Goals': int(row['Goals']) if pd.notna(row['Goals']) else 0
                })
            # Crear un diccionario con la estructura esperada
            summary['top_scorers'] = {
                'count': len(top_scorers_list),
                'players': top_scorers_list
            }
        
        if all(col in df.columns for col in ['Assists', 'Player', 'Team']) and len(df) > 0:
            top_assisters_df = df.nlargest(5, 'Assists')[['Player', 'Team', 'Assists']]
            # Convertir explícitamente a lista de diccionarios
            top_assisters_list = []
            for _, row in top_assisters_df.iterrows():
                top_assisters_list.append({
                    'Player': str(row['Player']),
                    'Team': str(row['Team']),
                    'Assists': int(row['Assists']) if pd.notna(row['Assists']) else 0
                })
            # Crear un diccionario con la estructura esperada
            summary['top_assisters'] = {
                'count': len(top_assisters_list),
                'players': top_assisters_list
            }
        
        # Distribución por equipo
        if 'Team' in df.columns:
            team_counts = df['Team'].value_counts().head(10).to_dict()
            summary['players_per_team'] = team_counts
        
        # Información de mercado
        if 'Market value' in df.columns:
            valid_values = df[df['Market value'] > 0]
            if len(valid_values) > 0:
                summary['market_value_stats'] = {
                    'highest_value': valid_values['Market value'].max(),
                    'average_value': round(valid_values['Market value'].mean(), 2),
                    'players_with_value': len(valid_values)
                }
        
        return summary
    
    def get_team_analysis(self, df: pd.DataFrame, team_name: Optional[str] = None) -> Dict:
        """Análisis específico por equipo."""
        
        if team_name:
            team_df = df[df['Team'] == team_name]
            if team_df.empty:
                return {"error": f"No se encontraron jugadores para {team_name}"}
        else:
            team_df = df
        
        analysis = {
            'team_name': team_name or 'All Teams',
            'player_count': len(team_df)
        }
        
        # Distribución por posición
        if 'Position_Group' in team_df.columns:
            pos_dist = team_df['Position_Group'].value_counts().to_dict()
            analysis['position_breakdown'] = pos_dist
        
        # Estadísticas del equipo
        if 'Age' in team_df.columns:
            analysis['age_profile'] = {
                'average_age': round(team_df['Age'].mean(), 1),
                'youngest': int(team_df['Age'].min()),
                'oldest': int(team_df['Age'].max())
            }
        
        # Performance colectiva
        if all(col in team_df.columns for col in ['Goals', 'Player']) and len(team_df) > 0:
            analysis['goals'] = {
                'total_goals': int(team_df['Goals'].sum()),
                'top_scorer': str(team_df.loc[team_df['Goals'].idxmax(), 'Player']),
                'top_scorer_goals': int(team_df['Goals'].max())
            }
        
        if all(col in team_df.columns for col in ['Assists', 'Player']) and len(team_df) > 0:
            analysis['assists'] = {
                'total_assists': int(team_df['Assists'].sum()),
                'top_assister': str(team_df.loc[team_df['Assists'].idxmax(), 'Player']),
                'top_assister_assists': int(team_df['Assists'].max())
            }
        
        return analysis