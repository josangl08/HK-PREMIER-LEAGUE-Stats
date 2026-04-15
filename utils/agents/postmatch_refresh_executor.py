# ABOUTME: Refresh executor for postmatch-stage intelligence that re-runs orchestration off the render path.
# ABOUTME: Keeps callbacks and future background workers on one explicit postmatch refresh entrypoint.

from __future__ import annotations

from typing import Any, Dict

from utils.agents.postmatch_intelligence_orchestrator import orchestrate_postmatch_intelligence
from utils.intelligence.artifact_registry import ArtifactRegistry


def execute_postmatch_refresh(
    payload: Dict[str, Any],
    *,
    registry: ArtifactRegistry | None = None,
) -> Dict[str, Any]:
    """Force-refresh the postmatch runtime payload for the current scope."""
    return orchestrate_postmatch_intelligence(
        payload,
        registry=registry,
        force_refresh=True,
    )
