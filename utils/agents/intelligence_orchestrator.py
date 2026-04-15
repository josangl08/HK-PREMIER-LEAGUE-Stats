# ABOUTME: Non-blocking orchestrator for season-stage intelligence using fresh artifacts first and background refresh planning second.
# ABOUTME: Coordinates registry freshness, deterministic signal generation, specialist agents, and UI-ready debug metadata.

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping

from utils.agents.orchestration_runtime import (
    collect_fresh_payload_artifacts,
    is_fresh_artifact_state,
    sync_session_memory_with_graceful_failure,
)
from utils.agents.season_agent import build_season_stage_analysis
from utils.agents.signal_agent import curate_signals
from utils.agents.stage_agents.season_agent import SeasonStageAgent
from utils.insights.season_signals import build_season_signals
from utils.intelligence.artifact_registry import ArtifactRegistry
from utils.intelligence.discovery_contracts import coerce_stage_analysis, serialize_stage_analysis
from utils.intelligence.discovery_overlay_mapper import build_overlay_candidates_from_analysis
from utils.intelligence.runtime_config import get_intelligence_runtime_config
from utils.intelligence.reevaluation_policy import decide_stage_reevaluation
from utils.intelligence.session_memory import (
    get_season_session_memory,
    put_season_session_memory,
)
from utils.intelligence.overlay_surface import resolve_stage_overlay_surface
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
    get_season_intelligence_state,
)
from utils.intelligence.stage_orchestrator import build_stage_runtime_result

logger = logging.getLogger(__name__)

_BASE_SEASON_ARTIFACTS = [
    SEASON_PROFILE_CONTEXT_ARTIFACT,
    "season_performance_context",
    "competition_split_context",
    "previous_season_context",
    RECENT_FORM_CONTEXT_ARTIFACT,
]


