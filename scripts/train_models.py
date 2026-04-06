# ABOUTME: Offline training script for AI models (clustering, prediction, similarity).
# ABOUTME: Loads data via HongKongDataManager, engineers features with MLPreprocessor, and saves models via ModelRegistry.

# Standard Library
import argparse
import logging
import os
import sys
from pathlib import Path

# Prevent OpenMP conflicts between TabPFN and XGBoost on macOS/Linux.
# Must be set before any ML library is imported.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

# Ensure project root is on the path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

# Third-party
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

# Project
from data.hong_kong_data_manager import HongKongDataManager
from data.processors.ml_preprocessor import MLPreprocessor
from ai_models.model_registry import ModelRegistry
from ai_models.predictor import train_xgboost, train_tabpfn
from ai_models.clustering import fit_kmeans, fit_umap, label_archetypes, FEATURE_LENSES, apply_quality_filters
from ai_models.similarity import build_embeddings

# Logger configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Columns used as regression targets (cross-sectional predictors)
PREDICTION_TARGETS = ["Goals", "Assists", "xG"]

# Season-to-season projection targets — union of all CAREER_ARC_ALL_METRICS
_PROJECTION_TARGETS = [
    "Goals", "Assists", "xG", "xA",
    "Shots on target, %", "Goal conversion, %",
    "Successful dribbles, %", "Crosses per 90",
    "Accurate passes, %", "Key passes per 90",
    "PAdj interceptions per 90", "Defensive duels won, %",
    "Aerial duels won, %", "Shots blocked per 90",
    "Prevented goals", "Save rate, %", "Clean sheets", "xG against per 90",
    "Minutes played",
]

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

    # ── Layer 3 Filter: AI Training Quality ───────────────────────────────
    # We use apply_quality_filters to ensure high-quality training data:
    # 1. Minimum minutes (180+) to avoid statistical noise.
    # 2. Bayesian smoothing for rate-based metrics (%) to regress low-volume outliers.
    initial_len = len(df)
    df = apply_quality_filters(df, min_minutes=180, smooth_rates=True)
    logger.info(f"AI Quality Filter: {initial_len} -> {len(df)} valid rows remain (Min 180 mins + Smoothed Rates).")

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

        # NOTE: TabPFN skipped — requires pre-downloaded HF weights (hangs on first run).
        # To enable: run `python -c "from tabpfn import TabPFNRegressor; TabPFNRegressor()"` once
        # to cache weights, then uncomment train_tabpfn() here.

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
        for k in [4, 5, 6, 8]:
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


