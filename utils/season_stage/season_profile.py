# ABOUTME: Season-pure role-profile logic for the opened season stage, including feature schemas and semantic scores.
# ABOUTME: Keeps season-specific clustering and role interpretation separate from dashboard-wide and career-aggregate logic.

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


SEASON_CLUSTER_EXCLUDED_FIELDS = {
    "Market value",
    "Contract expires",
    "Team within selected timeframe",
    "Team",
    "League",
    "season_team",
    "Age",
    "Birth country",
    "Passport country",
    "Foot",
    "Height",
    "Weight",
    "On loan",
    "Wyscout id",
    "Full name",
    "Team logo",
    "besoccer_season_rating",
    "Yellow cards",
    "Red cards",
    "Yellow cards per 90",
    "Red cards per 90",
    "Fouls per 90",
    "Minutes_per_Match",
    "Age_Category",
    "efficiency_index",
    "defensive_wall",
    "PAdj Sliding tackles",
}

SEASON_CLUSTER_FEATURES_BY_POS_GROUP = {
    "Forward": [
        "Goals per 90", "xG per 90", "Shots per 90", "Shots on target, %", "Goal conversion, %",
        "Non-penalty goals per 90", "Head goals per 90", "xA per 90", "Assists per 90",
        "Touches in box per 90", "Offensive duels won, %", "Aerial duels won, %",
    ],
    "Winger": [
        "Goals per 90", "xG per 90", "Shots per 90", "Touches in box per 90", "Dribbles per 90",
        "Successful dribbles, %", "Crosses per 90", "Accurate crosses, %", "xA per 90",
        "Key passes per 90", "Progressive runs per 90",
    ],
    "Midfielder": [
        "xA per 90", "Key passes per 90", "Shot assists per 90", "Smart passes per 90",
        "Accurate smart passes, %", "Through passes per 90", "Accurate through passes, %",
        "Passes per 90", "Accurate passes, %", "Progressive passes per 90",
        "Accurate progressive passes, %", "Passes to final third per 90",
        "Accurate passes to final third, %", "Progressive runs per 90",
        "Interceptions per 90", "Defensive duels won, %",
    ],
    "Defender": [
        "Interceptions per 90", "Defensive duels per 90", "Defensive duels won, %",
        "Aerial duels per 90", "Aerial duels won, %", "Sliding tackles per 90",
        "Shots blocked per 90", "Passes per 90", "Accurate passes, %",
        "Long passes per 90", "Accurate long passes, %", "Progressive passes per 90",
        "Accurate progressive passes, %",
    ],
    "Goalkeeper": [
        "Save rate, %", "Prevented goals per 90", "xG against per 90", "Clean sheets",
        "Passes per 90", "Accurate passes, %", "Long passes per 90", "Accurate long passes, %",
        "Back passes received as GK per 90", "Exits per 90",
    ],
}

SEASON_QUADRANT_AXES_BY_POS_GROUP = {
    "Forward": {
        "x_label": "Creation",
        "y_label": "Finishing",
        "x_features": ["xA per 90", "Assists per 90", "Offensive duels won, %", "Touches in box per 90"],
        "y_features": ["Goals per 90", "xG per 90", "Shots per 90", "Shots on target, %", "Goal conversion, %"],
        "quadrants": {
            "top_left": "Creator Forward",
            "top_right": "Complete Threat",
            "bottom_left": "Support Forward",
            "bottom_right": "Box Finisher",
        },
    },
    "Winger": {
        "x_label": "Direct Threat",
        "y_label": "Creation",
        "x_features": ["Goals per 90", "xG per 90", "Shots per 90", "Touches in box per 90"],
        "y_features": ["Dribbles per 90", "Successful dribbles, %", "Crosses per 90", "Accurate crosses, %", "xA per 90", "Key passes per 90", "Progressive runs per 90"],
        "quadrants": {
            "top_left": "Creative Wide",
            "top_right": "Wide Creator",
            "bottom_left": "Support Wide",
            "bottom_right": "Direct Runner",
        },
    },
    "Midfielder": {
        "x_label": "Progression",
        "y_label": "Creation",
        "x_features": ["Passes per 90", "Accurate passes, %", "Progressive passes per 90", "Accurate progressive passes, %", "Passes to final third per 90", "Progressive runs per 90"],
        "y_features": ["xA per 90", "Key passes per 90", "Shot assists per 90", "Smart passes per 90", "Through passes per 90"],
        "quadrants": {
            "top_left": "Pure Creator",
            "top_right": "Creative Progressor",
            "bottom_left": "Support Midfielder",
            "bottom_right": "Controller / Carrier",
        },
    },
    "Defender": {
        "x_label": "Distribution",
        "y_label": "Defensive Control",
        "x_features": ["Passes per 90", "Accurate passes, %", "Long passes per 90", "Accurate long passes, %", "Progressive passes per 90"],
        "y_features": ["Interceptions per 90", "Defensive duels per 90", "Defensive duels won, %", "Aerial duels won, %", "Shots blocked per 90"],
        "quadrants": {
            "top_left": "Defensive Wall",
            "top_right": "Ball-Playing Stopper",
            "bottom_left": "Low-Involvement Defender",
            "bottom_right": "Build-Up Defender",
        },
    },
    "Goalkeeper": {
        "x_label": "Distribution",
        "y_label": "Shot-Stopping",
        "x_features": ["Passes per 90", "Accurate passes, %", "Long passes per 90", "Accurate long passes, %", "Exits per 90"],
        "y_features": ["Save rate, %", "Prevented goals per 90", "xG against per 90", "Clean sheets"],
        "quadrants": {
            "top_left": "Shot Stopper",
            "top_right": "Complete Keeper",
            "bottom_left": "Conservative Keeper",
            "bottom_right": "Build-Up Keeper",
        },
    },
}

