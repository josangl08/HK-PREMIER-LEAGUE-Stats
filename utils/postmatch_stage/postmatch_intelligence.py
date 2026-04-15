# ABOUTME: Postmatch-stage intelligence integration surface for recent-match artifact contracts and deterministic payload assembly.
# ABOUTME: Wraps existing postmatch helpers into JSON-safe artifacts so shared stage orchestration can reuse match-level intelligence without UI coupling.

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
import logging
from typing import Any, Dict, List, Mapping

import pandas as pd

from utils.agents.stage_agents.postmatch_agent import PostmatchStageAgent
from utils.domain_ai.postmatch_ai import get_postmatch_payloads
from utils.intelligence.artifact_keys import build_artifact_key
from utils.intelligence.artifact_registry import ArtifactRegistry
from utils.intelligence.discovery_contracts import serialize_stage_analysis
from utils.intelligence.discovery_overlay_mapper import build_overlay_candidates_from_analysis
from utils.intelligence.freshness_manager import (
    FRESHNESS_FRESH,
    FRESHNESS_HOT,
    FRESHNESS_WARM,
    build_artifact_fingerprint,
    build_dependency_fingerprint_map,
    evaluate_artifact_freshness,
    serialize_timestamp,
    utc_now,
)
from utils.intelligence.runtime_config import get_intelligence_runtime_config
from utils.intelligence.stage_orchestrator import build_runtime_artifact_record
from utils.intelligence.versioning import (
    ARTIFACT_SCHEMA_VERSION,
    get_intelligence_version_bundle,
)

POSTMATCH_MATCH_CONTEXT_ARTIFACT = "postmatch_match_context"
POSTMATCH_PERFORMANCE_CONTEXT_ARTIFACT = "postmatch_performance_context"
POSTMATCH_REFLECTION_PAYLOADS_ARTIFACT = "postmatch_reflection_payloads"
POSTMATCH_SIGNALS_ARTIFACT = "postmatch_signals"
POSTMATCH_OVERLAY_CANDIDATES_ARTIFACT = "postmatch_overlay_candidates"
POSTMATCH_STAGE_ANALYSIS_ARTIFACT = "postmatch_stage_analysis"
POSTMATCH_STAGE_ANALYSIS_CONTRACT_VERSION = "v1"

logger = logging.getLogger(__name__)

POSTMATCH_BASE_ARTIFACT_TYPES = [
    POSTMATCH_MATCH_CONTEXT_ARTIFACT,
    POSTMATCH_PERFORMANCE_CONTEXT_ARTIFACT,
    POSTMATCH_REFLECTION_PAYLOADS_ARTIFACT,
]

POSTMATCH_ARTIFACT_TYPES = [
    *POSTMATCH_BASE_ARTIFACT_TYPES,
    POSTMATCH_SIGNALS_ARTIFACT,
    POSTMATCH_OVERLAY_CANDIDATES_ARTIFACT,
    POSTMATCH_STAGE_ANALYSIS_ARTIFACT,
]

POSTMATCH_ARTIFACT_DEPENDENCIES = {
    POSTMATCH_SIGNALS_ARTIFACT: POSTMATCH_BASE_ARTIFACT_TYPES,
    POSTMATCH_STAGE_ANALYSIS_ARTIFACT: POSTMATCH_BASE_ARTIFACT_TYPES,
    POSTMATCH_OVERLAY_CANDIDATES_ARTIFACT: [POSTMATCH_STAGE_ANALYSIS_ARTIFACT],
}

POSTMATCH_FRESHNESS_POLICY = {
    POSTMATCH_MATCH_CONTEXT_ARTIFACT: {"regime": FRESHNESS_HOT, "ttl_hours": 12},
    POSTMATCH_PERFORMANCE_CONTEXT_ARTIFACT: {"regime": FRESHNESS_HOT, "ttl_hours": 12},
    POSTMATCH_REFLECTION_PAYLOADS_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 24},
    POSTMATCH_SIGNALS_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 24},
    POSTMATCH_OVERLAY_CANDIDATES_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 24},
    POSTMATCH_STAGE_ANALYSIS_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 24},
}

_POSTMATCH_PLACEHOLDER_BODY = "Postmatch AI entrypoint is prepared for structured reflective payloads."


