# ABOUTME: Non-blocking orchestrator for prematch-stage intelligence using the shared stage-runtime contract.
# ABOUTME: Persists prematch artifacts, curates one tactical candidate, and emits one UI-ready payload shape for callbacks and helpers.

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping

from utils.agents.orchestration_runtime import collect_fresh_payload_artifacts, sync_session_memory_with_graceful_failure
from utils.agents.prematch_signal_agent import curate_prematch_signals, is_viable_prematch_candidate
from utils.intelligence.artifact_registry import ArtifactRegistry
from utils.intelligence.overlay_surface import resolve_stage_overlay_surface
from utils.intelligence.reevaluation_policy import decide_stage_reevaluation
from utils.intelligence.runtime_config import get_intelligence_runtime_config
from utils.intelligence.session_memory import get_prematch_session_memory, put_prematch_session_memory
from utils.intelligence.stage_orchestrator import build_stage_runtime_result
from utils.prematch_stage.prematch_intelligence import (
    PREMATCH_BASE_ARTIFACT_TYPES,
    PREMATCH_OVERLAY_CANDIDATES_ARTIFACT,
    PREMATCH_SIGNALS_ARTIFACT,
    PREMATCH_STAGE_ANALYSIS_ARTIFACT,
    _prematch_source_checksum,
    build_prematch_artifact_record,
    build_prematch_signals_payload,
    build_prematch_stage_analysis_payload,
    get_prematch_intelligence_state,
)

logger = logging.getLogger(__name__)


def _persist_prematch_artifact(
    artifact_type: str,
    payload: Mapping[str, Any],
    *,
    player_id: str,
    fixture_id: str,
    base_payloads: Mapping[str, Mapping[str, Any]],
    dependency_fingerprint_map: Mapping[str, str] | None,
    registry: ArtifactRegistry,
    runtime_config: Mapping[str, Any],
) -> Dict[str, Any]:
    """Persist one prematch runtime artifact with graceful degradation."""
    record = build_prematch_artifact_record(
        artifact_type,
        payload,
        player_id=player_id,
        fixture_id=fixture_id,
        source_checksum=_prematch_source_checksum(base_payloads),
        dependency_fingerprint_map=dependency_fingerprint_map,
    )
    if not runtime_config.get("derived_writes_enabled", True):
        return {"artifact": record, "persisted": False, "failure": None}
    try:
        stored = registry.put_artifact(record["artifact_key"], record)
        return {"artifact": stored, "persisted": True, "failure": None}
    except Exception as exc:
        logger.exception(
            "Prematch orchestrator artifact persistence failed artifact=%s player_id=%s fixture_id=%s: %s",
            artifact_type,
            player_id,
            fixture_id,
            exc,
        )
        return {"artifact": record, "persisted": False, "failure": str(exc)}


