# ABOUTME: Career-stage intelligence integration surface for artifact contracts, freshness policy, and deterministic context assembly.
# ABOUTME: Wraps existing career intelligence utilities in JSON-safe artifact payloads so multi-stage orchestration can reuse the season architecture.

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
import logging
from typing import Any, Dict, List, Mapping

import pandas as pd

from utils.career_intelligence import (
    build_career_dashboard_brief,
    get_career_phase_data,
    get_career_signals,
    get_development_priorities,
)
from utils.agents.career_signal_agent import (
    curate_career_signals,
    is_viable_career_candidate,
)
from utils.agents.orchestration_runtime import sync_session_memory_with_graceful_failure
from utils.agents.stage_agents.career_agent import CareerStageAgent
from utils.intelligence.artifact_keys import build_artifact_key
from utils.intelligence.artifact_registry import ArtifactRegistry
from utils.intelligence.discovery_contracts import serialize_stage_analysis
from utils.intelligence.discovery_overlay_mapper import build_overlay_candidates_from_analysis
from utils.intelligence.freshness_manager import (
    FRESHNESS_COLD,
    FRESHNESS_FRESH,
    FRESHNESS_WARM,
    build_dependency_fingerprint_map,
    build_artifact_fingerprint,
    evaluate_artifact_freshness,
    resolve_freshness_policy,
    serialize_timestamp,
    utc_now,
)
from utils.intelligence.overlay_surface import resolve_stage_overlay_surface
from utils.intelligence.runtime_config import get_intelligence_runtime_config
from utils.intelligence.session_memory import (
    get_career_session_memory,
    put_career_session_memory,
)
from utils.intelligence.versioning import (
    ARTIFACT_SCHEMA_VERSION,
    get_intelligence_version_bundle,
)

CAREER_PHASE_CONTEXT_ARTIFACT = "career_phase_context"
CAREER_SIGNALS_CONTEXT_ARTIFACT = "career_signals_context"
CAREER_PRIORITIES_CONTEXT_ARTIFACT = "career_priorities_context"
CAREER_DASHBOARD_BRIEF_ARTIFACT = "career_dashboard_brief"
CAREER_SIGNALS_ARTIFACT = "career_signals"
CAREER_OVERLAY_CANDIDATES_ARTIFACT = "career_overlay_candidates"
CAREER_STAGE_ANALYSIS_ARTIFACT = "career_stage_analysis"
CAREER_STAGE_ANALYSIS_CONTRACT_VERSION = "v2"

CAREER_ARTIFACT_TYPES = [
    CAREER_PHASE_CONTEXT_ARTIFACT,
    CAREER_SIGNALS_CONTEXT_ARTIFACT,
    CAREER_PRIORITIES_CONTEXT_ARTIFACT,
    CAREER_DASHBOARD_BRIEF_ARTIFACT,
    CAREER_SIGNALS_ARTIFACT,
    CAREER_OVERLAY_CANDIDATES_ARTIFACT,
    CAREER_STAGE_ANALYSIS_ARTIFACT,
]

CAREER_BASE_ARTIFACT_TYPES = [
    CAREER_PHASE_CONTEXT_ARTIFACT,
    CAREER_SIGNALS_CONTEXT_ARTIFACT,
    CAREER_PRIORITIES_CONTEXT_ARTIFACT,
    CAREER_DASHBOARD_BRIEF_ARTIFACT,
]

CAREER_ARTIFACT_DEPENDENCIES = {
    CAREER_PHASE_CONTEXT_ARTIFACT: [],
    CAREER_SIGNALS_CONTEXT_ARTIFACT: [],
    CAREER_PRIORITIES_CONTEXT_ARTIFACT: [],
    CAREER_DASHBOARD_BRIEF_ARTIFACT: [],
    CAREER_SIGNALS_ARTIFACT: [
        CAREER_PHASE_CONTEXT_ARTIFACT,
        CAREER_SIGNALS_CONTEXT_ARTIFACT,
        CAREER_PRIORITIES_CONTEXT_ARTIFACT,
        CAREER_DASHBOARD_BRIEF_ARTIFACT,
    ],
    CAREER_OVERLAY_CANDIDATES_ARTIFACT: [
        CAREER_SIGNALS_ARTIFACT,
        CAREER_STAGE_ANALYSIS_ARTIFACT,
    ],
    CAREER_STAGE_ANALYSIS_ARTIFACT: [
        CAREER_PHASE_CONTEXT_ARTIFACT,
        CAREER_SIGNALS_CONTEXT_ARTIFACT,
        CAREER_PRIORITIES_CONTEXT_ARTIFACT,
        CAREER_DASHBOARD_BRIEF_ARTIFACT,
        CAREER_SIGNALS_ARTIFACT,
    ],
}