def _is_placeholder_postmatch_reflection(payload: Mapping[str, Any] | None) -> bool:
    body = str((payload or {}).get("body") or "").strip()
    return body == _POSTMATCH_PLACEHOLDER_BODY


def _safe_scalar(value: Any) -> Any:
    """Convert nested values into JSON-safe primitives."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value):
        return _safe_scalar(asdict(value))
    if isinstance(value, dict):
        return {str(key): _safe_scalar(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_scalar(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _safe_mapping(mapping: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Normalize a mapping into JSON-safe values."""
    if not mapping:
        return {}
    return {str(key): _safe_scalar(value) for key, value in mapping.items()}


def _safe_records(records: List[Any] | None) -> List[Dict[str, Any]]:
    """Normalize a list of records or dataclasses into JSON-safe shallow dicts."""
    normalized: List[Dict[str, Any]] = []
    for record in records or []:
        if is_dataclass(record):
            normalized.append(_safe_mapping(asdict(record)))
            continue
        if isinstance(record, dict):
            normalized.append(_safe_mapping(record))
            continue
        normalized.append({"value": _safe_scalar(record)})
    return normalized


def build_postmatch_artifact_scope(player_id: str, match_id: str) -> Dict[str, str]:
    """Return the canonical postmatch artifact scope."""
    return {
        "player_id": str(player_id or ""),
        "match_id": str(match_id or ""),
        "stage": "postmatch",
    }


def build_postmatch_artifact_key(artifact_type: str, player_id: str, match_id: str) -> str:
    """Return the deterministic registry key for a postmatch artifact."""
    return build_artifact_key(
        artifact_type,
        build_postmatch_artifact_scope(player_id, match_id),
    )


def build_postmatch_match_context_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build the durable postmatch match-context payload from the stage payload."""
    keys = [
        "match_id",
        "fixture_id",
        "opponent",
        "home_team",
        "away_team",
        "competition",
        "kickoff_display",
        "date",
        "stadium",
        "result",
        "rating",
    ]
    return {
        str(key): _safe_scalar(payload.get(key))
        for key in keys
    }


def build_postmatch_performance_context_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build the player-performance context payload for postmatch refresh decisions."""
    player_stats = _safe_mapping(payload.get("player_stats") or {})
    performance_stats = _safe_mapping(player_stats.get("performance_stats") or {})
    match_stats = _safe_mapping(payload.get("match_stats") or {})
    recent_ratings = [_safe_scalar(item) for item in list(payload.get("recent_ratings") or [])[:5]]
    recent_contributions = [_safe_scalar(item) for item in list(payload.get("recent_contributions") or [])[:5]]

    keys = [
        "player_id",
        "position",
        "minutes_played",
        "goals",
        "assists",
        "yellow_cards",
        "red_cards",
        "started",
        "subbed_in",
        "subbed_out",
        "own_goals",
        "absence_reason",
    ]
    performance_payload = {
        str(key): _safe_scalar(payload.get(key))
        for key in keys
    }
    performance_payload["player_stats"] = player_stats
    performance_payload["performance_stats"] = performance_stats
    performance_payload["match_stats"] = match_stats
    performance_payload["recent_ratings"] = recent_ratings
    performance_payload["recent_contributions"] = recent_contributions
    return performance_payload


def build_postmatch_reflection_payloads_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build reflective postmatch payloads from the deterministic-first domain AI entrypoint."""
    context = {
        "match_context": build_postmatch_match_context_payload(payload),
        "performance_context": build_postmatch_performance_context_payload(payload),
    }
    reflections = get_postmatch_payloads(context, allow_llm_synthesis=False)
    normalized_reflections = [
        record
        for record in _safe_records(reflections)
        if not _is_placeholder_postmatch_reflection(record)
    ]
    return {
        "payloads": deepcopy(normalized_reflections),
        "payload_count": len(normalized_reflections),
        "selected_payload": deepcopy(normalized_reflections[0]) if normalized_reflections else None,
    }


def build_postmatch_overlay_candidates_payload(
    match_context_payload: Dict[str, Any],
    performance_context_payload: Dict[str, Any],
    reflection_payloads_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Build lightweight postmatch overlay candidates from reflective payloads."""
    selected_payload = deepcopy(reflection_payloads_payload.get("selected_payload"))
    candidates: List[Dict[str, Any]] = []
    if selected_payload:
        candidates.append(
            {
                "candidate_type": "postmatch_reflection",
                "headline": selected_payload.get("label"),
                "body": selected_payload.get("body"),
                "support": selected_payload.get("support"),
                "confidence": selected_payload.get("confidence"),
                "evidence_key": selected_payload.get("evidence_key"),
                "emphasis": selected_payload.get("emphasis"),
                "match_result": match_context_payload.get("result"),
                "minutes_played": performance_context_payload.get("minutes_played"),
            }
        )
    return {
        "candidates": candidates,
        "candidate_count": len(candidates),
        "selected_candidate": deepcopy(candidates[0]) if candidates else None,
    }


