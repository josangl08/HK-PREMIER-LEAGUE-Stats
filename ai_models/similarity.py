# ABOUTME: Player similarity and embeddings (Sentence Transformers).
# ABOUTME: Enables "Finding Similar Players" across the league via cosine similarity.

"""
Similarity module for player comparisons.
Encodes player-season stats as text via all-MiniLM-L6-v2, then performs
cosine similarity search to find tactically equivalent players.
"""

# Standard Library
import logging
from typing import List, Optional

# Third-party
import numpy as np
import pandas as pd

# Project
from ai_models.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

_EMBED_MODEL_ID = "player_embeddings"
_META_MODEL_ID = "player_embeddings_meta"


def _serialize_player_row(row: pd.Series) -> str:
    """
    Serializes a player-season row to a text description for embedding.
    Format: "Position, Season: col1=val1, col2=val2, ..."
    Uses top-5 numeric columns by absolute value.
    """
    position = str(row.get("Position", "Unknown"))
    season = str(row.get("Season", "Unknown"))

    # Identify numeric columns (exclude metadata columns)
    meta_cols = {"Player", "Season", "Team", "Position", "player_name"}
    numeric_vals = {}
    for col in row.index:
        if col in meta_cols:
            continue
        val = row[col]
        if pd.isna(val):
            continue
        # Handle both Python and Numpy numeric types
        if isinstance(val, (int, float, np.number)):
            numeric_vals[col] = float(val)

    # Top 5 by absolute value
    top5 = sorted(numeric_vals.items(), key=lambda kv: abs(kv[1]), reverse=True)[:5]
    stats_str = ", ".join(f"{k}={v:.2f}" for k, v in top5)

    return f"{position}, {season}: {stats_str}"


def build_embeddings(
    player_stats_df: pd.DataFrame,
    force_rebuild: bool = False,
) -> np.ndarray:
    """
    Builds sentence-transformer embeddings from player-season stats.

    Each row is serialized as a text description and encoded with
    all-MiniLM-L6-v2 (embedding dim = 384).

    Embeddings and player metadata are cached via ModelRegistry.
    If cached embeddings exist and force_rebuild is False, they are returned directly.

    Args:
        player_stats_df: DataFrame with one row per player-season.
        force_rebuild: If True, re-encode even if cache exists.

    Returns:
        Numpy array of shape (n_players, 384).
    """
    registry = ModelRegistry()

    if not force_rebuild:
        try:
            embeddings = registry.load(_EMBED_MODEL_ID)
            logger.info(f"Loaded cached embeddings from registry (shape={embeddings.shape}).")
            return embeddings
        except Exception:
            pass

    from sentence_transformers import SentenceTransformer

    logger.info("Building player embeddings with all-MiniLM-L6-v2 ...")
    texts = [_serialize_player_row(row) for _, row in player_stats_df.iterrows()]

    st_model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = st_model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

    # Persist embeddings array
    registry.save(
        embeddings,
        model_id=_EMBED_MODEL_ID,
        model_type="embeddings",
        metrics={"n_players": len(texts), "embedding_dim": embeddings.shape[1]},
        features=[],
    )

    # Persist player metadata (player, season, team) alongside
    meta_cols = [c for c in ["Player", "Season", "Team", "Position"] if c in player_stats_df.columns]
    meta_df = player_stats_df[meta_cols].reset_index(drop=True)
    registry.save(
        meta_df,
        model_id=_META_MODEL_ID,
        model_type="embeddings",
        metrics={},
        features=[],
    )

    logger.info(f"Embeddings built: shape={embeddings.shape}")
    return embeddings


def find_similar(
    query_embedding: np.ndarray,
    corpus_embeddings: np.ndarray,
    player_meta: pd.DataFrame,
    k: int = 10,
    seasons: Optional[List[str]] = None,
    query_index: Optional[int] = None,
) -> pd.DataFrame:
    """
    Finds the top-k most similar players to a query embedding via cosine similarity.

    Args:
        query_embedding: 1D array of shape (384,) for the query player.
        corpus_embeddings: 2D array of shape (n_players, 384).
        player_meta: DataFrame with columns Player/Season/Team (aligned with corpus rows).
        k: Number of similar players to return.
        seasons: Optional list of seasons to restrict results to.
        query_index: Row index of the query player in corpus to exclude self (avoid score=1.0).

    Returns:
        DataFrame with columns: player_name, season, team, similarity_score.
        Sorted descending by similarity_score.
    """
    from sklearn.metrics.pairwise import cosine_similarity

    scores = cosine_similarity(query_embedding.reshape(1, -1), corpus_embeddings)[0]

    # Build result dataframe
    meta = player_meta.copy().reset_index(drop=True)
    meta["similarity_score"] = scores

    # Exclude query player itself
    if query_index is not None:
        meta = meta.drop(index=query_index)
    else:
        # Heuristic: exclude row(s) with score ≥ 0.9999
        meta = meta[meta["similarity_score"] < 0.9999]

    # Apply season filter
    if seasons:
        season_col = "Season" if "Season" in meta.columns else None
        if season_col:
            meta = meta[meta[season_col].isin(seasons)]

    # Rename columns for consistency
    rename_map = {}
    if "Player" in meta.columns:
        rename_map["Player"] = "player_name"
    if "Season" in meta.columns:
        rename_map["Season"] = "season"
    if "Team" in meta.columns:
        rename_map["Team"] = "team"
    meta = meta.rename(columns=rename_map)

    # Ensure required columns exist
    for col in ["player_name", "season", "team"]:
        if col not in meta.columns:
            meta[col] = "Unknown"

    result = (
        meta[["player_name", "season", "team", "similarity_score"]]
        .sort_values("similarity_score", ascending=False)
        .head(k)
        .reset_index(drop=True)
    )
    return result