def train_projection_models() -> None:
    """
    Trains season-to-season projection models (TabPFN + XGBoost) for each metric.

    Loads all players with ≥2 seasons from the database, builds transition pairs via
    MLPreprocessor.build_projection_pairs(), then trains and registers one TabPFN model
    and one XGBoost model per metric target.

    Models saved to ModelRegistry as:
      - tabpfn_proj_{metric}     (primary)
      - xgboost_proj_{metric}    (comparison)
      - proj_scaler_{metric}     (StandardScaler, needed for inference)
    """
    from sqlalchemy import select
    from models.db_models import Player
    from utils.db_engine import SessionFactory
    from utils.stage_helpers import _fetch_player_season_history, _get_position_group
    from data.processors.ml_preprocessor import _PROJECTION_FEATURE_METRICS

    logger.info("=" * 60)
    logger.info("PIPELINE 4: Season Projection model training")
    logger.info("=" * 60)

    dm = HongKongDataManager(auto_load=False)
    dm.refresh_data()

    # Collect player histories from DB
    player_records = []
    try:
        with SessionFactory() as sess:
            players = sess.execute(select(Player)).scalars().all()
            for p in players:
                try:
                    history_df = _fetch_player_season_history(p.name)
                except Exception:
                    continue
                if history_df is None or len(history_df) < 2:
                    continue
                try:
                    pos_group = _get_position_group(p.name, dm)
                except Exception:
                    pos_group = "Midfielder"

                birth_year = None
                if p.birth_date:
                    birth_year = p.birth_date.year
                elif p.age:
                    birth_year = 2025 - p.age  # approximate

                player_records.append({
                    "history_df": history_df,
                    "pos_group": pos_group,
                    "birth_year": birth_year,
                })
    except Exception as e:
        logger.error(f"DB load failed: {e}")
        return

    logger.info(f"Collected {len(player_records)} player histories with ≥2 seasons.")

    if not player_records:
        logger.error("No player records — aborting projection training.")
        return

    # Build season-to-season transition pairs
    pp = MLPreprocessor()
    X_df, y_dict = pp.build_projection_pairs(player_records, target_metrics=_PROJECTION_TARGETS)

    if X_df.empty:
        logger.error("No projection pairs built — aborting.")
        return

    feature_cols = list(X_df.columns)
    X_raw = X_df.values.astype(np.float64)
    registry = ModelRegistry()

    # ── Temporal holdout: reserve most recent transition season as test set ────
    # build_projection_pairs preserves row order by player history.
    # We identify rows whose SOURCE season is the penultimate season (2023-24→2024-25)
    # so these pairs are never seen during training — true out-of-sample evaluation.
    _holdout_mask = np.zeros(len(X_df), dtype=bool)
    _train_mask = np.ones(len(X_df), dtype=bool)
    _penultimate_season = "2023-24"
    if "Season" in X_df.columns:
        _holdout_mask = (X_df["Season"] == _penultimate_season).values
        _train_mask = ~_holdout_mask
        logger.info(
            f"Temporal holdout: {_holdout_mask.sum()} pairs reserved "
            f"(source season {_penultimate_season}) — never seen during training."
        )
    else:
        # Fallback: reserve last 15% of rows
        _split = int(len(X_df) * 0.85)
        _train_mask[:] = False
        _train_mask[:_split] = True
        _holdout_mask[_split:] = True
        logger.info(
            f"Temporal holdout (fallback 15%): {_holdout_mask.sum()} pairs reserved."
        )

    X_raw_train = X_raw[_train_mask]
    X_raw_holdout = X_raw[_holdout_mask]

    # ── Correlation matrix: top features per target metric ────────────────────
    logger.info("Feature–target Pearson correlations (top 8 per metric):")
    for _tgt in _PROJECTION_TARGETS:
        _y_c = y_dict.get(_tgt, np.array([]))
        _valid_c = ~np.isnan(_y_c) & (_y_c >= 0)
        if _valid_c.sum() < 10:
            continue
        _Xc = X_raw[_valid_c]
        _yc = _y_c[_valid_c]
        with np.errstate(divide="ignore", invalid="ignore"):
            _corrs = np.array([
                np.corrcoef(_Xc[:, j], _yc)[0, 1] if np.std(_Xc[:, j]) > 0 else 0.0
                for j in range(_Xc.shape[1])
            ])
        _corrs = np.nan_to_num(_corrs, nan=0.0)
        _top = np.argsort(np.abs(_corrs))[::-1][:8]
        _top_pairs = [(feature_cols[i], round(float(_corrs[i]), 3)) for i in _top]
        logger.info(f"  [{_tgt}]: {_top_pairs}")

    import xgboost as xgb
    from tabpfn import TabPFNRegressor
    from sklearn.model_selection import TimeSeriesSplit

    # TabPFN is designed for N < 1000 — subsample if larger
    _TABPFN_MAX = 1000
    _MIN_R2 = 0.30  # threshold for "active" model in dashboard

    xgb_params = dict(
        n_estimators=100, learning_rate=0.05, max_depth=3,
        min_child_weight=5, subsample=0.8, colsample_bytree=0.8,
        reg_alpha=0.1, reg_lambda=1.0, random_state=42, verbosity=0,
    )

    summary_rows: list = []

    for metric in _PROJECTION_TARGETS:
        y = y_dict.get(metric, np.array([]))
        if len(y) == 0:
            continue

        # Include y=0 (survivorship bias fix) — train split only
        valid_train = ~np.isnan(y) & (y >= 0) & _train_mask
        valid_hold  = ~np.isnan(y) & (y >= 0) & _holdout_mask
        n_valid = int(valid_train.sum())
        if n_valid < 10:
            logger.warning(f"Projection [{metric}]: only {n_valid} train samples — skipping.")
            continue

        X_valid = X_raw_train[valid_train[_train_mask]]
        y_valid = y[valid_train]

        # Holdout set (never seen during training)
        X_hold = X_raw_holdout[valid_hold[_holdout_mask]] if valid_hold.sum() > 0 else None
        y_hold = y[valid_hold] if valid_hold.sum() > 0 else None

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_valid)
        registry.save(
            scaler,
            model_id=f"proj_scaler_{metric}",
            model_type="predictors",
            metrics={"n_samples": n_valid},
            features=feature_cols,
        )

        # ── TabPFN ─────────────────────────────────────────────────────────────
        # Subsample to _TABPFN_MAX if needed — TabPFN optimised for small-N.
        # Bug fix: use TimeSeriesSplit (not KFold) to respect temporal order.
        if n_valid > _TABPFN_MAX:
            rng = np.random.default_rng(42)
            idx_sub = rng.choice(n_valid, _TABPFN_MAX, replace=False)
            idx_sub.sort()  # preserve temporal order for TimeSeriesSplit
            X_pfn, y_pfn = X_scaled[idx_sub], y_valid[idx_sub]
            logger.info(f"  TabPFN proj [{metric}]: subsampled {n_valid} → {_TABPFN_MAX}")
        else:
            X_pfn, y_pfn = X_scaled, y_valid
        n_pfn = len(y_pfn)

        n_folds_pfn = min(5, max(3, n_pfn // 30))
        tscv_pfn = TimeSeriesSplit(n_splits=n_folds_pfn)
        pfn_rmse, pfn_mae, pfn_r2, pfn_dir = [], [], [], []
        logger.info(f"  TabPFN proj [{metric}] — {n_folds_pfn}-fold TSplit on {n_pfn} samples …")
        pfn_cv_metrics: dict = {}
        try:
            for fold_tr, fold_val in tscv_pfn.split(X_pfn):
                _m = TabPFNRegressor(device="cpu", n_estimators=16)
                _m.fit(X_pfn[fold_tr], y_pfn[fold_tr])
                _preds = _m.predict(X_pfn[fold_val])
                pfn_rmse.append(float(np.sqrt(mean_squared_error(y_pfn[fold_val], _preds))))
                pfn_mae.append(float(mean_absolute_error(y_pfn[fold_val], _preds)))
                pfn_r2.append(float(r2_score(y_pfn[fold_val], _preds)))
                # Directional accuracy: % of predictions correctly above/below training median
                _med = float(np.median(y_pfn[fold_tr]))
                pfn_dir.append(float(np.mean(((_preds - _med) * (y_pfn[fold_val] - _med)) > 0)))
            pfn_cv_metrics = {
                "rmse": float(np.mean(pfn_rmse)),
                "mae":  float(np.mean(pfn_mae)),
                "r2":   float(np.mean(pfn_r2)),
                "dir_acc": float(np.mean(pfn_dir)),
                "cv_folds": n_folds_pfn,
            }
            final_pfn = TabPFNRegressor(device="cpu", n_estimators=32)
            final_pfn.fit(X_pfn, y_pfn)
            # Holdout R² for TabPFN (true out-of-sample, saved into registry metrics)
            pfn_holdout_r2 = float("nan")
            if X_hold is not None and len(X_hold) >= 3:
                try:
                    _ph = final_pfn.predict(scaler.transform(X_hold))
                    pfn_holdout_r2 = float(r2_score(y_hold, _ph))
                except Exception: pass
            pfn_cv_metrics["holdout_r2"] = pfn_holdout_r2
            registry.save(
                final_pfn,
                model_id=f"tabpfn_proj_{metric}",
                model_type="predictors",
                metrics=pfn_cv_metrics,
                features=feature_cols,
            )
            logger.info(f"    TabPFN CV {pfn_cv_metrics}")
        except Exception as e:
            logger.warning(f"    TabPFN proj [{metric}] failed: {e}")

        # ── XGBoost ────────────────────────────────────────────────────────────
        n_splits_xgb = min(5, max(3, n_valid // 30))
        tscv = TimeSeriesSplit(n_splits=n_splits_xgb)
        xgb_rmse, xgb_mae, xgb_r2, xgb_dir = [], [], [], []
        logger.info(f"  XGBoost proj [{metric}] — {n_splits_xgb}-fold TSplit on {n_valid} samples …")
        xgb_cv_metrics: dict = {}
        try:
            for fold_tr, fold_val in tscv.split(X_scaled):
                _m = xgb.XGBRegressor(**xgb_params)
                _m.fit(X_scaled[fold_tr], y_valid[fold_tr])
                _preds = _m.predict(X_scaled[fold_val])
                xgb_rmse.append(float(np.sqrt(mean_squared_error(y_valid[fold_val], _preds))))
                xgb_mae.append(float(mean_absolute_error(y_valid[fold_val], _preds)))
                xgb_r2.append(float(r2_score(y_valid[fold_val], _preds)))
                _med = float(np.median(y_valid[fold_tr]))
                xgb_dir.append(float(np.mean(((_preds - _med) * (y_valid[fold_val] - _med)) > 0)))
            xgb_cv_metrics = {
                "rmse": float(np.mean(xgb_rmse)),
                "mae":  float(np.mean(xgb_mae)),
                "r2":   float(np.mean(xgb_r2)),
                "dir_acc": float(np.mean(xgb_dir)),
                "cv_folds": n_splits_xgb,
            }
            final_xgb = xgb.XGBRegressor(**xgb_params)
            final_xgb.fit(X_scaled, y_valid)
            # Holdout R² for XGBoost (true out-of-sample, saved into registry metrics)
            xgb_holdout_r2 = float("nan")
            if X_hold is not None and len(X_hold) >= 3:
                try:
                    _xh = final_xgb.predict(scaler.transform(X_hold))
                    xgb_holdout_r2 = float(r2_score(y_hold, _xh))
                except Exception: pass
            xgb_cv_metrics["holdout_r2"] = xgb_holdout_r2
            registry.save(
                final_xgb,
                model_id=f"xgboost_proj_{metric}",
                model_type="predictors",
                metrics=xgb_cv_metrics,
                features=feature_cols,
            )
            logger.info(f"    XGBoost CV {xgb_cv_metrics}")
        except Exception as e:
            logger.warning(f"    XGBoost proj [{metric}] failed: {e}")

        # Pick best model for summary (TabPFN > XGBoost if both available)
        best_m, best_metrics = ("—", {})
        for _name, _m in [("TabPFN", pfn_cv_metrics), ("XGBoost", xgb_cv_metrics)]:
            if _m and _m.get("r2", -999) > best_metrics.get("r2", -999):
                best_m, best_metrics = _name, _m

        # Best holdout R² across both models
        holdout_r2 = best_metrics.get("holdout_r2", float("nan"))

        summary_rows.append({
            "metric": metric,
            "model": best_m,
            "n": n_valid,
            "r2": best_metrics.get("r2", float("nan")),
            "holdout_r2": holdout_r2,
            "dir_acc": best_metrics.get("dir_acc", float("nan")),
            "mae": best_metrics.get("mae", float("nan")),
        })

    # ── Final accuracy summary table ───────────────────────────────────────────
    logger.info("")
    logger.info("╔══════════════════════════════════════════════════════════════════════╗")
    logger.info("║  PROJECTION MODEL ACCURACY SUMMARY                                  ║")
    logger.info("╠══════════════════════════════════════════════════════════════════════╣")
    logger.info(f"  {'Metric':<30} {'Model':<8} {'N':>5}  {'CV R²':>6}  {'Hold R²':>8}  {'Dir.Acc':>8}  {'MAE':>8}  {'Active?':>7}")
    logger.info("  " + "─" * 80)
    for row in summary_rows:
        r2_pct  = f"{max(0.0, row['r2']) * 100:.1f}%"       if not np.isnan(row['r2'])         else "   n/a"
        hr2_pct = f"{row['holdout_r2'] * 100:.1f}%"         if not np.isnan(row['holdout_r2']) else "    n/a"
        dir_pct = f"{row['dir_acc'] * 100:.1f}%"            if not np.isnan(row['dir_acc'])    else "    n/a"
        mae_str = f"{row['mae']:.3f}"                        if not np.isnan(row['mae'])        else "    n/a"
        # Active if holdout R² ≥ 0.25 (preferred) or CV R² ≥ 0.30 (fallback)
        _h = row["holdout_r2"]
        _c = row["r2"]
        if not np.isnan(_h):
            active = "✅" if _h >= 0.25 else "—"
        else:
            active = "✅" if (not np.isnan(_c) and _c >= _MIN_R2) else "—"
        logger.info(
            f"  {row['metric']:<30} {row['model']:<8} {row['n']:>5}  "
            f"{r2_pct:>6}  {hr2_pct:>8}  {dir_pct:>8}  {mae_str:>8}  {active:>7}"
        )
    logger.info("╚══════════════════════════════════════════════════════════════════════════════════╝")
    logger.info("  CV R²     = k-fold cross-validation R² (TimeSeriesSplit)")
    logger.info("  Hold R²   = true out-of-sample R² on reserved 2023-24→2024-25 pairs")
    logger.info("  Dir.Acc   = % predictions with correct direction (above/below median)")
    logger.info("  Active    = model used in dashboard (Hold R² ≥ 25% or CV R² ≥ 30%)")
    logger.info("")
    logger.info("Season Projection training complete.\n")


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
    parser.add_argument("--skip-projection", action="store_true", help="Skip season projection pipeline.")
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

    if not args.skip_projection:
        train_projection_models()
    else:
        logger.info("Season projection pipeline skipped.")

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
