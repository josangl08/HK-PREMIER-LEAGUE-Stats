# ABOUTME: Non-blocking orchestrator for season-stage intelligence using fresh artifacts first and background refresh planning second.
# ABOUTME: Coordinates registry freshness, deterministic signal generation, specialist agents, and UI-ready debug metadata.

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping

from utils.agents.season_agent import build_season_stage_analysis
from utils.agents.signal_agent import curate_signals
from utils.insights.season_signals import build_season_signals
from utils.intelligence.artifact_registry import ArtifactRegistry
from utils.intelligence.runtime_config import get_intelligence_runtime_config
from utils.intelligence.session_memory import (
    get_season_session_memory,
    put_season_session_memory,
)
from utils.season_stage.season_intelligence import (
    RECENT_FORM_CONTEXT_ARTIFACT,
    SEASON_ARTIFACT_DEPENDENCIES,
    SEASON_OVERLAY_CANDIDATES_ARTIFACT,
    SEASON_PROFILE_CONTEXT_ARTIFACT,
    SEASON_SIGNALS_ARTIFACT,
    SEASON_STAGE_ANALYSIS_ARTIFACT,
    build_relevant_season_source_checksum,
    build_season_artifact_fingerprint_inputs,
    build_season_artifact_record,
    build_season_overlay_candidates_payload,
    build_season_signals_payload,
    build_season_stage_analysis_payload,
    get_season_intelligence_state,
)

logger = logging.getLogger(__name__)

_BASE_SEASON_ARTIFACTS = [
    SEASON_PROFILE_CONTEXT_ARTIFACT,
    "season_performance_context",
    "competition_split_context",
    "previous_season_context",
    RECENT_FORM_CONTEXT_ARTIFACT,
]


def _is_fresh(artifact_state: Mapping[str, Any] | None) -> bool:
    """Return whether an artifact-state entry is fresh."""
    return str(((artifact_state or {}).get("freshness") or {}).get("status") or "") == "fresh"


