# ABOUTME: Non-blocking orchestrator for career-stage intelligence using fresh artifacts first and background refresh planning second.
# ABOUTME: Coordinates registry freshness, career specialist agents, curated signals, session memory, and UI-ready debug metadata.

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping

from utils.agents.orchestration_runtime import (
    collect_fresh_payload_artifacts,
    is_fresh_artifact_state,
)
from utils.agents.career_signal_agent import (
    curate_career_signals,
    is_viable_career_candidate,
)
from utils.career_stage.career_intelligence import (
    CAREER_ARTIFACT_DEPENDENCIES,
    CAREER_ARTIFACT_TYPES,
    CAREER_BASE_ARTIFACT_TYPES,
    CAREER_OVERLAY_CANDIDATES_ARTIFACT,
    CAREER_SIGNALS_ARTIFACT,
    CAREER_STAGE_ANALYSIS_ARTIFACT,
    _build_curated_career_overlay_payload,
    _career_source_checksum,
    _persist_runtime_career_artifact,
    _sync_career_session_memory,
    build_career_artifact_fingerprint_inputs,
    build_career_artifact_key,
    build_career_artifact_record,
    build_career_base_artifact_payloads,
    build_career_stage_analysis_payload,
    build_career_stage_analysis_record,
    get_career_freshness_policy,
)
from utils.insights.career_signals import (
    build_career_signals,
    build_career_signals_payload,
)
from utils.intelligence.artifact_registry import ArtifactRegistry
from utils.intelligence.discovery_overlay_mapper import build_overlay_candidates_from_analysis
from utils.intelligence.freshness_manager import (
    FRESHNESS_FRESH,
    build_artifact_fingerprint,
    build_dependency_fingerprint_map,
    evaluate_artifact_freshness,
)
from utils.intelligence.overlay_surface import resolve_stage_overlay_surface
from utils.intelligence.runtime_config import get_intelligence_runtime_config
from utils.intelligence.session_memory import get_career_session_memory

logger = logging.getLogger(__name__)


def get_career_intelligence_state(
    data: Dict[str, Any],
    *,
    registry: ArtifactRegistry | None = None,
) -> Dict[str, Any]:
    """Load career artifacts from the registry and decide which ones need refresh."""
    player = data.get("player") or {}
    player_id = str(player.get("player_id") or player.get("id") or data.get("player_id") or "")
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
            stored_artifact = active_registry.put_artifact(
                artifact_key,
                build_career_artifact_record(
                    artifact_type,
                    base_payloads[artifact_type],
                    player_id=player_id,
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
            "freshness_policy": get_career_freshness_policy(artifact_type),
            "expected_fingerprint": expected_fingerprint,
            "payload_contract": base_payloads.get(artifact_type),
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
        "scope": {"player_id": player_id, "stage": "career"},
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

    runtime_artifacts = collect_fresh_payload_artifacts(artifact_states)
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

    stored_signals = (artifact_states.get(CAREER_SIGNALS_ARTIFACT) or {}).get("artifact")
    if (
        is_fresh_artifact_state(artifact_states.get(CAREER_SIGNALS_ARTIFACT))
        and stored_signals
    ):
        signals_payload = dict((stored_signals.get("payload") or {}))
        served_from["signals"] = "artifact"
    elif base_ready:
        built_signals = build_career_signals(runtime_artifacts)
        signals_payload = build_career_signals_payload(built_signals)
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
        served_from["signals"] = "inline"

    stored_analysis = (artifact_states.get(CAREER_STAGE_ANALYSIS_ARTIFACT) or {}).get("artifact")
    if (
        not force_refresh
        and is_fresh_artifact_state(artifact_states.get(CAREER_STAGE_ANALYSIS_ARTIFACT))
        and stored_analysis
    ):
        stage_analysis_payload = dict((stored_analysis.get("payload") or {}))
        shared_stage_analysis = dict(stage_analysis_payload)
        served_from["analysis"] = "artifact"
    elif base_ready:
        shared_stage_analysis = build_career_stage_analysis_payload(
            data,
            registry=active_registry,
            force_refresh=force_refresh,
            session_memory=session_memory,
        )
        stage_analysis_payload = dict(shared_stage_analysis)
        runtime_artifacts[CAREER_STAGE_ANALYSIS_ARTIFACT] = build_career_stage_analysis_record(
            stage_analysis_payload,
            player_id=player_id,
            source_checksum=_career_source_checksum(state.get("base_payloads") or {}),
            llm_enabled=bool(runtime_config.get("career_agent_llm_enabled")),
            model_profile=str(runtime_config.get("career_agent_model_profile") or "flash"),
        )
        served_from["analysis"] = str(((stage_analysis_payload.get("debug") or {}).get("analysis_source")) or "inline")

    stored_overlay = (artifact_states.get(CAREER_OVERLAY_CANDIDATES_ARTIFACT) or {}).get("artifact")
    if shared_stage_analysis is not None:
        shared_overlay_payload = build_overlay_candidates_from_analysis(shared_stage_analysis)
        shared_overlay_surface = resolve_stage_overlay_surface("career", shared_overlay_payload)
        shared_primary_candidate = shared_overlay_surface.get("primary_candidate")
        if shared_primary_candidate and is_viable_career_candidate(shared_primary_candidate):
            overlay_payload = shared_overlay_payload
            overlay_surface = shared_overlay_surface
            served_from["overlay"] = f"analysis_{served_from['analysis']}"
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
        else:
            overlay_payload = None
            overlay_surface = resolve_stage_overlay_surface("career", {"candidates": []})
    if overlay_payload is None and signals_payload is not None:
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

    result = {
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

    logger.info(
        "Career orchestrator mode=%s base_ready=%s refresh_plan=%s served_from=%s",
        mode,
        base_ready,
        refresh_plan,
        served_from,
    )
    if write_failures:
        logger.warning(
            "Career orchestrator degraded persistence player_id=%s failures=%s",
            player_id,
            write_failures,
        )
    return result
