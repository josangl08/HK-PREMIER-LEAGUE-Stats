import pandas as pd
import numpy as np
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class HongKongDataProcessor:
    """
    Procesador específico para datos de jugadores de la Liga de Hong Kong.
    Versión corregida para manejar mejor posiciones y equipos.
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
            'Player', 'Team within selected timeframe', 'Primary position', 'Age', 'Matches played'
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
        df_clean = self._process_positions_improved(df_clean)
        
        # 5. Limpiar equipos 
        df_clean = self._process_teams_improved(df_clean)
        
        # 6. Limpiar información personal
        df_clean = self._process_personal_info(df_clean)
        
        # 7. Agregar columnas calculadas
        df_clean = self._add_calculated_columns(df_clean, season)
        
        # 8. Validación final
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
            df = df.copy()
            df['Player'] = df['Player'].astype(str).str.strip()
            
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
        
        return df
    
    def _process_teams_improved(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Procesa equipos usando 'Team within selected timeframe' 
        como equipo principal de Hong Kong.
        """
        
        # Crear diccionario para las nuevas columnas de equipo
        team_columns = {}
        
        # Procesar equipo de Hong Kong (Team within selected timeframe)
        if 'Team within selected timeframe' in df.columns:
            # Este es el equipo principal para el análisis de la liga
            team_hk = df['Team within selected timeframe'].astype(str).str.strip()
            team_hk = team_hk.replace({'nan': '', 'None': '', '': None})
            team_columns['Team_HK'] = team_hk
            
            # También crear una versión limpia
            team_hk_clean = team_hk.fillna('Sin equipo HK')
            team_columns['Team_HK_Clean'] = team_hk_clean
        
        # Procesar equipo actual
        if 'Team' in df.columns:
            team_current = df['Team'].astype(str).str.strip()
            team_current = team_current.replace({'nan': '', 'None': '', '': None})
            team_columns['Team_Current'] = team_current
            
            # Crear versión limpia
            team_current_clean = team_current.fillna('Sin equipo actual')
            team_columns['Team_Current_Clean'] = team_current_clean
        
        # Para compatibilidad con el resto del código, usar Team_HK como 'Team' principal
        if 'Team_HK' in team_columns:
            team_columns['Team'] = team_columns['Team_HK_Clean']
        
        # Agregar todas las columnas de equipo de una vez
        if team_columns:
            new_df = pd.concat([df, pd.DataFrame(team_columns, index=df.index)], axis=1)
            
            # Eliminar jugadores sin equipo de Hong Kong válido
            if 'Team' in new_df.columns:
                initial_count = len(new_df)
                mask = (
                    new_df['Team'].notna() & 
                    (new_df['Team'] != 'Sin equipo HK') &
                    (new_df['Team'].str.strip() != '')
                )
                new_df = new_df[mask].copy()
                
                if len(new_df) < initial_count:
                    print(f"Eliminados {initial_count - len(new_df)} jugadores sin equipo HK válido")
            
            return new_df
        else:
            return df
    
    def _process_positions_improved(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Procesa posiciones manejando.
        Primary, Secondary, Third position y sus porcentajes.
        """
        
        # Crear diccionario para las nuevas columnas de posición
        position_columns = {}
        
        # Procesar posición primaria
        if 'Primary position' in df.columns:
            primary_pos = df['Primary position'].astype(str).str.strip()
            primary_pos = primary_pos.replace({'nan': '', 'None': '', '': None})
            
            # Limpiar y mapear a nombres completos
            primary_clean = primary_pos.fillna('Unknown')
            primary_full = primary_clean.map(self.position_mapping).fillna(primary_clean)
            primary_group = primary_clean.apply(self._get_position_group)
            
            position_columns['Position_Primary'] = primary_clean
            position_columns['Position_Primary_Full'] = primary_full
            position_columns['Position_Primary_Group'] = primary_group
        
        # Procesar posición secundaria
        if 'Secondary position' in df.columns:
            secondary_pos = df['Secondary position'].astype(str).str.strip()
            secondary_pos = secondary_pos.replace({'nan': '', 'None': '', '': None})
            secondary_clean = secondary_pos.fillna('')
            position_columns['Position_Secondary'] = secondary_clean
        
        # Procesar posición terciaria
        if 'Third position' in df.columns:
            third_pos = df['Third position'].astype(str).str.strip()
            third_pos = third_pos.replace({'nan': '', 'None': '', '': None})
            third_clean = third_pos.fillna('')
            position_columns['Position_Third'] = third_clean
        
        # Procesar porcentajes de posición
        if 'Primary position, %' in df.columns:
            primary_pct = pd.to_numeric(df['Primary position, %'], errors='coerce').fillna(0)
            position_columns['Position_Primary_Pct'] = primary_pct
        
        if 'Secondary position, %' in df.columns:
            secondary_pct = pd.to_numeric(df['Secondary position, %'], errors='coerce').fillna(0)
            position_columns['Position_Secondary_Pct'] = secondary_pct
        
        if 'Third position, %' in df.columns:
            third_pct = pd.to_numeric(df['Third position, %'], errors='coerce').fillna(0)
            position_columns['Position_Third_Pct'] = third_pct
        
        # Crear posición dominante basada en porcentajes
        if all(col in position_columns for col in ['Position_Primary_Pct', 'Position_Secondary_Pct', 'Position_Third_Pct']):
            # Comparar porcentajes para determinar posición dominante
            def get_dominant_position(row):
                positions = [
                    (row.get('Position_Primary', ''), row.get('Position_Primary_Pct', 0)),
                    (row.get('Position_Secondary', ''), row.get('Position_Secondary_Pct', 0)),
                    (row.get('Position_Third', ''), row.get('Position_Third_Pct', 0))
                ]
                # Filtrar posiciones vacías y obtener la de mayor porcentaje
                valid_positions = [(pos, pct) for pos, pct in positions if pos and pos != '']
                if valid_positions:
                    dominant = max(valid_positions, key=lambda x: x[1])
                    return dominant[0] if dominant[1] > 0 else row.get('Position_Primary', 'Unknown')
                return row.get('Position_Primary', 'Unknown')
            
            # Aplicar a un DataFrame temporal para calcular la posición dominante
            temp_df = pd.DataFrame(position_columns)
            position_columns['Position_Dominant'] = temp_df.apply(get_dominant_position, axis=1)
            
            # Crear grupo de posición dominante
            position_columns['Position_Dominant_Group'] = position_columns['Position_Dominant'].apply(self._get_position_group)
        
        # Para compatibilidad con el resto del código
        if 'Position_Primary' in position_columns:
            position_columns['Position_Clean'] = position_columns['Position_Primary']
            position_columns['Position_Full'] = position_columns['Position_Primary_Full']
            position_columns['Position_Group'] = position_columns['Position_Primary_Group']
        
        # Agregar todas las columnas de posición de una vez
        if position_columns:
            new_df = pd.concat([df, pd.DataFrame(position_columns, index=df.index)], axis=1)
            return new_df
        else:
            return df
    
    def _get_position_group(self, position):
        """Determina el grupo de posición (Goalkeeper, Defender, etc.)."""
        if not position or position == '' or position == 'Unknown':
            return 'Unknown'
        
        for group, positions in self.position_groups.items():
            if position in positions:
                return group
        return 'Unknown'
    
    def _process_numeric_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Procesa y limpia datos numéricos."""
        
        # Convertir columnas numéricas básicas
        for col in self.numeric_columns:
            if col in df.columns:
                # Limpiar valores especiales
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
                # Convertir porcentajes a decimal (mantener como porcentaje 0-100)
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
            if max_matches > 0:
                new_columns['Playing_Time_Category'] = pd.cut(
                    df['Matches played'],
                    bins=[0, max_matches*0.25, max_matches*0.5, max_matches*0.75, max_matches],
                    labels=['Rarely plays', 'Occasional', 'Regular', 'Key player'],
                    include_lowest=True
                )
            else:
                new_columns['Playing_Time_Category'] = 'No data'
        
        # Calcular eficiencia de gol
        if all(col in df.columns for col in ['Goals', 'Shots']):
            new_columns['Goal_Efficiency'] = np.where(
                df['Shots'] > 0,
                (df['Goals'] / df['Shots'] * 100).round(2),
                0
            )
        
        # Indicador de versatilidad (contando posiciones válidas)
        versatility_count = 0
        if 'Position_Primary' in df.columns:
            versatility_count += (df['Position_Primary'].notna() & (df['Position_Primary'] != '')).astype(int)
        if 'Position_Secondary' in df.columns:
            versatility_count += (df['Position_Secondary'].notna() & (df['Position_Secondary'] != '')).astype(int)
        if 'Position_Third' in df.columns:
            versatility_count += (df['Position_Third'].notna() & (df['Position_Third'] != '')).astype(int)
        
        if isinstance(versatility_count, pd.Series):
            new_columns['Position_Versatility'] = versatility_count
        
        # Indicador de juventud del equipo
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
            top_scorers_df = df.nlargest(10, 'Goals')[['Player', 'Team', 'Goals']]
            # Convertir explícitamente a lista de diccionarios
            top_scorers_list = []
            for _, row in top_scorers_df.iterrows():
                top_scorers_list.append({
                    'Player': str(row['Player']),
                    'Team': str(row['Team']),
                    'Goals': int(row['Goals']) if pd.notna(row['Goals']) else 0
                })
            summary['top_scorers'] = {
                'count': len(top_scorers_list),
                'players': top_scorers_list
            }
        
        if all(col in df.columns for col in ['Assists', 'Player', 'Team']) and len(df) > 0:
            top_assisters_df = df.nlargest(10, 'Assists')[['Player', 'Team', 'Assists']]
            # Convertir explícitamente a lista de diccionarios
            top_assisters_list = []
            for _, row in top_assisters_df.iterrows():
                top_assisters_list.append({
                    'Player': str(row['Player']),
                    'Team': str(row['Team']),
                    'Assists': int(row['Assists']) if pd.notna(row['Assists']) else 0
                })
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