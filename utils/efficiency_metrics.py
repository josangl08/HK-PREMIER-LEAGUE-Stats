# ABOUTME: This module provides classes for calculating efficiency metrics and percentile rankings.
# ABOUTME: It includes EfficiencyMetricsCalculator and PercentileRankingSystem for advanced player analysis.

import pandas as pd
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class EfficiencyMetricsCalculator:
    """
    Calculate efficiency ratios and comparative metrics.
    Focuses on chance conversion quality and performance vs benchmarks.
    """

    def __init__(self, processed_data: pd.DataFrame):
        """
        Args:
            processed_data: Full season DataFrame
        """
        self.data = processed_data

    # Offensive Efficiency
    def calculate_goals_xg_ratio(self, group_by: str = None) -> Dict:
        """
        Goals vs Expected Goals ratio.
        > 1.0: Overperforming (clinical finishing)
        < 1.0: Underperforming (wasting chances)
        """
        results = {}

        grouped_data = self._group_data(group_by)

        for group_name, group_data in grouped_data:
            goals = pd.to_numeric(group_data.get('Goals', 0), errors='coerce').fillna(0).sum()
            xg = pd.to_numeric(group_data.get('xG', 0), errors='coerce').fillna(0).sum()

            if xg > 0:
                ratio = goals / xg
            else:
                ratio = 0 if goals == 0 else float('inf')

            results[group_name] = {
                'goals': float(goals),
                'xG': float(xg),
                'ratio': round(ratio, 3),
                'interpretation': self._interpret_xg_ratio(ratio),
                'sample_size': len(group_data)
            }

        return results

    def calculate_assists_xa_ratio(self, group_by: str = None) -> Dict:
        """
        Assists vs Expected Assists ratio.
        Indicates chance creation quality and teammate finishing.
        """
        results = {}

        grouped_data = self._group_data(group_by)

        for group_name, group_data in grouped_data:
            assists = pd.to_numeric(group_data.get('Assists', 0), errors='coerce').fillna(0).sum()
            xa = pd.to_numeric(group_data.get('xA', 0), errors='coerce').fillna(0).sum()

            if xa > 0:
                ratio = assists / xa
            else:
                ratio = 0 if assists == 0 else float('inf')

            results[group_name] = {
                'assists': float(assists),
                'xA': float(xa),
                'ratio': round(ratio, 3),
                'interpretation': self._interpret_xa_ratio(ratio),
                'sample_size': len(group_data)
            }

        return results

    # Defensive Efficiency
    def calculate_defensive_efficiency(self, group_by: str = None) -> Dict:
        """
        Defensive action success rate.
        (Successful defensive actions) / (Total defensive actions)
        """
        results = {}

        grouped_data = self._group_data(group_by)

        for group_name, group_data in grouped_data:
            tackles = pd.to_numeric(group_data.get('Tackles per 90', 0), errors='coerce').fillna(0).sum()
            interceptions = pd.to_numeric(group_data.get('Interceptions per 90', 0), errors='coerce').fillna(0).sum()
            duels_won_pct = pd.to_numeric(group_data.get('Defensive duels won, %', 0), errors='coerce').fillna(0).mean()

            total_defensive_actions = tackles + interceptions
            success_rate = duels_won_pct  # Using duels won % as proxy for success rate

            results[group_name] = {
                'total_defensive_actions': round(total_defensive_actions, 2),
                'success_rate_percentage': round(success_rate, 2),
                'tackles_per_90': round(tackles / len(group_data) if len(group_data) > 0 else 0, 2),
                'interceptions_per_90': round(interceptions / len(group_data) if len(group_data) > 0 else 0, 2),
                'sample_size': len(group_data)
            }

        return results

    # Shot Quality
    def calculate_shot_accuracy(self, group_by: str = None) -> Dict:
        """
        Shots on target / Total shots ratio.
        Higher = more clinical, lower = wasteful.
        """
        results = {}

        grouped_data = self._group_data(group_by)

        for group_name, group_data in grouped_data:
            total_shots = pd.to_numeric(group_data.get('Shots', 0), errors='coerce').fillna(0).sum()
            shots_on_target_pct = pd.to_numeric(group_data.get('Shots on target, %', 0), errors='coerce').fillna(0).mean()

            # Calculate shots on target from percentage
            shots_on_target = (total_shots * shots_on_target_pct) / 100 if total_shots > 0 else 0

            accuracy = shots_on_target_pct if total_shots > 0 else 0

            results[group_name] = {
                'total_shots': float(total_shots),
                'shots_on_target': round(shots_on_target, 2),
                'accuracy_percentage': round(accuracy, 2),
                'sample_size': len(group_data)
            }

        return results

    def calculate_xg_per_shot(self, group_by: str = None) -> Dict:
        """
        Average quality per shot (xG / Shots).
        Higher = better quality chances.
        """
        results = {}

        grouped_data = self._group_data(group_by)

        for group_name, group_data in grouped_data:
            total_shots = pd.to_numeric(group_data.get('Shots', 0), errors='coerce').fillna(0).sum()
            total_xg = pd.to_numeric(group_data.get('xG', 0), errors='coerce').fillna(0).sum()

            xg_per_shot = (total_xg / total_shots) if total_shots > 0 else 0

            results[group_name] = {
                'total_shots': float(total_shots),
                'total_xG': float(total_xg),
                'xG_per_shot': round(xg_per_shot, 3),
                'interpretation': self._interpret_xg_per_shot(xg_per_shot),
                'sample_size': len(group_data)
            }

        return results

    # Pass Completion Under Pressure
    def calculate_pass_completion_under_pressure(self,
                                                 group_by: str = None) -> Dict:
        """
        Pass accuracy in dense areas (proxy: interception rate).
        Lower interception = better under pressure performance.
        """
        results = {}

        grouped_data = self._group_data(group_by)

        for group_name, group_data in grouped_data:
            pass_accuracy = pd.to_numeric(group_data.get('Accurate passes, %', 0), errors='coerce').fillna(0).mean()
            interceptions_conceded = pd.to_numeric(group_data.get('Interceptions per 90', 0), errors='coerce').fillna(0).mean()

            # Lower interception rate + higher pass accuracy = better under pressure
            under_pressure_score = pass_accuracy - (interceptions_conceded * 2)  # Penalize interceptions

            results[group_name] = {
                'pass_accuracy': round(pass_accuracy, 2),
                'interceptions_per_90': round(interceptions_conceded, 2),
                'under_pressure_score': round(under_pressure_score, 2),
                'sample_size': len(group_data)
            }

        return results

    # Utility Methods
    def get_efficiency_profile(self, identifier: str,
                              level: str = 'player') -> Dict:
        """Comprehensive efficiency report for entity."""
        # Filter data based on level
        if level == 'player':
            filtered_data = self.data[self.data['Player'] == identifier]
            if filtered_data.empty:
                logger.warning(f"Player '{identifier}' not found")
                return {}
            profile_id = identifier
        elif level == 'team':
            filtered_data = self.data[self.data['Team'] == identifier]
            if filtered_data.empty:
                logger.warning(f"Team '{identifier}' not found")
                return {}
            profile_id = identifier
        elif level == 'position':
            filtered_data = self.data[self.data.get('Position_Group', '') == identifier]
            if filtered_data.empty:
                logger.warning(f"Position '{identifier}' not found")
                return {}
            profile_id = identifier
        else:
            logger.error(f"Invalid level: {level}")
            return {}

        # Create temporary calculator with filtered data
        temp_calc = EfficiencyMetricsCalculator(filtered_data)

        profile = {
            'identifier': profile_id,
            'level': level,
            'goals_xg_ratio': temp_calc.calculate_goals_xg_ratio(),
            'assists_xa_ratio': temp_calc.calculate_assists_xa_ratio(),
            'shot_accuracy': temp_calc.calculate_shot_accuracy(),
            'xg_per_shot': temp_calc.calculate_xg_per_shot(),
            'defensive_efficiency': temp_calc.calculate_defensive_efficiency(),
            'pass_under_pressure': temp_calc.calculate_pass_completion_under_pressure()
        }

        return profile

    def compare_to_benchmarks(self, identifier: str,
                             metric: str) -> Dict:
        """Compare player/team to position/league benchmarks."""
        player_data = self.data[self.data['Player'] == identifier]

        if player_data.empty:
            logger.warning(f"Player '{identifier}' not found")
            return {}

        position = player_data['Position_Group'].iloc[0] if 'Position_Group' in player_data.columns else None

        if not position:
            return {}

        # Get player metric value
        player_value = pd.to_numeric(player_data.get(metric, 0), errors='coerce').fillna(0).iloc[0]

        # Get position benchmark
        position_data = self.data[self.data.get('Position_Group', '') == position]
        position_mean = pd.to_numeric(position_data.get(metric, 0), errors='coerce').fillna(0).mean()
        position_std = pd.to_numeric(position_data.get(metric, 0), errors='coerce').fillna(0).std()

        # Get league benchmark
        league_mean = pd.to_numeric(self.data.get(metric, 0), errors='coerce').fillna(0).mean()
        league_std = pd.to_numeric(self.data.get(metric, 0), errors='coerce').fillna(0).std()

        # Calculate z-scores
        position_zscore = (player_value - position_mean) / position_std if position_std > 0 else 0
        league_zscore = (player_value - league_mean) / league_std if league_std > 0 else 0

        return {
            'player': identifier,
            'metric': metric,
            'player_value': round(float(player_value), 3),
            'position_benchmark': {
                'position': position,
                'mean': round(float(position_mean), 3),
                'std': round(float(position_std), 3),
                'z_score': round(float(position_zscore), 3)
            },
            'league_benchmark': {
                'mean': round(float(league_mean), 3),
                'std': round(float(league_std), 3),
                'z_score': round(float(league_zscore), 3)
            }
        }

    def detect_efficiency_outliers(self, metric: str,
                                   std_threshold: float = 2.0) -> List[str]:
        """Identify players with unusual efficiency patterns."""
        metric_values = pd.to_numeric(self.data.get(metric, 0), errors='coerce').fillna(0)

        mean_value = metric_values.mean()
        std_value = metric_values.std()

        if std_value == 0:
            return []

        # Calculate z-scores
        z_scores = (metric_values - mean_value) / std_value

        # Find outliers (beyond threshold standard deviations)
        outlier_indices = self.data[abs(z_scores) > std_threshold].index.tolist()

        outliers = []
        for idx in outlier_indices:
            player_name = self.data.loc[idx, 'Player'] if 'Player' in self.data.columns else f"Player_{idx}"
            outliers.append(player_name)

        return outliers

    # Helper Methods
    def _group_data(self, group_by: str = None):
        """Helper to group data by specified column."""
        if group_by == 'position':
            return self.data.groupby('Position_Group')
        elif group_by == 'team':
            return self.data.groupby('Team')
        elif group_by == 'player':
            return self.data.groupby('Player')
        else:
            return [('league', self.data)]

    def _interpret_xg_ratio(self, ratio: float) -> str:
        """Interpret goals/xG ratio."""
        if ratio > 1.2:
            return 'Excellent finishing (clinical)'
        elif ratio > 1.0:
            return 'Good finishing (above expected)'
        elif ratio > 0.8:
            return 'Average finishing'
        else:
            return 'Below expected finishing'

    def _interpret_xa_ratio(self, ratio: float) -> str:
        """Interpret assists/xA ratio."""
        if ratio > 1.2:
            return 'Excellent chance creation'
        elif ratio > 1.0:
            return 'Good chance creation'
        elif ratio > 0.8:
            return 'Average chance creation'
        else:
            return 'Below expected chance creation'

    def _interpret_xg_per_shot(self, xg_per_shot: float) -> str:
        """Interpret xG per shot value."""
        if xg_per_shot > 0.15:
            return 'High quality chances'
        elif xg_per_shot > 0.10:
            return 'Good quality chances'
        elif xg_per_shot > 0.05:
            return 'Average quality chances'
        else:
            return 'Low quality chances'

