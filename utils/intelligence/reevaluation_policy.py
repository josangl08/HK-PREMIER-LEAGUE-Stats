# ABOUTME: Explicit reevaluation helpers for deciding when persisted stage analyses must be recomputed.
# ABOUTME: Separates freshness and dependency-change checks from stage-specific reasoning logic.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping


@dataclass(frozen=True)
class ReevaluationDecision:
    should_reevaluate: bool
    reasons: List[str]
    changed_dependencies: List[str]
    freshness_status: str


def _freshness_state(entry: Mapping[str, Any] | None) -> str:
    freshness = ((entry or {}).get("freshness") or {}).get("status")
    return str(freshness or "")


def decide_stage_reevaluation(
    *,
    artifact_states: Mapping[str, Mapping[str, Any]] | None,
    dependency_fingerprints: Mapping[str, str] | None,
    trigger_context: Mapping[str, Any] | None = None,
) -> ReevaluationDecision:
    """Return an explicit reevaluation decision for a stage analysis."""
    artifact_states = artifact_states or {}
    dependency_fingerprints = dependency_fingerprints or {}
    trigger_context = trigger_context or {}

    reasons: List[str] = []
    changed_dependencies: List[str] = []
    freshness_status = "fresh"

    for artifact_type, state in artifact_states.items():
        state_status = _freshness_state(state)
        if state_status and state_status != "fresh":
            freshness_status = state_status
            reasons.append(f"artifact_{artifact_type}_{state_status}")

    for dependency_name, dependency_fp in dependency_fingerprints.items():
        current_artifact = (artifact_states.get(dependency_name) or {}).get("artifact") or {}
        stored_fp = str(current_artifact.get("fingerprint") or "")
        if dependency_fp and stored_fp and dependency_fp != stored_fp:
            changed_dependencies.append(str(dependency_name))

    if changed_dependencies:
        reasons.append("dependency_fingerprint_changed")

    if trigger_context.get("force"):
        reasons.append("forced_trigger")

    return ReevaluationDecision(
        should_reevaluate=bool(reasons),
        reasons=reasons,
        changed_dependencies=changed_dependencies,
        freshness_status=freshness_status,
    )
