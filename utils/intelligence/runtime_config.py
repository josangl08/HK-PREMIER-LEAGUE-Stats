# ABOUTME: Runtime configuration helpers for stage intelligence persistence, storage roots, and debug logging flags.
# ABOUTME: Centralizes environment-driven settings so artifact storage behavior can change across environments without code edits.

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict


def _read_bool_env(name: str, default: bool) -> bool:
    """Read a boolean environment variable using common truthy/falsey forms."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _read_path_env(name: str, default: Path) -> Path:
    """Read a path environment variable or fall back to the provided default path."""
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    return Path(raw_value).expanduser()


def get_intelligence_runtime_config() -> Dict[str, Any]:
    """Return the resolved runtime configuration for stage intelligence persistence."""
    project_root = Path(__file__).resolve().parents[2]
    runtime_root = _read_path_env(
        "INTELLIGENCE_RUNTIME_ROOT",
        project_root / "runtime",
    )
    artifacts_root = _read_path_env(
        "INTELLIGENCE_ARTIFACTS_ROOT",
        runtime_root / "intelligence_artifacts",
    )
    session_memory_root = _read_path_env(
        "INTELLIGENCE_SESSION_MEMORY_ROOT",
        runtime_root / "intelligence_session_memory",
    )
    return {
        "runtime_root": runtime_root,
        "artifacts_root": artifacts_root,
        "session_memory_root": session_memory_root,
        "persistence_enabled": _read_bool_env("INTELLIGENCE_PERSISTENCE_ENABLED", True),
        "derived_writes_enabled": _read_bool_env("INTELLIGENCE_DERIVED_WRITES_ENABLED", True),
        "debug_logging_enabled": _read_bool_env("INTELLIGENCE_DEBUG_LOGGING_ENABLED", False),
        "artifact_max_entries": int(os.getenv("INTELLIGENCE_ARTIFACT_MAX_ENTRIES", "500")),
        "artifact_max_age_hours": int(os.getenv("INTELLIGENCE_ARTIFACT_MAX_AGE_HOURS", "168")),
        "session_memory_max_entries": int(os.getenv("INTELLIGENCE_SESSION_MEMORY_MAX_ENTRIES", "500")),
        "session_memory_max_age_hours": int(os.getenv("INTELLIGENCE_SESSION_MEMORY_MAX_AGE_HOURS", "168")),
    }