class PercentileRankingSystem:
    """
    Compute percentile rankings for comprehensive performance comparison.
    Optimized with aggressive caching for expensive calculations.
    """

    def __init__(self, processed_data: pd.DataFrame):
        """
        Args:
            processed_data: Full season DataFrame
        """
        self.data = processed_data
        self._percentile_cache = {}
        self._ranking_cache = {}

    # Core Percentile Methods
    def get_player_percentiles(self, player_name: str,
                               by_position: bool = True) -> Dict:
        """
        Get percentile rankings for player across key metrics.
        by_position: Compare vs same position (True) or all players (False)
        """
        player_data = self.data[self.data['Player'] == player_name]

        if player_data.empty:
            logger.warning(f"Player '{player_name}' not found")
            return {}

        position = player_data['Position_Group'].iloc[0] if 'Position_Group' in player_data.columns else None

        # Define key metrics to analyze
        key_metrics = [
            'Goals', 'Assists', 'xG', 'xA', 'Shots', 'Shots on target, %',
            'Passes per 90', 'Accurate passes, %',
            'Tackles per 90', 'Interceptions per 90',
            'Duels won, %', 'Defensive duels won, %'
        ]

        # Filter comparison data
        if by_position and position:
            comparison_data = self.data[self.data.get('Position_Group', '') == position]
        else:
            comparison_data = self.data

        percentiles = {}

        for metric in key_metrics:
            if metric not in player_data.columns or metric not in comparison_data.columns:
                continue

            player_value = pd.to_numeric(player_data[metric].iloc[0], errors='coerce')
            if pd.isna(player_value):
                continue

            # Calculate percentile rank
            metric_values = pd.to_numeric(comparison_data[metric], errors='coerce').dropna()

            if len(metric_values) > 0:
                percentile = (metric_values < player_value).sum() / len(metric_values) * 100
                percentiles[metric] = {
                    'value': round(float(player_value), 3),
                    'percentile': round(float(percentile), 2),
                    'comparison_group': position if by_position else 'league',
                    'comparison_size': len(metric_values)
                }

        return {
            'player': player_name,
            'position': position,
            'comparison_type': 'position' if by_position else 'league',
            'metrics': percentiles
        }

    def get_position_percentiles(self, position: str,
                                metric: str) -> Dict:
        """
        Get percentile distribution for metric within position.
        Returns: {10th: val, 25th: val, 50th: val, 75th: val, 90th: val}
        """
        position_data = self.data[self.data.get('Position_Group', '') == position]

        if position_data.empty or metric not in position_data.columns:
            logger.warning(f"Position '{position}' not found or metric '{metric}' not available")
            return {}

        metric_values = pd.to_numeric(position_data[metric], errors='coerce').dropna()

        if len(metric_values) == 0:
            return {}

        percentiles = {
            '10th': round(float(metric_values.quantile(0.10)), 3),
            '25th': round(float(metric_values.quantile(0.25)), 3),
            '50th': round(float(metric_values.quantile(0.50)), 3),
            '75th': round(float(metric_values.quantile(0.75)), 3),
            '90th': round(float(metric_values.quantile(0.90)), 3),
            'min': round(float(metric_values.min()), 3),
            'max': round(float(metric_values.max()), 3),
            'mean': round(float(metric_values.mean()), 3),
            'sample_size': len(metric_values)
        }

        return {
            'position': position,
            'metric': metric,
            'distribution': percentiles
        }

    def get_team_percentiles(self, team_name: str) -> Dict:
        """Get percentile rankings for team-level metrics."""
        team_data = self.data[self.data['Team'] == team_name]

        if team_data.empty:
            logger.warning(f"Team '{team_name}' not found")
            return {}

        # Aggregate team-level metrics
        team_metrics = {
            'total_goals': pd.to_numeric(team_data.get('Goals', 0), errors='coerce').sum(),
            'total_assists': pd.to_numeric(team_data.get('Assists', 0), errors='coerce').sum(),
            'avg_pass_accuracy': pd.to_numeric(team_data.get('Accurate passes, %', 0), errors='coerce').mean(),
            'total_tackles': pd.to_numeric(team_data.get('Tackles per 90', 0), errors='coerce').sum(),
            'total_interceptions': pd.to_numeric(team_data.get('Interceptions per 90', 0), errors='coerce').sum(),
            'squad_size': len(team_data)
        }

        # Calculate percentiles vs other teams
        all_teams = self.data['Team'].unique()
        team_percentiles = {}

        for metric_name, team_value in team_metrics.items():
            if metric_name == 'squad_size':
                continue

            # Get same metric for all teams
            team_values = []
            for other_team in all_teams:
                other_team_data = self.data[self.data['Team'] == other_team]

                if 'total' in metric_name:
                    col_name = metric_name.replace('total_', '').replace('_', ' ').title()
                    if 'Goals' in col_name:
                        col_name = 'Goals'
                    elif 'Assists' in col_name:
                        col_name = 'Assists'
                    elif 'Tackles' in col_name:
                        col_name = 'Tackles per 90'
                    elif 'Interceptions' in col_name:
                        col_name = 'Interceptions per 90'

                    other_value = pd.to_numeric(other_team_data.get(col_name, 0), errors='coerce').sum()
                elif 'avg' in metric_name:
                    col_name = metric_name.replace('avg_', '').replace('_', ' ').title()
                    if 'Pass Accuracy' in col_name:
                        col_name = 'Accurate passes, %'

                    other_value = pd.to_numeric(other_team_data.get(col_name, 0), errors='coerce').mean()
                else:
                    continue

                team_values.append(other_value)

            if len(team_values) > 0:
                percentile = (sum(v < team_value for v in team_values) / len(team_values)) * 100
                team_percentiles[metric_name] = {
                    'value': round(float(team_value), 3),
                    'percentile': round(float(percentile), 2)
                }

        return {
            'team': team_name,
            'metrics': team_percentiles,
            'squad_size': team_metrics['squad_size']
        }

    # Ranking Methods
    def get_position_rankings(self, position: str,
                             metric: str,
                             top_n: int = 10) -> List[Dict]:
        """
        Get top N players in position for specific metric.
        Returns ranked list with percentile position.
        """
        position_data = self.data[self.data.get('Position_Group', '') == position]

        if position_data.empty or metric not in position_data.columns:
            logger.warning(f"Position '{position}' or metric '{metric}' not available")
            return []

        # Sort by metric (descending)
        metric_values = pd.to_numeric(position_data[metric], errors='coerce')
        position_data = position_data.copy()
        position_data['_metric_value'] = metric_values

        # Drop NaN values and sort
        position_data = position_data.dropna(subset=['_metric_value'])
        position_data = position_data.sort_values('_metric_value', ascending=False)

        # Get top N
        top_players = position_data.head(top_n)

        rankings = []
        total_players = len(position_data)

        for idx, (_, row) in enumerate(top_players.iterrows(), start=1):
            percentile = ((total_players - idx) / total_players) * 100
            rankings.append({
                'rank': idx,
                'player': row['Player'] if 'Player' in row else 'Unknown',
                'team': row['Team'] if 'Team' in row else 'Unknown',
                'value': round(float(row['_metric_value']), 3),
                'percentile': round(percentile, 2)
            })

        return rankings

    def get_league_rankings(self, metric: str,
                           min_matches: int = 5,
                           top_n: int = 10) -> List[Dict]:
        """Get league-wide rankings for metric."""
        # Filter players with minimum matches
        if 'Matches played' in self.data.columns:
            qualified_data = self.data[
                pd.to_numeric(self.data['Matches played'], errors='coerce') >= min_matches
            ]
        else:
            qualified_data = self.data

        if metric not in qualified_data.columns:
            logger.warning(f"Metric '{metric}' not available")
            return []

        # Sort by metric (descending)
        metric_values = pd.to_numeric(qualified_data[metric], errors='coerce')
        qualified_data = qualified_data.copy()
        qualified_data['_metric_value'] = metric_values

        # Drop NaN values and sort
        qualified_data = qualified_data.dropna(subset=['_metric_value'])
        qualified_data = qualified_data.sort_values('_metric_value', ascending=False)

        # Get top N
        top_players = qualified_data.head(top_n)

        rankings = []
        total_players = len(qualified_data)

        for idx, (_, row) in enumerate(top_players.iterrows(), start=1):
            percentile = ((total_players - idx) / total_players) * 100
            rankings.append({
                'rank': idx,
                'player': row['Player'] if 'Player' in row else 'Unknown',
                'team': row['Team'] if 'Team' in row else 'Unknown',
                'position': row['Position_Group'] if 'Position_Group' in row else 'Unknown',
                'value': round(float(row['_metric_value']), 3),
                'percentile': round(percentile, 2),
                'matches_played': int(row['Matches played']) if 'Matches played' in row else 0
            })

        return rankings

    # Comparative Ranking
    def get_relative_ranking(self, player_name: str,
                            metric: str) -> Dict:
        """
        Get player's rank relative to peers.
        Returns: rank, percentile, min, max, mean, std
        """
        player_data = self.data[self.data['Player'] == player_name]

        if player_data.empty:
            logger.warning(f"Player '{player_name}' not found")
            return {}

        position = player_data['Position_Group'].iloc[0] if 'Position_Group' in player_data.columns else None

        if not position or metric not in self.data.columns:
            return {}

        # Get position peers
        position_data = self.data[self.data.get('Position_Group', '') == position]
        metric_values = pd.to_numeric(position_data[metric], errors='coerce').dropna()

        if len(metric_values) == 0:
            return {}

        player_value = pd.to_numeric(player_data[metric].iloc[0], errors='coerce')

        if pd.isna(player_value):
            return {}

        # Calculate rank (1-indexed, lower number = better)
        rank = (metric_values > player_value).sum() + 1
        percentile = ((metric_values < player_value).sum() / len(metric_values)) * 100

        return {
            'player': player_name,
            'position': position,
            'metric': metric,
            'value': round(float(player_value), 3),
            'rank': int(rank),
            'total_in_position': len(metric_values),
            'percentile': round(float(percentile), 2),
            'min': round(float(metric_values.min()), 3),
            'max': round(float(metric_values.max()), 3),
            'mean': round(float(metric_values.mean()), 3),
            'std': round(float(metric_values.std()), 3)
        }

    # Cache Management
    def compute_all_percentiles(self, metrics: List[str]) -> None:
        """Pre-compute all percentiles for list of metrics."""
        logger.info(f"Pre-computing percentiles for {len(metrics)} metrics...")

        positions = self.data['Position_Group'].unique() if 'Position_Group' in self.data.columns else []

        for metric in metrics:
            if metric not in self.data.columns:
                continue

            # Cache league-wide percentiles
            cache_key = f"league_{metric}"
            metric_values = pd.to_numeric(self.data[metric], errors='coerce').dropna()

            if len(metric_values) > 0:
                self._percentile_cache[cache_key] = {
                    '10th': float(metric_values.quantile(0.10)),
                    '25th': float(metric_values.quantile(0.25)),
                    '50th': float(metric_values.quantile(0.50)),
                    '75th': float(metric_values.quantile(0.75)),
                    '90th': float(metric_values.quantile(0.90))
                }

            # Cache position-specific percentiles
            for position in positions:
                position_data = self.data[self.data['Position_Group'] == position]
                position_metric_values = pd.to_numeric(position_data[metric], errors='coerce').dropna()

                if len(position_metric_values) > 0:
                    cache_key = f"{position}_{metric}"
                    self._percentile_cache[cache_key] = {
                        '10th': float(position_metric_values.quantile(0.10)),
                        '25th': float(position_metric_values.quantile(0.25)),
                        '50th': float(position_metric_values.quantile(0.50)),
                        '75th': float(position_metric_values.quantile(0.75)),
                        '90th': float(position_metric_values.quantile(0.90))
                    }

        logger.info(f"Cached {len(self._percentile_cache)} percentile distributions")

    def clear_cache(self) -> None:
        """Clear percentile cache."""
        self._percentile_cache.clear()
        self._ranking_cache.clear()
        logger.info("Cache cleared")

    def get_cache_stats(self) -> Dict:
        """Report cache hit rates and memory usage."""
        import sys

        percentile_cache_size = sys.getsizeof(self._percentile_cache)
        ranking_cache_size = sys.getsizeof(self._ranking_cache)
        total_size = percentile_cache_size + ranking_cache_size

        return {
            'percentile_cache_entries': len(self._percentile_cache),
            'ranking_cache_entries': len(self._ranking_cache),
            'total_cache_entries': len(self._percentile_cache) + len(self._ranking_cache),
            'percentile_cache_size_bytes': percentile_cache_size,
            'ranking_cache_size_bytes': ranking_cache_size,
            'total_cache_size_bytes': total_size,
            'total_cache_size_kb': round(total_size / 1024, 2)
        }
