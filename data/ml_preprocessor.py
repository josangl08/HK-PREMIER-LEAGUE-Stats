# ABOUTME: ML feature engineering pipeline for tabular player season data.
# ABOUTME: Provides lagged stats, rolling averages, positional z-scores, and time-series splits.

import numpy as np
import pandas as pd


_EXCLUDE_ALWAYS = {"player_id", "player_name", "name"}


class MLPreprocessor:
    """Transforms ETL player season DataFrames into ML-ready feature matrices."""

    # ------------------------------------------------------------------
    # Feature Engineering
    # ------------------------------------------------------------------

    def build_features(self, df, player_col, season_col):
        """Add _lag1 and _roll3 columns for all numeric metrics, grouped by player.

        Rows are ordered by season within each player group before computing shifts.
        Players with fewer than 2 seasons will have NaN in lag/roll columns.

        Args:
            df (pd.DataFrame): Input with one row per player-season.
            player_col (str): Column identifying the player.
            season_col (str): Column identifying the season (sortable strings or ints).

        Returns:
            pd.DataFrame: Original columns plus *_lag1 and *_roll3 for each numeric column.
        """
        df = df.copy()
        numeric_cols = [
            c for c in df.select_dtypes(include=[np.number]).columns
            if c not in {player_col, season_col}
        ]

        df = df.sort_values([player_col, season_col]).reset_index(drop=True)

        for col in numeric_cols:
            grouped = df.groupby(player_col)[col]
            df[f"{col}_lag1"] = grouped.shift(1)
            df[f"{col}_roll3"] = grouped.transform(
                lambda s: s.shift(1).rolling(window=3, min_periods=1).mean()
            )
            # Players with only 1 season: lag1=NaN, roll3=NaN (shift produces NaN for first row)
            # roll3 uses min_periods=1 so it fills from 1 value, but for a single-season player
            # the shift makes it NaN regardless.

        return df

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def normalize_by_position(self, df, position_col):
        """Apply per-position z-score normalization to all numeric columns.

        Groups with a single player (std=0) are set to 0.0 rather than NaN.

        Args:
            df (pd.DataFrame): Input DataFrame.
            position_col (str): Column containing player position labels.

        Returns:
            pd.DataFrame: Same shape as input with numeric columns z-scored within position.
        """
        df = df.copy()
        numeric_cols = [
            c for c in df.select_dtypes(include=[np.number]).columns
            if c != position_col
        ]

        grouped = df.groupby(position_col)
        for col in numeric_cols:
            mean = grouped[col].transform("mean")
            std = grouped[col].transform(lambda s: s.std(ddof=0))
            df[col] = np.where(std == 0, 0.0, (df[col] - mean) / std)
        return df

    # ------------------------------------------------------------------
    # Splitting
    # ------------------------------------------------------------------

    def time_series_split(self, df, season_col, test_seasons=1):
        """Split into train/test preserving temporal order (no data leakage).

        Args:
            df (pd.DataFrame): Input DataFrame.
            season_col (str): Column with season labels (sorted lexicographically or numerically).
            test_seasons (int): Number of most recent seasons to use as test set.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame]: (train_df, test_df)
        """
        seasons_sorted = sorted(df[season_col].unique())
        test_season_labels = set(seasons_sorted[-test_seasons:])
        train_mask = ~df[season_col].isin(test_season_labels)
        return df[train_mask].reset_index(drop=True), df[~train_mask].reset_index(drop=True)

    # ------------------------------------------------------------------
    # Feature Selection
    # ------------------------------------------------------------------

    def select_features(self, df, position, target):
        """Return numeric feature names relevant to the given position and target.

        Excludes identifier and metadata columns plus the target itself.

        Args:
            df (pd.DataFrame): Feature DataFrame.
            position (str): Player position (used for future positional filtering).
            target (str): Target column name to exclude from features.

        Returns:
            list[str]: Ordered list of feature column names.
        """
        excluded = _EXCLUDE_ALWAYS | {target, "season", "position", "player_id", "player_name"}
        features = [
            c for c in df.select_dtypes(include=[np.number]).columns
            if c.lower() not in {e.lower() for e in excluded} and c != target
        ]
        return features

    # ------------------------------------------------------------------
    # Imputation
    # ------------------------------------------------------------------

    def impute(self, df, strategy="median"):
        """Fill NaN values in numeric columns using the specified strategy.

        Args:
            df (pd.DataFrame): Input DataFrame (may contain NaNs from lag/roll).
            strategy (str): Imputation strategy. Currently supports 'median'.

        Returns:
            pd.DataFrame: DataFrame with no NaN values in numeric columns.
        """
        df = df.copy()
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if strategy == "median":
            df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())
        else:
            raise ValueError(f"Unknown imputation strategy: {strategy!r}")
        return df