def _is_viable_season_overlay_candidate(candidate: Mapping[str, Any] | None) -> bool:
    """Return whether a season overlay candidate is usable for UI and session memory."""
    candidate = candidate or {}
    title = str(candidate.get("title") or "").strip()
    body = str(candidate.get("body") or "").strip()
    signal_id = str(candidate.get("signal_id") or "").strip()

    if not signal_id:
        return False
    if title.lower() == "stage intelligence":
        return False
    if not title and not body:
        return False
    return True


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
    return sync_session_memory_with_graceful_failure(
        persist_fn=lambda: _build_updated_session_memory(
            player_id=player_id,
            season=season,
            current_candidate=current_candidate,
            existing_memory=existing_memory,
        ),
        logger=logger,
        log_message="Season session memory persistence failed player_id=%s season=%s signal_id=%s: %s",
        log_args=(
            player_id,
            season,
            str((current_candidate or {}).get("signal_id") or ""),
        ),
        existing_memory=existing_memory,
    )


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
    fresh_artifacts = collect_fresh_payload_artifacts(artifact_states)
    runtime_artifacts = dict(fresh_artifacts)
    persisted_artifacts: List[str] = []
    player_id = str((state.get("scope") or {}).get("player_id") or "")
    season = str((state.get("scope") or {}).get("season") or "")
    base_payloads = state.get("base_payloads") or {}
    base_ready = all(artifact_type in fresh_artifacts for artifact_type in _BASE_SEASON_ARTIFACTS)
    session_memory = get_season_session_memory(player_id=player_id, season=season) or {}
    persisted_session_memory = False
    write_failures: List[Dict[str, str]] = []
    current_memory_candidate = dict(session_memory.get("current_candidate") or {})
    if current_memory_candidate and not _is_viable_season_overlay_candidate(current_memory_candidate):
        memory_result = _sync_session_memory(
            player_id=player_id,
            season=season,
            current_candidate=None,
            existing_memory=session_memory,
        )
        session_memory = memory_result["memory"]
        persisted_session_memory = memory_result["persisted"]
        if memory_result["failure"]:
            write_failures.append({"target": "session_memory", "error": memory_result["failure"]})
        logger.info(
            "Season session memory cleared stale candidate player_id=%s season=%s signal_id=%s",
            player_id,
            season,
            str(current_memory_candidate.get("signal_id") or ""),
        )
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
    llm_enabled = bool(runtime_config.get("season_agent_llm_enabled", False))
    stored_analysis = (artifact_states.get(SEASON_STAGE_ANALYSIS_ARTIFACT) or {}).get("artifact")
    stored_analysis_payload = dict((stored_analysis or {}).get("payload") or {})
    stored_analysis_source = str(((stored_analysis_payload.get("debug") or {}).get("analysis_source")) or "artifact")
    reevaluation = decide_stage_reevaluation(
        stage_name="season",
        artifact_states=artifact_states,
        primary_artifact_type=SEASON_STAGE_ANALYSIS_ARTIFACT,
        dependency_fingerprints={},
        refresh_plan=refresh_plan,
        trigger_context={
            "season_context_changed": bool(
                set(refresh_plan)
                & {
                    SEASON_PROFILE_CONTEXT_ARTIFACT,
                    "season_performance_context",
                    "competition_split_context",
                    "previous_season_context",
                    RECENT_FORM_CONTEXT_ARTIFACT,
                    SEASON_STAGE_ANALYSIS_ARTIFACT,
                }
            ),
            "new_match_available": bool(
                set(refresh_plan) & {"season_performance_context", RECENT_FORM_CONTEXT_ARTIFACT}
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
                    SEASON_SIGNALS_ARTIFACT,
                    SEASON_STAGE_ANALYSIS_ARTIFACT,
                    SEASON_OVERLAY_CANDIDATES_ARTIFACT,
                ]
            )
        )

    stage_analysis_payload = None
    shared_stage_analysis = None
    signals_payload = None
    overlay_payload = None
    overlay_surface = {
        "stage": "season",
        "candidates": [],
        "candidate_count": 0,
        "primary_candidate": None,
        "visible_primary": None,
        "deferred_candidates": [],
        "inbox_entries": [],
    }
    worth_noticing = None
    served_from = {
        "analysis": "fallback",
        "signals": "fallback",
        "overlay": "fallback",
    }

    stored_signals = (artifact_states.get(SEASON_SIGNALS_ARTIFACT) or {}).get("artifact")
    if is_fresh_artifact_state(artifact_states.get(SEASON_SIGNALS_ARTIFACT)) and stored_signals:
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

    if (
        not reevaluation.should_reevaluate
        and is_fresh_artifact_state(artifact_states.get(SEASON_STAGE_ANALYSIS_ARTIFACT))
        and stored_analysis
    ):
        stage_analysis_payload = dict((stored_analysis.get("payload") or {}))
        coerced_analysis = coerce_stage_analysis(stage_analysis_payload)
        if coerced_analysis is not None:
            shared_stage_analysis = serialize_stage_analysis(coerced_analysis)
        served_from["analysis"] = "artifact"
    elif base_ready:
        shared_stage_analysis = serialize_stage_analysis(
            SeasonStageAgent().analyze(
                scope={"player_id": player_id, "season": season, "stage": "season"},
                artifacts=runtime_artifacts,
                session_memory=session_memory,
            )
        )
        persisted_analysis = _persist_runtime_artifact(
            SEASON_STAGE_ANALYSIS_ARTIFACT,
            shared_stage_analysis,
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
    if shared_stage_analysis is not None:
        shared_overlay_payload = build_overlay_candidates_from_analysis(shared_stage_analysis)
        shared_overlay_surface = resolve_stage_overlay_surface("season", shared_overlay_payload)
        shared_primary_candidate = shared_overlay_surface.get("primary_candidate")
        if _is_viable_season_overlay_candidate(shared_primary_candidate):
            overlay_payload = shared_overlay_payload
            overlay_surface = shared_overlay_surface
            worth_noticing = shared_primary_candidate
            served_from["overlay"] = "artifact" if served_from["analysis"] == "artifact" else "inline"
            if not (
                is_fresh_artifact_state(artifact_states.get(SEASON_OVERLAY_CANDIDATES_ARTIFACT))
                and stored_overlay
            ):
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
            memory_result = _sync_session_memory(
                player_id=player_id,
                season=season,
                current_candidate=worth_noticing,
                existing_memory=session_memory,
            )
            session_memory = memory_result["memory"]
            persisted_session_memory = memory_result["persisted"]
            if memory_result["failure"]:
                write_failures.append({"target": "session_memory", "error": memory_result["failure"]})

    if (
        worth_noticing is None
        and is_fresh_artifact_state(artifact_states.get(SEASON_OVERLAY_CANDIDATES_ARTIFACT))
        and stored_overlay
    ):
        overlay_payload = dict((stored_overlay.get("payload") or {}))
        overlay_surface = resolve_stage_overlay_surface("season", overlay_payload)
        worth_noticing = overlay_surface.get("primary_candidate")
        if _is_viable_season_overlay_candidate(worth_noticing):
            served_from["overlay"] = "artifact"
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
        else:
            worth_noticing = None
            overlay_surface["primary_candidate"] = None
            overlay_surface["visible_primary"] = None
            logger.info(
                "Season orchestrator ignored stale overlay candidate player_id=%s season=%s",
                player_id,
                season,
            )
            if signals_payload and (signals_payload.get("signals") or []):
                rebuilt_candidate = curate_signals(
                    signals_payload.get("signals") or [],
                    session_state=session_state,
                    session_memory=session_memory,
                )
                overlay_payload = build_season_overlay_candidates_payload(
                    signals_payload.get("signals") or [],
                    selected_candidate=rebuilt_candidate,
                )
                overlay_surface = resolve_stage_overlay_surface("season", overlay_payload)
                worth_noticing = overlay_surface.get("primary_candidate")
                if _is_viable_season_overlay_candidate(worth_noticing):
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
                    served_from["overlay"] = "inline"
                    memory_result = _sync_session_memory(
                        player_id=player_id,
                        season=season,
                        current_candidate=worth_noticing,
                        existing_memory=session_memory,
                    )
                    session_memory = memory_result["memory"]
                    persisted_session_memory = memory_result["persisted"]
                    if memory_result["failure"]:
                        write_failures.append({"target": "session_memory", "error": memory_result["failure"]})
    elif worth_noticing is None and signals_payload and (signals_payload.get("signals") or []):
        next_candidate = curate_signals(
            signals_payload.get("signals") or [],
            session_state=session_state,
            session_memory=session_memory,
        )
        current_candidate = dict(session_memory.get("current_candidate") or {})
        if current_candidate and not _is_viable_season_overlay_candidate(current_candidate):
            current_candidate = {}
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
        overlay_surface = resolve_stage_overlay_surface("season", overlay_payload)
        worth_noticing = overlay_surface.get("primary_candidate")
        if not _is_viable_season_overlay_candidate(worth_noticing):
            worth_noticing = None
            overlay_surface["primary_candidate"] = None
            overlay_surface["visible_primary"] = None
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

    if shared_stage_analysis is None and base_ready:
        shared_stage_analysis = serialize_stage_analysis(
            SeasonStageAgent().analyze(
                scope={"player_id": player_id, "season": season, "stage": "season"},
                artifacts=runtime_artifacts,
                session_memory=session_memory,
            )
        )
    if not stage_analysis_payload and base_ready:
        fallback_analysis_payload = build_season_stage_analysis(runtime_artifacts)
        if fallback_analysis_payload and fallback_analysis_payload.get("available"):
            stage_analysis_payload = fallback_analysis_payload

    result = build_stage_runtime_result(
        stage_name="season",
        state=state,
        runtime_config=runtime_config,
        stage_analysis=stage_analysis_payload,
        shared_stage_analysis=shared_stage_analysis,
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
    result["worth_noticing"] = worth_noticing

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
