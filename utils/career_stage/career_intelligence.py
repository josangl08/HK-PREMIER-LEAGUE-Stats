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
    CAREER_SIGNALS_ARTIFACT: [CAREER_STAGE_ANALYSIS_ARTIFACT],
    CAREER_OVERLAY_CANDIDATES_ARTIFACT: [CAREER_STAGE_ANALYSIS_ARTIFACT],
    CAREER_STAGE_ANALYSIS_ARTIFACT: [
        CAREER_PHASE_CONTEXT_ARTIFACT,
        CAREER_SIGNALS_CONTEXT_ARTIFACT,
        CAREER_PRIORITIES_CONTEXT_ARTIFACT,
        CAREER_DASHBOARD_BRIEF_ARTIFACT,
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
    try:
        stored_memory = _build_updated_career_session_memory(
            player_id=player_id,
            current_candidate=current_candidate,
            existing_memory=existing_memory,
        )
        return {
            "memory": stored_memory,
            "persisted": True,
            "failure": None,
        }
    except Exception as exc:
        logger.exception(
            "Career session memory persistence failed player_id=%s signal_id=%s: %s",
            player_id,
            str((current_candidate or {}).get("signal_id") or ""),
            exc,
        )
        return {
            "memory": dict(existing_memory or {}),
            "persisted": False,
            "failure": str(exc),
        }


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
    """Load career artifacts from the registry and decide which ones need refresh."""
    player = data.get("player") or {}
    player_id = str(player.get("player_id") or player.get("id") or data.get("player_id") or "")
    scope = build_career_artifact_scope(player_id)
    active_registry = registry or ArtifactRegistry()
    base_payloads = build_career_base_artifact_payloads(data)
    artifact_states: Dict[str, Any] = {}
    refresh_plan: List[str] = []
    persisted_base_artifacts: List[str] = []

    for artifact_type in CAREER_ARTIFACT_TYPES:
        artifact_key = build_career_artifact_key(artifact_type, player_id)
        dependency_fingerprint_map = build_dependency_fingerprint_map(
            {
                dependency: artifact_states[dependency]["artifact"]
                for dependency in CAREER_ARTIFACT_DEPENDENCIES.get(artifact_type, [])
                if dependency in artifact_states
            }
        )
        if artifact_type in base_payloads:
            source_checksum = build_artifact_fingerprint(base_payloads.get(artifact_type) or {})
        elif artifact_type == CAREER_STAGE_ANALYSIS_ARTIFACT:
            source_checksum = _career_source_checksum(base_payloads)
        else:
            source_checksum = build_artifact_fingerprint(base_payloads)
        expected_fingerprint = build_artifact_fingerprint(
            build_career_artifact_fingerprint_inputs(
                artifact_type,
                player_id=player_id,
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
                for dependency in CAREER_ARTIFACT_DEPENDENCIES.get(artifact_type, [])
            ],
            dependency_fingerprint_map=dependency_fingerprint_map,
        )

        if artifact_type in base_payloads and freshness["status"] != FRESHNESS_FRESH:
            stored_artifact = persist_base_career_artifact(
                artifact_type,
                deepcopy(base_payloads[artifact_type]),
                player_id=player_id,
                registry=active_registry,
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
            "freshness_policy": get_career_freshness_policy(artifact_type),
            "expected_fingerprint": expected_fingerprint,
            "payload_contract": deepcopy(base_payloads.get(artifact_type)),
        }

    logger.info(
        "Career intelligence state player_id=%s fresh=%s refresh=%s",
        player_id or "unknown",
        sorted(
            artifact_type
            for artifact_type, state in artifact_states.items()
            if state["freshness"]["status"] == FRESHNESS_FRESH
        ),
        refresh_plan,
    )

    return {
        "scope": scope,
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


def orchestrate_career_intelligence(
    data: Dict[str, Any],
    *,
    registry: ArtifactRegistry | None = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Orchestrate career intelligence using the season-style artifact lifecycle."""
    active_registry = registry or ArtifactRegistry()
    runtime_config = get_intelligence_runtime_config()
    state = get_career_intelligence_state(data, registry=active_registry)
    artifact_states = state.get("artifacts") or {}
    refresh_plan = list(state.get("refresh_plan") or [])
    player = data.get("player") or {}
    player_id = str(player.get("player_id") or player.get("id") or data.get("player_id") or "")

    runtime_artifacts = {
        artifact_type: state_entry["artifact"]
        for artifact_type, state_entry in artifact_states.items()
        if state_entry.get("artifact") and (state_entry.get("freshness") or {}).get("status") == FRESHNESS_FRESH
    }
    base_ready = all(artifact_type in runtime_artifacts for artifact_type in CAREER_BASE_ARTIFACT_TYPES)
    persisted_artifacts: List[str] = []
    served_from = {"analysis": "fallback", "signals": "fallback", "overlay": "fallback"}
    stage_analysis_payload = None
    shared_stage_analysis = None
    signals_payload = None
    overlay_payload = None
    overlay_surface = resolve_stage_overlay_surface("career", {"candidates": []})

    logger.info(
        "Career intelligence runtime config player_id=%s artifacts_root=%s session_memory_root=%s persistence_enabled=%s derived_writes_enabled=%s",
        player_id,
        str(runtime_config.get("artifacts_root") or ""),
        str(runtime_config.get("session_memory_root") or ""),
        bool(runtime_config.get("persistence_enabled")),
        bool(runtime_config.get("derived_writes_enabled")),
    )
    session_memory = get_career_session_memory(player_id=player_id) or {}
    persisted_session_memory = False
    write_failures: List[Dict[str, str]] = []
    current_memory_candidate = dict(session_memory.get("current_candidate") or {})
    if current_memory_candidate and not is_viable_career_candidate(current_memory_candidate):
        memory_result = _sync_career_session_memory(
            player_id=player_id,
            current_candidate=None,
            existing_memory=session_memory,
        )
        session_memory = memory_result["memory"]
        persisted_session_memory = memory_result["persisted"]
        if memory_result["failure"]:
            write_failures.append({"target": "session_memory", "error": memory_result["failure"]})
        logger.info(
            "Career session memory cleared stale candidate player_id=%s signal_id=%s",
            player_id,
            str(current_memory_candidate.get("signal_id") or ""),
        )
    logger.info(
        "Career session memory %s player_id=%s current_novelty_key=%s seen_count=%s",
        "hit" if session_memory else "miss",
        player_id,
        str(session_memory.get("current_novelty_key") or ""),
        len(session_memory.get("seen_novelty_keys") or []),
    )

    stored_analysis = (artifact_states.get(CAREER_STAGE_ANALYSIS_ARTIFACT) or {}).get("artifact")
    if (
        not force_refresh
        and (artifact_states.get(CAREER_STAGE_ANALYSIS_ARTIFACT) or {}).get("freshness", {}).get("status") == FRESHNESS_FRESH
        and stored_analysis
    ):
        stage_analysis_payload = dict((stored_analysis.get("payload") or {}))
        shared_stage_analysis = deepcopy(stage_analysis_payload)
        served_from["analysis"] = "artifact"
    elif base_ready:
        shared_stage_analysis = build_career_stage_analysis_payload(
            data,
            registry=active_registry,
            force_refresh=force_refresh,
            session_memory=session_memory,
        )
        stage_analysis_payload = deepcopy(shared_stage_analysis)
        runtime_artifacts[CAREER_STAGE_ANALYSIS_ARTIFACT] = build_career_stage_analysis_record(
            stage_analysis_payload,
            player_id=player_id,
            source_checksum=_career_source_checksum(state.get("base_payloads") or {}),
            llm_enabled=bool(runtime_config.get("career_agent_llm_enabled")),
            model_profile=str(runtime_config.get("career_agent_model_profile") or "flash"),
        )
        served_from["analysis"] = str(((stage_analysis_payload.get("debug") or {}).get("analysis_source")) or "inline")

    stored_signals = (artifact_states.get(CAREER_SIGNALS_ARTIFACT) or {}).get("artifact")
    if (
        (artifact_states.get(CAREER_SIGNALS_ARTIFACT) or {}).get("freshness", {}).get("status") == FRESHNESS_FRESH
        and stored_signals
    ):
        signals_payload = dict((stored_signals.get("payload") or {}))
        served_from["signals"] = "artifact"
    elif shared_stage_analysis is not None:
        shared_overlay_payload = build_overlay_candidates_from_analysis(shared_stage_analysis)
        signals_payload = build_career_signals_payload(shared_overlay_payload.get("candidates") or [])
        persisted_signals = _persist_runtime_career_artifact(
            CAREER_SIGNALS_ARTIFACT,
            signals_payload,
            player_id=player_id,
            base_payloads=state.get("base_payloads") or {},
            dependency_artifacts=runtime_artifacts,
            registry=active_registry,
            runtime_config=runtime_config,
        )
        runtime_artifacts[CAREER_SIGNALS_ARTIFACT] = persisted_signals["artifact"]
        if persisted_signals["persisted"]:
            persisted_artifacts.append(CAREER_SIGNALS_ARTIFACT)
        elif persisted_signals["failure"]:
            write_failures.append({"target": CAREER_SIGNALS_ARTIFACT, "error": persisted_signals["failure"]})
        served_from["signals"] = f"analysis_{served_from['analysis']}"

    stored_overlay = (artifact_states.get(CAREER_OVERLAY_CANDIDATES_ARTIFACT) or {}).get("artifact")
    if signals_payload is not None:
        shared_candidates = list((signals_payload or {}).get("signals") or [])
        curation_result = curate_career_signals(
            shared_candidates,
            session_memory=session_memory,
        )
        selected_candidate = dict(curation_result.get("candidate") or {})
        if shared_candidates:
            overlay_payload = _build_curated_career_overlay_payload(
                shared_candidates,
                selected_candidate=selected_candidate or None,
            )
            overlay_surface = resolve_stage_overlay_surface("career", overlay_payload)
            overlay_source = str(curation_result.get("source") or "inline")
            served_from["overlay"] = (
                "session_memory"
                if overlay_source == "session_memory"
                else f"signals_{served_from['signals']}"
            )
            persisted_overlay = _persist_runtime_career_artifact(
                CAREER_OVERLAY_CANDIDATES_ARTIFACT,
                overlay_payload,
                player_id=player_id,
                base_payloads=state.get("base_payloads") or {},
                dependency_artifacts=runtime_artifacts,
                registry=active_registry,
                runtime_config=runtime_config,
            )
            runtime_artifacts[CAREER_OVERLAY_CANDIDATES_ARTIFACT] = persisted_overlay["artifact"]
            if persisted_overlay["persisted"]:
                persisted_artifacts.append(CAREER_OVERLAY_CANDIDATES_ARTIFACT)
            elif persisted_overlay["failure"]:
                write_failures.append(
                    {"target": CAREER_OVERLAY_CANDIDATES_ARTIFACT, "error": persisted_overlay["failure"]}
                )
    if overlay_payload is None and stored_overlay:
        overlay_payload = dict((stored_overlay.get("payload") or {}))
        overlay_surface = resolve_stage_overlay_surface("career", overlay_payload)
        served_from["overlay"] = "artifact"
        current_artifact_candidate = dict((overlay_surface or {}).get("primary_candidate") or {})
        if current_artifact_candidate and is_viable_career_candidate(current_artifact_candidate):
            memory_result = _sync_career_session_memory(
                player_id=player_id,
                current_candidate=current_artifact_candidate,
                existing_memory=session_memory,
            )
            session_memory = memory_result["memory"]
            persisted_session_memory = persisted_session_memory or memory_result["persisted"]
            if memory_result["failure"]:
                write_failures.append({"target": "session_memory", "error": memory_result["failure"]})
            logger.info(
                "Career session memory synced from artifact player_id=%s signal_id=%s novelty_key=%s",
                player_id,
                str(current_artifact_candidate.get("signal_id") or ""),
                str(current_artifact_candidate.get("novelty_key") or ""),
            )

    current_candidate = dict((overlay_surface or {}).get("primary_candidate") or {})
    if current_candidate and is_viable_career_candidate(current_candidate):
        memory_result = _sync_career_session_memory(
            player_id=player_id,
            current_candidate=current_candidate,
            existing_memory=session_memory,
        )
        session_memory = memory_result["memory"]
        persisted_session_memory = persisted_session_memory or memory_result["persisted"]
        if memory_result["failure"]:
            write_failures.append({"target": "session_memory", "error": memory_result["failure"]})

    if persisted_artifacts:
        refresh_plan = [
            artifact_type
            for artifact_type in refresh_plan
            if artifact_type not in persisted_artifacts
        ]

    background_refresh_required = bool(refresh_plan)
    mode = "fast_path" if not background_refresh_required else "slow_path"
    fallback_reason = None
    if not base_ready and background_refresh_required:
        fallback_reason = "base_artifacts_not_ready"
    elif not current_candidate and signals_payload:
        fallback_reason = "no_curated_signal"
    elif not stage_analysis_payload and not signals_payload:
        fallback_reason = "no_intelligence_payload_available"
    logger.info(
        "Career orchestrator mode=%s base_ready=%s refresh_plan=%s served_from=%s",
        mode,
        base_ready,
        refresh_plan,
        served_from,
    )
    return {
        "available": bool(stage_analysis_payload or overlay_payload),
        "mode": mode,
        "non_blocking": True,
        "background_refresh_required": background_refresh_required,
        "refresh_plan": refresh_plan,
        "stage_analysis": stage_analysis_payload,
        "shared_stage_analysis": shared_stage_analysis,
        "signals": signals_payload,
        "overlay_candidates": overlay_payload,
        "overlay_surface": overlay_surface,
        "debug": {
            "scope": state.get("scope") or {},
            "served_from": served_from,
            "base_ready": base_ready,
            "non_blocking": True,
            "background_refresh_requested": background_refresh_required,
            "fallback_reason": fallback_reason,
            "refresh_requested_for": refresh_plan,
            "persisted_artifacts": persisted_artifacts,
            "runtime": {
                "artifacts_root": str(runtime_config.get("artifacts_root") or ""),
                "session_memory_root": str(runtime_config.get("session_memory_root") or ""),
                "persistence_enabled": bool(runtime_config.get("persistence_enabled")),
                "derived_writes_enabled": bool(runtime_config.get("derived_writes_enabled")),
            },
            "freshness": (state.get("debug") or {}).get("freshness") or {},
            "artifact_keys": (state.get("debug") or {}).get("artifact_keys") or {},
            "expected_fingerprints": (state.get("debug") or {}).get("expected_fingerprints") or {},
            "persisted_session_memory": persisted_session_memory,
            "session_memory": session_memory,
            "write_failures": write_failures,
            "overlay_surface": overlay_surface,
        },
    }
    if write_failures:
        logger.warning(
            "Career orchestrator degraded persistence player_id=%s failures=%s",
            player_id,
            write_failures,
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
