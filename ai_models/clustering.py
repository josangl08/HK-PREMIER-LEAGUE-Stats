# ABOUTME: Clustering and dimensionality reduction (K-Means & UMAP).
# ABOUTME: Identifies player archetypes and styles based on stats.

"""
Clustering module for discovering player archetypes.
Uses K-Means for grouping and UMAP for high-dimensional visualization.
"""

# Standard Library
import logging
from typing import Any, Dict, List, Optional, Tuple

# Third-party
import numpy as np
import pandas as pd

# Project
from ai_models.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

# Predefined feature lenses — maps lens name → relevant column substrings
FEATURE_LENSES: Dict[str, List[str]] = {
    "overall": [],  # empty = use all features passed in
    "physical": ["speed", "sprint", "distance", "aerial", "duel", "strength"],
    "creative": ["key_pass", "assist", "through_ball", "chance", "dribble", "cross"],
    "defensive": ["tackle", "interception", "clearance", "block", "duel_won", "clean_sheet"],
}

# Archetype label patterns: frozenset of top-feature keyword substrings → label
_ARCHETYPE_PATTERNS: List[Tuple[frozenset, str]] = [
    (frozenset(["goals_per90", "shots_per90", "xg_per90"]), "Lethal Finisher"),
    (frozenset(["key_pass", "assist", "through_ball"]), "Creative Maestro"),
    (frozenset(["tackle", "interception", "duel_won"]), "Defensive Wall"),
    (frozenset(["pass", "pass_accuracy", "key_pass"]), "Midfield Metronome"),
    (frozenset(["aerial", "headed_goal", "shots_per90"]), "Target Man"),
    (frozenset(["dribble", "fouls_won", "key_pass"]), "Tricky Winger"),
    (frozenset(["clean_sheet", "save", "goals_conceded"]), "Shot Stopper"),
    (frozenset(["goals", "assist", "shots"]), "Box Threat"),
    (frozenset(["pass", "possession", "ball_recovery"]), "Anchor Midfielder"),
]


def _apply_lens(X: np.ndarray, feature_names: List[str], feature_lens: str) -> np.ndarray:
    """Filter feature matrix columns to those relevant to the given lens."""
    keywords = FEATURE_LENSES.get(feature_lens, [])
    if not keywords:
        return X
    indices = [
        i for i, name in enumerate(feature_names)
        if any(kw in name.lower() for kw in keywords)
    ]
    if not indices:
        logger.warning(f"fit_kmeans: lens '{feature_lens}' matched no features; using all.")
        return X
    return X[:, indices]


def fit_kmeans(
    X: np.ndarray,
    k: int,
    feature_lens: str = "overall",
    feature_names: Optional[List[str]] = None,
) -> Tuple[np.ndarray, Any]:
    """
    Fits a K-Means clustering model to the feature matrix.

    Args:
        X: Feature matrix (n_samples, n_features), already scaled.
        k: Number of clusters.
        feature_lens: One of 'overall', 'physical', 'creative', 'defensive'.
        feature_names: Column names for X (used for lens filtering and registry metadata).

    Returns:
        Tuple of (cluster labels array of shape (n_samples,), fitted KMeans model).
    """
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    feature_names = feature_names or list(range(X.shape[1]))
    X_lens = _apply_lens(X, feature_names, feature_lens)

    model = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = model.fit_predict(X_lens)

    sil_score = float(silhouette_score(X_lens, labels)) if k > 1 and len(set(labels)) > 1 else 0.0
    logger.info(f"KMeans k={k} lens={feature_lens} silhouette={sil_score:.4f}")

    metrics = {"silhouette_score": sil_score, "k": k, "feature_lens": feature_lens}
    registry = ModelRegistry()
    registry.save(
        model,
        model_id=f"kmeans_{feature_lens}_k{k}",
        model_type="clustering",
        metrics=metrics,
        features=list(feature_names),
    )
    return labels, model


def fit_umap(
    X: np.ndarray,
    player_names: List[str],
    random_state: int = 42,
) -> Tuple[pd.DataFrame, Any]:
    """
    Reduces feature matrix to 2D via UMAP for interactive visualization.

    Args:
        X: Feature matrix (n_samples, n_features), already scaled.
        player_names: List of player name strings, one per row.
        random_state: Fixed seed for reproducibility.

    Returns:
        Tuple of (DataFrame with columns x, y, player_name; fitted UMAP reducer).
    """
    import umap as umap_lib

    reducer = umap_lib.UMAP(n_components=2, random_state=random_state)
    embedding = reducer.fit_transform(X)

    umap_df = pd.DataFrame({
        "x": embedding[:, 0],
        "y": embedding[:, 1],
        "player_name": player_names,
    })

    registry = ModelRegistry()
    registry.save(
        reducer,
        model_id="umap_2d",
        model_type="clustering",
        metrics={},
        features=[],
    )
    return umap_df, reducer


def label_archetypes(
    kmeans_model: Any,
    feature_names: List[str],
) -> List[str]:
    """
    Assigns semantic archetype labels to K-Means cluster centroids.

    Strategy:
    1. Compute z-scores of centroids across all clusters.
    2. For each centroid, identify top-3 dominant features by abs z-score.
    3. Match against predefined archetype patterns (partial: ≥2 keyword overlaps).
    4. Default to "Cluster {i}" if no match found.

    Args:
        kmeans_model: Fitted KMeans model with .cluster_centers_ attribute.
        feature_names: Feature names corresponding to centroid columns.

    Returns:
        List of archetype label strings, one per cluster.
    """
    centroids = kmeans_model.cluster_centers_  # (k, n_features)
    centroid_mean = centroids.mean(axis=0)
    centroid_std = centroids.std(axis=0) + 1e-8  # avoid division by zero
    z_scores = (centroids - centroid_mean) / centroid_std  # (k, n_features)

    feature_names_lower = [str(f).lower() for f in feature_names]
    labels = []

    for i, z_row in enumerate(z_scores):
        top3_indices = np.argsort(np.abs(z_row))[::-1][:3]
        top3_features = {feature_names_lower[j] for j in top3_indices}

        best_label = None
        best_overlap = 0

        for pattern_keywords, archetype_label in _ARCHETYPE_PATTERNS:
            overlap = sum(
                any(kw in feat for kw in pattern_keywords)
                for feat in top3_features
            )
            if overlap >= 2 and overlap > best_overlap:
                best_overlap = overlap
                best_label = archetype_label

        labels.append(best_label if best_label else f"Cluster {i}")
        logger.info(f"Cluster {i} top features: {top3_features} → '{labels[-1]}'")

    return labels
