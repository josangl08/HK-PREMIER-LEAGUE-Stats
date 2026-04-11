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
# API Keys & Methods
# ---------------------------------------------------------------------------

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
AI_METHOD = os.getenv("AI_METHOD", "api_key")  # 'api_key', 'subscription', 'vertexai'
VERTEX_PROJECT = os.getenv("VERTEX_PROJECT")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")

if AI_METHOD == "api_key" and GOOGLE_API_KEY is None:
    logger.warning(
        "AI_METHOD is 'api_key' but GOOGLE_API_KEY environment variable is not set. "
        "Features requiring Gemini will be unavailable."
    )
elif AI_METHOD == "subscription" and not os.path.exists(_PROJECT_ROOT / "token.json"):
    logger.warning(
        "AI_METHOD is 'subscription' but 'token.json' is missing. "
        "Run 'python scripts/auth_bridge.py' to authenticate."
    )
elif AI_METHOD == "vertexai" and not VERTEX_PROJECT:
    logger.warning(
        "AI_METHOD is 'vertexai' but VERTEX_PROJECT is not set."
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
    # Track 2 — Agentic (Tier 1 Elite Strategy)
    "orchestrator": {
        "primary": "gemini-3-pro-preview",
        "fallback": "gemini-2.5-pro",
        "temperature": 0.0,
    },
    "worker": {
        "primary": "gemini-3-flash-preview",
        "fallback_1": "gemini-2.5-flash",
        "fallback_2": "gemini-2.5-flash-lite-preview-06-17",
        "temperature": 0.7,
    },
    "researcher": {
        "model": "deep-research-pro-preview-12-2025",
        "temperature": 0.2,
    },
    "image_gen": {
        "tier_1": "gemini-3-pro-image-preview",   # Nano Banana Pro (1/day)
        "tier_2": "gemini-3.1-flash-image-preview", # Nano Banana 2 (next 5)
        "tier_3": "gemini-2.5-flash-image",        # Nano Banana (next 10)
    },
    # Track 3 — GenAI
    "gemini": {
        "model": "gemini-2.5-pro",
        "temperature": 0.7,
        "max_output_tokens": 2048,
    },
}
