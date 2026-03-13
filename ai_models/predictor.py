# ABOUTME: Regression models for performance prediction (XGBoost & TabPFN).
# ABOUTME: Handles training, inference, and SHAP explainability for goals, assists, and xG.

"""
Predictor module for player performance forecasting.
Includes classical (XGBoost) and state-of-the-art (TabPFN) tabular models.
"""

# Standard Library
import logging
from typing import Any, Dict, List, Optional, Tuple

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
            n_estimators=200, learning_rate=0.05, random_state=42, verbosity=0
        )
        fold_model.fit(X_tr, y_tr)
        preds = fold_model.predict(X_val)
        rmse_scores.append(float(np.sqrt(mean_squared_error(y_val, preds))))
        mae_scores.append(float(mean_absolute_error(y_val, preds)))
        r2_scores.append(float(r2_score(y_val, preds)))

    # Final model trained on all data
    model = xgb.XGBRegressor(
        n_estimators=200, learning_rate=0.05, random_state=42, verbosity=0
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
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

        model = TabPFNRegressor(device="cpu")
        model.fit(X, y)
        preds = model.predict(X)
        metrics = {
            "rmse": float(np.sqrt(mean_squared_error(y, preds))),
            "mae": float(mean_absolute_error(y, preds)),
            "r2": float(r2_score(y, preds)),
        }
        logger.info(f"TabPFN [{target}] train metrics: {metrics}")

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
