# ABOUTME: Refresh executor for prematch-stage intelligence that re-runs orchestration off the render path.
# ABOUTME: Keeps callbacks and future background workers on one explicit prematch refresh entrypoint.

from __future__ import annotations

from typing import Any, Dict

from utils.agents.prematch_intelligence_orchestrator import orchestrate_prematch_intelligence
from utils.intelligence.artifact_registry import ArtifactRegistry


def execute_prematch_refresh(
    payload: Dict[str, Any],
    *,
    registry: ArtifactRegistry | None = None,
) -> Dict[str, Any]:
    """Force-refresh the prematch runtime payload for the current scope."""
    return orchestrate_prematch_intelligence(
        payload,
        registry=registry,
        force_refresh=True,
    )
