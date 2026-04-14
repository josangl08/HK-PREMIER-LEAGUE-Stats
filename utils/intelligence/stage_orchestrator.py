# ABOUTME: Shared runtime for persisted stage analyses, reevaluation decisions, and overlay preparation.
# ABOUTME: Reuses or recomputes stage intelligence outside the critical render path using one analysis contract.

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from utils.agents.stage_agents.base import StageAgent
from utils.intelligence.artifact_keys import build_artifact_key
from utils.intelligence.artifact_registry import ArtifactRegistry
from utils.intelligence.discovery_contracts import StageAnalysis, coerce_stage_analysis, serialize_stage_analysis
from utils.intelligence.discovery_overlay_mapper import build_overlay_candidates_from_analysis
from utils.intelligence.overlay_surface import resolve_stage_overlay_surface
from utils.intelligence.reevaluation_policy import ReevaluationDecision


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_stage_analysis_artifact(
    *,
    stage_name: str,
    scope: Mapping[str, Any],
    analysis: StageAnalysis,
    dependency_fingerprint_map: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """Build a generic persisted artifact envelope for a shared stage analysis."""
    normalized_scope = {str(key): str(value) for key, value in dict(scope or {}).items()}
    artifact_type = f"{stage_name}_stage_analysis_runtime"
    return {
        "artifact_key": build_artifact_key(artifact_type, normalized_scope),
        "artifact_type": artifact_type,
        "scope": normalized_scope,
        "version": "1.0",
        "computed_at": _utc_timestamp(),
        "expires_at": None,
        "freshness_status": "fresh",
        "fingerprint": build_artifact_key(artifact_type, {**normalized_scope, **dict(dependency_fingerprint_map or {})}),
        "dependencies": sorted(str(key) for key in dict(dependency_fingerprint_map or {})),
        "dependency_fingerprint_map": dict(dependency_fingerprint_map or {}),
        "payload": serialize_stage_analysis(analysis),
    }


def get_persisted_stage_analysis(
    *,
    stage_name: str,
    scope: Mapping[str, Any],
    registry: ArtifactRegistry | None = None,
) -> StageAnalysis | None:
    """Return the persisted shared analysis artifact payload for a given stage scope."""
    active_registry = registry or ArtifactRegistry()
    artifact_key = build_artifact_key(f"{stage_name}_stage_analysis_runtime", dict(scope or {}))
    artifact = active_registry.get_artifact(artifact_key)
    if not artifact:
        return None
    return coerce_stage_analysis((artifact.get("payload") or {}))


def orchestrate_stage_analysis(
    *,
    stage_name: str,
    scope: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
    dependency_fingerprint_map: Mapping[str, str] | None,
    decision: ReevaluationDecision,
    agent: StageAgent,
    registry: ArtifactRegistry | None = None,
    session_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Reuse or recompute a stage analysis and prepare a shared overlay surface."""
    active_registry = registry or ArtifactRegistry()
    persisted_analysis = get_persisted_stage_analysis(
        stage_name=stage_name,
        scope=scope,
        registry=active_registry,
    )

    served_from = "artifact"
    analysis = persisted_analysis
    if analysis is None or decision.should_reevaluate:
        analysis = agent.analyze(
            scope={str(key): str(value) for key, value in dict(scope or {}).items()},
            artifacts=artifacts,
            session_memory=session_memory,
        )
        artifact = build_stage_analysis_artifact(
            stage_name=stage_name,
            scope=scope,
            analysis=analysis,
            dependency_fingerprint_map=dependency_fingerprint_map,
        )
        active_registry.put_artifact(artifact["artifact_key"], artifact)
        served_from = "agent"

    overlay_payload = build_overlay_candidates_from_analysis(analysis)
    overlay_surface = resolve_stage_overlay_surface(stage_name, overlay_payload)
    return {
        "analysis": serialize_stage_analysis(analysis),
        "overlay_payload": overlay_payload,
        "overlay_surface": overlay_surface,
        "served_from": served_from,
        "reevaluation": {
            "should_reevaluate": decision.should_reevaluate,
            "reasons": list(decision.reasons),
            "changed_dependencies": list(decision.changed_dependencies),
            "freshness_status": decision.freshness_status,
        },
    }
