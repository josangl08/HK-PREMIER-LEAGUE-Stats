# ABOUTME: Regression models for performance prediction (XGBoost & TabPFN).
# ABOUTME: Handles training, inference, and SHAP explainability for goals, assists, and xG.

"""
Predictor module for player performance forecasting.
Includes classical (XGBoost) and state-of-the-art (TabPFN) tabular models.
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

# Project
from ai_models.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


def train_xgboost(
    X: np.ndarray,
    y: np.ndarray,
    target: str,
    n_splits: int = 5,
) -> Tuple[Any, Dict[str, float]]:
    """
    Trains an XGBoost regressor with temporal cross-validation.

    Args:
        X: Feature matrix (n_samples, n_features).
        y: Target vector (n_samples,).
        target: Target metric name (used as model_id suffix).
        n_splits: Number of TimeSeriesSplit folds.

    Returns:
        Tuple of (trained XGBoost model, metrics dict with rmse/mae/r2).
    """
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    import xgboost as xgb

    tscv = TimeSeriesSplit(n_splits=n_splits)
    rmse_scores, mae_scores, r2_scores = [], [], []

    for train_idx, val_idx in tscv.split(X):
        X_tr, X_val = X[train_idx], X[val_idx]
        y_tr, y_val = y[train_idx], y[val_idx]
        fold_model = xgb.XGBRegressor(
            n_estimators=100, learning_rate=0.05, max_depth=3,
            min_child_weight=5, subsample=0.8, colsample_bytree=0.8,
            reg_alpha=0.1, reg_lambda=1.0, random_state=42, verbosity=0,
        )
        fold_model.fit(X_tr, y_tr)
        preds = fold_model.predict(X_val)
        rmse_scores.append(float(np.sqrt(mean_squared_error(y_val, preds))))
        mae_scores.append(float(mean_absolute_error(y_val, preds)))
        r2_scores.append(float(r2_score(y_val, preds)))

    # Final model trained on all data
    model = xgb.XGBRegressor(
        n_estimators=100, learning_rate=0.05, max_depth=3,
        min_child_weight=5, subsample=0.8, colsample_bytree=0.8,
        reg_alpha=0.1, reg_lambda=1.0, random_state=42, verbosity=0,
    )
    model.fit(X, y)

    metrics = {
        "rmse": float(np.mean(rmse_scores)),
        "mae": float(np.mean(mae_scores)),
        "r2": float(np.mean(r2_scores)),
    }
    logger.info(f"XGBoost [{target}] CV metrics: {metrics}")

    registry = ModelRegistry()
    registry.save(
        model,
        model_id=f"xgboost_{target}",
        model_type="predictors",
        metrics=metrics,
        features=list(range(X.shape[1])),
    )
    return model, metrics


def train_tabpfn(
    X: np.ndarray,
    y: np.ndarray,
    target: str,
) -> Tuple[Any, Dict[str, float]]:
    """
    Trains a TabPFN regressor (zero-shot, optimised for <2500 rows).
    Falls back to XGBoost if dataset exceeds 2500 rows or TabPFN is not installed.

    Args:
        X: Feature matrix (n_samples, n_features).
        y: Target vector (n_samples,).
        target: Target metric name (used as model_id suffix).

    Returns:
        Tuple of (trained model, metrics dict with rmse/mae/r2).
    """
    if len(X) > 2500:
        logger.warning(
            f"train_tabpfn: dataset has {len(X)} rows (>2500). Falling back to XGBoost."
        )
        return train_xgboost(X, y, target)

    try:
        from tabpfn import TabPFNRegressor
        from sklearn.model_selection import KFold
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

        # Honest k-fold CV — never evaluate on training data
        n_folds = min(5, max(3, len(X) // 30))
        kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)
        rmse_scores, mae_scores, r2_scores = [], [], []
        for tr_idx, val_idx in kf.split(X):
            _m = TabPFNRegressor(device="cpu", n_estimators=16)
            _m.fit(X[tr_idx], y[tr_idx])
            _p = _m.predict(X[val_idx])
            rmse_scores.append(float(np.sqrt(mean_squared_error(y[val_idx], _p))))
            mae_scores.append(float(mean_absolute_error(y[val_idx], _p)))
            r2_scores.append(float(r2_score(y[val_idx], _p)))

        model = TabPFNRegressor(device="cpu", n_estimators=32)
        model.fit(X, y)
        metrics = {
            "rmse": float(np.mean(rmse_scores)),
            "mae":  float(np.mean(mae_scores)),
            "r2":   float(np.mean(r2_scores)),
            "cv_folds": n_folds,
        }
        logger.info(f"TabPFN [{target}] CV metrics: {metrics}")

    except ImportError:
        logger.warning("TabPFN not installed. Falling back to XGBoost.")
        return train_xgboost(X, y, target)
    except (RuntimeError, Exception) as e:
        # Covers: gated model download failure, HuggingFace auth errors, CUDA errors
        logger.warning(f"TabPFN unavailable ({type(e).__name__}: {e}). Falling back to XGBoost.")
        return train_xgboost(X, y, target)

    registry = ModelRegistry()
    registry.save(
        model,
        model_id=f"tabpfn_{target}",
        model_type="predictors",
        metrics=metrics,
        features=list(range(X.shape[1])),
    )
    return model, metrics


def predict(
    model: Any,
    X: np.ndarray,
    mode: Optional[str] = None,
) -> np.ndarray:
    """
    Generates predictions using a trained model.

    Args:
        model: Trained model (XGBoost or TabPFN).
        X: Feature matrix for prediction.
        mode: None for regression output; "classification" for tier labels
              (Elite / Average / Low Impact based on 25th/75th percentile).

    Returns:
        Numpy array of predicted values or string labels.
    """
    raw_preds = model.predict(X)

    if mode == "classification":
        q25, q75 = np.percentile(raw_preds, [25, 75])
        labels = np.where(
            raw_preds > q75,
            "Elite",
            np.where(raw_preds < q25, "Low Impact", "Average"),
        )
        return labels

    return raw_preds


def predict_with_interval(
    model: Any,
    X: np.ndarray,
    model_id: str,
) -> dict:
    """
    Returns a point prediction with a ±1 RMSE confidence interval.

    The interval is derived from the cross-validation RMSE stored in the
    ModelRegistry at training time — no re-fitting required.

    Args:
        model: Trained model (XGBoost or TabPFN).
        X: Feature matrix for a single player (1, n_features).
        model_id: Registry key (e.g. "xgboost_Goals") used to look up the RMSE.

    Returns:
        Dict with keys: prediction, lower, upper, rmse.
    """
    raw = predict(model, X)
    point = float(raw[0])

    rmse = 0.0
    try:
        registry = ModelRegistry()
        reg_data = registry._load_registry()
        rmse = float(
            reg_data.get(model_id, {}).get("latest", {}).get("metrics", {}).get("rmse", 0.0)
        )
    except Exception:
        pass

    return {
        "prediction": point,
        "lower": max(0.0, point - rmse),
        "upper": point + rmse,
        "rmse": rmse,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Transferability Score (TabPFN Transfer Learning)
# ──────────────────────────────────────────────────────────────────────────────

# Hardcoded percentile benchmarks for "higher-tier league" success.
# These represent the ~75th-percentile threshold values observed in top Asian /
# lower-tier European leagues, used as synthetic reference rows for TabPFN.
_LEAGUE_BENCHMARKS: Dict[str, Dict[str, float]] = {
    "Forward": {
        "xG": 0.45, "Goals": 12.0, "Goal conversion, %": 18.0,
        "Shots on target, %": 52.0, "Assists": 4.0, "Minutes played": 2200.0,
        "Dribbles per 90": 2.1, "Aerial duels won, %": 42.0,
    },
    "Winger": {
        "xG": 0.28, "Goals": 7.0, "Assists": 6.0, "Successful dribbles, %": 58.0,
        "Crosses per 90": 3.2, "Key passes per 90": 2.4, "Minutes played": 2000.0,
        "xA": 0.22,
    },
    "Midfielder": {
        "xA": 0.20, "Assists": 5.0, "Accurate passes, %": 82.0,
        "Key passes per 90": 2.0, "Goals": 4.0, "Minutes played": 2300.0,
        "Interceptions per 90": 3.5, "Duels won, %": 52.0,
    },
    "Defender": {
        "PAdj interceptions per 90": 8.0, "Defensive duels won, %": 68.0,
        "Aerial duels won, %": 62.0, "Shots blocked per 90": 0.9,
        "Accurate passes, %": 80.0, "Minutes played": 2400.0,
        "Fouls per 90": 1.2, "xClean sheets": 12.0,
    },
    "Goalkeeper": {
        "Save rate, %": 72.0, "Prevented goals": 5.0, "Clean sheets": 10.0,
        "xG against per 90": 1.1, "Minutes played": 2700.0,
        "xClean sheets": 11.0, "Passes per 90": 28.0, "Long passes per 90": 12.0,
    },
}


def get_transferability_score(
    career_stats: Dict[str, Any],
    pos_group: str,
    player_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Estimates the probability that a player would succeed in a higher-tier league
    using TabPFN transfer learning with synthetic reference data.

    Falls back to a rule-based percentile calculation when TabPFN is unavailable.

    Args:
        career_stats: Dict of career (or season-averaged) stats for the player.
        pos_group:    Position group (e.g. "Forward", "Defender").
        player_id:    Optional — used for ModelRegistry caching.

    Returns:
        Dict with keys:
            ``score``        — float 0-1 (probability of higher-league success)
            ``label``        — "Elite" | "Promising" | "Developing"
            ``key_factors``  — list of up to 3 metric names driving the score
    """
    benchmarks = _LEAGUE_BENCHMARKS.get(pos_group, _LEAGUE_BENCHMARKS["Midfielder"])
    feature_keys = list(benchmarks.keys())

    # Build player feature vector (normalised against benchmarks)
    player_vec = np.array(
        [float(career_stats.get(k) or 0) / max(benchmarks[k], 1e-6) for k in feature_keys],
        dtype=np.float32,
    )

    # Build synthetic reference dataset:
    # Row 0 = "elite" player (1.2× benchmark), Row 1 = "average" (1.0×), Row 2 = "low" (0.6×)
    ref_X = np.array([
        [1.2] * len(feature_keys),
        [1.0] * len(feature_keys),
        [0.6] * len(feature_keys),
    ], dtype=np.float32)
    ref_y = np.array([1.0, 0.6, 0.2], dtype=np.float32)

    # Combine reference + player row for TabPFN inference
    X_combined = np.vstack([ref_X, player_vec.reshape(1, -1)])

    score = 0.0
    used_tabpfn = False
    try:
        from tabpfn import TabPFNRegressor

        model = TabPFNRegressor(device="cpu")
        model.fit(ref_X, ref_y)
        raw = model.predict(player_vec.reshape(1, -1))
        score = float(np.clip(raw[0], 0.0, 1.0))
        used_tabpfn = True
    except Exception as e:
        logger.warning(f"get_transferability_score: TabPFN unavailable ({e}). Using rule-based fallback.")

    if not used_tabpfn:
        # Rule-based fallback: mean normalised ratio, clipped to [0, 1]
        score = float(np.clip(np.mean(player_vec), 0.0, 1.0))

    # Key factors = top-3 features closest to or exceeding benchmark
    ratios = list(zip(feature_keys, player_vec.tolist()))
    top_factors = [k for k, v in sorted(ratios, key=lambda x: x[1], reverse=True)[:3]]

    if score >= 0.75:
        label = "Elite"
    elif score >= 0.45:
        label = "Promising"
    else:
        label = "Developing"

    result = {"score": round(score, 3), "label": label, "key_factors": top_factors}

    # Optionally cache
    if player_id:
        try:
            registry = ModelRegistry()
            registry.save(
                result,
                model_id=f"transferability_{player_id}",
                model_type="predictors",
                metrics={"score": score},
                features=feature_keys,
            )
        except Exception:
            pass

    return result


def compute_shap(model: Any, X: np.ndarray) -> np.ndarray:
    """
    Computes SHAP values for the given model and input matrix.

    Args:
        model: Trained model (XGBoost or compatible tree model).
        X: Feature matrix (n_samples, n_features).

    Returns:
        2D numpy array of SHAP values (n_samples, n_features).
    """
    import shap

    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
    except Exception:
        logger.warning("TreeExplainer failed; falling back to shap.Explainer.")
        explainer = shap.Explainer(model)
        explanation = explainer(X)
        shap_values = explanation.values

    return np.array(shap_values)
