# ABOUTME: Filesystem-backed registry for persisted intelligence artifacts with simple get, put, and invalidation APIs.
# ABOUTME: Stores JSON payloads plus registry metadata so tests and runtime can reuse analytical artifacts without external services.

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Optional

from utils.intelligence.runtime_config import get_intelligence_runtime_config


class ArtifactRegistry:
    """Filesystem registry for stage-intelligence artifacts."""

    def __init__(self, base_dir: Path | str | None = None):
        runtime_config = get_intelligence_runtime_config()
        if base_dir is None:
            base_dir = runtime_config["artifacts_root"]
        self.base_dir = Path(base_dir)
        self.artifacts_dir = self.base_dir / "artifacts"
        self.registry_path = self.base_dir / "registry.json"
        self.persistence_enabled = bool(runtime_config["persistence_enabled"])
        self.max_entries = int(runtime_config["artifact_max_entries"])
        self.max_age_hours = int(runtime_config["artifact_max_age_hours"])
        self._initialize_storage()

    def _initialize_storage(self) -> None:
        if not self.persistence_enabled:
            return
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if not self.registry_path.exists():
            self.registry_path.write_text("{}", encoding="utf-8")

    def _load_index(self) -> Dict[str, Dict[str, Any]]:
        if not self.persistence_enabled or not self.registry_path.exists():
            return {}
        return json.loads(self.registry_path.read_text(encoding="utf-8"))

    def _save_index(self, index: Dict[str, Dict[str, Any]]) -> None:
        if not self.persistence_enabled:
            return
        self.registry_path.write_text(
            json.dumps(index, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _artifact_filename(self, artifact_key: str) -> str:
        digest = sha256(artifact_key.encode("utf-8")).hexdigest()
        return f"{digest}.json"

    def _artifact_path(self, artifact_key: str) -> Path:
        return self.artifacts_dir / self._artifact_filename(artifact_key)

    def get_artifact(self, artifact_key: str) -> Optional[Dict[str, Any]]:
        """Return a stored artifact payload by key."""
        if not self.persistence_enabled:
            return None
        index = self._load_index()
        entry = index.get(artifact_key)
        if entry is None:
            return None

        artifact_path = self._artifact_path(artifact_key)
        if not artifact_path.exists():
            index.pop(artifact_key, None)
            self._save_index(index)
            return None

        return json.loads(artifact_path.read_text(encoding="utf-8"))

    def put_artifact(self, artifact_key: str, artifact: Dict[str, Any]) -> Dict[str, Any]:
        """Persist an artifact payload and update registry metadata."""
        stored_artifact = deepcopy(artifact)
        stored_artifact["artifact_key"] = artifact_key
        if not self.persistence_enabled:
            return stored_artifact

        artifact_path = self._artifact_path(artifact_key)
        artifact_path.write_text(
            json.dumps(stored_artifact, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        index = self._load_index()
        index[artifact_key] = {
            "artifact_type": stored_artifact.get("artifact_type"),
            "scope": stored_artifact.get("scope", {}),
            "version": stored_artifact.get("version"),
            "fingerprint": stored_artifact.get("fingerprint"),
            "freshness_status": stored_artifact.get("freshness_status"),
            "dependencies": stored_artifact.get("dependencies", []),
            "path": str(artifact_path),
        }
        self._save_index(index)
        return stored_artifact

    def invalidate_artifact(self, artifact_key: str) -> bool:
        """Delete an artifact payload and registry entry when present."""
        if not self.persistence_enabled:
            return False
        index = self._load_index()
        existed = artifact_key in index
        index.pop(artifact_key, None)
        self._save_index(index)

        artifact_path = self._artifact_path(artifact_key)
        artifact_path.unlink(missing_ok=True)
        return existed or artifact_path.exists()

    def prune_artifacts(
        self,
        *,
        max_entries: int | None = None,
        max_age_hours: int | None = None,
    ) -> Dict[str, Any]:
        """Prune artifact entries by age and count without running during render by default."""
        if not self.persistence_enabled:
            return {"pruned_keys": [], "remaining_entries": 0}

        max_entries = self.max_entries if max_entries is None else int(max_entries)
        max_age_hours = self.max_age_hours if max_age_hours is None else int(max_age_hours)
        index = self._load_index()
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=max_age_hours)
        candidates = []
        pruned_keys = []

        for artifact_key, entry in index.items():
            artifact = self.get_artifact(artifact_key)
            computed_at_raw = str((artifact or {}).get("computed_at") or "")
            computed_at = None
            if computed_at_raw:
                try:
                    computed_at = datetime.fromisoformat(computed_at_raw.replace("Z", "+00:00"))
                except ValueError:
                    computed_at = None
            candidates.append(
                {
                    "artifact_key": artifact_key,
                    "computed_at": computed_at,
                }
            )
            if computed_at is not None and computed_at < cutoff:
                if self.invalidate_artifact(artifact_key):
                    pruned_keys.append(artifact_key)

        if max_entries >= 0:
            remaining_index = self._load_index()
            remaining_candidates = []
            for artifact_key in remaining_index:
                artifact = self.get_artifact(artifact_key)
                computed_at_raw = str((artifact or {}).get("computed_at") or "")
                computed_at = None
                if computed_at_raw:
                    try:
                        computed_at = datetime.fromisoformat(computed_at_raw.replace("Z", "+00:00"))
                    except ValueError:
                        computed_at = None
                remaining_candidates.append((artifact_key, computed_at or datetime.min.replace(tzinfo=timezone.utc)))
            remaining_candidates.sort(key=lambda item: item[1], reverse=True)
            for artifact_key, _ in remaining_candidates[max_entries:]:
                if self.invalidate_artifact(artifact_key) and artifact_key not in pruned_keys:
                    pruned_keys.append(artifact_key)

        return {
            "pruned_keys": pruned_keys,
            "remaining_entries": len(self._load_index()),
        }


_DEFAULT_REGISTRY: ArtifactRegistry | None = None


def _get_default_registry() -> ArtifactRegistry:
    """Lazily initialize the shared registry to avoid import-time filesystem side effects."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = ArtifactRegistry()
    return _DEFAULT_REGISTRY


def get_artifact(
    artifact_key: str,
    registry: ArtifactRegistry | None = None,
) -> Optional[Dict[str, Any]]:
    """Module-level getter that defaults to the shared registry instance."""
    active_registry = registry or _get_default_registry()
    return active_registry.get_artifact(artifact_key)


def put_artifact(
    artifact_key: str,
    artifact: Dict[str, Any],
    registry: ArtifactRegistry | None = None,
) -> Dict[str, Any]:
    """Module-level put helper for the shared registry instance."""
    active_registry = registry or _get_default_registry()
    return active_registry.put_artifact(artifact_key, artifact)


def invalidate_artifact(
    artifact_key: str,
    registry: ArtifactRegistry | None = None,
) -> bool:
    """Module-level invalidation helper for the shared registry instance."""
    active_registry = registry or _get_default_registry()
    return active_registry.invalidate_artifact(artifact_key)