def _sync_prematch_session_memory(
    *,
    player_id: str,
    fixture_id: str,
    current_candidate: Mapping[str, Any] | None,
    existing_memory: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Persist prematch session memory with graceful degradation."""
    existing_memory = existing_memory or {}
    seen_novelty_keys = list(existing_memory.get("seen_novelty_keys") or [])
    novelty_key = str((current_candidate or {}).get("novelty_key") or "")
    if novelty_key and novelty_key not in seen_novelty_keys:
        seen_novelty_keys.append(novelty_key)
    return sync_session_memory_with_graceful_failure(
        persist_fn=lambda: put_prematch_session_memory(
            player_id=player_id,
            fixture_id=fixture_id,
            current_novelty_key=novelty_key or None,
            seen_novelty_keys=seen_novelty_keys,
            last_curated_signal_id=str((current_candidate or {}).get("signal_id") or "") or None,
            current_candidate=dict(current_candidate or {}) if current_candidate else None,
            current_anchor=str((current_candidate or {}).get("anchor") or "") or None,
            current_priority=(current_candidate or {}).get("priority"),
        ),
        logger=logger,
        log_message="Prematch session memory persistence failed player_id=%s fixture_id=%s signal_id=%s: %s",
        log_args=(player_id, fixture_id, str((current_candidate or {}).get("signal_id") or "")),
        existing_memory=existing_memory,
    )


def orchestrate_prematch_intelligence(
    payload: Dict[str, Any],
    *,
    registry: ArtifactRegistry | None = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Orchestrate prematch intelligence on the shared stage-runtime contract."""
    active_registry = registry or ArtifactRegistry()
    runtime_config = get_intelligence_runtime_config()
    state = get_prematch_intelligence_state(payload, registry=active_registry)
    artifact_states = state.get("artifacts") or {}
    refresh_plan = list(state.get("refresh_plan") or [])
    runtime_artifacts = collect_fresh_payload_artifacts(artifact_states)
    base_ready = all(artifact_type in runtime_artifacts for artifact_type in PREMATCH_BASE_ARTIFACT_TYPES)
    scope = state.get("scope") or {}
    player_id = str(scope.get("player_id") or "")
    fixture_id = str(scope.get("fixture_id") or "")
    session_memory = get_prematch_session_memory(player_id=player_id, fixture_id=fixture_id) or {}
    persisted_session_memory = False
    persisted_artifacts: List[str] = []
    write_failures: List[Dict[str, str]] = []
    served_from = {"analysis": "fallback", "signals": "fallback", "overlay": "fallback"}
    llm_enabled = bool(runtime_config.get("prematch_agent_llm_enabled"))

    stored_analysis = (artifact_states.get(PREMATCH_STAGE_ANALYSIS_ARTIFACT) or {}).get("artifact")
    stored_analysis_payload = dict((stored_analysis or {}).get("payload") or {})
    stored_analysis_source = str(((stored_analysis_payload.get("debug") or {}).get("analysis_source")) or "artifact")
    reevaluation = decide_stage_reevaluation(
        stage_name="prematch",
        artifact_states=artifact_states,
        primary_artifact_type=PREMATCH_STAGE_ANALYSIS_ARTIFACT,
        dependency_fingerprints={},
        refresh_plan=refresh_plan,
        trigger_context={
            "force": force_refresh,
            "fixture_changed": bool(PREMATCH_STAGE_ANALYSIS_ARTIFACT in refresh_plan and not stored_analysis),
            "next_match_changed": bool(
                set(refresh_plan)
                & set(PREMATCH_BASE_ARTIFACT_TYPES + [PREMATCH_STAGE_ANALYSIS_ARTIFACT])
            ),
            "llm_first_required": bool(llm_enabled and stored_analysis and stored_analysis_source != "agentic"),
        },
    )
    reevaluation_metadata = {
        "should_reevaluate": bool(reevaluation.should_reevaluate),
        "reason": reevaluation.reason,
        "reasons": list(reevaluation.reasons),
        "freshness_status": reevaluation.freshness_status,
        "soft_stale": bool(reevaluation.soft_stale),
        "hard_stale": bool(reevaluation.hard_stale),
        "age_hours": reevaluation.age_hours,
        "policy": dict(reevaluation.policy or {}),
    }
    if reevaluation.should_reevaluate:
        refresh_plan = list(
            dict.fromkeys(
                [
                    *refresh_plan,
                    PREMATCH_SIGNALS_ARTIFACT,
                    PREMATCH_STAGE_ANALYSIS_ARTIFACT,
                    PREMATCH_OVERLAY_CANDIDATES_ARTIFACT,
                ]
            )
        )

    if (
        not force_refresh
        and not reevaluation.should_reevaluate
        and stored_analysis
        and PREMATCH_STAGE_ANALYSIS_ARTIFACT in runtime_artifacts
    ):
        stage_analysis = dict(stored_analysis.get("payload") or {})
        served_from["analysis"] = "artifact"
    else:
        stage_analysis = build_prematch_stage_analysis_payload(
            payload,
            registry=active_registry,
            force_refresh=force_refresh or not runtime_config.get("persistence_enabled", True),
        )
        runtime_artifacts[PREMATCH_STAGE_ANALYSIS_ARTIFACT] = {"payload": stage_analysis}
        persisted_artifacts.append(PREMATCH_STAGE_ANALYSIS_ARTIFACT)
        served_from["analysis"] = str(((stage_analysis.get("debug") or {}).get("analysis_source")) or "inline")

    stored_signals = (artifact_states.get(PREMATCH_SIGNALS_ARTIFACT) or {}).get("artifact")
    if stored_signals and PREMATCH_SIGNALS_ARTIFACT in runtime_artifacts:
        signals_payload = dict(stored_signals.get("payload") or {})
        served_from["signals"] = "artifact"
    else:
        signals_payload = build_prematch_signals_payload(stage_analysis)
        persisted_signal = _persist_prematch_artifact(
            PREMATCH_SIGNALS_ARTIFACT,
            signals_payload,
            player_id=player_id,
            fixture_id=fixture_id,
            base_payloads=state.get("base_payloads") or {},
            dependency_fingerprint_map={PREMATCH_STAGE_ANALYSIS_ARTIFACT: str((artifact_states.get(PREMATCH_STAGE_ANALYSIS_ARTIFACT) or {}).get("expected_fingerprint") or "")},
            registry=active_registry,
            runtime_config=runtime_config,
        )
        runtime_artifacts[PREMATCH_SIGNALS_ARTIFACT] = persisted_signal["artifact"]
        if persisted_signal["persisted"]:
            persisted_artifacts.append(PREMATCH_SIGNALS_ARTIFACT)
        elif persisted_signal["failure"]:
            write_failures.append({"target": PREMATCH_SIGNALS_ARTIFACT, "error": persisted_signal["failure"]})
        served_from["signals"] = "inline"

    stored_overlay = (artifact_states.get(PREMATCH_OVERLAY_CANDIDATES_ARTIFACT) or {}).get("artifact")
    if stored_overlay and PREMATCH_OVERLAY_CANDIDATES_ARTIFACT in runtime_artifacts and not force_refresh:
        overlay_payload = dict(stored_overlay.get("payload") or {})
        overlay_surface = resolve_stage_overlay_surface("prematch", overlay_payload)
        served_from["overlay"] = "artifact"
    else:
        curation = curate_prematch_signals(
            list((signals_payload or {}).get("signals") or []),
            session_memory=session_memory,
        )
        selected_candidate = dict(curation.get("candidate") or {})
        overlay_payload = {
            "candidates": list((signals_payload or {}).get("signals") or []),
            "candidate_count": len(list((signals_payload or {}).get("signals") or [])),
            "selected_candidate": selected_candidate or None,
        }
        overlay_surface = resolve_stage_overlay_surface("prematch", overlay_payload)
        served_from["overlay"] = str(curation.get("source") or "inline")
        persisted_overlay = _persist_prematch_artifact(
            PREMATCH_OVERLAY_CANDIDATES_ARTIFACT,
            overlay_payload,
            player_id=player_id,
            fixture_id=fixture_id,
            base_payloads=state.get("base_payloads") or {},
            dependency_fingerprint_map={PREMATCH_SIGNALS_ARTIFACT: str((artifact_states.get(PREMATCH_SIGNALS_ARTIFACT) or {}).get("expected_fingerprint") or "")},
            registry=active_registry,
            runtime_config=runtime_config,
        )
        runtime_artifacts[PREMATCH_OVERLAY_CANDIDATES_ARTIFACT] = persisted_overlay["artifact"]
        if persisted_overlay["persisted"]:
            persisted_artifacts.append(PREMATCH_OVERLAY_CANDIDATES_ARTIFACT)
        elif persisted_overlay["failure"]:
            write_failures.append({"target": PREMATCH_OVERLAY_CANDIDATES_ARTIFACT, "error": persisted_overlay["failure"]})

    current_candidate = dict((overlay_surface or {}).get("primary_candidate") or {})
    if current_candidate and is_viable_prematch_candidate(current_candidate):
        memory_result = _sync_prematch_session_memory(
            player_id=player_id,
            fixture_id=fixture_id,
            current_candidate=current_candidate,
            existing_memory=session_memory,
        )
        session_memory = memory_result["memory"]
        persisted_session_memory = bool(memory_result["persisted"])
        if memory_result["failure"]:
            write_failures.append({"target": "session_memory", "error": memory_result["failure"]})

    refresh_plan = [artifact_type for artifact_type in refresh_plan if artifact_type not in persisted_artifacts]
    fallback_reason = None
    if not base_ready and refresh_plan:
        fallback_reason = "base_artifacts_not_ready"
    elif not current_candidate:
        fallback_reason = "no_curated_signal"
    return build_stage_runtime_result(
        stage_name="prematch",
        state=state,
        runtime_config=runtime_config,
        stage_analysis=stage_analysis,
        shared_stage_analysis=stage_analysis,
        signals=signals_payload,
        overlay_candidates=overlay_payload,
        overlay_surface=overlay_surface,
        served_from=served_from,
        refresh_plan=refresh_plan,
        persisted_artifacts=persisted_artifacts,
        session_memory=session_memory,
        persisted_session_memory=persisted_session_memory,
        base_ready=base_ready,
        fallback_reason=fallback_reason,
        write_failures=write_failures,
        reevaluation=reevaluation_metadata,
    )
