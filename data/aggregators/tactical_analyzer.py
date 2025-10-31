# ABOUTME: This module contains the TacticalAnalyzer class for advanced tactical metrics.
# ABOUTME: It calculates tempo, pressing intensity, and other tactical patterns from player data.

import pandas as pd
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class TacticalAnalyzer:
    """
    Analyzes tactical patterns and styles from season aggregates.
    Uses proxy metrics to estimate temporal/transitional behaviors.
    """

    def __init__(self, processed_data: pd.DataFrame):
        """
        Args:
            processed_data: Processed DataFrame from HongKongDataProcessor
                           Must contain standard Wyscout columns
        """
        self.data = processed_data
        self.validate_required_columns()

    # Tempo Analysis
    def analyze_tempo(self, group_by: str = None) -> Dict:
        """
        Compute tempo metrics (pass speed, possession flow).
        group_by: 'position', 'team', None (league-wide)
        """
        results = {}

        for group_name, group_data in self._iterate_groups(group_by):
            tempo_metrics = {
                'passes_per_90': self._safe_mean(
                    self._compute_passes_per_90(group_data)
                ),
                'possession_cycle_ratio': self._safe_mean(
                    self._compute_possession_cycles(group_data)
                ),
                'build_up_speed': self._safe_mean(
                    self._compute_build_up_speed(group_data)
                ),
                'sample_size': len(group_data)
            }
            results[group_name] = tempo_metrics

        return results

    def _compute_passes_per_90(self, data: pd.DataFrame) -> pd.Series:
        """Passes per 90 minutes (proxy for tempo)."""
        if 'Passes per 90' in data.columns:
            return pd.to_numeric(data['Passes per 90'], errors='coerce').fillna(0)
        return pd.Series([0] * len(data))

    def _compute_possession_cycles(self, data: pd.DataFrame) -> pd.Series:
        """Possession duration proxy (forward/backward pass ratio)."""
        if 'Forward passes per 90' in data.columns and 'Backward passes per 90' in data.columns:
            forward = pd.to_numeric(data['Forward passes per 90'], errors='coerce').fillna(0)
            backward = pd.to_numeric(data['Backward passes per 90'], errors='coerce').fillna(0)

            # Ratio > 1 = more forward play (faster cycles)
            # Ratio < 1 = more backward play (slower cycles)
            return forward / (backward + 1)  # +1 to avoid division by zero
        return pd.Series([0] * len(data))

    def _compute_build_up_speed(self, data: pd.DataFrame) -> pd.Series:
        """Build-up speed index (long passes + quick passes per 90)."""
        result = pd.Series(0.0, index=data.index, dtype=float)

        if 'Long passes per 90' in data.columns:
            long_passes = pd.to_numeric(data['Long passes per 90'], errors='coerce').fillna(0)
            result += long_passes

        if 'Through passes per 90' in data.columns:
            through_passes = pd.to_numeric(data['Through passes per 90'], errors='coerce').fillna(0)
            result += through_passes * 1.5  # Through passes weighted higher

        return result

    # Pressing Intensity
    def analyze_pressing_intensity(self, group_by: str = None) -> Dict:
        """
        Compute pressing intensity metrics (defensive aggression).
        group_by: 'position', 'team', None (league-wide)
        """
        results = {}

        for group_name, group_data in self._iterate_groups(group_by):
            pressing_metrics = {
                'defensive_intensity': self._safe_mean(
                    self._compute_defensive_intensity(group_data)
                ),
                'pressing_success_rate': self._safe_mean(
                    self._compute_pressing_success_proxy(group_data)
                ),
                'tackles_per_90': self._safe_mean(
                    pd.to_numeric(group_data.get('Tackles per 90', 0), errors='coerce')
                ),
                'interceptions_per_90': self._safe_mean(
                    pd.to_numeric(group_data.get('Interceptions per 90', 0), errors='coerce')
                ),
                'sample_size': len(group_data)
            }
            results[group_name] = pressing_metrics

        return results

    def _compute_ppda(self, data: pd.DataFrame) -> pd.Series:
        """
        Passes Per Defensive Action (lower = more intense).
        PPDA = Passes by opponent / Defensive actions by team

        Note: This is a simplified proxy since we don't have opponent passes.
        We use inverse of defensive actions as intensity measure.
        """
        tackles = pd.to_numeric(data.get('Tackles per 90', 0), errors='coerce').fillna(0)
        interceptions = pd.to_numeric(data.get('Interceptions per 90', 0), errors='coerce').fillna(0)

        defensive_actions = tackles + interceptions
        # Return inverse (lower defensive actions = higher PPDA = less intense pressing)
        return defensive_actions

    def _compute_defensive_intensity(self, data: pd.DataFrame) -> pd.Series:
        """Defensive actions in attacking third per 90."""
        # Proxy: Sum of all defensive actions (tackles + interceptions)
        tackles = pd.to_numeric(data.get('Tackles per 90', 0), errors='coerce').fillna(0)
        interceptions = pd.to_numeric(data.get('Interceptions per 90', 0), errors='coerce').fillna(0)

        return tackles + interceptions

    def _compute_pressing_success_proxy(self, data: pd.DataFrame) -> pd.Series:
        """Successful pressures proxy (tackles + interceptions per 90)."""
        tackles = pd.to_numeric(data.get('Tackles per 90', 0), errors='coerce').fillna(0)
        interceptions = pd.to_numeric(data.get('Interceptions per 90', 0), errors='coerce').fillna(0)
        duels_won_pct = pd.to_numeric(data.get('Defensive duels won, %', 0), errors='coerce').fillna(0)

        # Weight by success rate (duels won %)
        defensive_actions = tackles + interceptions
        return defensive_actions * (duels_won_pct / 100.0)

    # Transition Analysis
    def analyze_transitions(self, group_by: str = None) -> Dict:
        """
        Compute transition speed metrics (speed of offense/defense switches).
        group_by: 'position', 'team', None (league-wide)
        """
        results = {}

        for group_name, group_data in self._iterate_groups(group_by):
            transition_metrics = {
                'counter_press_intensity': self._safe_mean(
                    self._compute_counter_press_proxy(group_data)
                ),
                'transition_speed': self._safe_mean(
                    self._compute_transition_speed_index(group_data)
                ),
                'recovery_rate': self._safe_mean(
                    self._compute_recovery_rate(group_data)
                ),
                'sample_size': len(group_data)
            }
            results[group_name] = transition_metrics

        return results

    def _compute_counter_press_proxy(self, data: pd.DataFrame) -> pd.Series:
        """
        Counter-pressing intensity proxy.
        (Tackles + Interceptions) / Possession losses

        Note: Since we don't have possession losses directly,
        we use inverse of pass accuracy as proxy for possession losses.
        """
        tackles = pd.to_numeric(data.get('Tackles per 90', 0), errors='coerce').fillna(0)
        interceptions = pd.to_numeric(data.get('Interceptions per 90', 0), errors='coerce').fillna(0)
        pass_accuracy = pd.to_numeric(data.get('Accurate passes, %', 100), errors='coerce').fillna(100)

        defensive_actions = tackles + interceptions
        # Higher inaccuracy (100 - accuracy) suggests more possession losses
        possession_loss_proxy = (100 - pass_accuracy) / 100.0 + 0.1  # +0.1 to avoid division by zero

        return defensive_actions / possession_loss_proxy

    def _compute_transition_speed_index(self, data: pd.DataFrame) -> pd.Series:
        """
        Transition speed proxy (through-balls + quick passes / total passes).
        Higher = more direct, aggressive transitions.
        """
        through_passes = pd.to_numeric(data.get('Through passes per 90', 0), errors='coerce').fillna(0)
        long_passes = pd.to_numeric(data.get('Long passes per 90', 0), errors='coerce').fillna(0)
        total_passes = pd.to_numeric(data.get('Passes per 90', 1), errors='coerce').fillna(1)

        # Avoid division by zero
        total_passes = total_passes.replace(0, 1)

        direct_passes = through_passes + long_passes
        return (direct_passes / total_passes) * 100  # Return as percentage

    def _compute_recovery_rate(self, data: pd.DataFrame) -> pd.Series:
        """
        Defensive recovery rate proxy.
        Successful defensive actions / Defensive actions attempted
        """
        duels_won_pct = pd.to_numeric(data.get('Defensive duels won, %', 0), errors='coerce').fillna(0)

        # Return defensive duels won percentage as recovery rate proxy
        return duels_won_pct

    # Formation & Positioning
    def analyze_formation_fingerprint(self, group_by: str = None) -> Dict:
        """
        Analyze tactical formation and positioning patterns.
        group_by: 'position', 'team', None (league-wide)
        """
        results = {}

        for group_name, group_data in self._iterate_groups(group_by):
            formation_metrics = {
                'position_distribution': self._compute_position_distribution(group_data),
                'width_index': self._safe_mean(
                    self._compute_width_index(group_data)
                ),
                'full_back_involvement': self._safe_mean(
                    self._compute_full_back_involvement(group_data)
                ),
                'striker_isolation': self._safe_mean(
                    self._compute_striker_isolation_index(group_data)
                ),
                'sample_size': len(group_data)
            }
            results[group_name] = formation_metrics

        return results

    def _compute_position_distribution(self, data: pd.DataFrame) -> Dict:
        """Position spread analysis (GK, DEF, MID, FWD counts)."""
        if 'Position_Group' not in data.columns:
            return {'Goalkeeper': 0, 'Defender': 0, 'Midfielder': 0, 'Forward': 0, 'Winger': 0}

        position_counts = data['Position_Group'].value_counts().to_dict()

        # Ensure all position groups are represented
        for pos_group in ['Goalkeeper', 'Defender', 'Midfielder', 'Forward', 'Winger']:
            if pos_group not in position_counts:
                position_counts[pos_group] = 0

        return position_counts

    def _compute_width_index(self, data: pd.DataFrame) -> pd.Series:
        """
        Width utilization (wing passes / total passes).
        Higher = wide play, lower = central play.
        """
        crosses = pd.to_numeric(data.get('Crosses per 90', 0), errors='coerce').fillna(0)
        total_passes = pd.to_numeric(data.get('Passes per 90', 1), errors='coerce').fillna(1)

        # Avoid division by zero
        total_passes = total_passes.replace(0, 1)

        # Crosses as proxy for wide play
        return (crosses / total_passes) * 100  # Return as percentage

    def _compute_full_back_involvement(self, data: pd.DataFrame) -> pd.Series:
        """Full-back passes / total passes (offensive contribution)."""
        if 'Position_Group' not in data.columns:
            return pd.Series([0] * len(data))

        # Identify full-backs (Defenders with high pass volume)
        is_defender = data.get('Position_Group', '') == 'Defender'
        passes = pd.to_numeric(data.get('Passes per 90', 0), errors='coerce').fillna(0)

        # Full-backs typically have higher pass volumes than CBs
        result = pd.Series(0.0, index=data.index, dtype=float)
        result[is_defender] = passes[is_defender]

        return result

    def _compute_striker_isolation_index(self, data: pd.DataFrame) -> pd.Series:
        """
        Striker isolation proxy.
        Forward actions / Total team actions
        """
        if 'Position_Group' not in data.columns:
            return pd.Series([0] * len(data))

        # Proxy: Forwards with low pass involvement but high shots
        is_forward = data.get('Position_Group', '').isin(['Forward', 'Winger'])
        passes = pd.to_numeric(data.get('Passes per 90', 0), errors='coerce').fillna(0)
        shots = pd.to_numeric(data.get('Shots', 0), errors='coerce').fillna(0)

        # Higher shots-to-passes ratio suggests isolation (getting ball less but shooting more)
        result = pd.Series(0.0, index=data.index, dtype=float)
        passes_safe = passes.replace(0, 1)
        result[is_forward] = (shots[is_forward] / passes_safe[is_forward]) * 100

        return result

    # Utility Methods
    def get_tactical_profile(self, identifier: str,
                            level: str = 'player') -> Dict:
        """
        Get complete tactical profile for entity.
        level: 'player', 'team', 'position'
        """
        # Filter data based on level
        if level == 'player':
            filtered_data = self.data[self.data['Player'] == identifier]
            if filtered_data.empty:
                logger.warning(f"Player '{identifier}' not found")
                return {}
            profile_data = {
                'player_name': identifier,
                'team': filtered_data['Team'].iloc[0] if 'Team' in filtered_data.columns else 'Unknown',
                'position': filtered_data['Position_Group'].iloc[0] if 'Position_Group' in filtered_data.columns else 'Unknown'
            }
        elif level == 'team':
            filtered_data = self.data[self.data['Team'] == identifier]
            if filtered_data.empty:
                logger.warning(f"Team '{identifier}' not found")
                return {}
            profile_data = {
                'team_name': identifier,
                'squad_size': len(filtered_data)
            }
        elif level == 'position':
            filtered_data = self.data[self.data['Position_Group'] == identifier]
            if filtered_data.empty:
                logger.warning(f"Position '{identifier}' not found")
                return {}
            profile_data = {
                'position_name': identifier,
                'player_count': len(filtered_data)
            }
        else:
            logger.error(f"Invalid level: {level}. Must be 'player', 'team', or 'position'")
            return {}

        # Compute all tactical metrics using filtered data
        temp_analyzer = TacticalAnalyzer(filtered_data)

        profile_data.update({
            'tempo': temp_analyzer.analyze_tempo(group_by=None),
            'pressing': temp_analyzer.analyze_pressing_intensity(group_by=None),
            'transitions': temp_analyzer.analyze_transitions(group_by=None),
            'formation': temp_analyzer.analyze_formation_fingerprint(group_by=None)
        })

        return profile_data

    def validate_required_columns(self) -> bool:
        """Validate essential columns exist."""
        required = [
            'Position_Group', 'Team', 'Player',
            'Passes per 90', 'Accurate passes, %',
            'Tackles per 90', 'Interceptions per 90'
        ]
        missing = [col for col in required if col not in self.data.columns]
        if missing:
            logger.warning(f"Missing tactical columns: {missing}")
            return False
        return True

    def get_data_completeness_report(self) -> Dict:
        """Report on available metrics for calculations."""
        # Check which columns are available
        required_columns = [
            'Passes per 90', 'Accurate passes, %',
            'Forward passes per 90', 'Backward passes per 90',
            'Long passes per 90', 'Through passes per 90',
            'Tackles per 90', 'Interceptions per 90',
            'Defensive duels won, %', 'Duels won, %',
            'Crosses per 90', 'Shots', 'xG', 'Assists', 'xA',
            'Shots on target, %', 'Position_Group', 'Team', 'Player'
        ]

        available_columns = [col for col in required_columns if col in self.data.columns]
        missing_columns = [col for col in required_columns if col not in self.data.columns]

        # Calculate data completeness percentage
        completeness_pct = (len(available_columns) / len(required_columns)) * 100

        # Check null percentages for available numeric columns
        null_report = {}
        for col in available_columns:
            if col not in ['Position_Group', 'Team', 'Player']:
                null_count = self.data[col].isna().sum()
                null_pct = (null_count / len(self.data)) * 100
                null_report[col] = {
                    'null_count': int(null_count),
                    'null_percentage': round(null_pct, 2)
                }

        return {
            'total_records': len(self.data),
            'completeness_percentage': round(completeness_pct, 2),
            'available_columns': available_columns,
            'missing_columns': missing_columns,
            'null_analysis': null_report,
            'capabilities': {
                'tempo_analysis': 'Passes per 90' in available_columns,
                'pressing_analysis': 'Tackles per 90' in available_columns and 'Interceptions per 90' in available_columns,
                'transition_analysis': 'Through passes per 90' in available_columns or 'Long passes per 90' in available_columns,
                'formation_analysis': 'Position_Group' in available_columns
            }
        }

    def _safe_divide(self, numerator, denominator, default=0):
        """Safe division handling zero denominators."""
        if denominator == 0 or pd.isna(denominator):
            return default
        try:
            result = float(numerator) / float(denominator)
            return 0 if pd.isna(result) else result
        except (TypeError, ValueError):
            return default

    def _safe_mean(self, series):
        """Safe mean calculation with null handling."""
        cleaned = pd.to_numeric(series, errors='coerce').dropna()
        return cleaned.mean() if len(cleaned) > 0 else 0

    def _iterate_groups(self, group_by):
        """DRY iterator for grouping logic."""
        if group_by == 'position':
            return self.data.groupby('Position_Group')
        elif group_by == 'team':
            return self.data.groupby('Team')
        else:
            return [('league', self.data)]
