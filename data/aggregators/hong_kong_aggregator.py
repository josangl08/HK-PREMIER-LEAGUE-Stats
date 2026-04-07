import json
import re
from pathlib import Path

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Any
import logging

from data.aggregators.tactical_analyzer import TacticalAnalyzer
from utils.efficiency_metrics import EfficiencyMetricsCalculator, PercentileRankingSystem
from data.validators.advanced_metrics_validator import AdvancedMetricsValidator

logger = logging.getLogger(__name__)

_TEAM_NAME_ALIASES = {
    "north dt.": "north district",
    "north district": "north district",
    "eastern dist.": "eastern district",
    "eastern district": "eastern district",
    "hkfc": "hong kong football club",
    "hong kong football club": "hong kong football club",
}


def _normalize_team_name_for_h2h(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return _TEAM_NAME_ALIASES.get(text, text)

class HongKongStatsAggregator:
    """
    Agregador de estadísticas para la Liga de Hong Kong.
    """

    def __init__(self, processed_data: pd.DataFrame):
        """
        Inicializa el agregador con datos procesados.

        Args:
            processed_data: DataFrame procesado por HongKongPlayerProcessor
        """
        self.data = processed_data.copy()
        self.season = processed_data['Season'].iloc[0] if 'Season' in processed_data.columns and len(processed_data) > 0 else 'Unknown'

        # Cache para optimizar consultas repetidas
        self._cache = {}

        # Inicializar logger para la clase
        self.logger = logging.getLogger(__name__)

        # Definir métricas clave por posición
        self.position_metrics = {
            'Goalkeeper': ['Save rate, %', 'Clean sheets', 'Prevented goals per 90', 'xG against per 90'],
            'Defender': ['Interceptions per 90', 'Defensive duels won, %', 'Aerial duels won, %', 'Shots blocked per 90'],
            'Midfielder': ['Assists', 'xA', 'Key passes per 90', 'Accurate passes, %'],
            'Winger': ['Goals', 'Assists', 'Dribbles per 90', 'Crosses per 90'],
            'Forward': ['Goals', 'xG', 'Shots on target, %', 'Goal conversion, %']
        }

        # Métricas generales para todos los jugadores
        self.general_metrics = [
            'Goals', 'Assists', 'Matches played', 'Minutes played',
            'Yellow cards', 'Red cards', 'Duels won, %'
        ]

        # NEW: Initialize tactical components
        self.tactical_analyzer = TacticalAnalyzer(processed_data)
        self.efficiency_calculator = EfficiencyMetricsCalculator(processed_data)
        self.percentile_system = PercentileRankingSystem(processed_data)
        self.validator = AdvancedMetricsValidator(processed_data)

        # Validate data quality (using a subset of required columns for now)
        required_cols = [
            'Position_Group', 'Team', 'Player', 'Passes per 90',
            'Tackles per 90', 'Interceptions per 90', 'xG', 'xA', 'Goals', 'Assists'
        ]
        if not self.validator.validate_schema(required_cols):
            self.logger.warning("Algunas columnas necesarias para análisis táctico o de eficiencia faltan.")

    # NEW: Tactical Methods
    def get_tactical_profile(self, identifier: str,
                            level: str = 'player') -> Dict:
        """
        Comprehensive tactical profile for player/team/position.
        Combines tempo, pressing, transitions, and formation data.
        """
        if level == 'player':
            player_data = self.data[self.data['Player'] == identifier]
            if player_data.empty:
                return {'error': f'Player {identifier} not found'}

            return {
                'tempo': self.tactical_analyzer.analyze_tempo(),
                'pressing': self.tactical_analyzer.analyze_pressing_intensity(),
                'transitions': self.tactical_analyzer.analyze_transitions(),
                'formation': self.tactical_analyzer.analyze_formation_fingerprint(),
                'player_name': identifier,
                'position': player_data.iloc[0].get('Position_Group', 'Unknown')
            }

        elif level == 'team':
            team_data = self.data[self.data['Team'] == identifier]
            if team_data.empty:
                return {'error': f'Team {identifier} not found'}

            return {
                'tempo': self.tactical_analyzer.analyze_tempo('team'),
                'pressing': self.tactical_analyzer.analyze_pressing_intensity('team'),
                'transitions': self.tactical_analyzer.analyze_transitions('team'),
                'formation': self.tactical_analyzer.analyze_formation_fingerprint('team'),
                'team_name': identifier
            }

        return {}

    def get_efficiency_metrics(self, identifier: str,
                              level: str = 'player') -> Dict:
        """Comprehensive efficiency report."""
        if level == 'player':
            # Simplified for now, will be more complex with actual implementation
            return {
                'goals_xg_ratio': self.efficiency_calculator.calculate_goals_xg_ratio(group_by=None),
                'assists_xa_ratio': self.efficiency_calculator.calculate_assists_xa_ratio(group_by=None),
                'shot_accuracy': self.efficiency_calculator.calculate_shot_accuracy(group_by=None)
            }
        elif level == 'team':
             return {
                'goals_xg_ratio': self.efficiency_calculator.calculate_goals_xg_ratio(group_by='team'),
                'assists_xa_ratio': self.efficiency_calculator.calculate_assists_xa_ratio(group_by='team'),
                'shot_accuracy': self.efficiency_calculator.calculate_shot_accuracy(group_by='team')
            }
        return {}

    def get_player_advanced_stats(self, player_name: str) -> Dict:
        """
        Complete advanced statistics for player.
        Combines existing stats with tactical and efficiency metrics.
        """
        base_stats = self.get_player_statistics(player_name)

        player_data = self.data[self.data['Player'] == player_name]
        if not player_data.empty:
            position = player_data.iloc[0].get('Position_Group', 'Unknown')

            advanced_stats = {
                **base_stats,
                'tactical_profile': {
                    'position_percentiles': self.percentile_system.get_player_percentiles(
                        player_name,
                        by_position=True
                    ),
                    'league_rankings': self.percentile_system.get_league_rankings(
                        'Goals', # Example metric
                        min_matches=5,
                        top_n=10
                    )
                },
                'efficiency_metrics': self.get_efficiency_metrics(player_name, level='player'),
                'data_quality': {
                    'completeness_score': round(
                        self.validator.get_data_readiness_score(), 1
                    ),
                    'validation_report': self.validator.generate_quality_report()
                }
            }
            return advanced_stats
        return base_stats
    
    def apply_filters(self, df: pd.DataFrame, position_filter: Optional[str] = None, age_range: Optional[List[int]] = None) -> pd.DataFrame:
        """
        Aplica filtros de posición y edad al DataFrame.
        
        Args:
            df: DataFrame a filtrar
            position_filter: Filtro de posición ('all', 'Goalkeeper', etc.)
            age_range: Lista con [min_age, max_age]
            
        Returns:
            DataFrame filtrado
        """
        filtered_df = df.copy()
        
        # Aplicar filtro de posición
        if position_filter and position_filter != 'all':
            if 'Position_Group' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['Position_Group'] == position_filter]
            elif 'Position_Primary_Group' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['Position_Primary_Group'] == position_filter]
        
        # Aplicar filtro de edad
        if age_range and len(age_range) == 2 and 'Age' in filtered_df.columns:
            min_age, max_age = age_range
            filtered_df = filtered_df[
                (filtered_df['Age'] >= min_age) & 
                (filtered_df['Age'] <= max_age)
            ]
        
        return filtered_df
    
    def get_league_statistics(self, position_filter: Optional[str] = None, age_range: Optional[List[int]] = None) -> Dict:
        """
        Genera estadísticas generales de toda la liga con filtros aplicados.
        
        Args:
            position_filter: Filtro de posición
            age_range: Rango de edad [min, max]
            
        Returns:
            Diccionario con estadísticas de la liga
        """
        cache_key = f'league_stats_{position_filter}_{age_range}'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Aplicar filtros
        filtered_data = self.apply_filters(self.data, position_filter, age_range)
        
        stats = {
            'overview': self._get_league_overview(filtered_data),
            'top_performers': self._get_top_performers(filtered_data),
            'position_analysis': self._get_position_analysis(filtered_data),
            'age_distribution': self._get_age_distribution(filtered_data),
            'team_comparison': self._get_team_comparison_summary(filtered_data)
        }
        
        self._cache[cache_key] = stats
        return stats
    
    def get_team_statistics(self, team_name: str, position_filter: Optional[str] = None, age_range: Optional[List[int]] = None) -> Dict:
        """
        Genera estadísticas específicas de un equipo con filtros aplicados.
        
        Args:
            team_name: Nombre del equipo
            position_filter: Filtro de posición
            age_range: Rango de edad [min, max]
            
        Returns:
            Diccionario con estadísticas del equipo
        """
        cache_key = f'team_stats_{team_name}_{position_filter}_{age_range}'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Filtrar por equipo primero
        team_data = self.data[self.data['Team'] == team_name]
        
        if team_data.empty:
            return {'error': f'No se encontraron datos para el equipo {team_name}'}
        
        # Aplicar filtros adicionales
        filtered_data = self.apply_filters(team_data, position_filter, age_range)
        
        stats = {
            'overview': self._get_team_overview(filtered_data, team_name),
            'squad_analysis': self._get_squad_analysis(filtered_data),
            'top_players': self._get_team_top_players(filtered_data),
            'position_breakdown': self._get_team_position_breakdown(filtered_data),
            'performance_metrics': self._get_team_performance_metrics(filtered_data),
            'league_comparison': self._get_team_league_comparison(team_name, filtered_data)
        }
        
        self._cache[cache_key] = stats
        return stats
    
    def get_player_statistics(self, player_name: str, team_name: Optional[str] = None) -> Dict:
        """
        Genera estadísticas específicas de un jugador.
        
        Args:
            player_name: Nombre del jugador
            team_name: Nombre del equipo (opcional para filtrar)
            
        Returns:
            Diccionario con estadísticas del jugador
        """
        cache_key = f'player_stats_{player_name}_{team_name or "all"}'
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Filtrar datos del jugador
        player_data = self.data[self.data['Player'] == player_name]
        if team_name:
            player_data = player_data[player_data['Team'] == team_name]
        
        if player_data.empty:
            return {'error': f'No se encontraron datos para el jugador {player_name}'}
        
        # Si hay múltiples registros, tomar el más reciente/completo
        player_record = player_data.iloc[0]
        
        stats = {
            'basic_info': self._get_player_basic_info(player_record),
            'performance_stats': self._get_player_performance_stats(player_record),
            'position_specific': self._get_player_position_specific_stats(player_record),
            'comparisons': self._get_player_comparisons(player_record),
            'percentiles': self._get_player_percentiles(player_record)
        }
        
        self._cache[cache_key] = stats
        return stats
    
    def _get_league_overview(self, data: pd.DataFrame) -> Dict:
        """Estadísticas generales de la liga."""
        total_players = len(data)
        total_teams = data['Team'].nunique()
        
        # Estadísticas agregadas
        total_goals = data['Goals'].sum() if 'Goals' in data.columns else 0
        total_assists = data['Assists'].sum() if 'Assists' in data.columns else 0
        total_matches = data['Matches played'].sum() if 'Matches played' in data.columns else 0
        total_minutes = data['Minutes played'].sum() if 'Minutes played' in data.columns else 0
        
        # Promedios
        avg_age = data['Age'].mean() if 'Age' in data.columns else 0
        avg_goals_per_player = total_goals / total_players if total_players > 0 else 0
        avg_assists_per_player = total_assists / total_players if total_players > 0 else 0
        
        return {
            'total_players': total_players,
            'total_teams': total_teams,
            'season': self.season,
            'total_goals': int(total_goals),
            'total_assists': int(total_assists),
            'total_matches_played': int(total_matches),
            'total_minutes_played': int(total_minutes),
            'average_age': round(avg_age, 1),
            'avg_goals_per_player': round(avg_goals_per_player, 2),
            'avg_assists_per_player': round(avg_assists_per_player, 2)
        }
    
    def _get_top_performers(self, data: pd.DataFrame) -> Dict:
        """Top performers de la liga en diferentes categorías."""
        performers = {}
        
        # Dividir en métodos más específicos
        performers.update(self._get_top_scorers(data))
        performers.update(self._get_top_assisters(data))
        performers.update(self._get_most_minutes_players(data))
        performers.update(self._get_best_passers(data))
        performers.update(self._get_best_dribblers(data))
        
        return performers

    def _get_top_scorers(self, data: pd.DataFrame) -> Dict:
        """Obtiene los mejores goleadores."""
        if 'Goals' not in data.columns:
            return {}
        
        top_scorers = data.nlargest(10, 'Goals')[['Player', 'Team', 'Goals', 'Position_Group']].to_dict('records')
        # Limpiar registros
        for player in top_scorers:
            player['Position_Group'] = player.get('Position_Group', 'Unknown')
        
        return {'top_scorers': top_scorers}

    def _get_top_assisters(self, data: pd.DataFrame) -> Dict:
        """Obtiene los mejores asistentes."""
        if 'Assists' not in data.columns:
            return {}
        
        top_assisters = data.nlargest(10, 'Assists')[['Player', 'Team', 'Assists', 'Position_Group']].to_dict('records')
        # Limpiar registros
        for player in top_assisters:
            player['Position_Group'] = player.get('Position_Group', 'Unknown')
        
        return {'top_assisters': top_assisters}

    def _get_most_minutes_players(self, data: pd.DataFrame) -> Dict:
        """Obtiene jugadores con más minutos."""
        if 'Minutes played' not in data.columns:
            return {}
        
        min_matches = 5  # Mínimo de partidos jugados
        eligible_players = data
        if 'Matches played' in data.columns:
            eligible_players = data[data['Matches played'] >= min_matches]
        
        most_played = eligible_players.nlargest(10, 'Minutes played')[
            ['Player', 'Team', 'Minutes played', 'Matches played']
        ].to_dict('records')
        
        return {'most_minutes': most_played}

    def _get_best_passers(self, data: pd.DataFrame) -> Dict:
        """Obtiene los mejores pasadores (con criterios mínimos)."""
        if not all(col in data.columns for col in ['Accurate passes, %', 'Matches played']):
            return {}
        
        min_matches = 5
        min_passes_per_90 = 15
        
        eligible_passers = data[
            (data['Matches played'] >= min_matches) & 
            (data.get('Passes per 90', 0) >= min_passes_per_90)
        ]
        
        if len(eligible_passers) == 0:
            return {}
        
        # Calcular pases totales
        passes_df = eligible_passers.copy()
        if 'Passes per 90' in passes_df.columns:
            passes_df['Total passes'] = (passes_df['Passes per 90'] * passes_df['Matches played']).astype(int)
        else:
            passes_df['Total passes'] = 0
        
        best_passers = passes_df.nlargest(10, 'Accurate passes, %')[
            ['Player', 'Team', 'Accurate passes, %', 'Passes per 90', 'Total passes']
        ].to_dict('records')
        
        return {'best_passers': best_passers}

    def _get_best_dribblers(self, data: pd.DataFrame) -> Dict:
        """Obtiene los mejores regateadores (con criterios mínimos)."""
        if not all(col in data.columns for col in ['Successful dribbles, %', 'Matches played']):
            return {}
        
        min_matches = 5
        min_dribbles_per_90 = 2
        
        eligible_dribblers = data[
            (data['Matches played'] >= min_matches) & 
            (data.get('Dribbles per 90', 0) >= min_dribbles_per_90)
        ]
        
        if len(eligible_dribblers) == 0:
            return {}
        
        # Calcular regates totales
        dribbles_df = eligible_dribblers.copy()
        if 'Dribbles per 90' in dribbles_df.columns:
            dribbles_df['Total dribbles'] = (dribbles_df['Dribbles per 90'] * dribbles_df['Matches played']).astype(int)
        else:
            dribbles_df['Total dribbles'] = 0
        
        best_dribblers = dribbles_df.nlargest(10, 'Successful dribbles, %')[
            ['Player', 'Team', 'Successful dribbles, %', 'Dribbles per 90', 'Total dribbles']
        ].to_dict('records')
        
        return {'best_dribblers': best_dribblers}
    
    def _get_position_analysis(self, data: pd.DataFrame) -> Dict:
        """Análisis por posición."""
        position_column = 'Position_Group'
        if position_column not in data.columns:
            # Fallback a otras columnas de posición
            if 'Position_Primary_Group' in data.columns:
                position_column = 'Position_Primary_Group'
            else:
                return {}
        
        position_stats = {}
        
        for position in data[position_column].unique():
            if pd.isna(position) or position == 'Unknown':
                continue
                
            pos_data = data[data[position_column] == position]
            
            position_stats[position] = {
                'player_count': len(pos_data),
                'avg_age': round(pos_data['Age'].mean(), 1) if 'Age' in pos_data.columns else 0,
                'total_goals': int(pos_data['Goals'].sum()) if 'Goals' in pos_data.columns else 0,
                'total_assists': int(pos_data['Assists'].sum()) if 'Assists' in pos_data.columns else 0,
                'avg_minutes': round(pos_data['Minutes played'].mean(), 0) if 'Minutes played' in pos_data.columns else 0
            }
            
            # Agregar métricas específicas por posición
            if position in self.position_metrics:
                for metric in self.position_metrics[position]:
                    if metric in pos_data.columns:
                        avg_value = pos_data[metric].mean()
                        clean_key = metric.lower().replace(" ", "_").replace(",", "").replace("%", "pct")
                        position_stats[position][f'avg_{clean_key}'] = round(avg_value, 2)
        
        return position_stats
    
    def _get_age_distribution(self, data: pd.DataFrame) -> Dict:
        """Distribución de edades simplificada."""
        if 'Age' not in data.columns or len(data) == 0:
            return {}
        
        # Crear bins de edad
        age_bins = [0, 21, 23, 25, 28, 32, 100]
        age_labels = ['U21', '21-22', '23-24', '25-27', '28-31', '32+']
        
        age_groups = pd.cut(data['Age'], bins=age_bins, labels=age_labels, include_lowest=True)
        age_distribution = age_groups.value_counts().to_dict()
        
        # Estadísticas básicas sin extracciones complejas
        stats = {
            'distribution': age_distribution,
            'youngest_player': {
                'name': data.loc[data['Age'].idxmin(), 'Player'],
                'age': int(data['Age'].min()),
                'team': data.loc[data['Age'].idxmin(), 'Team']
            },
            'oldest_player': {
                'name': data.loc[data['Age'].idxmax(), 'Player'],
                'age': int(data['Age'].max()),
                'team': data.loc[data['Age'].idxmax(), 'Team']
            },
            'median_age': float(data['Age'].median()),
            'avg_age_by_position': data.groupby('Position_Group')['Age'].mean().round(1).to_dict() if 'Position_Group' in data.columns else {}
        }
        
        return stats
    
    def _get_team_comparison_summary(self, data: pd.DataFrame) -> Dict:
        """Resumen de comparación entre equipos."""
        if 'Team' not in data.columns:
            return {}
        
        team_stats = []
        
        for team in data['Team'].unique():
            team_data = data[data['Team'] == team]
            
            team_summary = {
                'team': team,
                'players': len(team_data),
                'avg_age': round(team_data['Age'].mean(), 1) if 'Age' in team_data.columns else 0,
                'total_goals': int(team_data['Goals'].sum()) if 'Goals' in team_data.columns else 0,
                'total_assists': int(team_data['Assists'].sum()) if 'Assists' in team_data.columns else 0,
                'total_minutes': int(team_data['Minutes played'].sum()) if 'Minutes played' in team_data.columns else 0
            }
            
            # Calcular promedios per capita
            if team_summary['players'] > 0:
                team_summary['goals_per_player'] = round(team_summary['total_goals'] / team_summary['players'], 2)
                team_summary['assists_per_player'] = round(team_summary['total_assists'] / team_summary['players'], 2)
                team_summary['minutes_per_player'] = round(team_summary['total_minutes'] / team_summary['players'], 0)
            
            team_stats.append(team_summary)
        
        # Ordenar por goals totales
        team_stats.sort(key=lambda x: x['total_goals'], reverse=True)
        
        return {
            'teams': team_stats,
            'most_goals': team_stats[0] if team_stats else None,
            'youngest_team': min(team_stats, key=lambda x: x['avg_age']) if team_stats else None,
            'oldest_team': max(team_stats, key=lambda x: x['avg_age']) if team_stats else None
        }
    
    def _get_team_overview(self, team_data: pd.DataFrame, team_name: str) -> Dict:
        """Overview específico del equipo."""
        return {
            'team_name': team_name,
            'total_players': len(team_data),
            'avg_age': round(team_data['Age'].mean(), 1) if 'Age' in team_data.columns else 0,
            'total_goals': int(team_data['Goals'].sum()) if 'Goals' in team_data.columns else 0,
            'total_assists': int(team_data['Assists'].sum()) if 'Assists' in team_data.columns else 0,
            'total_minutes': int(team_data['Minutes played'].sum()) if 'Minutes played' in team_data.columns else 0,
            'total_matches': int(team_data['Matches played'].sum()) if 'Matches played' in team_data.columns else 0,
            'season': self.season
        }
    
    def _get_squad_analysis(self, team_data: pd.DataFrame) -> Dict:
        """Análisis del plantel del equipo."""
        analysis = {}
        
        # Distribución por posición
        position_column = 'Position_Group'
        if position_column in team_data.columns:
            analysis['position_distribution'] = team_data[position_column].value_counts().to_dict()
        elif 'Position_Primary_Group' in team_data.columns:
            analysis['position_distribution'] = team_data['Position_Primary_Group'].value_counts().to_dict()
        
        # Distribución por edad
        if 'Age_Category' in team_data.columns:
            analysis['age_distribution'] = team_data['Age_Category'].value_counts().to_dict()
        elif 'Age' in team_data.columns:
            analysis['age_stats'] = {
                'youngest': int(team_data['Age'].min()),
                'oldest': int(team_data['Age'].max()),
                'average': round(team_data['Age'].mean(), 1)
            }
        
        # Tiempo de juego
        if 'Playing_Time_Category' in team_data.columns:
            analysis['playing_time_distribution'] = team_data['Playing_Time_Category'].value_counts().to_dict()
        
        # Valor de mercado
        if 'Market_Value_Category' in team_data.columns:
            analysis['market_value_distribution'] = team_data['Market_Value_Category'].value_counts().to_dict()
        
        return analysis
    
    def _extract_scalar_value(self, value: Union[pd.Series, Any]) -> Any:
        """
        Extrae valor escalar de una Serie de pandas o devuelve el valor tal como está.
        """
        if hasattr(value, 'iloc') and len(value) > 0:
            return value.iloc[0]
        elif hasattr(value, 'values') and len(value) > 0:
            return value.values[0]
        else:
            return value
    
    def _get_team_top_players(self, team_data: pd.DataFrame) -> Dict:
        """Top players del equipo en diferentes métricas."""
        top_players = {}
        
        # Configuración de métricas a evaluar
        metrics_config = [
            ('top_scorer', 'Goals', 'goals', 'Goals'),
            ('top_assister', 'Assists', 'assists', 'Assists'),
            ('most_played', 'Minutes played', 'minutes', 'Minutes played'),
            ('most_valuable', 'Market value', 'value', 'Market value')
        ]
        
        for key, column, value_key, display_name in metrics_config:
            player_info = self._get_top_player_for_metric(team_data, column, value_key, display_name)
            if player_info:
                top_players[key] = player_info
        
        return top_players

    def _get_top_player_for_metric(self, team_data: pd.DataFrame, column: str, value_key: str, display_name: str) -> Optional[Dict]:
        """Obtiene el mejor jugador para una métrica específica."""
        if column not in team_data.columns or len(team_data) == 0:
            return None
        
        metric_series = team_data[column]
        if metric_series.empty or metric_series.max() <= 0:
            return None
        
        try:
            top_player_idx = metric_series.idxmax()
            top_player_row = team_data.loc[top_player_idx]
            
            player_info = {
                'name': str(top_player_row['Player']),
                value_key: int(top_player_row[column].item()),
                'position': str(top_player_row.get('Position_Group', 'Unknown'))
            }
            
            # Añadir información adicional según la métrica
            if column == 'Minutes played' and 'Matches played' in top_player_row.index:
                player_info['matches'] = int(top_player_row['Matches played'].item())
            
            return player_info
        except Exception as e:
            self.logger.warning(f"Error obteniendo top player para {display_name}: {e}")
            return None
    
    def _get_team_position_breakdown(self, team_data: pd.DataFrame) -> Dict:
        """Desglose detallado por posición del equipo."""
        position_column = 'Position_Group'
        if position_column not in team_data.columns:
            # Fallback
            if 'Position_Primary_Group' in team_data.columns:
                position_column = 'Position_Primary_Group'
            else:
                return {}
        
        breakdown = {}
        
        for position in team_data[position_column].unique():
            if pd.isna(position) or position == 'Unknown':
                continue
                
            pos_players = team_data[team_data[position_column] == position]
            
            breakdown[position] = {
                'count': len(pos_players),
                'players': pos_players[['Player', 'Age', 'Goals', 'Assists']].to_dict('records') if len(pos_players) <= 10 else [],
                'avg_age': round(pos_players['Age'].mean(), 1) if 'Age' in pos_players.columns else 0,
                'total_goals': int(pos_players['Goals'].sum()) if 'Goals' in pos_players.columns else 0,
                'total_assists': int(pos_players['Assists'].sum()) if 'Assists' in pos_players.columns else 0
            }
            
            # Agregar métricas específicas por posición
            if position in self.position_metrics:
                for metric in self.position_metrics[position]:
                    if metric in pos_players.columns:
                        avg_value = pos_players[metric].mean()
                        clean_key = metric.lower().replace(" ", "_").replace(",", "").replace("%", "pct")
                        breakdown[position][f'avg_{clean_key}'] = round(avg_value, 2)
        
        return breakdown
    
    def _get_team_performance_metrics(self, team_data: pd.DataFrame) -> Dict:
        """Métricas de performance del equipo."""
        metrics = {}
        
        # Métricas ofensivas
        offensive_metrics = ['Goals', 'Assists', 'xG', 'xA', 'Shots per 90', 'Shots on target, %']
        metrics['offensive'] = {}
        for metric in offensive_metrics:
            if metric in team_data.columns:
                total_val = team_data[metric].sum()
                avg_val = team_data[metric].mean()
                metrics['offensive'][metric] = {
                    'total': total_val,
                    'average': round(avg_val, 2),
                    'top_player': team_data.loc[team_data[metric].idxmax(), 'Player'] if team_data[metric].max() > 0 else None
                }
        
        # Métricas defensivas
        defensive_metrics = ['Defensive duels won, %', 'Aerial duels won, %', 'Interceptions per 90', 'Fouls per 90']
        metrics['defensive'] = {}
        for metric in defensive_metrics:
            if metric in team_data.columns:
                avg_val = team_data[metric].mean()
                metrics['defensive'][metric] = {
                    'average': round(avg_val, 2),
                    'top_player': team_data.loc[team_data[metric].idxmax(), 'Player'] if team_data[metric].max() > 0 else None
                }
        
        # Métricas de pase
        passing_metrics = ['Accurate passes, %', 'Forward passes per 90', 'Key passes per 90']
        metrics['passing'] = {}
        for metric in passing_metrics:
            if metric in team_data.columns:
                avg_val = team_data[metric].mean()
                metrics['passing'][metric] = {
                    'average': round(avg_val, 2),
                    'top_player': team_data.loc[team_data[metric].idxmax(), 'Player'] if team_data[metric].max() > 0 else None
                }
        
        return metrics
    
    def _get_team_league_comparison(self, team_name: str, team_data: pd.DataFrame) -> Dict:
        """Comparación del equipo con el resto de la liga."""
        comparison = {}
        
        # Comparar métricas clave
        key_metrics = ['Goals', 'Assists', 'Age', 'Minutes played']
        
        for metric in key_metrics:
            if metric in self.data.columns and metric in team_data.columns:
                team_avg = team_data[metric].mean()
                league_avg = self.data[metric].mean()
                
                comparison[metric] = {
                    'team_average': round(team_avg, 2),
                    'league_average': round(league_avg, 2),
                    'difference': round(team_avg - league_avg, 2),
                    'percentage_diff': round(((team_avg - league_avg) / league_avg) * 100, 1) if league_avg != 0 else 0
                }
        
        # Ranking del equipo en la liga
        team_totals = self.data.groupby('Team').agg({
            'Goals': 'sum',
            'Assists': 'sum',
            'Minutes played': 'sum'
        }).sort_values('Goals', ascending=False)
        
        if team_name in team_totals.index:
            comparison['rankings'] = {
                'goals_ranking': list(team_totals.index).index(team_name) + 1,
                'total_teams': len(team_totals)
            }
        
        return comparison
    
    def _get_player_basic_info(self, player_record: pd.Series) -> Dict:
        """Información básica del jugador."""
        info = {
            'name': player_record['Player'],
            'team': player_record['Team'],
            'season': self.season
        }
        
        # Campos opcionales
        optional_fields = {
            'age': 'Age',
            'position': 'Position_Clean',
            'position_group': 'Position_Group',
            'position_primary': 'Position_Primary',
            'position_secondary': 'Position_Secondary',
            'position_third': 'Position_Third',
            'height': 'Height',
            'weight': 'Weight',
            'foot': 'Foot',
            'market_value': 'Market value',
            'matches_played': 'Matches played',
            'minutes_played': 'Minutes played'
        }
        
        for key, column in optional_fields.items():
            if column in player_record.index and pd.notna(player_record[column]):
                info[key] = player_record[column]
        
        return info
    
    def _get_player_performance_stats(self, player_record: pd.Series) -> Dict:
        """Estadísticas de performance del jugador."""
        stats = {}
        
        # Métricas principales
        main_metrics = {
            'goals': 'Goals',
            'assists': 'Assists',
            'xg': 'xG',
            'xa': 'xA',
            'shots': 'Shots',
            'shots_per_90': 'Shots per 90',
            'goal_conversion_pct': 'Goal conversion, %',
            'shots_on_target_pct': 'Shots on target, %'
        }
        
        for key, column in main_metrics.items():
            if column in player_record.index and pd.notna(player_record[column]):
                stats[key] = player_record[column]
        
        # Métricas calculadas
        if 'Minutes_per_Match' in player_record.index:
            stats['minutes_per_match'] = round(player_record['Minutes_per_Match'], 1)
        
        if 'Goal_Efficiency' in player_record.index:
            stats['goal_efficiency'] = round(player_record['Goal_Efficiency'], 2)
        
        return stats
    
    def _get_player_position_specific_stats(self, player_record: pd.Series) -> Dict:
        """Estadísticas específicas de la posición del jugador."""
        position_group = player_record.get('Position_Group', 'Unknown')
        
        if position_group not in self.position_metrics:
            return {}
        
        stats = {}
        for metric in self.position_metrics[position_group]:
            if metric in player_record.index and pd.notna(player_record[metric]):
                clean_key = metric.lower().replace(' ', '_').replace(',', '').replace('%', 'pct')
                stats[clean_key] = player_record[metric]
        
        return stats
    
    def _get_player_comparisons(self, player_record: pd.Series) -> Dict:
        """Comparaciones del jugador con promedios de liga, equipo y posición."""
        comparisons = {}
        
        position_group = player_record.get('Position_Group', 'Unknown')
        team = player_record['Team']
        
        # Datos para comparación
        league_data = self.data
        team_data = self.data[self.data['Team'] == team]
        
        # Usar column apropiada para posición
        position_column = 'Position_Group'
        if position_column not in self.data.columns and 'Position_Primary_Group' in self.data.columns:
            position_column = 'Position_Primary_Group'
            position_group = player_record.get('Position_Primary_Group', 'Unknown')
        
        position_data = self.data[self.data[position_column] == position_group] if position_group != 'Unknown' else pd.DataFrame()
        
        # Métricas para comparar
        compare_metrics = ['Goals', 'Assists', 'Minutes played', 'Age']
        
        for metric in compare_metrics:
            if metric in player_record.index and metric in league_data.columns:
                player_value = player_record[metric]
                
                comparisons[metric] = {
                    'player': player_value,
                    'league_avg': round(league_data[metric].mean(), 2),
                    'team_avg': round(team_data[metric].mean(), 2) if len(team_data) > 1 else player_value,
                    'position_avg': round(position_data[metric].mean(), 2) if len(position_data) > 1 else player_value
                }
        
        return comparisons
    
    def _get_player_percentiles(self, player_record: pd.Series) -> Dict:
        """Percentiles del jugador en la liga para diferentes métricas."""
        percentiles = {}
        
        position_group = player_record.get('Position_Group', 'Unknown')
        
        # Usar datos de la misma posición para percentiles más relevantes
        position_column = 'Position_Group'
        if position_column not in self.data.columns and 'Position_Primary_Group' in self.data.columns:
            position_column = 'Position_Primary_Group'
            position_group = player_record.get('Position_Primary_Group', 'Unknown')
        
        if position_group != 'Unknown':
            comparison_data = self.data[self.data[position_column] == position_group]
        else:
            comparison_data = self.data
        
        # Métricas para calcular percentiles
        metrics_for_percentiles = ['Goals', 'Assists', 'Accurate passes, %', 'Minutes played']
        
        for metric in metrics_for_percentiles:
            if metric in player_record.index and metric in comparison_data.columns:
                player_value = player_record[metric]
                
                # Calcular percentil
                percentile = (comparison_data[metric] <= player_value).mean() * 100
                percentiles[metric] = round(percentile, 1)
        
        return percentiles
    
    def get_comparative_data_for_charts(self, level: str, identifier: Optional[str] = None) -> Dict:
        """
        Prepara datos específicamente para gráficos de Plotly.
        
        Args:
            level: 'league', 'team', or 'player'
            identifier: team_name para 'team', player_name para 'player'
            
        Returns:
            Diccionario con datos formateados para gráficos
        """
        chart_data = {}
        
        if level == 'league':
            chart_data = self._prepare_league_chart_data()
        elif level == 'team' and identifier:
            chart_data = self._prepare_team_chart_data(identifier)
        elif level == 'player' and identifier:
            chart_data = self._prepare_player_chart_data(identifier)
        
        return chart_data
    
    def _prepare_league_chart_data(self) -> Dict:
        """Prepara datos de la liga para gráficos avanzados."""
        data = {}
        
        # Datos para gráfico de barras de goles por equipo (original)
        if all(col in self.data.columns for col in ['Team', 'Goals']):
            team_goals = self.data.groupby('Team')['Goals'].sum().sort_values(ascending=False)
            data['team_goals'] = {
                'teams': team_goals.index.tolist(),
                'goals': team_goals.values.tolist()
            }
        
        # Datos para distribución de edades (original)
        if 'Age' in self.data.columns:
            age_counts = self.data['Age'].value_counts().sort_index()
            data['age_distribution'] = {
                'ages': age_counts.index.tolist(),
                'counts': age_counts.values.tolist()
            }
        
        # Datos para gráfico de dispersión goles vs asistencias (original)
        if all(col in self.data.columns for col in ['Goals', 'Assists', 'Player', 'Team']):
            data['goals_vs_assists'] = {
                'goals': self.data['Goals'].tolist(),
                'assists': self.data['Assists'].tolist(),
                'players': self.data['Player'].tolist(),
                'teams': self.data['Team'].tolist()
            }
        
        # Datos para gráfico de posiciones (original)
        position_column = 'Position_Group'
        if position_column in self.data.columns:
            pos_counts = self.data[position_column].value_counts()
            data['position_distribution'] = {
                'positions': pos_counts.index.tolist(),
                'counts': pos_counts.values.tolist()
            }
        elif 'Position_Primary_Group' in self.data.columns:
            pos_counts = self.data['Position_Primary_Group'].value_counts()
            data['position_distribution'] = {
                'positions': pos_counts.index.tolist(),
                'counts': pos_counts.values.tolist()
            }
        
        # NUEVO: Datos para radar chart de posiciones
        if position_column in self.data.columns:
            position_analysis = {}
            
            for position in self.data[position_column].unique():
                if pd.isna(position) or position == 'Unknown':
                    continue
                    
                pos_data = self.data[self.data[position_column] == position]
                player_count = len(pos_data)
                
                if player_count == 0:
                    continue
                
                # Calcular métricas por jugador
                total_goals = pos_data['Goals'].sum() if 'Goals' in pos_data.columns else 0
                total_assists = pos_data['Assists'].sum() if 'Assists' in pos_data.columns else 0
                avg_goals_per_player = total_goals / player_count
                avg_assists_per_player = total_assists / player_count
                
                # Métricas de precisión
                pass_accuracy = pos_data['Accurate passes, %'].mean() if 'Accurate passes, %' in pos_data.columns else 0
                dribble_success = pos_data['Successful dribbles, %'].mean() if 'Successful dribbles, %' in pos_data.columns else 0
                duels_won = pos_data['Duels won, %'].mean() if 'Duels won, %' in pos_data.columns else 0
                
                position_analysis[position] = {
                    'player_count': player_count,
                    'avg_goals_per_player': round(avg_goals_per_player, 2),
                    'avg_assists_per_player': round(avg_assists_per_player, 2),
                    'avg_accurate_passes_pct': round(pass_accuracy, 2),
                    'avg_successful_dribbles_pct': round(dribble_success, 2),
                    'avg_duels_won_pct': round(duels_won, 2)
                }
            
            data['position_analysis'] = position_analysis
        
        # Datos para gráfico de edad vs rendimiento
        if all(col in self.data.columns for col in ['Age', 'Goals', 'Player']):
            # Filtrar jugadores con al menos 1 gol para mejor visibilidad
            players_with_goals = self.data[self.data['Goals'] > 0]
            
            if not players_with_goals.empty:
                data['age_performance'] = {
                    'ages': players_with_goals['Age'].tolist(),
                    'goals': players_with_goals['Goals'].tolist(),
                    'players': players_with_goals['Player'].tolist(),
                    'teams': players_with_goals['Team'].tolist(),
                    'positions': players_with_goals[position_column].tolist() if position_column in players_with_goals.columns else []
                }

        # NUEVO: Datos tácticos para heatmap (tempo vs pressing por equipo)
        if 'Team' in self.data.columns:
            try:
                teams = self.data['Team'].unique()
                tactical_data = {}

                for team in teams:
                    if pd.isna(team):
                        continue

                    # Get tactical profile for team
                    team_profile = self.get_tactical_profile(team, level='team')

                    if 'error' in team_profile:
                        continue

                    # Extract tempo and pressing metrics
                    tempo_data = team_profile.get('tempo', {})
                    pressing_data = team_profile.get('pressing', {})
                    transitions_data = team_profile.get('transitions', {})
                    formation_data = team_profile.get('formation', {})

                    tactical_data[team] = {
                        'tempo_passes_per_90': tempo_data.get(
                            'passes_per_90', 0
                        ),
                        'pressing_ppda': pressing_data.get('ppda', 0),
                        'pressing_defensive_actions_att_third': (
                            pressing_data.get(
                                'defensive_actions_attacking_third_per_90', 0
                            )
                        ),
                        'transition_recovery_time': transitions_data.get(
                            'avg_recovery_time_proxy', 0
                        ),
                        'formation_wide_play_ratio': formation_data.get(
                            'wide_play_vs_central_ratio', 0
                        )
                    }

                data['tactical_fingerprints'] = tactical_data

            except Exception as e:
                logger.warning(
                    f"Error preparando datos tácticos: {e}"
                )

        return data
    
    def _prepare_team_chart_data(self, team_name: str) -> Dict:
        """Prepara datos del equipo para gráficos."""
        team_data = self.data[self.data['Team'] == team_name]
        data = {}

        # Chart 1: Team vs League Radar (6-8 key metrics)
        radar_metrics = ['Goals', 'Assists', 'Accurate passes, %', 'xG', 'Duels won, %', 'Tackles per 90']
        if all(col in team_data.columns for col in radar_metrics):
            team_values = []
            league_values = []
            valid_metrics = []

            for metric in radar_metrics:
                team_val = team_data[metric].mean()
                league_val = self.data[metric].mean()
                if not (pd.isna(team_val) or pd.isna(league_val)):
                    valid_metrics.append(metric)
                    team_values.append(float(team_val))
                    league_values.append(float(league_val))

            if valid_metrics:
                data['team_vs_league_radar'] = {
                    'metrics': valid_metrics,
                    'team_values': team_values,
                    'league_values': league_values
                }

        # Chart 2: Squad Depth by Position
        if 'Position_Group' in team_data.columns:
            position_counts = team_data['Position_Group'].value_counts().to_dict()
            position_ages = team_data.groupby('Position_Group')['Age'].mean().to_dict()
            position_minutes = team_data.groupby('Position_Group')['Minutes played'].sum().to_dict()

            data['squad_depth'] = {
                'positions': list(position_counts.keys()),
                'player_counts': list(position_counts.values()),
                'avg_ages': [position_ages.get(pos, 0) for pos in position_counts.keys()],
                'total_minutes': [position_minutes.get(pos, 0) for pos in position_counts.keys()]
            }

        # Chart 3: Player Minutes Treemap
        if all(col in team_data.columns for col in ['Minutes played', 'Player', 'Position_Group']):
            # Sort by minutes descending
            sorted_team = team_data.sort_values('Minutes played', ascending=False)

            data['player_minutes'] = {
                'players': sorted_team['Player'].tolist(),
                'minutes': sorted_team['Minutes played'].tolist(),
                'positions': sorted_team['Position_Group'].tolist(),
                'matches': sorted_team['Matches played'].tolist() if 'Matches played' in sorted_team.columns else []
            }

        # Chart 4: Tactical Fingerprint Heatmap
        try:
            # Get team-level tactical profile
            team_tactical = self.tactical_analyzer.get_tactical_profile(
                level='team',
                entity_name=team_name
            )

            if team_tactical and 'tempo' in team_tactical:
                # Extract key tactical metrics
                tactical_metrics = []
                tactical_values = []

                # Tempo metrics
                if 'passes_per_90' in team_tactical['tempo']:
                    tactical_metrics.append('Passes per 90')
                    tactical_values.append(team_tactical['tempo']['passes_per_90'])

                # Pressing metrics
                if 'ppda' in team_tactical['pressing']:
                    tactical_metrics.append('PPDA')
                    tactical_values.append(team_tactical['pressing']['ppda'])

                if 'defensive_actions_att_third' in team_tactical['pressing']:
                    tactical_metrics.append('High Press')
                    tactical_values.append(team_tactical['pressing']['defensive_actions_att_third'])

                # Formation metrics
                if 'wide_play_ratio' in team_tactical['formation']:
                    tactical_metrics.append('Wide Play')
                    tactical_values.append(team_tactical['formation']['wide_play_ratio'])

                # Transition metrics
                if 'recovery_time' in team_tactical['transitions']:
                    tactical_metrics.append('Recovery Speed')
                    tactical_values.append(team_tactical['transitions']['recovery_time'])

                if tactical_metrics:
                    data['tactical_fingerprint'] = {
                        'metrics': tactical_metrics,
                        'values': tactical_values,
                        'team_name': team_name
                    }
        except Exception as e:
            logger.warning(f"Error preparing tactical fingerprint for {team_name}: {e}")

        return data
    
    def _prepare_player_chart_data(self, player_name: str) -> Dict:
        """Prepara datos del jugador para gráficos."""
        player_data = self.data[self.data['Player'] == player_name]

        if player_data.empty:
            return {}

        player_record = player_data.iloc[0]
        data = {}

        # Get position info
        position_column = 'Position_Group'
        position_group = player_record.get(position_column, 'Unknown')

        # Fallback si no existe Position_Group
        if position_group == 'Unknown' and 'Position_Primary_Group' in player_record.index:
            position_column = 'Position_Primary_Group'
            position_group = player_record.get(position_column, 'Unknown')

        # Chart 1: Player vs Position Radar with Percentiles
        if position_group != 'Unknown' and position_group in self.position_metrics:
            position_data = self.data[self.data[position_column] == position_group]

            player_metrics = {}
            position_metrics_avg = {}
            percentile_values = {}

            for metric in self.position_metrics[position_group]:
                if metric in player_record.index and metric in position_data.columns:
                    player_val = player_record[metric]
                    player_metrics[metric] = player_val
                    position_metrics_avg[metric] = position_data[metric].mean()

                    # Calculate percentile for this metric
                    try:
                        percentile = self.percentile_system.get_player_percentile(
                            player_name, metric, by_position=True
                        )
                        if percentile is not None:
                            percentile_values[metric] = percentile
                    except Exception:
                        pass

            if player_metrics:
                data['player_vs_position_radar'] = {
                    'metrics': list(player_metrics.keys()),
                    'player_values': list(player_metrics.values()),
                    'position_avg': list(position_metrics_avg.values()),
                    'percentiles': [percentile_values.get(m, 50) for m in player_metrics.keys()]
                }

        # Chart 2: Percentile Rankings (Top 6-8 metrics)
        try:
            # Get all percentiles for player
            key_metrics = ['Goals', 'Assists', 'xG', 'xA', 'Accurate passes, %', 'Duels won, %']
            percentile_data = {}

            for metric in key_metrics:
                if metric in player_record.index:
                    percentile = self.percentile_system.get_player_percentile(
                        player_name, metric, by_position=True
                    )
                    if percentile is not None:
                        percentile_data[metric] = {
                            'percentile': percentile,
                            'value': float(player_record[metric]),
                            'position_avg': float(self.data[self.data[position_column] == position_group][metric].mean())
                        }

            if percentile_data:
                data['player_percentiles'] = percentile_data
        except Exception as e:
            logger.warning(f"Error calculating percentiles for {player_name}: {e}")

        # Chart 3: Efficiency Scatter (Goals/xG vs Assists/xA)
        try:
            efficiency_data = self.efficiency_calculator.calculate_efficiency_metrics(
                player_name=player_name
            )

            if efficiency_data and 'goals_efficiency' in efficiency_data:
                data['efficiency_scatter'] = {
                    'goals_efficiency': efficiency_data['goals_efficiency']['ratio'],
                    'assists_efficiency': efficiency_data.get('assists_efficiency', {}).get('ratio', 1.0),
                    'player_name': player_name,
                    'goals': float(player_record.get('Goals', 0)),
                    'xG': float(player_record.get('xG', 0)),
                    'assists': float(player_record.get('Assists', 0)),
                    'xA': float(player_record.get('xA', 0))
                }
        except Exception as e:
            logger.warning(f"Error calculating efficiency for {player_name}: {e}")

        # Chart 4: Position-specific Performance Heatmap
        if position_group != 'Unknown' and position_group in self.position_metrics:
            try:
                # Get all position-specific metrics
                heatmap_data = {}

                for metric in self.position_metrics[position_group]:
                    if metric in player_record.index:
                        player_val = float(player_record[metric])
                        position_avg = float(position_data[metric].mean())
                        league_avg = float(self.data[metric].mean())

                        # Calculate normalized value (0-100 scale)
                        if position_avg > 0:
                            normalized = (player_val / position_avg) * 100
                        else:
                            normalized = 0

                        heatmap_data[metric] = {
                            'player_value': player_val,
                            'position_avg': position_avg,
                            'league_avg': league_avg,
                            'normalized': min(normalized, 200)  # Cap at 200%
                        }

                if heatmap_data:
                    data['position_performance_heatmap'] = heatmap_data
            except Exception as e:
                logger.warning(f"Error preparing heatmap for {player_name}: {e}")

        return data
    
    def clear_cache(self):
        """Limpia el cache del agregador."""
        self._cache.clear()
    
    def get_available_entities(self, entity_type: str, team_name: Optional[str] = None) -> List[str]:
        """
        Método consolidado para obtener listas de entidades disponibles.
        
        Args:
            entity_type: 'teams' o 'players'
            team_name: Para filtrar jugadores por equipo (solo cuando entity_type='players')
            
        Returns:
            Lista ordenada de entidades disponibles
        """
        if entity_type == 'teams':
            if 'Team' in self.data.columns:
                return sorted(self.data['Team'].unique().tolist())
            return []
        
        elif entity_type == 'players':
            if 'Player' not in self.data.columns:
                return []
            
            if team_name:
                players = self.data[self.data['Team'] == team_name]['Player'].unique()
            else:
                players = self.data['Player'].unique()
            
            return sorted(players.tolist())
        
        else:
            raise ValueError(f"entity_type debe ser 'teams' o 'players', recibido: {entity_type}")

    def get_available_teams(self) -> List[str]:
        """Retorna lista de equipos disponibles."""
        return self.get_available_entities('teams')

    def get_available_players(self, team_name: Optional[str] = None) -> List[str]:
        """Retorna lista de jugadores disponibles."""
        return self.get_available_entities('players', team_name)


