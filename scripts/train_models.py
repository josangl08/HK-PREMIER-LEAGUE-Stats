# ABOUTME: Offline training script for AI models (clustering, prediction, similarity).
# ABOUTME: Loads data via HongKongDataManager, engineers features with MLPreprocessor, and saves models via ModelRegistry.

# Standard Library
import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on the path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

# Third-party
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

# Project
from data.hong_kong_data_manager import HongKongDataManager
from data.processors.ml_preprocessor import MLPreprocessor
from ai_models.model_registry import ModelRegistry
from ai_models.predictor import train_xgboost, train_tabpfn
from ai_models.clustering import fit_kmeans, fit_umap, label_archetypes, FEATURE_LENSES
from ai_models.similarity import build_embeddings

# Logger configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Columns used as regression targets
PREDICTION_TARGETS = ["Goals", "Assists", "xG"]

# Meta/non-feature columns
META_COLS = {"Player", "Season", "Team", "Position", "player_name"}


# ──────────────────────────────────────────────────────────────────────────────
# Data loading
# ──────────────────────────────────────────────────────────────────────────────

def load_data(seasons=None) -> pd.DataFrame:
    """Loads and refreshes processed player data via HongKongDataManager."""
    logger.info("Initialising HongKongDataManager …")
    dm = HongKongDataManager(auto_load=False)
    if not dm.refresh_data():
        logger.warning("Data refresh returned False — using cached data if available.")

    df = dm.processed_data
    if df is None or df.empty:
        raise RuntimeError("No processed data available. Run the ETL extractors first.")

    if seasons:
        df = df[df["Season"].isin(seasons)]
        logger.info(f"Filtered to seasons: {seasons} → {len(df)} rows")
    else:
        logger.info(f"Loaded {len(df)} player-season rows.")

    return df.reset_index(drop=True)


# ──────────────────────────────────────────────────────────────────────────────
# Feature engineering
# ──────────────────────────────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Applies MLPreprocessor transformations to the raw DataFrame."""
    pp = MLPreprocessor()

    numeric_cols = [
        c for c in df.columns
        if c not in META_COLS and pd.api.types.is_numeric_dtype(df[c])
    ]

    logger.info(f"Engineering features for {len(numeric_cols)} numeric columns …")
    df = pp.compute_temporal_features(df, numeric_cols)
    df = pp.compute_positional_zscores(df, numeric_cols)
    df = pp.compute_benchmark_deltas(df, numeric_cols)
    df = pp.inject_composite_metrics(df)
    logger.info(f"Feature engineering complete — DataFrame now has {df.shape[1]} columns.")
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Training pipelines
# ──────────────────────────────────────────────────────────────────────────────

