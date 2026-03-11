# ABOUTME: Filesystem-based model registry for persisting and loading trained AI models.
# ABOUTME: Supports versioning (max 3 per model_id), metadata tracking, and auto-directory setup.

import json
import logging
import joblib
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_VERSIONS = 3

SUBDIRS = ["predictors", "clustering", "embeddings"]


class ModelNotFoundError(Exception):
    """Raised when a requested model_id or version does not exist in the registry."""
    pass


class ModelRegistry:
    """Filesystem model registry. Stores models as .pkl files with JSON metadata."""

    def __init__(self, models_dir=None):
        if models_dir is None:
            models_dir = Path(__file__).parent.parent / "models"
        self.models_dir = Path(models_dir)
        self.registry_path = self.models_dir / "registry.json"
        self._init_dirs()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_dirs(self):
        self.models_dir.mkdir(parents=True, exist_ok=True)
        for sub in SUBDIRS:
            (self.models_dir / sub).mkdir(exist_ok=True)
        if not self.registry_path.exists():
            self.registry_path.write_text("{}", encoding="utf-8")

    def _load_registry(self):
        return json.loads(self.registry_path.read_text(encoding="utf-8"))

    def _save_registry(self, data):
        self.registry_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, model, model_id, model_type, metrics, features):
        """Persist a trained model with metadata. Prunes to MAX_VERSIONS.

        Args:
            model: Trained model object (sklearn/xgboost/tabpfn compatible).
            model_id (str): Unique identifier for this model.
            model_type (str): Subdirectory category ('predictors', 'clustering', 'embeddings').
            metrics (dict): Evaluation metrics (e.g. {'rmse': 0.5}).
            features (list): Feature names used during training.
        """
        registry = self._load_registry()
        entry = registry.setdefault(model_id, {"versions": []})

        # Determine next version number
        versions = entry["versions"]
        next_version = (versions[-1]["version"] + 1) if versions else 1

        # Serialize model
        pkl_path = self.models_dir / model_type / f"{model_id}_v{next_version}.pkl"
        joblib.dump(model, pkl_path)

        version_entry = {
            "version": next_version,
            "path": str(pkl_path),
            "model_type": model_type,
            "metrics": metrics,
            "features": features,
            "trained_at": datetime.now(timezone.utc).isoformat(),
        }

        # Append and prune oldest if over limit
        versions.append(version_entry)
        if len(versions) > MAX_VERSIONS:
            oldest = versions.pop(0)
            try:
                Path(oldest["path"]).unlink(missing_ok=True)
            except Exception:
                pass

        entry["latest"] = versions[-1]
        self._save_registry(registry)

    def load(self, model_id, version=None):
        """Load a model by model_id, optionally specifying a version number.

        Args:
            model_id (str): The model identifier.
            version (int | None): Specific version to load. None loads the latest.

        Returns:
            The deserialized model object.

        Raises:
            ModelNotFoundError: If model_id or version does not exist.
        """
        registry = self._load_registry()
        if model_id not in registry:
            raise ModelNotFoundError(f"Model '{model_id}' not found in registry.")

        entry = registry[model_id]
        if version is None:
            pkl_path = entry["latest"]["path"]
        else:
            matches = [v for v in entry["versions"] if v["version"] == version]
            if not matches:
                raise ModelNotFoundError(
                    f"Model '{model_id}' version {version} not found in registry."
                )
            pkl_path = matches[0]["path"]

        return joblib.load(pkl_path)

    def list_models(self):
        """Return metadata for all registered models.

        Returns:
            list[dict]: Each dict has model_id, version, model_type, trained_at, metrics.
        """
        registry = self._load_registry()
        result = []
        for model_id, entry in registry.items():
            latest = entry.get("latest", {})
            result.append({
                "model_id": model_id,
                "version": latest.get("version"),
                "model_type": latest.get("model_type"),
                "trained_at": latest.get("trained_at"),
                "metrics": latest.get("metrics", {}),
            })
        return result