SEASON_ROLE_LABELS_BY_POS_GROUP = {
    "Forward": ["Lethal Finisher", "Box Threat", "Creative Forward", "Target Forward"],
    "Winger": ["Direct Runner", "Wide Creator", "Inside Threat"],
    "Midfielder": ["Creative Maestro", "Progressive Midfielder", "Ball-Winning Midfielder", "Box-to-Box Engine"],
    "Defender": ["Defensive Wall", "Ball-Playing Defender", "Wide Progressor", "Aerial Enforcer"],
    "Goalkeeper": ["Shot Stopper", "Build-Up Keeper", "Sweeper Keeper"],
}


def get_season_role_feature_schema(pos_group: str) -> List[str]:
    return list(SEASON_CLUSTER_FEATURES_BY_POS_GROUP.get(pos_group, SEASON_CLUSTER_FEATURES_BY_POS_GROUP["Midfielder"]))


def filter_available_role_features(df: pd.DataFrame, pos_group: str) -> List[str]:
    schema = get_season_role_feature_schema(pos_group)
    return [feature for feature in schema if feature in df.columns and pd.api.types.is_numeric_dtype(df[feature])]


def _safe_standardize(series: pd.Series) -> pd.Series:
    std = float(series.std() or 0.0)
    if std <= 1e-8:
        return pd.Series(0.0, index=series.index)
    return (series - float(series.mean() or 0.0)) / std


def compute_semantic_axis_scores(df: pd.DataFrame, pos_group: str) -> pd.DataFrame:
    result = df.copy()
    config = SEASON_QUADRANT_AXES_BY_POS_GROUP.get(pos_group, SEASON_QUADRANT_AXES_BY_POS_GROUP["Midfielder"])

    for feature in config["x_features"] + config["y_features"]:
        if feature in result.columns:
            result[f"__z__{feature}"] = _safe_standardize(pd.to_numeric(result[feature], errors="coerce").fillna(0.0))

    x_sources = [f"__z__{feature}" for feature in config["x_features"] if f"__z__{feature}" in result.columns]
    y_sources = [f"__z__{feature}" for feature in config["y_features"] if f"__z__{feature}" in result.columns]

    result["semantic_axis_x"] = result[x_sources].mean(axis=1) if x_sources else 0.0
    result["semantic_axis_y"] = result[y_sources].mean(axis=1) if y_sources else 0.0
    return result


def _resolve_cluster_role_labels(df: pd.DataFrame, pos_group: str) -> Dict[int, str]:
    labels = SEASON_ROLE_LABELS_BY_POS_GROUP.get(pos_group, SEASON_ROLE_LABELS_BY_POS_GROUP["Midfielder"])
    by_cluster = {}
    grouped = df.groupby("cluster_id")[["semantic_axis_x", "semantic_axis_y"]].mean()
    ranked = grouped.sort_values(["semantic_axis_y", "semantic_axis_x"], ascending=False)

    for idx, cluster_id in enumerate(ranked.index.tolist()):
        by_cluster[int(cluster_id)] = labels[min(idx, len(labels) - 1)]
    return by_cluster


def compute_profile_clarity(player_vector: np.ndarray, centroids: np.ndarray) -> Dict[str, str]:
    if centroids is None or len(centroids) < 2:
        return {"label": "Low-confidence profile", "copy": "The sample is too limited to define a stable role with confidence."}

    distances = np.linalg.norm(centroids - player_vector, axis=1)
    ordered = np.sort(distances)
    if len(ordered) < 2:
        return {"label": "Low-confidence profile", "copy": "The sample is too limited to define a stable role with confidence."}
    margin = float(ordered[1] - ordered[0])
    if margin >= 0.55:
        return {"label": "Clear profile", "copy": "This season shows a well-defined role rather than a mixed profile."}
    if margin >= 0.2:
        return {"label": "Hybrid profile", "copy": "This season blends two nearby role families rather than fitting one pure role."}
    return {"label": "Low-confidence profile", "copy": "The season sample is too compressed to define a stable role with high confidence."}