def train_predictors(df: pd.DataFrame) -> None:
    """
    Trains XGBoost and TabPFN models for each prediction target.
    Uses time-series split to separate train/test.
    """
    logger.info("=" * 60)
    logger.info("PIPELINE 1: Predictor training")
    logger.info("=" * 60)

    pp = MLPreprocessor()
    feature_cols = [
        c for c in df.columns
        if c not in META_COLS and pd.api.types.is_numeric_dtype(df[c])
    ]
    registry = ModelRegistry()

    for target in PREDICTION_TARGETS:
        if target not in df.columns:
            logger.warning(f"Target '{target}' not in DataFrame — skipping.")
            continue

        # Drop rows where target is NaN
        sub = df.dropna(subset=[target])
        feat_cols_no_target = [c for c in feature_cols if c != target]

        try:
            train_idx, _ = pp.time_series_split(sub, n_test_seasons=1)
        except ValueError as e:
            logger.warning(f"time_series_split failed for {target}: {e} — using all data.")
            train_idx = sub.index.to_numpy()

        X_raw = sub.loc[train_idx, feat_cols_no_target].fillna(0).values
        y = sub.loc[train_idx, target].values

        # Fit and persist scaler so the dashboard can reproduce the same transform
        scaler = StandardScaler()
        X = scaler.fit_transform(X_raw)
        registry.save(
            scaler,
            model_id=f"scaler_{target}",
            model_type="predictors",
            metrics={},
            features=feat_cols_no_target,   # <-- actual column names
        )
        logger.info(f"Scaler for '{target}' saved with {len(feat_cols_no_target)} features.")

        logger.info(f"Training XGBoost for target='{target}' on {len(X)} samples …")
        _, xgb_metrics = train_xgboost(X, y, target=target, n_splits=min(5, len(X) // 2 or 1))
        # Overwrite feature list with real column names (train_xgboost saves indices by default)
        reg_data = registry._load_registry()
        for mid in [f"xgboost_{target}", f"tabpfn_{target}"]:
            if mid in reg_data:
                reg_data[mid]["latest"]["features"] = feat_cols_no_target
                for v in reg_data[mid]["versions"]:
                    v["features"] = feat_cols_no_target
        registry._save_registry(reg_data)
        logger.info(f"  XGBoost [{target}]: {xgb_metrics}")

        logger.info(f"Training TabPFN for target='{target}' …")
        _, pfn_metrics = train_tabpfn(X, y, target=target)
        logger.info(f"  TabPFN  [{target}]: {pfn_metrics}")

    logger.info("Predictor training complete.\n")


def train_clustering(df: pd.DataFrame) -> None:
    """
    Trains KMeans + UMAP for each feature lens.
    Saves models to ModelRegistry under 'clustering'.
    """
    logger.info("=" * 60)
    logger.info("PIPELINE 2: Clustering training")
    logger.info("=" * 60)

    feature_cols = [
        c for c in df.columns
        if c not in META_COLS and pd.api.types.is_numeric_dtype(df[c])
    ]
    X_raw = df[feature_cols].fillna(0).values
    scaler = StandardScaler()
    X = scaler.fit_transform(X_raw)

    player_names = df["Player"].values if "Player" in df.columns else [str(i) for i in range(len(df))]

    for lens in FEATURE_LENSES:
        for k in [4, 5, 6]:
            logger.info(f"Fitting KMeans k={k} lens='{lens}' …")
            try:
                labels, kmeans_model = fit_kmeans(X, k=k, feature_lens=lens, feature_names=feature_cols)
                archetype_labels = label_archetypes(kmeans_model, feature_cols)
                logger.info(f"  Archetypes: {archetype_labels}")
            except Exception as e:
                logger.error(f"KMeans failed for k={k} lens={lens}: {e}")

    # Fit UMAP once on overall features
    logger.info("Fitting UMAP 2D projection on all features …")
    try:
        umap_df, _ = fit_umap(X, player_names=list(player_names))
        logger.info(f"  UMAP fitted — {len(umap_df)} points.")
    except Exception as e:
        logger.error(f"UMAP failed: {e}")

    logger.info("Clustering training complete.\n")


def train_embeddings(df: pd.DataFrame) -> None:
    """
    Builds and caches sentence-transformer player embeddings.
    """
    logger.info("=" * 60)
    logger.info("PIPELINE 3: Player embeddings")
    logger.info("=" * 60)

    logger.info(f"Building embeddings for {len(df)} player-season rows …")
    try:
        embeddings = build_embeddings(df, force_rebuild=True)
        logger.info(f"  Embeddings shape: {embeddings.shape}")
    except Exception as e:
        logger.error(f"Embedding build failed: {e}")

    logger.info("Embedding pipeline complete.\n")


# ──────────────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train AI models for HK Premier League Stats.")
    parser.add_argument("--seasons", nargs="+", help="Seasons to include in training (e.g. 2022-23 2023-24).")
    parser.add_argument("--skip-predictors", action="store_true", help="Skip predictor pipeline.")
    parser.add_argument("--skip-clustering", action="store_true", help="Skip clustering pipeline.")
    parser.add_argument("--skip-embeddings", action="store_true", help="Skip embedding pipeline.")
    args = parser.parse_args()

    logger.info("╔══════════════════════════════════════════╗")
    logger.info("║   HK Premier League — Model Training     ║")
    logger.info("╚══════════════════════════════════════════╝")

    df_raw = load_data(seasons=args.seasons)
    df = engineer_features(df_raw)

    if not args.skip_predictors:
        train_predictors(df)
    else:
        logger.info("Predictor pipeline skipped.")

    if not args.skip_clustering:
        train_clustering(df)
    else:
        logger.info("Clustering pipeline skipped.")

    if not args.skip_embeddings:
        train_embeddings(df)
    else:
        logger.info("Embedding pipeline skipped.")

    logger.info("╔══════════════════════════════════════════╗")
    logger.info("║   Training complete — models saved       ║")
    logger.info("╚══════════════════════════════════════════╝")

    # List all registered models
    try:
        registry = ModelRegistry()
        models = registry.list_models()
        logger.info(f"Registry contains {len(models)} models:")
        for m in models:
            logger.info(f"  [{m['model_type']}] {m['model_id']} v{m['version']} — {m['metrics']}")
    except Exception as e:
        logger.warning(f"Could not list models: {e}")


if __name__ == "__main__":
    main()
