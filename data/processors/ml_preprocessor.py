# ABOUTME: Feature engineering pipeline for ML models (clustering, prediction, similarity).
# ABOUTME: Implements temporal features, positional z-scores, benchmarking deltas, and composite metrics.

import pandas as pd
import numpy as np
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class MLPreprocessor:
    """
    Processor for engineering ML-ready features from raw seasonal stats.
    """

    def __init__(self):
        self.position_buckets = {
            'GK': ['Goalkeeper'],
            'DEF': ['Defender'],
            'MID': ['Midfielder', 'Winger'],
            'FWD': ['Forward']
        }
        # Invert mapping for easier lookup
        self.pos_to_bucket = {
            pos: bucket
            for bucket, positions in self.position_buckets.items()
            for pos in positions
        }

    def _map_position_bucket(self, df: pd.DataFrame) -> pd.Series:
        """Map Position column to GK/DEF/MID/FWD bucket, defaulting to MID."""
        pos_col = "Position" if "Position" in df.columns else None
        if pos_col is None:
            return pd.Series("MID", index=df.index)
        return df[pos_col].map(self.pos_to_bucket).fillna("MID")

    def compute_temporal_features(self, df: pd.DataFrame, metrics: List[str]) -> pd.DataFrame:
        """
        Computes lag_1 and roll_3 for numeric metrics per player-season.

        Args:
            df: DataFrame with player stats and 'Season', 'Player' columns.
            metrics: List of numeric column names to process.

        Returns:
            DataFrame with additional lag_1 and roll_3 columns.
        """
        df = df.copy()
        df = df.sort_values(["Player", "Season"]).reset_index(drop=True)
        new_cols = {}
        for col in metrics:
            if col not in df.columns:
                logger.warning(f"compute_temporal_features: column '{col}' not found, skipping.")
                continue
            new_cols[f"{col}_lag_1"] = df.groupby("Player")[col].shift(1)
            new_cols[f"{col}_roll_3"] = (
                df.groupby("Player")[col]
                .transform(lambda s: s.rolling(3, min_periods=1).mean())
            )
        if new_cols:
            df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
        return df

    def compute_positional_zscores(self, df: pd.DataFrame, metrics: List[str]) -> pd.DataFrame:
        """
        Computes z-score per metric grouped by position bucket (GK/DEF/MID/FWD).

        Args:
            df: DataFrame with 'Position' and metric columns.
            metrics: List of numeric column names to process.

        Returns:
            DataFrame with additional *_zscore_positional columns.
        """
        df = df.copy()
        df["_pos_bucket"] = self._map_position_bucket(df)
        for col in metrics:
            if col not in df.columns:
                logger.warning(f"compute_positional_zscores: column '{col}' not found, skipping.")
                continue
            df[f"{col}_zscore_positional"] = df.groupby("_pos_bucket")[col].transform(
                lambda g: (g - g.mean()) / g.std() if len(g) >= 2 else pd.Series(0.0, index=g.index)
            )
        df.drop(columns=["_pos_bucket"], inplace=True)
        return df

    def compute_benchmark_deltas(self, df: pd.DataFrame, metrics: List[str]) -> pd.DataFrame:
        """
        Computes 4 delta types (league_avg, team_avg, positional_league_avg, positional_team_avg).

        Args:
            df: DataFrame with 'Team', 'Position' and metric columns.
            metrics: List of numeric column names to process.

        Returns:
            DataFrame with additional delta columns.
        """
        df = df.copy()
        df["_pos_bucket"] = self._map_position_bucket(df)
        for col in metrics:
            if col not in df.columns:
                logger.warning(f"compute_benchmark_deltas: column '{col}' not found, skipping.")
                continue
            league_mean = df[col].mean()
            df[f"{col}_delta_league_avg"] = df[col] - league_mean

            team_mean = df.groupby("Team")[col].transform("mean")
            df[f"{col}_delta_team_avg"] = df[col] - team_mean

            pos_league_mean = df.groupby("_pos_bucket")[col].transform("mean")
            df[f"{col}_delta_positional_league_avg"] = df[col] - pos_league_mean

            pos_team_mean = df.groupby(["Team", "_pos_bucket"])[col].transform("mean")
            df[f"{col}_delta_positional_team_avg"] = df[col] - pos_team_mean

        df.drop(columns=["_pos_bucket"], inplace=True)
        return df

    def inject_composite_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Computes efficiency_index and defensive_wall with edge case handling.

        efficiency_index = (goals + assists) / xG, clamped to [0, 5] (xG < 0.1 → clamp to 5)
        defensive_wall   = interceptions + duels_won_pct * tackles - yellow_cards

        Args:
            df: DataFrame with necessary base metrics.

        Returns:
            DataFrame with efficiency_index and defensive_wall columns.
        """
        df = df.copy()

        # Column name aliases — try multiple common names
        def _get_col(candidates, default=0.0) -> pd.Series:
            for name in candidates:
                if name in df.columns:
                    return df[name].fillna(0.0)
            logger.warning(f"inject_composite_metrics: none of {candidates} found, using {default}.")
            return pd.Series(default, index=df.index)

        goals = _get_col(["Goals", "goals", "Goals_Scored"])
        assists = _get_col(["Assists", "assists"])
        xg = _get_col(["xG", "Expected_Goals", "expected_goals", "xGoals"])
        interceptions = _get_col(["Interceptions", "interceptions"])
        duels_won_pct = _get_col(["Duels_Won_Pct", "duels_won_pct", "Duel_Win_Pct"])
        tackles = _get_col(["Tackles", "tackles"])
        yellow_cards = _get_col(["Yellow_Cards", "yellow_cards", "Yellows"])

        # efficiency_index: clamp xG to minimum 0.1 before dividing
        xg_safe = xg.clip(lower=0.1)
        df["efficiency_index"] = ((goals + assists) / xg_safe).clip(0, 5)

        # defensive_wall
        df["defensive_wall"] = interceptions + duels_won_pct * tackles - yellow_cards

        return df

    def time_series_split(self, df: pd.DataFrame, n_test_seasons: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns train/test indices by season order.

        Args:
            df: DataFrame with 'Season' column.
            n_test_seasons: Number of recent seasons to include in test set.

        Returns:
            Tuple of (train_indices, test_indices).
        """
        sorted_seasons = sorted(df["Season"].unique())
        if n_test_seasons >= len(sorted_seasons):
            raise ValueError(
                f"n_test_seasons={n_test_seasons} must be < total seasons ({len(sorted_seasons)})."
            )
        train_seasons = set(sorted_seasons[:-n_test_seasons])
        test_seasons = set(sorted_seasons[-n_test_seasons:])

        train_mask = df["Season"].isin(train_seasons)
        test_mask = df["Season"].isin(test_seasons)

        return df.index[train_mask].to_numpy(), df.index[test_mask].to_numpy()