def _collect_fresh_payload_artifacts(artifact_states: Mapping[str, Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Return fresh artifact envelopes keyed by artifact type."""
    fresh_artifacts: Dict[str, Dict[str, Any]] = {}
    for artifact_type, state in artifact_states.items():
        if _is_fresh(state) and state.get("artifact"):
            fresh_artifacts[artifact_type] = dict(state["artifact"])
    return fresh_artifacts


def _persist_runtime_artifact(
    artifact_type: str,
    payload: Dict[str, Any],
    *,
    player_id: str,
    season: str,
    base_payloads: Mapping[str, Mapping[str, Any]],
    dependency_artifacts: Mapping[str, Mapping[str, Any]],
    registry: ArtifactRegistry,
    runtime_config: Mapping[str, Any],
) -> Dict[str, Any]:
    """Persist a derived runtime artifact built inline during orchestration."""
    dependency_fingerprint_map = {
        dependency: str((dependency_artifacts.get(dependency) or {}).get("fingerprint") or "")
        for dependency in SEASON_ARTIFACT_DEPENDENCIES.get(artifact_type, [])
        if dependency_artifacts.get(dependency) is not None
    }
    record = build_season_artifact_record(
        artifact_type,
        payload,
        player_id=player_id,
        season=season,
        fingerprint_inputs=build_season_artifact_fingerprint_inputs(
            artifact_type,
            player_id=player_id,
            season=season,
            source_checksum=build_relevant_season_source_checksum(artifact_type, base_payloads),
            dependency_fingerprint_map=dependency_fingerprint_map,
        ),
        dependency_fingerprint_map=dependency_fingerprint_map,
    )
    if not runtime_config.get("derived_writes_enabled", True):
        logger.info(
            "Season orchestrator skipped artifact write artifact=%s player_id=%s season=%s reason=derived_writes_disabled",
            artifact_type,
            player_id,
            season,
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
            "Season orchestrator artifact persistence failed artifact=%s player_id=%s season=%s: %s",
            artifact_type,
            player_id,
            season,
            exc,
        )
        return {
            "artifact": record,
            "persisted": False,
            "failure": str(exc),
            "skipped": None,
        }

    logger.info(
        "Season orchestrator persisted artifact=%s player_id=%s season=%s dependencies=%s",
        artifact_type,
        player_id,
        season,
        sorted(dependency_fingerprint_map),
    )
    return {
        "artifact": stored,
        "persisted": True,
        "failure": None,
        "skipped": None,
    }


def _build_updated_session_memory(
    *,
    player_id: str,
    season: str,
    current_candidate: Mapping[str, Any] | None,
    existing_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build the next persisted session-memory state for season intelligence."""
    existing_memory = existing_memory or {}
    seen_novelty_keys = list(existing_memory.get("seen_novelty_keys") or [])
    novelty_key = str((current_candidate or {}).get("novelty_key") or "")
    if novelty_key and novelty_key not in seen_novelty_keys:
        seen_novelty_keys.append(novelty_key)

    return put_season_session_memory(
        player_id=player_id,
        season=season,
        current_novelty_key=novelty_key or None,
        seen_novelty_keys=seen_novelty_keys,
        last_curated_signal_id=str((current_candidate or {}).get("signal_id") or "") or None,
        current_candidate=dict(current_candidate or {}) if current_candidate else None,
        current_anchor=str((current_candidate or {}).get("anchor") or "") or None,
        current_priority=(current_candidate or {}).get("priority"),
    )


def _sync_session_memory(
    *,
    player_id: str,
    season: str,
    current_candidate: Mapping[str, Any] | None,
    existing_memory: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Persist session memory with graceful degradation on failure."""
    try:
        stored_memory = _build_updated_session_memory(
            player_id=player_id,
            season=season,
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
            "Season session memory persistence failed player_id=%s season=%s signal_id=%s: %s",
            player_id,
            season,
            str((current_candidate or {}).get("signal_id") or ""),
            exc,
        )
        return {
            "memory": dict(existing_memory or {}),
            "persisted": False,
            "failure": str(exc),
        }


def orchestrate_season_intelligence(
    stage_payload: Dict[str, Any],
    *,
    session_state: Mapping[str, Any] | None = None,
    registry: ArtifactRegistry | None = None,
) -> Dict[str, Any]:
    """Orchestrate season intelligence in a non-blocking way for the season stage."""
    active_registry = registry or ArtifactRegistry()
    runtime_config = get_intelligence_runtime_config()
    state = get_season_intelligence_state(stage_payload, registry=active_registry)
    artifact_states = state.get("artifacts") or {}
    refresh_plan = list(state.get("refresh_plan") or [])
    fresh_artifacts = _collect_fresh_payload_artifacts(artifact_states)
    runtime_artifacts = dict(fresh_artifacts)
    persisted_artifacts: List[str] = []
    player_id = str((state.get("scope") or {}).get("player_id") or "")
    season = str((state.get("scope") or {}).get("season") or "")
    base_payloads = state.get("base_payloads") or {}
    base_ready = all(artifact_type in fresh_artifacts for artifact_type in _BASE_SEASON_ARTIFACTS)
    session_memory = get_season_session_memory(player_id=player_id, season=season) or {}
    persisted_session_memory = False
    write_failures: List[Dict[str, str]] = []
    logger.info(
        "Season intelligence runtime config player_id=%s season=%s artifacts_root=%s session_memory_root=%s persistence_enabled=%s derived_writes_enabled=%s",
        player_id,
        season,
        str(runtime_config.get("artifacts_root") or ""),
        str(runtime_config.get("session_memory_root") or ""),
        bool(runtime_config.get("persistence_enabled")),
        bool(runtime_config.get("derived_writes_enabled")),
    )
    logger.info(
        "Season session memory %s player_id=%s season=%s current_novelty_key=%s seen_count=%s",
        "hit" if session_memory else "miss",
        player_id,
        season,
        str(session_memory.get("current_novelty_key") or ""),
        len(session_memory.get("seen_novelty_keys") or []),
    )

    stage_analysis_payload = None
    signals_payload = None
    overlay_payload = None
    worth_noticing = None
    served_from = {
        "analysis": "fallback",
        "signals": "fallback",
        "overlay": "fallback",
    }

    stored_signals = (artifact_states.get(SEASON_SIGNALS_ARTIFACT) or {}).get("artifact")
    if _is_fresh(artifact_states.get(SEASON_SIGNALS_ARTIFACT)) and stored_signals:
        signals_payload = dict((stored_signals.get("payload") or {}))
        served_from["signals"] = "artifact"
    elif base_ready:
        built_signals = build_season_signals(runtime_artifacts)
        signals_payload = build_season_signals_payload(built_signals)
        persisted_signal = _persist_runtime_artifact(
            SEASON_SIGNALS_ARTIFACT,
            signals_payload,
            player_id=player_id,
            season=season,
            base_payloads=base_payloads,
            dependency_artifacts=runtime_artifacts,
            registry=active_registry,
            runtime_config=runtime_config,
        )
        runtime_artifacts[SEASON_SIGNALS_ARTIFACT] = persisted_signal["artifact"]
        if persisted_signal["persisted"]:
            persisted_artifacts.append(SEASON_SIGNALS_ARTIFACT)
        elif persisted_signal["failure"]:
            write_failures.append(
                {"target": SEASON_SIGNALS_ARTIFACT, "error": persisted_signal["failure"]}
            )
        served_from["signals"] = "inline"

    stored_analysis = (artifact_states.get(SEASON_STAGE_ANALYSIS_ARTIFACT) or {}).get("artifact")
    if _is_fresh(artifact_states.get(SEASON_STAGE_ANALYSIS_ARTIFACT)) and stored_analysis:
        stage_analysis_payload = dict((stored_analysis.get("payload") or {}))
        served_from["analysis"] = "artifact"
    elif base_ready:
        inline_analysis = build_season_stage_analysis(runtime_artifacts)
        stage_analysis_payload = build_season_stage_analysis_payload(inline_analysis)
        persisted_analysis = _persist_runtime_artifact(
            SEASON_STAGE_ANALYSIS_ARTIFACT,
            stage_analysis_payload,
            player_id=player_id,
            season=season,
            base_payloads=base_payloads,
            dependency_artifacts=runtime_artifacts,
            registry=active_registry,
            runtime_config=runtime_config,
        )
        runtime_artifacts[SEASON_STAGE_ANALYSIS_ARTIFACT] = persisted_analysis["artifact"]
        if persisted_analysis["persisted"]:
            persisted_artifacts.append(SEASON_STAGE_ANALYSIS_ARTIFACT)
        elif persisted_analysis["failure"]:
            write_failures.append(
                {"target": SEASON_STAGE_ANALYSIS_ARTIFACT, "error": persisted_analysis["failure"]}
            )
        served_from["analysis"] = "inline"

    stored_overlay = (artifact_states.get(SEASON_OVERLAY_CANDIDATES_ARTIFACT) or {}).get("artifact")
    if _is_fresh(artifact_states.get(SEASON_OVERLAY_CANDIDATES_ARTIFACT)) and stored_overlay:
        overlay_payload = dict((stored_overlay.get("payload") or {}))
        worth_noticing = overlay_payload.get("selected_candidate")
        served_from["overlay"] = "artifact"
        if worth_noticing:
            memory_result = _sync_session_memory(
                player_id=player_id,
                season=season,
                current_candidate=worth_noticing,
                existing_memory=session_memory,
            )
            session_memory = memory_result["memory"]
            persisted_session_memory = memory_result["persisted"]
            if memory_result["failure"]:
                write_failures.append(
                    {"target": "session_memory", "error": memory_result["failure"]}
                )
            logger.info(
                "Season session memory synced from artifact player_id=%s season=%s signal_id=%s novelty_key=%s",
                player_id,
                season,
                str(worth_noticing.get("signal_id") or ""),
                str(worth_noticing.get("novelty_key") or ""),
            )
    elif signals_payload and (signals_payload.get("signals") or []):
        next_candidate = curate_signals(
            signals_payload.get("signals") or [],
            session_state=session_state,
            session_memory=session_memory,
        )
        current_candidate = dict(session_memory.get("current_candidate") or {})
        worth_noticing = next_candidate
        if not worth_noticing and current_candidate:
            worth_noticing = current_candidate
            served_from["overlay"] = "session_memory"
            logger.info(
                "Season orchestrator preserved current insight from session memory player_id=%s season=%s signal_id=%s novelty_key=%s",
                player_id,
                season,
                str(current_candidate.get("signal_id") or ""),
                str(current_candidate.get("novelty_key") or ""),
            )
        elif worth_noticing:
            served_from["overlay"] = "inline"
            if current_candidate:
                logger.info(
                    "Season orchestrator replaced current insight player_id=%s season=%s old_signal_id=%s new_signal_id=%s",
                    player_id,
                    season,
                    str(current_candidate.get("signal_id") or ""),
                    str(worth_noticing.get("signal_id") or ""),
                )
            else:
                logger.info(
                    "Season orchestrator selected first insight player_id=%s season=%s signal_id=%s novelty_key=%s",
                    player_id,
                    season,
                    str(worth_noticing.get("signal_id") or ""),
                    str(worth_noticing.get("novelty_key") or ""),
                )

        overlay_payload = build_season_overlay_candidates_payload(
            signals_payload.get("signals") or [],
            selected_candidate=worth_noticing,
        )
        persisted_overlay = _persist_runtime_artifact(
            SEASON_OVERLAY_CANDIDATES_ARTIFACT,
            overlay_payload,
            player_id=player_id,
            season=season,
            base_payloads=base_payloads,
            dependency_artifacts=runtime_artifacts,
            registry=active_registry,
            runtime_config=runtime_config,
        )
        runtime_artifacts[SEASON_OVERLAY_CANDIDATES_ARTIFACT] = persisted_overlay["artifact"]
        if persisted_overlay["persisted"]:
            persisted_artifacts.append(SEASON_OVERLAY_CANDIDATES_ARTIFACT)
        elif persisted_overlay["failure"]:
            write_failures.append(
                {"target": SEASON_OVERLAY_CANDIDATES_ARTIFACT, "error": persisted_overlay["failure"]}
            )
        if worth_noticing:
            memory_result = _sync_session_memory(
                player_id=player_id,
                season=season,
                current_candidate=worth_noticing,
                existing_memory=session_memory,
            )
            session_memory = memory_result["memory"]
            persisted_session_memory = memory_result["persisted"]
            if memory_result["failure"]:
                write_failures.append(
                    {"target": "session_memory", "error": memory_result["failure"]}
                )
            logger.info(
                "Season session memory updated player_id=%s season=%s signal_id=%s novelty_key=%s seen_count=%s",
                player_id,
                season,
                str(worth_noticing.get("signal_id") or ""),
                str(worth_noticing.get("novelty_key") or ""),
                len(session_memory.get("seen_novelty_keys") or []),
            )

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
    elif not worth_noticing and signals_payload:
        fallback_reason = "no_curated_signal"
    elif not stage_analysis_payload and not signals_payload:
        fallback_reason = "no_intelligence_payload_available"

    result = {
        "available": bool(stage_analysis_payload or worth_noticing or signals_payload),
        "mode": mode,
        "non_blocking": True,
        "background_refresh_required": background_refresh_required,
        "refresh_plan": refresh_plan,
        "stage_analysis": stage_analysis_payload,
        "signals": signals_payload,
        "worth_noticing": worth_noticing,
        "overlay_candidates": overlay_payload,
        "debug": {
            "scope": state.get("scope") or {},
            "served_from": served_from,
            "base_ready": base_ready,
            "non_blocking": True,
            "fallback_reason": fallback_reason,
            "background_refresh_requested": background_refresh_required,
            "refresh_requested_for": refresh_plan,
            "persisted_artifacts": persisted_artifacts,
            "session_memory": session_memory,
            "persisted_session_memory": persisted_session_memory,
            "runtime": {
                "artifacts_root": str(runtime_config.get("artifacts_root") or ""),
                "session_memory_root": str(runtime_config.get("session_memory_root") or ""),
                "persistence_enabled": bool(runtime_config.get("persistence_enabled")),
                "derived_writes_enabled": bool(runtime_config.get("derived_writes_enabled")),
            },
            "write_failures": write_failures,
            "freshness": (state.get("debug") or {}).get("freshness") or {},
            "artifact_keys": (state.get("debug") or {}).get("artifact_keys") or {},
            "expected_fingerprints": (state.get("debug") or {}).get("expected_fingerprints") or {},
        },
    }

    logger.info(
        "Season orchestrator mode=%s base_ready=%s refresh_plan=%s served_from=%s",
        mode,
        base_ready,
        refresh_plan,
        served_from,
    )
    if write_failures:
        logger.warning(
            "Season orchestrator degraded persistence player_id=%s season=%s failures=%s",
            player_id,
            season,
            write_failures,
        )
    logger.debug("Season orchestrator payload=%s", result)
    return result