def build_postmatch_signals_payload(stage_analysis_payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Build persisted postmatch signal inputs from the shared stage analysis."""
    overlay_payload = build_overlay_candidates_from_analysis(stage_analysis_payload)
    candidates = [dict(candidate) for candidate in list((overlay_payload or {}).get("candidates") or [])]
    return {
        "signals": candidates,
        "signal_count": len(candidates),
    }


def build_postmatch_artifact_payloads(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build JSON-safe deterministic payloads for the postmatch stage artifacts."""
    match_context_payload = build_postmatch_match_context_payload(payload)
    performance_context_payload = build_postmatch_performance_context_payload(payload)
    reflection_payloads_payload = build_postmatch_reflection_payloads_payload(payload)
    overlay_candidates_payload = build_postmatch_overlay_candidates_payload(
        match_context_payload,
        performance_context_payload,
        reflection_payloads_payload,
    )
    return {
        POSTMATCH_MATCH_CONTEXT_ARTIFACT: match_context_payload,
        POSTMATCH_PERFORMANCE_CONTEXT_ARTIFACT: performance_context_payload,
        POSTMATCH_REFLECTION_PAYLOADS_ARTIFACT: reflection_payloads_payload,
    }


def _postmatch_source_checksum(base_payloads: Mapping[str, Mapping[str, Any]]) -> str:
    """Build a deterministic checksum for postmatch facts that materially affect analysis."""
    relevant_payload = {
        artifact_type: deepcopy(base_payloads.get(artifact_type) or {})
        for artifact_type in (
            POSTMATCH_MATCH_CONTEXT_ARTIFACT,
            POSTMATCH_PERFORMANCE_CONTEXT_ARTIFACT,
            POSTMATCH_REFLECTION_PAYLOADS_ARTIFACT,
        )
    }
    return build_artifact_fingerprint(relevant_payload)


def build_postmatch_artifact_fingerprint_inputs(
    artifact_type: str,
    *,
    player_id: str,
    match_id: str,
    source_checksum: str,
    dependency_fingerprint_map: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """Return fingerprint inputs for any postmatch artifact."""
    return {
        "artifact_type": artifact_type,
        "scope": build_postmatch_artifact_scope(player_id, match_id),
        "source_checksum": source_checksum,
        "dependency_fingerprint_map": dict(dependency_fingerprint_map or {}),
        "version_bundle": get_intelligence_version_bundle(),
    }


def build_postmatch_artifact_record(
    artifact_type: str,
    payload: Mapping[str, Any],
    *,
    player_id: str,
    match_id: str,
    source_checksum: str,
    dependency_fingerprint_map: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """Build a persisted artifact record for any postmatch runtime artifact."""
    ttl_hours = int(POSTMATCH_FRESHNESS_POLICY[artifact_type]["ttl_hours"])
    return build_runtime_artifact_record(
        artifact_type=artifact_type,
        scope=build_postmatch_artifact_scope(player_id, match_id),
        payload=payload,
        ttl_hours=ttl_hours,
        fingerprint_inputs=build_postmatch_artifact_fingerprint_inputs(
            artifact_type,
            player_id=player_id,
            match_id=match_id,
            source_checksum=source_checksum,
            dependency_fingerprint_map=dependency_fingerprint_map,
        ),
        dependency_fingerprint_map=dependency_fingerprint_map,
    )


def get_postmatch_intelligence_state(
    payload: Dict[str, Any],
    *,
    registry: ArtifactRegistry | None = None,
) -> Dict[str, Any]:
    """Load postmatch artifacts from the registry and decide which ones need refresh."""
    player_id = str(payload.get("player_id") or "")
    match_id = str(payload.get("match_id") or payload.get("fixture_id") or "")
    active_registry = registry or ArtifactRegistry()
    base_payloads = build_postmatch_artifact_payloads(payload)
    artifact_states: Dict[str, Any] = {}
    refresh_plan: List[str] = []
    persisted_base_artifacts: List[str] = []

    for artifact_type in POSTMATCH_ARTIFACT_TYPES:
        artifact_key = build_postmatch_artifact_key(artifact_type, player_id, match_id)
        dependency_fingerprint_map = build_dependency_fingerprint_map(
            {
                dependency: (artifact_states.get(dependency) or {}).get("artifact")
                for dependency in POSTMATCH_ARTIFACT_DEPENDENCIES.get(artifact_type, [])
            }
        )
        if artifact_type in base_payloads:
            source_checksum = build_artifact_fingerprint(base_payloads[artifact_type] or {})
        else:
            source_checksum = _postmatch_source_checksum(base_payloads)
        expected_fingerprint = build_artifact_fingerprint(
            build_postmatch_artifact_fingerprint_inputs(
                artifact_type,
                player_id=player_id,
                match_id=match_id,
                source_checksum=source_checksum,
                dependency_fingerprint_map=dependency_fingerprint_map,
            )
        )
        stored_artifact = active_registry.get_artifact(artifact_key)
        freshness = evaluate_artifact_freshness(
            stored_artifact,
            expected_fingerprint=expected_fingerprint,
            dependency_artifacts=[
                (artifact_states.get(dependency) or {}).get("artifact")
                for dependency in POSTMATCH_ARTIFACT_DEPENDENCIES.get(artifact_type, [])
            ],
            dependency_fingerprint_map=dependency_fingerprint_map,
        )
        if artifact_type in base_payloads and freshness["status"] != FRESHNESS_FRESH:
            stored_artifact = active_registry.put_artifact(
                artifact_key,
                build_postmatch_artifact_record(
                    artifact_type,
                    base_payloads[artifact_type],
                    player_id=player_id,
                    match_id=match_id,
                    source_checksum=build_artifact_fingerprint(base_payloads[artifact_type] or {}),
                ),
            )
            freshness = {
                "status": FRESHNESS_FRESH,
                "is_usable": True,
                "reasons": ["materialized_base_artifact"],
            }
            persisted_base_artifacts.append(artifact_type)
        if freshness["status"] != FRESHNESS_FRESH:
            refresh_plan.append(artifact_type)
        artifact_states[artifact_type] = {
            "artifact_key": artifact_key,
            "artifact": stored_artifact,
            "freshness": freshness,
            "freshness_policy": POSTMATCH_FRESHNESS_POLICY.get(artifact_type) or {},
            "expected_fingerprint": expected_fingerprint,
            "payload_contract": base_payloads.get(artifact_type),
        }

    return {
        "scope": build_postmatch_artifact_scope(player_id, match_id),
        "base_payloads": base_payloads,
        "artifacts": artifact_states,
        "refresh_plan": refresh_plan,
        "debug": {
            "artifact_keys": {
                artifact_type: state["artifact_key"]
                for artifact_type, state in artifact_states.items()
            },
            "expected_fingerprints": {
                artifact_type: state["expected_fingerprint"]
                for artifact_type, state in artifact_states.items()
            },
            "freshness": {
                artifact_type: state["freshness"]["status"]
                for artifact_type, state in artifact_states.items()
            },
            "persisted_base_artifacts": persisted_base_artifacts,
        },
    }


def build_postmatch_stage_analysis_fingerprint_inputs(
    *,
    player_id: str,
    match_id: str,
    source_checksum: str,
    llm_enabled: bool,
    model_profile: str,
) -> Dict[str, Any]:
    """Return fingerprint inputs for the persisted postmatch stage analysis."""
    return {
        "artifact_type": POSTMATCH_STAGE_ANALYSIS_ARTIFACT,
        "scope": build_postmatch_artifact_scope(player_id, match_id),
        "source_checksum": source_checksum,
        "analysis_contract_version": POSTMATCH_STAGE_ANALYSIS_CONTRACT_VERSION,
        "runtime_flavor": {
            "llm_enabled": bool(llm_enabled),
            "model_profile": str(model_profile or "flash"),
        },
        "version_bundle": get_intelligence_version_bundle(),
    }


def build_postmatch_stage_analysis_record(
    payload: Dict[str, Any],
    *,
    player_id: str,
    match_id: str,
    source_checksum: str,
    llm_enabled: bool,
    model_profile: str,
) -> Dict[str, Any]:
    """Build a persisted artifact record for postmatch stage analysis."""
    current_time = utc_now()
    ttl_hours = int(POSTMATCH_FRESHNESS_POLICY[POSTMATCH_STAGE_ANALYSIS_ARTIFACT]["ttl_hours"])
    fingerprint_inputs = build_postmatch_stage_analysis_fingerprint_inputs(
        player_id=player_id,
        match_id=match_id,
        source_checksum=source_checksum,
        llm_enabled=llm_enabled,
        model_profile=model_profile,
    )
    return {
        "artifact_key": build_postmatch_artifact_key(POSTMATCH_STAGE_ANALYSIS_ARTIFACT, player_id, match_id),
        "artifact_type": POSTMATCH_STAGE_ANALYSIS_ARTIFACT,
        "scope": build_postmatch_artifact_scope(player_id, match_id),
        "version": ARTIFACT_SCHEMA_VERSION,
        "computed_at": serialize_timestamp(current_time),
        "expires_at": serialize_timestamp(current_time + pd.Timedelta(hours=ttl_hours)),
        "freshness_status": FRESHNESS_FRESH,
        "fingerprint": build_artifact_fingerprint(fingerprint_inputs),
        "dependency_fingerprints": {
            "source_checksum": source_checksum,
        },
        "payload": deepcopy(payload),
    }


def build_postmatch_stage_analysis_payload(
    payload: Dict[str, Any],
    *,
    registry: ArtifactRegistry | None = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Build or reuse the shared postmatch stage-analysis payload using persisted fingerprints."""
    player_id = str(payload.get("player_id") or "")
    match_id = str(payload.get("match_id") or payload.get("fixture_id") or "")
    scope = build_postmatch_artifact_scope(player_id, match_id)
    base_payloads = build_postmatch_artifact_payloads(payload)
    source_checksum = _postmatch_source_checksum(base_payloads)
    active_registry = registry or ArtifactRegistry()
    runtime_config = get_intelligence_runtime_config()
    llm_enabled = bool(runtime_config.get("postmatch_agent_llm_enabled"))
    model_profile = str(runtime_config.get("postmatch_agent_model_profile") or "flash")

    artifact_key = build_postmatch_artifact_key(POSTMATCH_STAGE_ANALYSIS_ARTIFACT, player_id, match_id)
    expected_fingerprint = build_artifact_fingerprint(
        build_postmatch_stage_analysis_fingerprint_inputs(
            player_id=player_id,
            match_id=match_id,
            source_checksum=source_checksum,
            llm_enabled=llm_enabled,
            model_profile=model_profile,
        )
    )
    stored_artifact = active_registry.get_artifact(artifact_key)
    if (
        not force_refresh
        and stored_artifact
        and str(stored_artifact.get("fingerprint") or "") == expected_fingerprint
    ):
        stored_payload = dict(stored_artifact.get("payload") or {})
        if stored_payload:
            debug = dict(stored_payload.get("debug") or {})
            analysis_source = str(debug.get("analysis_source") or "artifact")
            if llm_enabled and analysis_source != "agentic":
                logger.info(
                    "Postmatch stage analysis ignoring stored artifact player_id=%s match_id=%s analysis_source=%s llm_enabled=%s model_profile=%s",
                    player_id,
                    match_id,
                    analysis_source,
                    llm_enabled,
                    model_profile,
                )
            else:
                debug.setdefault("analysis_source", "artifact")
                stored_payload["debug"] = debug
                return stored_payload

    artifacts = {
        artifact_type: {"payload": artifact_payload}
        for artifact_type, artifact_payload in base_payloads.items()
    }
    analysis = PostmatchStageAgent().analyze(scope=scope, artifacts=artifacts, session_memory=None)
    serialized = serialize_stage_analysis(analysis)
    debug = dict(serialized.get("debug") or {})
    debug.setdefault("analysis_source", "agentic" if debug.get("llm_generated") else "fallback")
    serialized["debug"] = debug
    record = build_postmatch_stage_analysis_record(
        serialized,
        player_id=player_id,
        match_id=match_id,
        source_checksum=source_checksum,
        llm_enabled=llm_enabled,
        model_profile=model_profile,
    )
    active_registry.put_artifact(record["artifact_key"], record)
    return serialized
