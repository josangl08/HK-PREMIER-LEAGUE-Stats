# ABOUTME: Clustering and dimensionality reduction (K-Means & UMAP).
# ABOUTME: Identifies player archetypes and styles based on stats.

"""
Clustering module for discovering player archetypes.
Uses K-Means for grouping and UMAP for high-dimensional visualization.
This version uses Position-Relative Z-Scores to compare players against their peers.
"""

# Standard Library
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

# Safeguard for Numba threading layer on macOS (Silicon)
if "NUMBA_THREADING_LAYER" not in os.environ:
    os.environ["NUMBA_THREADING_LAYER"] = "workqueue"

# Third-party
import numpy as np
import pandas as pd

# Project
from ai_models.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

# Predefined feature lenses
FEATURE_LENSES: Dict[str, List[str]] = {
    "overall": [],
    "physical": ["speed", "sprint", "distance", "aerial", "duel", "strength"],
    "creative": ["key_pass", "assist", "through_ball", "chance", "dribble", "cross"],
    "defensive": ["tackle", "interception", "clearance", "block", "duel_won", "clean_sheet"],
}

# Archetype label patterns: Semantic interpretation of cluster centers
_ARCHETYPE_PATTERNS: List[Tuple[frozenset, str]] = [
    (frozenset(["save rate", "clean sheet", "prevented goals"]), "Shot Stopper"),
    (frozenset(["interception", "tackle", "defensive duel", "blocked"]), "Defensive Wall"),
    (frozenset(["pass", "accurate pass", "long pass", "progressive pass"]), "Deep-Lying Distributor"),
    (frozenset(["goals", "shots", "xg", "penalty"]), "Lethal Finisher"),
    (frozenset(["key pass", "assist", "through pass", "xa"]), "Creative Maestro"),
    (frozenset(["dribble", "progressive run", "acceleration"]), "Tricky Winger"),
    (frozenset(["pass", "accurate pass", "short / medium pass"]), "Midfield Metronome"),
    (frozenset(["aerial duel", "head goal", "height"]), "Target Man"),
    (frozenset(["touches in box", "offensive duel"]), "Box Threat"),
    (frozenset(["market value", "age"]), "Valuable Prospect"),
    (frozenset(["distance", "hsr", "sprint"]), "Physical Engine"),
]


def apply_quality_filters(
    df: pd.DataFrame, 
    min_minutes: int = 45, # Lowered to 45 to allow everyone to see data
    smooth_rates: bool = True,
    m_constant: float = 25.0
) -> pd.DataFrame:
    """
    Applies quality filters and Bayesian smoothing to avoid statistical noise.
    """
    df = df.copy()
    if "Minutes played" in df.columns:
        df = df[df["Minutes played"] >= min_minutes]
        
    if not smooth_rates or df.empty:
        return df

    rate_cols = [c for c in df.columns if '%' in c or 'rate' in c.lower()]
    for col in rate_cols:
        if not pd.api.types.is_numeric_dtype(df[col]): continue
        
        prefix = col.split(',')[0].replace('Accurate', '').replace('Successful', '').strip()
        vol_col = next((v for v in df.columns if prefix.lower() in v.lower() and 'per 90' in v.lower() and v != col), None)
        
        if not vol_col:
            if 'dribble' in col.lower(): vol_col = 'Dribbles per 90'
            elif 'cross' in col.lower(): vol_col = 'Crosses per 90'
            elif 'duel' in col.lower(): vol_col = 'Duels per 90'
            elif 'shot' in col.lower(): vol_col = 'Shots per 90'

        if vol_col and vol_col in df.columns and "Minutes played" in df.columns:
            vol = df[vol_col] * (df["Minutes played"] / 90.0)
            global_mean = df[col].mean()
            df[col] = (df[col] * vol + global_mean * m_constant) / (vol + m_constant)
            df[col] = df[col].clip(0, 100)
    return df