def build_season_profile_context(season_df: pd.DataFrame, player_name: str, pos_group: str, season: str) -> Dict[str, Any]:
    if season_df is None or season_df.empty:
        return {
            "available": False,
            "season": season,
            "pos_group": pos_group,
            "archetype_label": f"{pos_group} Profile",
            "profile_clarity": {"label": "Low-confidence profile", "copy": "Season cohort data is not available for this role view."},
            "nearest_profiles": [],
        }
    cohort = season_df[season_df.get("Position_Group", pd.Series(dtype=str)) == pos_group].copy()
    if cohort.empty:
        cohort = season_df.copy()
    if cohort.empty:
        return {
            "available": False,
            "season": season,
            "pos_group": pos_group,
            "archetype_label": f"{pos_group} Profile",
            "profile_clarity": {"label": "Low-confidence profile", "copy": "Profile data is not available for this season."},
            "nearest_profiles": [],
        }

    feature_cols = filter_available_role_features(cohort, pos_group)
    if len(feature_cols) < 4 or len(cohort) < 3:
        return {
            "available": False,
            "season": season,
            "pos_group": pos_group,
            "archetype_label": f"{pos_group} Profile",
            "profile_clarity": {"label": "Low-confidence profile", "copy": "Not enough season cohort data is available to build a stable role profile."},
            "nearest_profiles": [],
        }

    cohort = cohort[["Player", "Team", "Season", "Position_Group"] + feature_cols].copy().reset_index(drop=True)
    cohort = compute_semantic_axis_scores(cohort, pos_group)
    X = cohort[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    labels = SEASON_ROLE_LABELS_BY_POS_GROUP.get(pos_group, SEASON_ROLE_LABELS_BY_POS_GROUP["Midfielder"])
    n_clusters = max(2, min(len(labels), len(cohort) - 1)) if len(cohort) > 2 else 2
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=20)
    cluster_ids = kmeans.fit_predict(X_scaled)
    cohort["cluster_id"] = cluster_ids
    cluster_role_labels = _resolve_cluster_role_labels(cohort, pos_group)
    cohort["cluster_label"] = cohort["cluster_id"].map(cluster_role_labels)

    player_rows = cohort[cohort["Player"] == player_name].copy()
    if player_rows.empty:
        player_rows = cohort.iloc[[0]].copy()
    player_row = player_rows.iloc[0]
    player_position = int(cohort.index[cohort["Player"] == str(player_row["Player"])][0])
    player_vector = X_scaled[player_position:player_position + 1]
    clarity = compute_profile_clarity(player_vector, kmeans.cluster_centers_)

    cohort["semantic_distance"] = np.sqrt(
        (cohort["semantic_axis_x"] - float(player_row["semantic_axis_x"])) ** 2 +
        (cohort["semantic_axis_y"] - float(player_row["semantic_axis_y"])) ** 2
    )
    nearest = cohort[cohort["Player"] != str(player_row["Player"])].sort_values("semantic_distance").head(3)

    axis_cfg = SEASON_QUADRANT_AXES_BY_POS_GROUP.get(pos_group, SEASON_QUADRANT_AXES_BY_POS_GROUP["Midfielder"])
    return {
        "available": True,
        "season": season,
        "pos_group": pos_group,
        "feature_cols": feature_cols,
        "cohort": cohort,
        "player_name": str(player_row["Player"]),
        "player_team": str(player_row.get("Team") or ""),
        "archetype_label": str(player_row.get("cluster_label") or f"{pos_group} Profile"),
        "cluster_id": int(player_row.get("cluster_id", 0) or 0),
        "profile_clarity": clarity,
        "axis_labels": {"x": axis_cfg["x_label"], "y": axis_cfg["y_label"]},
        "quadrant_labels": axis_cfg.get("quadrants", {}),
        "player_point": {
            "x": float(player_row["semantic_axis_x"]),
            "y": float(player_row["semantic_axis_y"]),
        },
        "nearest_profiles": [
            {
                "name": str(row["Player"]),
                "team": str(row.get("Team") or ""),
                "label": str(row.get("cluster_label") or ""),
                "x": float(row["semantic_axis_x"]),
                "y": float(row["semantic_axis_y"]),
            }
            for _, row in nearest.iterrows()
        ],
        "kmeans_model": kmeans,
        "scaled_matrix": X_scaled,
    }