CAREER_FRESHNESS_POLICY = {
    CAREER_PHASE_CONTEXT_ARTIFACT: {"regime": FRESHNESS_COLD, "ttl_hours": 72},
    CAREER_SIGNALS_CONTEXT_ARTIFACT: {"regime": FRESHNESS_COLD, "ttl_hours": 72},
    CAREER_PRIORITIES_CONTEXT_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 48},
    CAREER_DASHBOARD_BRIEF_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 48},
    CAREER_SIGNALS_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 48},
    CAREER_OVERLAY_CANDIDATES_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 48},
    CAREER_STAGE_ANALYSIS_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 48},
}

logger = logging.getLogger(__name__)


def _build_curated_career_overlay_payload(
    candidates: List[Dict[str, Any]] | None,
    *,
    selected_candidate: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build the overlay-candidate artifact payload for career with an explicit selection."""
    safe_candidates = deepcopy(candidates or [])
    safe_selected = deepcopy(selected_candidate) if selected_candidate else None
    if safe_selected:
        selected_signal_id = str(safe_selected.get("signal_id") or "")
        matching_index = next(
            (
                idx
                for idx, candidate in enumerate(safe_candidates)
                if str(candidate.get("signal_id") or "") == selected_signal_id and selected_signal_id
            ),
            None,
        )
        if matching_index is None:
            safe_candidates.insert(0, deepcopy(safe_selected))
        else:
            merged_candidate = dict(safe_candidates[matching_index])
            merged_candidate.update({key: value for key, value in safe_selected.items() if value not in (None, "")})
            safe_candidates[matching_index] = merged_candidate
    return {
        "candidates": safe_candidates,
        "candidate_count": len(safe_candidates),
        "selected_candidate": safe_selected,
    }


def build_career_signals_payload(
    candidates: List[Mapping[str, Any]] | None,
) -> Dict[str, Any]:
    """Build the runtime career-signals payload from shared discovery candidates."""
    safe_candidates = [deepcopy(dict(candidate)) for candidate in (candidates or []) if candidate]
    return {
        "signals": safe_candidates,
        "signal_count": len(safe_candidates),
    }
def _build_updated_career_session_memory(
    *,
    player_id: str,
    current_candidate: Mapping[str, Any] | None,
    existing_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build the next persisted session-memory state for career intelligence."""
    existing_memory = existing_memory or {}
    seen_novelty_keys = list(existing_memory.get("seen_novelty_keys") or [])
    novelty_key = str((current_candidate or {}).get("novelty_key") or "")
    if novelty_key and novelty_key not in seen_novelty_keys:
        seen_novelty_keys.append(novelty_key)

    return put_career_session_memory(
        player_id=player_id,
        current_novelty_key=novelty_key or None,
        seen_novelty_keys=seen_novelty_keys,
        last_curated_signal_id=str((current_candidate or {}).get("signal_id") or "") or None,
        current_candidate=dict(current_candidate or {}) if current_candidate else None,
        current_anchor=str((current_candidate or {}).get("anchor") or "") or None,
        current_priority=(current_candidate or {}).get("priority"),
    )


def _sync_career_session_memory(
    *,
    player_id: str,
    current_candidate: Mapping[str, Any] | None,
    existing_memory: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Persist career session memory with graceful degradation on failure."""
    return sync_session_memory_with_graceful_failure(
        persist_fn=lambda: _build_updated_career_session_memory(
            player_id=player_id,
            current_candidate=current_candidate,
            existing_memory=existing_memory,
        ),
        logger=logger,
        log_message="Career session memory persistence failed player_id=%s signal_id=%s: %s",
        log_args=(
            player_id,
            str((current_candidate or {}).get("signal_id") or ""),
        ),
        existing_memory=existing_memory,
    )


def _safe_scalar(value: Any) -> Any:
    """Convert pandas/numpy scalars into plain JSON-safe values."""
    if is_dataclass(value):
        return _safe_scalar(asdict(value))
    if isinstance(value, dict):
        return {
            str(key): _safe_scalar(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_safe_scalar(item) for item in value]
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _safe_mapping(mapping: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Normalize a mapping into JSON-safe scalar values."""
    if not mapping:
        return {}
    return {
        str(key): _safe_scalar(value)
        for key, value in mapping.items()
    }


def _safe_records(records: List[Mapping[str, Any]] | None) -> List[Dict[str, Any]]:
    """Normalize list items into JSON-safe shallow dicts."""
    return [_safe_mapping(record) for record in (records or [])]


def build_career_artifact_scope(player_id: str) -> Dict[str, str]:
    """Return the canonical career artifact scope."""
    return {
        "player_id": str(player_id or ""),
        "stage": "career",
    }


def build_career_artifact_key(artifact_type: str, player_id: str) -> str:
    """Return the deterministic registry key for a career artifact."""
    return build_artifact_key(artifact_type, build_career_artifact_scope(player_id))


def build_career_phase_context_payload(player: Dict[str, Any], history_df: pd.DataFrame) -> Dict[str, Any]:
    """Build the durable career phase context payload."""
    phase_data = get_career_phase_data(player, history_df)
    return deepcopy(_safe_mapping(phase_data))


def build_career_signals_context_payload(
    player: Dict[str, Any],
    history_df: pd.DataFrame,
    career_phase_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the career signal-context payload."""
    signals = get_career_signals(player, history_df, career_phase_data)
    return deepcopy(_safe_mapping(signals))


def build_career_priorities_context_payload(percentiles_data: Dict[str, int] | None) -> Dict[str, Any]:
    """Build the development-priority payload."""
    priorities = get_development_priorities(percentiles_data or {})
    return {
        "priorities": deepcopy(_safe_records(priorities)),
        "priority_count": len(priorities),
    }


def build_career_dashboard_brief_payload(
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    development_priorities: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the career dashboard brief artifact payload."""
    brief = build_career_dashboard_brief(
        data,
        career_phase_data,
        career_signals,
        development_priorities,
    )
    return {
        "player_name": str(
            (data.get("player") or {}).get("player_name")
            or data.get("player_name")
            or ""
        ),
        "career_thesis": deepcopy(_safe_mapping(getattr(brief, "career_thesis", {}) or {})),
        "signals": deepcopy(_safe_records([getattr(item, "__dict__", item) for item in getattr(brief, "signals", [])])),
        "levers": deepcopy(_safe_records([getattr(item, "__dict__", item) for item in getattr(brief, "levers", [])])),
        "outlook": deepcopy(_safe_mapping(getattr(brief, "outlook", {}) or {})),
    }


def build_career_base_artifact_payloads(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build the deterministic base artifact payloads for the career stage."""
    player = data.get("player") or {}
    history_df = data.get("history_df")
    if history_df is None:
        history_df = pd.DataFrame()
    percentiles_data = data.get("percentiles_data") or {}
    career_phase_data = get_career_phase_data(player, history_df)
    career_signals = get_career_signals(player, history_df, career_phase_data)
    development_priorities = get_development_priorities(percentiles_data)

    payloads = {
        CAREER_PHASE_CONTEXT_ARTIFACT: build_career_phase_context_payload(player, history_df),
        CAREER_SIGNALS_CONTEXT_ARTIFACT: build_career_signals_context_payload(
            player,
            history_df,
            career_phase_data,
        ),
        CAREER_PRIORITIES_CONTEXT_ARTIFACT: build_career_priorities_context_payload(percentiles_data),
        CAREER_DASHBOARD_BRIEF_ARTIFACT: build_career_dashboard_brief_payload(
            data,
            career_phase_data,
            career_signals,
            development_priorities,
        ),
    }
    return payloads


def get_career_freshness_policy(artifact_type: str) -> Dict[str, Any]:
    """Return the hot/warm/cold freshness policy for a career artifact."""
    return resolve_freshness_policy(artifact_type, CAREER_FRESHNESS_POLICY)


def build_career_artifact_fingerprint_inputs(
    artifact_type: str,
    *,
    player_id: str,
    source_checksum: str,
    dependency_fingerprint_map: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """Build canonical fingerprint inputs for a career artifact type."""
    policy = get_career_freshness_policy(artifact_type)
    inputs = {
        "artifact_type": artifact_type,
        "player_id": str(player_id or ""),
        "stage": "career",
        "source_checksum": source_checksum,
        "analysis_contract_version": CAREER_STAGE_ANALYSIS_CONTRACT_VERSION,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "regime": policy["regime"],
        "ttl_hours": policy["ttl_hours"],
        "version_bundle": get_intelligence_version_bundle(),
    }
    if dependency_fingerprint_map:
        inputs["dependency_fingerprints"] = dict(sorted(dependency_fingerprint_map.items()))
    return inputs


def build_career_artifact_record(
    artifact_type: str,
    payload: Dict[str, Any],
    *,
    player_id: str,
    source_checksum: str,
    dependency_fingerprint_map: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """Build a persisted artifact envelope for a career artifact type."""
    policy = get_career_freshness_policy(artifact_type)
    current_time = utc_now()
    ttl_hours = int(policy["ttl_hours"])
    dependency_fingerprint_map = dict(dependency_fingerprint_map or {})
    return {
        "artifact_key": build_career_artifact_key(artifact_type, player_id),
        "artifact_type": artifact_type,
        "scope": build_career_artifact_scope(player_id),
        "version": ARTIFACT_SCHEMA_VERSION,
        "computed_at": serialize_timestamp(current_time),
        "expires_at": serialize_timestamp(current_time + pd.Timedelta(hours=ttl_hours)),
        "freshness_status": FRESHNESS_FRESH,
        "fingerprint": build_artifact_fingerprint(
            build_career_artifact_fingerprint_inputs(
                artifact_type,
                player_id=player_id,
                source_checksum=source_checksum,
                dependency_fingerprint_map=dependency_fingerprint_map,
            )
        ),
        "dependencies": list(CAREER_ARTIFACT_DEPENDENCIES.get(artifact_type, [])),
        "dependency_fingerprints": dependency_fingerprint_map,
        "freshness_policy": policy,
        "payload": deepcopy(payload),
    }


def persist_base_career_artifact(
    artifact_type: str,
    payload: Dict[str, Any],
    *,
    player_id: str,
    registry: ArtifactRegistry,
) -> Dict[str, Any]:
    """Persist a deterministic base career artifact."""
    record = build_career_artifact_record(
        artifact_type,
        payload,
        player_id=player_id,
        source_checksum=build_artifact_fingerprint(payload or {}),
    )
    stored = registry.put_artifact(record["artifact_key"], record)
    logger.info(
        "Career intelligence persisted base artifact=%s player_id=%s",
        artifact_type,
        player_id,
    )
    return stored


def _persist_runtime_career_artifact(
    artifact_type: str,
    payload: Dict[str, Any],
    *,
    player_id: str,
    base_payloads: Mapping[str, Mapping[str, Any]],
    dependency_artifacts: Mapping[str, Mapping[str, Any]],
    registry: ArtifactRegistry,
    runtime_config: Mapping[str, Any],
) -> Dict[str, Any]:
    """Persist a derived career runtime artifact with season-style degraded-write handling."""
    del base_payloads  # kept for signature parity with season orchestrator
    dependency_fingerprint_map = {
        dependency: str((dependency_artifacts.get(dependency) or {}).get("fingerprint") or "")
        for dependency in CAREER_ARTIFACT_DEPENDENCIES.get(artifact_type, [])
        if dependency_artifacts.get(dependency) is not None
    }
    record = build_career_artifact_record(
        artifact_type,
        payload,
        player_id=player_id,
        source_checksum=build_artifact_fingerprint(payload or {}),
        dependency_fingerprint_map=dependency_fingerprint_map,
    )
    if not runtime_config.get("derived_writes_enabled", True):
        logger.info(
            "Career orchestrator skipped artifact write artifact=%s player_id=%s reason=derived_writes_disabled",
            artifact_type,
            player_id,
        )
        return {
            "artifact": record,
            "persisted": False,
            "failure": None,
            "skipped": "derived_writes_disabled",
        }

    try:
        stored = registry.put_artifact(record["artifact_key"], record)
    except Exception as exc:
        logger.exception(
            "Career orchestrator artifact persistence failed artifact=%s player_id=%s: %s",
            artifact_type,
            player_id,
            exc,
        )
        return {
            "artifact": record,
            "persisted": False,
            "failure": str(exc),
            "skipped": None,
        }

    logger.info(
        "Career orchestrator persisted artifact=%s player_id=%s dependencies=%s",
        artifact_type,
        player_id,
        sorted(dependency_fingerprint_map),
    )
    return {
        "artifact": stored,
        "persisted": True,
        "failure": None,
        "skipped": None,
    }


def _persist_runtime_career_stage_analysis(
    payload: Dict[str, Any],
    *,
    player_id: str,
    source_checksum: str,
    llm_enabled: bool,
    model_profile: str,
    registry: ArtifactRegistry,
    runtime_config: Mapping[str, Any],
) -> Dict[str, Any]:
    """Persist career stage analysis with runtime-flavor fingerprinting and degraded-write handling."""
    record = build_career_stage_analysis_record(
        payload,
        player_id=player_id,
        source_checksum=source_checksum,
        llm_enabled=llm_enabled,
        model_profile=model_profile,
    )
    if not runtime_config.get("derived_writes_enabled", True):
        logger.info(
            "Career orchestrator skipped artifact write artifact=%s player_id=%s reason=derived_writes_disabled",
            CAREER_STAGE_ANALYSIS_ARTIFACT,
            player_id,
        )
        return {
            "artifact": record,
            "persisted": False,
            "failure": None,
            "skipped": "derived_writes_disabled",
        }
    try:
        stored = registry.put_artifact(record["artifact_key"], record)
    except Exception as exc:
        logger.exception(
            "Career orchestrator artifact persistence failed artifact=%s player_id=%s: %s",
            CAREER_STAGE_ANALYSIS_ARTIFACT,
            player_id,
            exc,
        )
        return {
            "artifact": record,
            "persisted": False,
            "failure": str(exc),
            "skipped": None,
        }
    logger.info(
        "Career orchestrator persisted artifact=%s player_id=%s",
        CAREER_STAGE_ANALYSIS_ARTIFACT,
        player_id,
    )
    return {
        "artifact": stored,
        "persisted": True,
        "failure": None,
        "skipped": None,
    }

def _career_source_checksum(base_payloads: Mapping[str, Mapping[str, Any]]) -> str:
    """Build a deterministic checksum for career facts that materially affect the analysis."""
    relevant_payload = {
        artifact_type: deepcopy(base_payloads.get(artifact_type) or {})
        for artifact_type in (
            CAREER_PHASE_CONTEXT_ARTIFACT,
            CAREER_SIGNALS_CONTEXT_ARTIFACT,
            CAREER_PRIORITIES_CONTEXT_ARTIFACT,
            CAREER_DASHBOARD_BRIEF_ARTIFACT,
        )
    }
    return build_artifact_fingerprint(relevant_payload)


def get_career_intelligence_state(
    data: Dict[str, Any],
    *,
    registry: ArtifactRegistry | None = None,
) -> Dict[str, Any]:
    """Compatibility wrapper that delegates to the dedicated career orchestrator module."""
    from utils.agents.career_intelligence_orchestrator import get_career_intelligence_state as _get_state

    return _get_state(data, registry=registry)


def orchestrate_career_intelligence(
    data: Dict[str, Any],
    *,
    registry: ArtifactRegistry | None = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Compatibility wrapper that delegates to the dedicated career orchestrator module."""
    from utils.agents.career_intelligence_orchestrator import (
        orchestrate_career_intelligence as _orchestrate_career_intelligence,
    )

    return _orchestrate_career_intelligence(
        data,
        registry=registry,
        force_refresh=force_refresh,
    )


def build_career_stage_analysis_fingerprint_inputs(
    *,
    player_id: str,
    source_checksum: str,
    llm_enabled: bool,
    model_profile: str,
) -> Dict[str, Any]:
    """Return the fingerprint inputs for the persisted career stage analysis."""
    return {
        "artifact_type": CAREER_STAGE_ANALYSIS_ARTIFACT,
        "scope": build_career_artifact_scope(player_id),
        "source_checksum": source_checksum,
        "analysis_contract_version": CAREER_STAGE_ANALYSIS_CONTRACT_VERSION,
        "runtime_flavor": {
            "llm_enabled": bool(llm_enabled),
            "model_profile": str(model_profile or "flash"),
        },
        "version_bundle": get_intelligence_version_bundle(),
    }


def build_career_stage_analysis_record(
    payload: Dict[str, Any],
    *,
    player_id: str,
    source_checksum: str,
    llm_enabled: bool,
    model_profile: str,
) -> Dict[str, Any]:
    """Build a persisted artifact record for career stage analysis."""
    current_time = utc_now()
    ttl_hours = int(CAREER_FRESHNESS_POLICY[CAREER_STAGE_ANALYSIS_ARTIFACT]["ttl_hours"])
    fingerprint_inputs = build_career_stage_analysis_fingerprint_inputs(
        player_id=player_id,
        source_checksum=source_checksum,
        llm_enabled=llm_enabled,
        model_profile=model_profile,
    )
    return {
        "artifact_key": build_career_artifact_key(CAREER_STAGE_ANALYSIS_ARTIFACT, player_id),
        "artifact_type": CAREER_STAGE_ANALYSIS_ARTIFACT,
        "scope": build_career_artifact_scope(player_id),
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


def build_career_stage_analysis_payload(
    data: Dict[str, Any],
    *,
    registry: ArtifactRegistry | None = None,
    force_refresh: bool = False,
    session_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build or reuse the shared stage-analysis payload for career using persisted fingerprints."""
    player = data.get("player") or {}
    player_id = str(player.get("player_id") or player.get("id") or "")
    scope = build_career_artifact_scope(player_id)
    base_payloads = build_career_base_artifact_payloads(data)
    source_checksum = _career_source_checksum(base_payloads)
    active_registry = registry or ArtifactRegistry()
    runtime_config = get_intelligence_runtime_config()
    llm_enabled = bool(runtime_config.get("career_agent_llm_enabled"))
    model_profile = str(runtime_config.get("career_agent_model_profile") or "flash")

    artifact_key = build_career_artifact_key(CAREER_STAGE_ANALYSIS_ARTIFACT, player_id)
    expected_fingerprint = build_artifact_fingerprint(
        build_career_stage_analysis_fingerprint_inputs(
            player_id=player_id,
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
        payload = dict(stored_artifact.get("payload") or {})
        if payload:
            debug = dict(payload.get("debug") or {})
            analysis_source = str(debug.get("analysis_source") or "artifact")
            if llm_enabled and analysis_source != "agentic":
                logger.info(
                    "Career stage analysis ignoring stored artifact player_id=%s analysis_source=%s llm_enabled=%s model_profile=%s",
                    player_id,
                    analysis_source,
                    llm_enabled,
                    model_profile,
                )
                payload = {}
            else:
                debug.setdefault("analysis_source", "artifact")
                payload["debug"] = debug
                return payload

    artifacts = {
        artifact_type: {"payload": payload}
        for artifact_type, payload in base_payloads.items()
    }
    logger.info(
        "Career stage analysis invoking agent player_id=%s llm_enabled=%s model_profile=%s force_refresh=%s",
        player_id,
        llm_enabled,
        model_profile,
        force_refresh,
    )
    analysis = CareerStageAgent().analyze(scope=scope, artifacts=artifacts, session_memory=session_memory)
    serialized = serialize_stage_analysis(analysis)
    debug = dict(serialized.get("debug") or {})
    debug.setdefault("analysis_source", "agentic" if debug.get("llm_generated") else "fallback")
    serialized["debug"] = debug
    logger.info(
        "Career stage analysis agent result player_id=%s analysis_source=%s llm_generated=%s discoveries=%s",
        player_id,
        str(debug.get("analysis_source") or "unknown"),
        bool(debug.get("llm_generated")),
        len(list(serialized.get("discoveries") or [])),
    )
    persisted_analysis = _persist_runtime_career_stage_analysis(
        serialized,
        player_id=player_id,
        source_checksum=source_checksum,
        llm_enabled=llm_enabled,
        model_profile=model_profile,
        registry=active_registry,
        runtime_config=runtime_config,
    )
    if persisted_analysis["failure"]:
        logger.warning(
            "Career stage analysis degraded persistence player_id=%s error=%s",
            player_id,
            persisted_analysis["failure"],
        )
    return serialized
