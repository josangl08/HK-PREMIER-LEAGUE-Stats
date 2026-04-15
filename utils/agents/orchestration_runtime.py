# ABOUTME: Shared orchestration runtime helpers for stage intelligence modules that manage fresh artifacts and session updates.
# ABOUTME: Keeps season and career aligned on freshness checks, artifact collection, and graceful session-memory persistence.

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Mapping


def is_fresh_artifact_state(artifact_state: Mapping[str, Any] | None) -> bool:
    """Return whether an artifact-state entry is fresh."""
    return str(((artifact_state or {}).get("freshness") or {}).get("status") or "") == "fresh"


def collect_fresh_payload_artifacts(
    artifact_states: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Return fresh artifact envelopes keyed by artifact type."""
    fresh_artifacts: Dict[str, Dict[str, Any]] = {}
    for artifact_type, state in artifact_states.items():
        if is_fresh_artifact_state(state) and state.get("artifact"):
            fresh_artifacts[artifact_type] = dict(state["artifact"])
    return fresh_artifacts


def sync_session_memory_with_graceful_failure(
    *,
    persist_fn: Callable[[], Dict[str, Any]],
    logger: logging.Logger,
    log_message: str,
    log_args: tuple[Any, ...],
    existing_memory: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Persist session memory but degrade gracefully when persistence fails."""
    try:
        stored_memory = persist_fn()
        return {
            "memory": stored_memory,
            "persisted": True,
            "failure": None,
        }
    except Exception as exc:
        logger.exception(log_message, *log_args, exc)
        return {
            "memory": dict(existing_memory or {}),
            "persisted": False,
            "failure": str(exc),
        }
