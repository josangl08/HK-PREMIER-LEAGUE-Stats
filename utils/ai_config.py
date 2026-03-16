# ABOUTME: Centralized AI configuration for all three TFM tracks (ML, Agentic, GenAI).
# ABOUTME: Loads API keys from environment and defines model paths and hyperparameter defaults.

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent

MODELS_DIR = _PROJECT_ROOT / "models"
MODEL_REGISTRY_PATH = MODELS_DIR / "registry.json"

# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY is None:
    logger.warning(
        "GOOGLE_API_KEY environment variable is not set. "
        "Features requiring Gemini (narrative generation, agent, background gen) "
        "will be unavailable."
    )

# Alias for backward compatibility if needed, though GOOGLE_API_KEY is preferred
GEMINI_API_KEY = GOOGLE_API_KEY

# ---------------------------------------------------------------------------
# Hyperparameter Defaults
# ---------------------------------------------------------------------------

AI_DEFAULTS = {
    # Track 1 — ML Analítico
    "xgboost": {
        "n_estimators": 300,
        "max_depth": 4,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": 42,
    },
    "kmeans": {
        "max_k": 8,          # Upper bound for elbow/silhouette search
        "random_state": 42,
        "n_init": 10,
    },
    "umap": {
        "n_components": 2,
        "n_neighbors": 15,
        "min_dist": 0.1,
        "random_state": 42,
    },
    # Track 1 — Similarity
    "sentence_transformer": {
        "model_name": "all-MiniLM-L6-v2",
    },
    # Track 2 — Agentic
    "langgraph": {
        "llm_model": "gemini-1.5-flash",
        "max_iterations": 10,
        "temperature": 0.2,
    },
    # Track 3 — GenAI
    "gemini": {
        "model": "gemini-1.5-flash",
        "temperature": 0.7,
        "max_output_tokens": 1024,
    },
}
