# ABOUTME: LSTM-based time-series model for match-by-match player performance forecasting.
# ABOUTME: Detects form, fatigue, and streaks from MatchHistory data. ADR-003 compliant (no Dash/Flask).

# Standard Library
import logging
from typing import Any, Dict, List, Optional

# Third-party
import numpy as np

logger = logging.getLogger(__name__)

_MIN_MATCHES_FOR_LSTM = 10


def build_match_sequences(
    match_records: List[Dict],
    feature_cols: List[str],
    seq_len: int = 5,
) -> np.ndarray:
    """
    Converts a chronologically ordered list of match dicts into overlapping
    sliding-window sequences for LSTM input.

    Args:
        match_records: List of dicts with at least the keys in feature_cols.
                       Must be sorted ascending by date before calling.
        feature_cols:  Column names to extract as features.
        seq_len:       Window size (number of past matches per sequence).

    Returns:
        Array of shape (n_sequences, seq_len, n_features).
        Returns empty array if fewer than seq_len+1 records.
    """
    if len(match_records) <= seq_len:
        return np.empty((0, seq_len, len(feature_cols)), dtype=np.float32)

    matrix = np.array(
        [[float(r.get(col) or 0) for col in feature_cols] for r in match_records],
        dtype=np.float32,
    )

    sequences = []
    for i in range(len(matrix) - seq_len):
        sequences.append(matrix[i : i + seq_len])

    return np.array(sequences, dtype=np.float32)


def train_lstm(
    sequences: np.ndarray,
    targets: np.ndarray,
    hidden_dim: int = 32,
    epochs: int = 50,
) -> Any:
    """
    Trains a single-layer LSTM regressor on match sequences.
    Falls back to a Ridge linear regression if PyTorch is unavailable.

    Args:
        sequences: Shape (n, seq_len, n_features).
        targets:   Shape (n,) — target values for the next match.
        hidden_dim: LSTM hidden state size.
        epochs:    Training epochs (PyTorch path only).

    Returns:
        Trained model object (PyTorch nn.Module or sklearn Ridge).
    """
    if len(sequences) == 0:
        raise ValueError("train_lstm: sequences array is empty.")

    try:
        import torch
        import torch.nn as nn

        n_samples, seq_len, n_features = sequences.shape

        class _LSTMRegressor(nn.Module):
            def __init__(self):
                super().__init__()
                self.lstm = nn.LSTM(n_features, hidden_dim, batch_first=True)
                self.fc   = nn.Linear(hidden_dim, 1)

            def forward(self, x):
                _, (h, _) = self.lstm(x)
                return self.fc(h[-1]).squeeze(-1)

        model = _LSTMRegressor()
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        criterion = nn.MSELoss()

        X_t = torch.tensor(sequences, dtype=torch.float32)
        y_t = torch.tensor(targets, dtype=torch.float32)

        model.train()
        for _ in range(epochs):
            optimizer.zero_grad()
            loss = criterion(model(X_t), y_t)
            loss.backward()
            optimizer.step()

        model.eval()
        logger.info(f"LSTM trained: {n_samples} samples, {epochs} epochs, hidden={hidden_dim}")
        return model

    except ImportError:
        logger.warning("PyTorch not available — falling back to Ridge regression for LSTM task.")
        from sklearn.linear_model import Ridge

        n_samples = sequences.shape[0]
        X_flat = sequences.reshape(n_samples, -1)
        model = Ridge(alpha=1.0)
        model.fit(X_flat, targets)
        return model


def forecast_next_match(model: Any, last_sequence: np.ndarray) -> Dict:
    """
    Predicts the next-match value given the most recent sequence window.

    Args:
        model:         Trained LSTM or Ridge model.
        last_sequence: Shape (seq_len, n_features).

    Returns:
        Dict with keys: ``prediction`` (float), ``confidence`` (float 0-1).
        Confidence is derived from the model type (LSTM: 0.70 baseline; Ridge: 0.55).
    """
    try:
        try:
            import torch
            import torch.nn as nn
            if isinstance(model, nn.Module):
                model.eval()
                x = torch.tensor(last_sequence[np.newaxis, ...], dtype=torch.float32)
                with torch.no_grad():
                    pred = float(model(x).item())
                return {"prediction": max(0.0, pred), "confidence": 0.70}
        except ImportError:
            pass

        # Ridge / sklearn path
        x_flat = last_sequence.reshape(1, -1)
        pred = float(model.predict(x_flat)[0])
        return {"prediction": max(0.0, pred), "confidence": 0.55}

    except Exception as e:
        logger.warning(f"forecast_next_match error: {e}")
        return {"prediction": 0.0, "confidence": 0.0}


def get_form_trend(
    match_records: List[Dict],
    metric: str,
    window: int = 5,
) -> Dict:
    """
    Computes recent form trend for a player across their last ``window`` matches.

    Args:
        match_records: Chronologically ordered list of match dicts.
        metric:        Key to inspect (e.g. ``"goals"``, ``"minutes_played"``).
        window:        Number of recent matches to use.

    Returns:
        Dict with:
            ``trend``       — "improving" | "declining" | "stable"
            ``slope``       — linear regression slope over the window
            ``last_n_avg``  — mean of the metric over the window
            ``error``       — present only when data is insufficient

    Requires ≥ ``_MIN_MATCHES_FOR_LSTM`` (10) total records for reliable output.
    """
    if len(match_records) < _MIN_MATCHES_FOR_LSTM:
        return {"error": "insufficient_data", "trend": "stable", "slope": 0.0, "last_n_avg": 0.0}

    recent = match_records[-window:]
    vals = [float(r.get(metric) or 0) for r in recent]

    if not vals or all(v == 0 for v in vals):
        return {"trend": "stable", "slope": 0.0, "last_n_avg": 0.0}

    x = np.arange(len(vals), dtype=np.float64)
    y = np.array(vals, dtype=np.float64)
    slope = float(np.polyfit(x, y, 1)[0])

    if slope > 0.05:
        trend = "improving"
    elif slope < -0.05:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "trend": trend,
        "slope": round(slope, 4),
        "last_n_avg": round(float(np.mean(vals)), 3),
    }
