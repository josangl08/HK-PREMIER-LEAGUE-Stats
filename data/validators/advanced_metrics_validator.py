# ABOUTME: This module provides the AdvancedMetricsValidator class for data quality checks.
# ABOUTME: It validates schema, handles nulls, detects outliers, and generates quality reports.

import pandas as pd
from typing import Dict, List
import logging
import numpy as np

logger = logging.getLogger(__name__)

class AdvancedMetricsValidator:
    """
    Comprehensive validation for advanced analytics calculations.
    Ensures data quality and provides detailed quality reports.
    """

    def __init__(self, processed_data: pd.DataFrame):
        """
        Args:
            processed_data: DataFrame to validate
        """
        self.data = processed_data
        self.validation_report = {}

    # Schema Validation
    def validate_schema(self, required_columns: List[str]) -> bool:
        """Validate DataFrame has required columns."""
        missing = [col for col in required_columns if col not in self.data.columns]

        if missing:
            logger.error(f"Missing required columns: {missing}")
            return False

        logger.info(f"Schema validation passed: {len(required_columns)} required columns present")
        return True

    def get_column_coverage(self) -> Dict[str, float]:
        """Report data completeness for each column (% non-null)."""
        coverage = {}

        for column in self.data.columns:
            non_null_count = self.data[column].notna().sum()
            total_count = len(self.data)

            if total_count > 0:
                coverage_pct = (non_null_count / total_count) * 100
                coverage[column] = round(coverage_pct, 2)
            else:
                coverage[column] = 0.0

        return coverage

    # Null Value Handling
    def get_null_value_strategy(self, column: str) -> str:
        """
        Determine best strategy for handling nulls.
        Returns: 'drop', 'fill_zero', 'fill_mean', 'fill_median'
        """
        if column not in self.data.columns:
            logger.warning(f"Column '{column}' not found")
            return 'drop'

        null_pct = (self.data[column].isna().sum() / len(self.data)) * 100

        # If >50% null, recommend dropping
        if null_pct > 50:
            return 'drop'

        # Explicitly handle 'Goals' to fill with zero if numeric
        if column == 'Goals':
            try:
                numeric_data = pd.to_numeric(self.data[column], errors='coerce')
                if numeric_data.notna().sum() > 0: # Check if it's actually numeric
                    return 'fill_zero'
            except:
                pass # Not numeric, continue with generic logic

        # Check if column is numeric
        try:
            numeric_data = pd.to_numeric(self.data[column], errors='coerce')
            is_numeric = numeric_data.notna().sum() > 0
        except:
            is_numeric = False

        if not is_numeric:
            # For categorical/text columns, fill with 'Unknown' or mode
            return 'fill_mode'

        # For numeric columns, check distribution
        numeric_data = pd.to_numeric(self.data[column], errors='coerce').dropna()

        if len(numeric_data) == 0:
            return 'fill_zero'

        # Check if data is sparse (many zeros)
        zero_pct = (numeric_data == 0).sum() / len(numeric_data) * 100

        if zero_pct > 30:
            return 'fill_zero'

        # Check skewness
        try:
            skewness = numeric_data.skew()
            # If highly skewed, use median
            if abs(skewness) > 1.0:
                return 'fill_median'
            else:
                return 'fill_mean'
        except:
            return 'fill_mean'

    def apply_null_handling(self, strategy: Dict[str, str]) -> pd.DataFrame:
        """
        Apply null handling strategy to DataFrame.
        strategy: {'column_name': 'strategy', ...}
        """
        df_cleaned = self.data.copy()

        for column, strat in strategy.items():
            if column not in df_cleaned.columns:
                continue

            if strat == 'drop':
                # Drop rows with null in this column
                df_cleaned = df_cleaned.dropna(subset=[column])
                logger.info(f"Dropped rows with null in '{column}'")

            elif strat == 'fill_zero':
                df_cleaned[column] = df_cleaned[column].fillna(0)
                logger.info(f"Filled nulls in '{column}' with 0")

            elif strat == 'fill_mean':
                mean_value = pd.to_numeric(df_cleaned[column], errors='coerce').mean()
                df_cleaned[column] = pd.to_numeric(df_cleaned[column], errors='coerce').fillna(mean_value)
                logger.info(f"Filled nulls in '{column}' with mean ({mean_value:.2f})")

            elif strat == 'fill_median':
                median_value = pd.to_numeric(df_cleaned[column], errors='coerce').median()
                df_cleaned[column] = pd.to_numeric(df_cleaned[column], errors='coerce').fillna(median_value)
                logger.info(f"Filled nulls in '{column}' with median ({median_value:.2f})")

            elif strat == 'fill_mode':
                mode_value = df_cleaned[column].mode()[0] if len(df_cleaned[column].mode()) > 0 else 'Unknown'
                df_cleaned[column] = df_cleaned[column].fillna(mode_value)
                logger.info(f"Filled nulls in '{column}' with mode ('{mode_value}')")

        return df_cleaned

    # Outlier Detection
    def detect_outliers(self, column: str,
                       method: str = 'iqr',
                       threshold: float = 1.5) -> List[Dict]:
        """
        Detect statistical outliers in column.
        method: 'iqr' (interquartile) or 'zscore'
        Returns list of outlier records with metadata.
        """
        if column not in self.data.columns:
            logger.warning(f"Column '{column}' not found")
            return []

        numeric_data = pd.to_numeric(self.data[column], errors='coerce')

        if numeric_data.isna().all():
            logger.warning(f"Column '{column}' has no numeric data")
            return []

        outliers = []

        if method == 'iqr':
            # Interquartile range method
            Q1 = numeric_data.quantile(0.25)
            Q3 = numeric_data.quantile(0.75)
            IQR = Q3 - Q1

            lower_bound = Q1 - (threshold * IQR)
            upper_bound = Q3 + (threshold * IQR)

            outlier_mask = (numeric_data < lower_bound) | (numeric_data > upper_bound)

            for idx in self.data[outlier_mask].index:
                outlier_value = numeric_data.loc[idx]
                if pd.notna(outlier_value):
                    outliers.append({
                        'index': int(idx),
                        'player': self.data.loc[idx, 'Player'] if 'Player' in self.data.columns else 'Unknown',
                        'team': self.data.loc[idx, 'Team'] if 'Team' in self.data.columns else 'Unknown',
                        'value': round(float(outlier_value), 3),
                        'lower_bound': round(float(lower_bound), 3),
                        'upper_bound': round(float(upper_bound), 3),
                        'method': 'IQR'
                    })

        elif method == 'zscore':
            # Z-score method
            mean = numeric_data.mean()
            std = numeric_data.std()

            if std == 0:
                return []

            z_scores = (numeric_data - mean) / std
            outlier_mask = abs(z_scores) > threshold

            for idx in self.data[outlier_mask].index:
                outlier_value = numeric_data.loc[idx]
                z_score = z_scores.loc[idx]

                if pd.notna(outlier_value) and pd.notna(z_score):
                    outliers.append({
                        'index': int(idx),
                        'player': self.data.loc[idx, 'Player'] if 'Player' in self.data.columns else 'Unknown',
                        'team': self.data.loc[idx, 'Team'] if 'Team' in self.data.columns else 'Unknown',
                        'value': round(float(outlier_value), 3),
                        'z_score': round(float(z_score), 3),
                        'mean': round(float(mean), 3),
                        'std': round(float(std), 3),
                        'method': 'Z-score'
                    })

        return outliers

    # Data Quality Checks
    def check_data_consistency(self) -> Dict:
        """
        Verify logical consistency (e.g., goals <= shots).
        Returns dict of consistency issues found.
        """
        issues = {
            'goals_vs_shots': [],
            'assists_vs_xa': [],
            'age_range': [],
            'matches_vs_minutes': []
        }

        # Check Goals <= Shots
        if 'Goals' in self.data.columns and 'Shots' in self.data.columns:
            goals = pd.to_numeric(self.data['Goals'], errors='coerce')
            shots = pd.to_numeric(self.data['Shots'], errors='coerce')

            invalid_mask = (goals > shots) & goals.notna() & shots.notna()

            for idx in self.data[invalid_mask].index:
                issues['goals_vs_shots'].append({
                    'player': self.data.loc[idx, 'Player'] if 'Player' in self.data.columns else 'Unknown',
                    'goals': int(goals.loc[idx]),
                    'shots': int(shots.loc[idx])
                })

        # Check Assists <= xA * 2 (reasonable upper bound)
        if 'Assists' in self.data.columns and 'xA' in self.data.columns:
            assists = pd.to_numeric(self.data['Assists'], errors='coerce')
            xa = pd.to_numeric(self.data['xA'], errors='coerce')

            invalid_mask = (assists > xa * 3) & assists.notna() & xa.notna() & (xa > 0)

            for idx in self.data[invalid_mask].index:
                issues['assists_vs_xa'].append({
                    'player': self.data.loc[idx, 'Player'] if 'Player' in self.data.columns else 'Unknown',
                    'assists': int(assists.loc[idx]),
                    'xA': round(float(xa.loc[idx]), 2)
                })

        # Check reasonable age range (14-50)
        if 'Age' in self.data.columns:
            age = pd.to_numeric(self.data['Age'], errors='coerce')

            invalid_mask = ((age < 14) | (age > 50)) & age.notna()

            for idx in self.data[invalid_mask].index:
                issues['age_range'].append({
                    'player': self.data.loc[idx, 'Player'] if 'Player' in self.data.columns else 'Unknown',
                    'age': int(age.loc[idx])
                })

        # Check Minutes played <= Matches played * 90
        if 'Minutes played' in self.data.columns and 'Matches played' in self.data.columns:
            minutes = pd.to_numeric(self.data['Minutes played'], errors='coerce')
            matches = pd.to_numeric(self.data['Matches played'], errors='coerce')

            invalid_mask = (minutes > matches * 120) & minutes.notna() & matches.notna()

            for idx in self.data[invalid_mask].index:
                issues['matches_vs_minutes'].append({
                    'player': self.data.loc[idx, 'Player'] if 'Player' in self.data.columns else 'Unknown',
                    'minutes': int(minutes.loc[idx]),
                    'matches': int(matches.loc[idx])
                })

        # Count total issues
        total_issues = sum(len(v) for v in issues.values())
        issues['total_issues'] = total_issues

        return issues

    def validate_metric_ranges(self) -> Dict:
        """
        Validate metrics are within logical ranges.
        E.g., accuracy % should be 0-100, not 0-1000.
        """
        range_validations = {}

        # Define expected ranges for percentage columns
        percentage_columns = [col for col in self.data.columns if '%' in col or 'percentage' in col.lower()]

        for col in percentage_columns:
            numeric_data = pd.to_numeric(self.data[col], errors='coerce').dropna()

            if len(numeric_data) == 0:
                continue

            out_of_range = ((numeric_data < 0) | (numeric_data > 100)).sum()
            min_val = numeric_data.min()
            max_val = numeric_data.max()

            range_validations[col] = {
                'expected_range': [0, 100],
                'actual_min': round(float(min_val), 2),
                'actual_max': round(float(max_val), 2),
                'out_of_range_count': int(out_of_range),
                'is_valid': out_of_range == 0
            }

        # Validate non-negative metrics (goals, assists, shots, etc.)
        non_negative_columns = ['Goals', 'Assists', 'Shots', 'xG', 'xA', 'Matches played', 'Minutes played']

        for col in non_negative_columns:
            if col not in self.data.columns:
                continue

            numeric_data = pd.to_numeric(self.data[col], errors='coerce').dropna()

            if len(numeric_data) == 0:
                continue

            negative_count = (numeric_data < 0).sum()
            min_val = numeric_data.min()

            range_validations[col] = {
                'expected_range': [0, float('inf')],
                'actual_min': round(float(min_val), 2),
                'negative_count': int(negative_count),
                'is_valid': negative_count == 0
            }

        return range_validations

    # Quality Reporting
    def generate_quality_report(self) -> Dict:
        """
        Comprehensive quality report with:
        - Completeness by column
        - Outliers detected
        - Data issues found
        - Recommendations
        """
        # Get column coverage
        coverage = self.get_column_coverage()

        # Get consistency issues
        consistency = self.check_data_consistency()

        # Get range validations
        range_validations = self.validate_metric_ranges()

        # Detect outliers in key metrics
        key_metrics = ['Goals', 'Assists', 'xG', 'xA', 'Shots', 'Passes per 90']
        outlier_summary = {}

        for metric in key_metrics:
            if metric in self.data.columns:
                outliers = self.detect_outliers(metric, method='iqr', threshold=1.5)
                if outliers:
                    outlier_summary[metric] = len(outliers)

        # Generate recommendations
        recommendations = []

        # Check for low coverage columns
        low_coverage_cols = [col for col, cov in coverage.items() if cov < 80]
        if low_coverage_cols:
            recommendations.append(f"Consider dropping or imputing {len(low_coverage_cols)} columns with <80% coverage")

        # Check for consistency issues
        if consistency.get('total_issues', 0) > 0:
            recommendations.append(f"Found {consistency['total_issues']} logical inconsistencies that need review")

        # Check for range violations
        invalid_ranges = [col for col, val in range_validations.items() if not val.get('is_valid', True)]
        if invalid_ranges:
            recommendations.append(f"Found {len(invalid_ranges)} columns with values outside expected ranges")

        # Check for excessive outliers
        high_outlier_metrics = [metric for metric, count in outlier_summary.items() if count > len(self.data) * 0.05]
        if high_outlier_metrics:
            recommendations.append(f"Metrics {high_outlier_metrics} have >5% outliers - review data quality")

        if not recommendations:
            recommendations.append("Data quality appears good - no major issues detected")

        return {
            'summary': {
                'total_records': len(self.data),
                'total_columns': len(self.data.columns),
                'completeness_score': round(sum(coverage.values()) / len(coverage), 2) if coverage else 0,
                'total_consistency_issues': consistency.get('total_issues', 0),
                'total_outlier_metrics': len(outlier_summary),
                'readiness_score': self.get_data_readiness_score()
            },
            'column_coverage': coverage,
            'consistency_checks': consistency,
            'range_validations': range_validations,
            'outlier_summary': outlier_summary,
            'recommendations': recommendations
        }

    def get_data_readiness_score(self) -> float:
        """
        Score 0-100 indicating readiness for analytics.
        0-60: Data issues present
        60-80: Acceptable, with caveats
        80+: High quality
        """
        score = 100.0

        # Factor 1: Completeness (30% weight)
        coverage = self.get_column_coverage()
        if coverage:
            avg_coverage = sum(coverage.values()) / len(coverage)
            completeness_score = (avg_coverage / 100) * 30
        else:
            completeness_score = 0

        # Factor 2: Consistency (40% weight)
        consistency = self.check_data_consistency()
        total_issues = consistency.get('total_issues', 0)
        issue_rate = total_issues / len(self.data) if len(self.data) > 0 else 0

        if issue_rate > 0.1:  # More than 10% of records have issues
            consistency_score = 0
        elif issue_rate > 0.05:  # 5-10% issues
            consistency_score = 20
        elif issue_rate > 0.01:  # 1-5% issues
            consistency_score = 30
        else:  # <1% issues
            consistency_score = 40

        # Factor 3: Range validity (30% weight)
        range_validations = self.validate_metric_ranges()
        if range_validations:
            valid_count = sum(1 for v in range_validations.values() if v.get('is_valid', True))
            range_score = (valid_count / len(range_validations)) * 30
        else:
            range_score = 30  # No validations = assume OK

        total_score = completeness_score + consistency_score + range_score

        return round(total_score, 2)