# ── Module-level helpers for timeline enrichment ──────────────────────────────

_HISTORICAL_RECORDS_DIR = Path(__file__).parent.parent / "historical_records"

# Wyscout player_id → Transfermarkt numeric ID (mirrors TM_ID_MAP in timeline_aggregator)
_WYSCOUT_TO_TM: Dict[str, str] = {
    "148891": "160182",  # José Ángel
    "125040": "146608",  # Manuel Bleda
    "355333": "339749",  # Felipe Sá
}


def get_season_summary(player_id: str, season: str) -> Dict:
    """
    Returns aggregated season stats for a player from local Transfermarkt historical records.

    Args:
        player_id: Wyscout or TM player ID.
        season: Season string, e.g. "2023-24".

    Returns:
        Dict with keys: season, pj, goals, assists, minutes,
        by_competition (list of {competition, pj, goals, assists}).
        Returns empty dict on error.
    """
    # Resolve TM ID: accept both Wyscout IDs (converted) and direct TM IDs
    tm_id = _WYSCOUT_TO_TM.get(player_id, player_id)
    record_path = _HISTORICAL_RECORDS_DIR / f"{tm_id}.json"

    if not record_path.exists():
        logger.debug(f"Historical records not found for TM ID {tm_id}")
        return {}

    try:
        data = json.loads(record_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Failed to read historical records for {tm_id}: {exc}")
        return {}

    season_data = data.get("seasons", {}).get(season)
    if not season_data:
        logger.debug(f"Season {season} not found in records for TM ID {tm_id}")
        return {}

    matches: List[Dict] = season_data.get("matches", [])
    summary = season_data.get("summary", {})

    # Aggregate by competition
    comp_stats: Dict[str, Dict] = {}
    for m in matches:
        # ONLY count as a played match if minutes > 0
        mins = int(m.get("minutes_played", 0) or 0)
        if mins <= 0:
            continue

        comp = m.get("competition", "Unknown")
        if comp not in comp_stats:
            comp_stats[comp] = {"competition": comp, "pj": 0, "goals": 0, "assists": 0}
        
        comp_stats[comp]["pj"] += 1
        comp_stats[comp]["goals"] += int(m.get("goals", 0) or 0)
        comp_stats[comp]["assists"] += int(m.get("assists", 0) or 0)

    return {
        "season": season,
        "pj": sum(c["pj"] for c in comp_stats.values()),
        "goals": summary.get("goals", 0),
        "assists": summary.get("assists", 0),
        "minutes": summary.get("minutes_played", 0),
        "by_competition": list(comp_stats.values()),
    }


def _strip_team_rank(name: str) -> str:
    """Remove ranking suffix from team name, e.g. 'Kitchee(7.)' → 'Kitchee'."""
    return re.sub(r"\s*\(\d+\.?\)\s*", "", name).strip()


def _parse_h2h_match(opponent_field: str, result: str) -> Optional[Dict]:
    """
    Parse a match from TM historical records opponent field.

    Args:
        opponent_field: e.g. "Kitchee(7.) vs Eastern(1.)" or "Eastern vs Lee Man"
        result: e.g. "2:1", "1:1", "0:3"

    Returns:
        Dict with home_team, away_team, home_score, away_score or None if unparseable.
    """
    if " vs " not in opponent_field:
        return None
    parts = opponent_field.split(" vs ", 1)
    home = _strip_team_rank(parts[0])
    away = _strip_team_rank(parts[1])

    score_match = re.match(r"(\d+)\s*:\s*(\d+)", result or "")
    if not score_match:
        return None

    return {
        "home_team": home,
        "away_team": away,
        "home_score": int(score_match.group(1)),
        "away_score": int(score_match.group(2)),
    }


def get_h2h_record(team_a: str, team_b: str, last_n: Optional[int] = None) -> Dict:
    """
    Returns head-to-head record for team_a vs team_b from local historical records.

    Scans all files in data/historical_records/ and collects unique matches
    where both teams appear. Reports W/D/L for team_a.

    Args:
        team_a: English team name (home team perspective for W/D/L).
        team_b: English team name.
        last_n: Maximum number of most recent matches to consider. `None` uses full record.

    Returns:
        Dict with wins, draws, losses (from team_a's perspective), matches_found.
    """
    team_a_lower = _normalize_team_name_for_h2h(team_a)
    team_b_lower = _normalize_team_name_for_h2h(team_b)

    # Collect unique matches keyed by (date, opponent_field) to avoid duplicates
    seen: Dict[str, Dict] = {}

    for record_path in _HISTORICAL_RECORDS_DIR.glob("*.json"):
        try:
            data = json.loads(record_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        for season_data in data.get("seasons", {}).values():
            for m in season_data.get("matches", []):
                parsed = _parse_h2h_match(m.get("opponent", ""), m.get("result", ""))
                if not parsed:
                    continue

                h_lower = _normalize_team_name_for_h2h(parsed["home_team"])
                a_lower = _normalize_team_name_for_h2h(parsed["away_team"])

                # Check if both teams are in this match
                teams_in_match = {h_lower, a_lower}
                if team_a_lower in teams_in_match and team_b_lower in teams_in_match:
                    key = f"{m.get('date','')}-{m.get('opponent','')}"
                    if key not in seen:
                        seen[key] = {**parsed, "date": m.get("date", "")}

    matches = sorted(seen.values(), key=lambda x: x.get("date", ""), reverse=True)
    if last_n is not None:
        matches = matches[:last_n]

    wins = draws = losses = 0
    for m in matches:
        h_lower = _normalize_team_name_for_h2h(m["home_team"])
        hs, as_ = m["home_score"], m["away_score"]

        if h_lower == team_a_lower:
            if hs > as_:
                wins += 1
            elif hs == as_:
                draws += 1
            else:
                losses += 1
        else:  # team_a is away
            if as_ > hs:
                wins += 1
            elif as_ == hs:
                draws += 1
            else:
                losses += 1

    return {"wins": wins, "draws": draws, "losses": losses, "matches_found": len(matches)}