def label_archetypes(
    kmeans_model: Any,
    feature_names: List[str],
    cluster_df: Optional[pd.DataFrame] = None
) -> List[str]:
    """
    Assigns semantic archetype labels based on dominant cluster traits.
    Purely statistical approach using z-scores of centroids.
    """
    centroids = kmeans_model.cluster_centers_
    
    # CRITICAL: feature_names MUST match centroids shape
    if len(feature_names) != centroids.shape[1]:
        logger.warning(f"label_archetypes: names ({len(feature_names)}) != centroids ({centroids.shape[1]}). Truncating/Padding.")
        if len(feature_names) > centroids.shape[1]:
            feature_names = feature_names[:centroids.shape[1]]
        else:
            feature_names = feature_names + [f"Feature {i}" for i in range(len(feature_names), centroids.shape[1])]

    centroid_mean = centroids.mean(axis=0)
    centroid_std = centroids.std(axis=0) + 1e-8
    z_scores = (centroids - centroid_mean) / centroid_std

    feature_names_lower = [str(f).lower() for f in feature_names]
    # Filter out derived/technical noise for cleaner labeling
    NOISE_FOR_DNA = {"red card", "yellow card", "foul", "conceded", "loss", "lost", "as gk", "exits", "lag_1", "roll_3"}

    labels = []
    for i, z_row in enumerate(z_scores):
        valid_indices = [j for j, name in enumerate(feature_names_lower) if not any(neg in name for neg in NOISE_FOR_DNA)]
        z_valid = z_row[valid_indices]
        
        # Identify top traits that define this group
        top5_local_idx = np.argsort(z_valid)[::-1][:5]
        top5_features = {feature_names_lower[valid_indices[j]] for j in top5_local_idx}

        best_label = None
        best_overlap = 0 # Must have at least one match

        for pattern_keywords, archetype_label in _ARCHETYPE_PATTERNS:
            overlap = sum(any(kw in feat for kw in pattern_keywords) for feat in top5_features)
            if overlap > best_overlap:
                best_overlap = overlap
                best_label = archetype_label

        labels.append(best_label if best_label else f"Cluster {i}")
        logger.info(f"Cluster {i} top features: {top5_features} -> '{labels[-1]}'")

    return labels


def fit_kmeans(X: np.ndarray, k: int, feature_lens: str = "overall", feature_names: Optional[List[str]] = None) -> Tuple[np.ndarray, Any]:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    feature_names = feature_names or []
    
    # 1. Lens Filtering (High priority)
    lens_features = FEATURE_LENSES.get(feature_lens.lower(), [])
    if lens_features:
        indices = [i for i, f in enumerate(feature_names) if any(lf in str(f).lower() for lf in lens_features)]
        logger.info(f"fit_kmeans: Using lens '{feature_lens}' filtering to {len(indices)} features.")
    else:
        # 2. Positional Z-Score Selection (Fallback)
        indices = [i for i, f in enumerate(feature_names) if "_zscore_positional" in str(f)]
    
    if indices:
        X_input = X[:, indices]
        selected_features = [feature_names[i] for i in indices]
    else:
        X_input = X
        selected_features = feature_names

    model = KMeans(n_clusters=k, random_state=42, n_init=20)
    labels = model.fit_predict(X_input)
    
    registry = ModelRegistry()
    # SAVE the selected features so they can be re-loaded for labeling
    registry.save(model, model_id=f"kmeans_{feature_lens}_k{k}", model_type="clustering", 
                  metrics={"k": k, "features_used": len(selected_features)}, 
                  features=selected_features)
    return labels, model

def fit_umap(X: np.ndarray, player_names: List[str], random_state: int = 42) -> Tuple[pd.DataFrame, Any]:
    import umap as umap_lib
    reducer = umap_lib.UMAP(n_components=2, random_state=random_state, n_neighbors=15, min_dist=0.1)
    embedding = reducer.fit_transform(X)
    umap_df = pd.DataFrame({"x": embedding[:, 0], "y": embedding[:, 1], "player_name": player_names})
    
    # Save to registry for downstream use
    registry = ModelRegistry()
    registry.save(reducer, model_id="umap_reducer", model_type="clustering", metrics={}, features=[])
    
    return umap_df, reducer
