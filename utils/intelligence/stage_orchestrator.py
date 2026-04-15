# ABOUTME: Shared runtime helpers for persisted stage analyses, overlay preparation, and cross-stage artifact envelopes.
# ABOUTME: Reuses or recomputes stage intelligence outside the critical render path using one analysis contract and one runtime-result shape.

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Any, Dict, Mapping

from utils.agents.stage_agents.base import StageAgent
from utils.intelligence.artifact_keys import build_artifact_key
from utils.intelligence.artifact_registry import ArtifactRegistry
from utils.intelligence.discovery_contracts import StageAnalysis, coerce_stage_analysis, serialize_stage_analysis
from utils.intelligence.discovery_overlay_mapper import build_overlay_candidates_from_analysis
from utils.intelligence.freshness_manager import FRESHNESS_FRESH, build_artifact_fingerprint
from utils.intelligence.overlay_surface import resolve_stage_overlay_surface
from utils.intelligence.reevaluation_policy import ReevaluationDecision
from utils.intelligence.versioning import ARTIFACT_SCHEMA_VERSION


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class StageRuntimeHooks:
    """Shared hook surface for stage-specific runtime dependencies."""

    stage_name: str
    base_artifact_loader: str
    derived_artifact_builder: str
    analysis_builder: str
    overlay_builder: str
    session_memory_getter: str
    session_memory_putter: str
    viability_predicate: str
    curation_function: str
    refresh_executor: str


def build_runtime_artifact_record(
    *,
    artifact_type: str,
    scope: Mapping[str, Any],
    payload: Mapping[str, Any],
    ttl_hours: int | None,
    fingerprint_inputs: Mapping[str, Any],
    dependency_fingerprint_map: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """Build a shared persisted artifact envelope for any stage-runtime artifact."""
    normalized_scope = {str(key): str(value) for key, value in dict(scope or {}).items()}
    dependency_fingerprint_map = {
        str(key): str(value)
        for key, value in dict(dependency_fingerprint_map or {}).items()
        if str(value)
    }
    computed_at = _utc_timestamp()
    expires_at = None
    if ttl_hours is not None:
        computed = datetime.fromisoformat(computed_at)
        expires_at = computed.replace(microsecond=0) + timedelta(hours=int(ttl_hours))
        expires_at = expires_at.astimezone(timezone.utc).isoformat()
    return {
        "artifact_key": build_artifact_key(artifact_type, normalized_scope),
        "artifact_type": artifact_type,
        "scope": normalized_scope,
        "version": ARTIFACT_SCHEMA_VERSION,
        "computed_at": computed_at,
        "expires_at": expires_at,
        "freshness_status": FRESHNESS_FRESH,
        "fingerprint": build_artifact_fingerprint(dict(fingerprint_inputs or {})),
        "dependency_fingerprints": dependency_fingerprint_map,
        "payload": dict(payload or {}),
    }


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


def build_empty_overlay_surface(stage_name: str) -> Dict[str, Any]:
    """Return the empty shared overlay surface contract for a stage."""
    return {
        "stage": str(stage_name or ""),
        "candidates": [],
        "candidate_count": 0,
        "primary_candidate": None,
        "visible_primary": None,
        "deferred_candidates": [],
        "inbox_entries": [],
    }


def build_stage_runtime_result(
    *,
    stage_name: str,
    state: Mapping[str, Any],
    runtime_config: Mapping[str, Any],
    stage_analysis: Mapping[str, Any] | None,
    shared_stage_analysis: Mapping[str, Any] | None = None,
    signals: Mapping[str, Any] | None = None,
    overlay_candidates: Mapping[str, Any] | None = None,
    overlay_surface: Mapping[str, Any] | None = None,
    served_from: Mapping[str, str] | None = None,
    refresh_plan: list[str] | None = None,
    persisted_artifacts: list[str] | None = None,
    session_memory: Mapping[str, Any] | None = None,
    persisted_session_memory: bool = False,
    base_ready: bool = True,
    fallback_reason: str | None = None,
    write_failures: list[Mapping[str, str]] | None = None,
    reevaluation: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build the shared runtime payload shape used by orchestrated stage intelligence."""
    refresh_plan = list(refresh_plan or [])
    overlay_surface = dict(overlay_surface or build_empty_overlay_surface(stage_name))
    return {
        "available": bool(stage_analysis or overlay_candidates or signals),
        "mode": "fast_path" if not refresh_plan else "slow_path",
        "non_blocking": True,
        "background_refresh_required": bool(refresh_plan),
        "refresh_plan": refresh_plan,
        "stage_analysis": dict(stage_analysis) if isinstance(stage_analysis, Mapping) else stage_analysis,
        "shared_stage_analysis": (
            dict(shared_stage_analysis)
            if isinstance(shared_stage_analysis, Mapping)
            else shared_stage_analysis
        ),
        "signals": dict(signals or {}),
        "overlay_candidates": dict(overlay_candidates or {}),
        "overlay_surface": overlay_surface,
        "reevaluation": dict(reevaluation or {}),
        "debug": {
            "scope": dict(state.get("scope") or {}),
            "served_from": dict(served_from or {}),
            "base_ready": bool(base_ready),
            "non_blocking": True,
            "fallback_reason": fallback_reason,
            "background_refresh_requested": bool(refresh_plan),
            "refresh_requested_for": refresh_plan,
            "persisted_artifacts": list(persisted_artifacts or []),
            "session_memory": dict(session_memory or {}),
            "persisted_session_memory": bool(persisted_session_memory),
            "runtime": {
                "artifacts_root": str(runtime_config.get("artifacts_root") or ""),
                "session_memory_root": str(runtime_config.get("session_memory_root") or ""),
                "persistence_enabled": bool(runtime_config.get("persistence_enabled")),
                "derived_writes_enabled": bool(runtime_config.get("derived_writes_enabled")),
            },
            "write_failures": list(write_failures or []),
            "overlay_surface": overlay_surface,
            "reevaluation": dict(reevaluation or {}),
            "freshness": dict((state.get("debug") or {}).get("freshness") or {}),
            "artifact_keys": dict((state.get("debug") or {}).get("artifact_keys") or {}),
            "expected_fingerprints": dict((state.get("debug") or {}).get("expected_fingerprints") or {}),
        },
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
