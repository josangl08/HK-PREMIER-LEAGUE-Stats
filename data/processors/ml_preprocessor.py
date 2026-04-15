# ABOUTME: Feature engineering pipeline for ML models (clustering, prediction, similarity).
# ABOUTME: Implements temporal features, positional z-scores, benchmarking deltas, and composite metrics.

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Projection model constants ─────────────────────────────────────────────────

# Canonical feature set for season-to-season projection models.
# Union of all CAREER_ARC_ALL_METRICS across positions + core stats.
# Missing columns are filled with 0 at training and inference time.
_PROJECTION_FEATURE_METRICS: List[str] = [
    # Core
    "Goals", "Assists", "Minutes played", "Yellow cards",
    # Attacking
    "xG", "xA", "Shots on target, %", "Goal conversion, %",
    "Successful dribbles, %", "Crosses per 90",
    # Midfield
    "Accurate passes, %", "Key passes per 90",
    # Defensive
    "PAdj interceptions per 90", "Defensive duels won, %",
    "Aerial duels won, %", "Shots blocked per 90",
    # Goalkeeper
    "Prevented goals", "Save rate, %", "Clean sheets", "xG against per 90",
]

# Position group → 4-bucket one-hot key
_POS_GROUP_TO_BUCKET: Dict[str, str] = {
    "Goalkeeper": "GK",
    "Defender": "DEF",
    "Midfielder": "MID",
    "Winger": "MID",
    "Forward": "FWD",
}
_POS_BUCKETS: List[str] = ["GK", "DEF", "MID", "FWD"]


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
        new_cols: Dict[str, pd.Series] = {}
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
        pos_bucket = self._map_position_bucket(df)
        new_cols: Dict[str, pd.Series] = {}
        
        for col in metrics:
            if col not in df.columns:
                logger.warning(f"compute_positional_zscores: column '{col}' not found, skipping.")
                continue
            # Store in dict to avoid fragmentation
            new_cols[f"{col}_zscore_positional"] = df.groupby(pos_bucket)[col].transform(
                lambda g: (g - g.mean()) / g.std() if len(g) >= 2 else pd.Series(0.0, index=g.index)
            )
            
        if new_cols:
            df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
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
        pos_bucket = self._map_position_bucket(df)
        new_cols: Dict[str, pd.Series] = {}
        
        for col in metrics:
            if col not in df.columns:
                logger.warning(f"compute_benchmark_deltas: column '{col}' not found, skipping.")
                continue
            league_mean = df[col].mean()
            new_cols[f"{col}_delta_league_avg"] = df[col] - league_mean

            team_mean = df.groupby("Team")[col].transform("mean")
            new_cols[f"{col}_delta_team_avg"] = df[col] - team_mean

            pos_league_mean = df.groupby(pos_bucket)[col].transform("mean")
            new_cols[f"{col}_delta_positional_league_avg"] = df[col] - pos_league_mean

            pos_team_mean = df.groupby(["Team", pos_bucket])[col].transform("mean")
            new_cols[f"{col}_delta_positional_team_avg"] = df[col] - pos_team_mean

        if new_cols:
            df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
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

        # Column name aliases — match exactly what HongKongDataProcessor produces
        goals = _get_col(["Goals", "goals", "Goals_Scored"])
        assists = _get_col(["Assists", "assists"])
        xg = _get_col(["xG", "Expected_Goals", "expected_goals", "xGoals"])
        interceptions = _get_col(["Interceptions per 90", "Interceptions", "interceptions", "PAdj Interceptions"])
        duels_won_pct = _get_col(["Duels won, %", "Duels_Won_Pct", "duels_won_pct", "Duel_Win_Pct"])
        tackles = _get_col(["Sliding tackles per 90", "PAdj Sliding tackles", "Tackles per 90", "Tackles", "tackles"])
        yellow_cards = _get_col(["Yellow cards", "Yellow_Cards", "yellow_cards", "Yellows"])

        # efficiency_index: clamp xG to minimum 0.1 before dividing
        xg_safe = xg.clip(lower=0.1)
        df["efficiency_index"] = ((goals + assists) / xg_safe).clip(0, 5)

        # defensive_wall
        df["defensive_wall"] = interceptions + duels_won_pct * tackles - yellow_cards

        return df

    def build_projection_pairs(
        self,
        player_records: List[Dict],
        target_metrics: Optional[List[str]] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, np.ndarray]]:
        """
        Builds season-to-season supervised training pairs for projection models.

        For each player record with ≥2 consecutive seasons, creates a feature row
        from season N and a target value from season N+1.

        Args:
            player_records: List of dicts with keys:
                - ``history_df``: pd.DataFrame (Season column + stat columns)
                - ``pos_group``: str (e.g. "Forward", "Defender")
                - ``birth_year``: Optional[int]
            target_metrics: Metrics to use as targets. Defaults to _PROJECTION_FEATURE_METRICS.

        Returns:
            Tuple of (X_df, y_dict) where:
            - X_df has one row per season-to-season transition
            - y_dict maps each target metric to a float array of next-season values
        """
        if target_metrics is None:
            target_metrics = _PROJECTION_FEATURE_METRICS

        feature_cols = (
            _PROJECTION_FEATURE_METRICS
            + [f"{m}_delta1" for m in _PROJECTION_FEATURE_METRICS]
            + [f"{m}_slope3" for m in _PROJECTION_FEATURE_METRICS]
            + [f"pos_{b}" for b in _POS_BUCKETS]
            + ["age_at_next", "age_at_next_sq", "is_peak_age"]
        )

        x_rows: List[Dict] = []
        y_rows: Dict[str, List[float]] = {m: [] for m in target_metrics}

        for record in player_records:
            history_df = record.get("history_df")
            pos_group = record.get("pos_group", "Midfielder")
            birth_year: Optional[int] = record.get("birth_year")

            if history_df is None or len(history_df) < 2:
                continue

            df = history_df.sort_values("Season").reset_index(drop=True)
            bucket = _POS_GROUP_TO_BUCKET.get(pos_group, "MID")

            for i in range(len(df) - 1):
                season_n = df.iloc[i]
                season_n1 = df.iloc[i + 1]

                row: Dict = {}
                for m in _PROJECTION_FEATURE_METRICS:
                    val_n = float(season_n.get(m, None) or 0) if season_n.get(m, None) is not None and not pd.isna(season_n.get(m, None)) else 0.0
                    row[m] = val_n

                    # Delta: change from previous season (momentum signal)
                    if i > 0:
                        val_prev = float(df.iloc[i - 1].get(m, None) or 0) if df.iloc[i - 1].get(m, None) is not None and not pd.isna(df.iloc[i - 1].get(m, None)) else 0.0
                        row[f"{m}_delta1"] = val_n - val_prev
                    else:
                        row[f"{m}_delta1"] = 0.0

                    # Slope: trend direction over last 3 seasons
                    if i >= 2:
                        _vals = [float(df.iloc[j].get(m, None) or 0) if df.iloc[j].get(m, None) is not None and not pd.isna(df.iloc[j].get(m, None)) else 0.0 for j in range(i - 2, i + 1)]
                        _x = np.arange(3, dtype=np.float64)
                        row[f"{m}_slope3"] = float(np.polyfit(_x, np.array(_vals, dtype=np.float64), 1)[0])
                    elif i >= 1:
                        val_prev = float(df.iloc[i - 1].get(m, None) or 0) if df.iloc[i - 1].get(m, None) is not None and not pd.isna(df.iloc[i - 1].get(m, None)) else 0.0
                        row[f"{m}_slope3"] = val_n - val_prev
                    else:
                        row[f"{m}_slope3"] = 0.0

                # Position one-hot encoding
                for b in _POS_BUCKETS:
                    row[f"pos_{b}"] = 1.0 if bucket == b else 0.0

                # Age features (linear + quadratic for age curve + peak flag)
                if birth_year:
                    try:
                        next_year = int(str(season_n1["Season"])[:4])
                        age = float(next_year - birth_year)
                        row["age_at_next"] = age
                        row["age_at_next_sq"] = age ** 2
                        row["is_peak_age"] = 1.0 if 24 <= age <= 28 else 0.0
                    except (ValueError, TypeError):
                        row["age_at_next"] = 0.0
                        row["age_at_next_sq"] = 0.0
                        row["is_peak_age"] = 0.0
                else:
                    row["age_at_next"] = 0.0
                    row["age_at_next_sq"] = 0.0
                    row["is_peak_age"] = 0.0

                x_rows.append(row)

                for m in target_metrics:
                    val = season_n1.get(m, None)
                    y_rows[m].append(
                        float(val) if val is not None and not pd.isna(val) else float("nan")
                    )

        if not x_rows:
            logger.warning("build_projection_pairs: no valid transition pairs built.")
            return (
                pd.DataFrame(columns=feature_cols),
                {m: np.array([], dtype=np.float64) for m in target_metrics},
            )

        X_df = pd.DataFrame(x_rows, columns=feature_cols).fillna(0.0)
        y_dict = {m: np.array(vals, dtype=np.float64) for m, vals in y_rows.items()}

        logger.info(
            f"build_projection_pairs: {len(X_df)} pairs from {len(player_records)} players."
        )
        return X_df, y_dict

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
