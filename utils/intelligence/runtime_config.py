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
        "stage_analysis_store_reuse_enabled": _read_bool_env("INTELLIGENCE_STAGE_ANALYSIS_STORE_REUSE_ENABLED", True),
        "derived_writes_enabled": _read_bool_env("INTELLIGENCE_DERIVED_WRITES_ENABLED", True),
        "debug_logging_enabled": _read_bool_env("INTELLIGENCE_DEBUG_LOGGING_ENABLED", False),
        "season_agent_llm_enabled": _read_bool_env("INTELLIGENCE_SEASON_AGENT_LLM_ENABLED", False),
        "season_agent_model_profile": str(os.getenv("INTELLIGENCE_SEASON_AGENT_MODEL_PROFILE", "flash")).strip().lower() or "flash",
        "season_agent_max_tools": int(os.getenv("INTELLIGENCE_SEASON_AGENT_MAX_TOOLS", "3")),
        "season_agent_model_retries": int(os.getenv("INTELLIGENCE_SEASON_AGENT_MODEL_RETRIES", "1")),
        "season_agent_retry_delay_seconds": float(os.getenv("INTELLIGENCE_SEASON_AGENT_RETRY_DELAY_SECONDS", "0.35")),
        "prematch_agent_llm_enabled": _read_bool_env("INTELLIGENCE_PREMATCH_AGENT_LLM_ENABLED", False),
        "prematch_agent_model_profile": str(os.getenv("INTELLIGENCE_PREMATCH_AGENT_MODEL_PROFILE", "flash")).strip().lower() or "flash",
        "prematch_agent_max_tools": int(os.getenv("INTELLIGENCE_PREMATCH_AGENT_MAX_TOOLS", "3")),
        "prematch_agent_model_retries": int(os.getenv("INTELLIGENCE_PREMATCH_AGENT_MODEL_RETRIES", "1")),
        "prematch_agent_retry_delay_seconds": float(os.getenv("INTELLIGENCE_PREMATCH_AGENT_RETRY_DELAY_SECONDS", "0.35")),
        "career_agent_llm_enabled": _read_bool_env("INTELLIGENCE_CAREER_AGENT_LLM_ENABLED", False),
        "career_agent_model_profile": str(os.getenv("INTELLIGENCE_CAREER_AGENT_MODEL_PROFILE", "flash")).strip().lower() or "flash",
        "career_agent_max_tools": int(os.getenv("INTELLIGENCE_CAREER_AGENT_MAX_TOOLS", "3")),
        "career_agent_model_retries": int(os.getenv("INTELLIGENCE_CAREER_AGENT_MODEL_RETRIES", "1")),
        "career_agent_retry_delay_seconds": float(os.getenv("INTELLIGENCE_CAREER_AGENT_RETRY_DELAY_SECONDS", "0.35")),
        "career_dashboard_ai_enabled": _read_bool_env("INTELLIGENCE_CAREER_DASHBOARD_AI_ENABLED", False),
        "artifact_max_entries": int(os.getenv("INTELLIGENCE_ARTIFACT_MAX_ENTRIES", "500")),
        "artifact_max_age_hours": int(os.getenv("INTELLIGENCE_ARTIFACT_MAX_AGE_HOURS", "168")),
        "session_memory_max_entries": int(os.getenv("INTELLIGENCE_SESSION_MEMORY_MAX_ENTRIES", "500")),
        "session_memory_max_age_hours": int(os.getenv("INTELLIGENCE_SESSION_MEMORY_MAX_AGE_HOURS", "168")),
    }
