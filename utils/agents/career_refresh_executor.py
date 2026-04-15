# ABOUTME: Lightweight refresh executor for career-stage derived intelligence artifacts outside the critical render path.
# ABOUTME: Rebuilds stale derived career artifacts deterministically, persists them, and returns execution metadata for orchestration and logs.

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping

from utils.agents.career_intelligence_orchestrator import get_career_intelligence_state
from utils.agents.career_signal_agent import curate_career_signals
from utils.agents.orchestration_runtime import collect_fresh_payload_artifacts
from utils.agents.stage_agents.career_agent import CareerStageAgent
from utils.insights.career_signals import build_career_signals, build_career_signals_payload
from utils.intelligence.artifact_registry import ArtifactRegistry
from utils.intelligence.discovery_contracts import serialize_stage_analysis
from utils.intelligence.runtime_config import get_intelligence_runtime_config
from utils.intelligence.session_memory import get_career_session_memory
from utils.career_stage.career_intelligence import (
    CAREER_ARTIFACT_DEPENDENCIES,
    CAREER_OVERLAY_CANDIDATES_ARTIFACT,
    CAREER_SIGNALS_ARTIFACT,
    CAREER_STAGE_ANALYSIS_ARTIFACT,
    _build_curated_career_overlay_payload,
    _career_source_checksum,
    _persist_runtime_career_artifact,
    _persist_runtime_career_stage_analysis,
)

logger = logging.getLogger(__name__)

DERIVED_CAREER_ARTIFACTS = [
    CAREER_SIGNALS_ARTIFACT,
    CAREER_STAGE_ANALYSIS_ARTIFACT,
    CAREER_OVERLAY_CANDIDATES_ARTIFACT,
]

_DERIVED_EXECUTION_ORDER = [
    CAREER_SIGNALS_ARTIFACT,
    CAREER_STAGE_ANALYSIS_ARTIFACT,
    CAREER_OVERLAY_CANDIDATES_ARTIFACT,
]


def _expand_requested_derived_artifacts(
    requested_artifacts: List[str],
) -> List[str]:
    """Expand requested derived artifacts to include any derived dependencies."""
    expanded = {
        artifact_type
        for artifact_type in requested_artifacts
        if artifact_type in DERIVED_CAREER_ARTIFACTS
    }

    changed = True
    while changed:
        changed = False
        for artifact_type in list(expanded):
            for dependency in CAREER_ARTIFACT_DEPENDENCIES.get(artifact_type, []):
                if dependency in DERIVED_CAREER_ARTIFACTS and dependency not in expanded:
                    expanded.add(dependency)
                    changed = True

    return [
        artifact_type
        for artifact_type in _DERIVED_EXECUTION_ORDER
        if artifact_type in expanded
    ]


def execute_career_refresh(
    stage_payload: Dict[str, Any],
    *,
    refresh_plan: List[str] | None = None,
    session_state: Mapping[str, Any] | None = None,
    registry: ArtifactRegistry | None = None,
) -> Dict[str, Any]:
    """Rebuild requested career derived artifacts without blocking the main render path."""
    active_registry = registry or ArtifactRegistry()
    runtime_config = get_intelligence_runtime_config()
    state = get_career_intelligence_state(stage_payload, registry=active_registry)
    artifact_states = state.get("artifacts") or {}
    requested_artifacts = list(refresh_plan or state.get("refresh_plan") or [])
    requested_derived = _expand_requested_derived_artifacts(requested_artifacts)
    fresh_artifacts = collect_fresh_payload_artifacts(artifact_states)
    runtime_artifacts = dict(fresh_artifacts)
    player_id = str((state.get("scope") or {}).get("player_id") or "")
    base_payloads = state.get("base_payloads") or {}
    refreshed_artifacts: List[str] = []
    skipped_artifacts: List[str] = []
    failed_artifacts: List[Dict[str, str]] = []
    session_memory = dict(
        (session_state or {}).get("session_memory")
        or get_career_session_memory(player_id=player_id)
        or {}
    )

    base_dependencies = [
        dependency
        for dependency in CAREER_ARTIFACT_DEPENDENCIES.get(CAREER_SIGNALS_ARTIFACT, [])
        if dependency not in DERIVED_CAREER_ARTIFACTS
    ]
    base_ready = all(runtime_artifacts.get(artifact_type) for artifact_type in base_dependencies)

    logger.info(
        "Career refresh executor started player_id=%s requested=%s base_ready=%s",
        player_id,
        requested_derived,
        base_ready,
    )

    if not requested_derived:
        logger.info(
            "Career refresh executor skipped player_id=%s reason=no_derived_artifacts_requested",
            player_id,
        )
        return {
            "executed": False,
            "player_id": player_id,
            "requested_artifacts": [],
            "refreshed_artifacts": [],
            "skipped_artifacts": [],
            "failed_artifacts": [],
            "base_ready": base_ready,
        }

    if not base_ready:
        logger.info(
            "Career refresh executor skipped player_id=%s reason=base_artifacts_not_ready",
            player_id,
        )
        return {
            "executed": False,
            "player_id": player_id,
            "requested_artifacts": requested_derived,
            "refreshed_artifacts": [],
            "skipped_artifacts": requested_derived,
            "failed_artifacts": [],
            "base_ready": False,
        }

    for artifact_type in requested_derived:
        try:
            if artifact_type == CAREER_SIGNALS_ARTIFACT:
                built_signals = build_career_signals(runtime_artifacts)
                payload = build_career_signals_payload(built_signals)
                persisted = _persist_runtime_career_artifact(
                    CAREER_SIGNALS_ARTIFACT,
                    payload,
                    player_id=player_id,
                    base_payloads=base_payloads,
                    dependency_artifacts=runtime_artifacts,
                    registry=active_registry,
                    runtime_config=runtime_config,
                )
            elif artifact_type == CAREER_STAGE_ANALYSIS_ARTIFACT:
                analysis = CareerStageAgent().analyze(
                    scope={"player_id": player_id, "stage": "career"},
                    artifacts=runtime_artifacts,
                    session_memory=session_memory,
                )
                payload = serialize_stage_analysis(analysis)
                persisted = _persist_runtime_career_stage_analysis(
                    payload,
                    player_id=player_id,
                    source_checksum=_career_source_checksum(base_payloads),
                    llm_enabled=bool(runtime_config.get("career_agent_llm_enabled")),
                    model_profile=str(runtime_config.get("career_agent_model_profile") or "flash"),
                    registry=active_registry,
                    runtime_config=runtime_config,
                )
            elif artifact_type == CAREER_OVERLAY_CANDIDATES_ARTIFACT:
                signals_payload = (runtime_artifacts.get(CAREER_SIGNALS_ARTIFACT) or {}).get("payload") or {}
                if not signals_payload.get("signals"):
                    skipped_artifacts.append(artifact_type)
                    continue
                curation_result = curate_career_signals(
                    signals_payload.get("signals") or [],
                    session_memory=session_memory,
                )
                payload = _build_curated_career_overlay_payload(
                    signals_payload.get("signals") or [],
                    selected_candidate=(curation_result.get("candidate") or None),
                )
                persisted = _persist_runtime_career_artifact(
                    CAREER_OVERLAY_CANDIDATES_ARTIFACT,
                    payload,
                    player_id=player_id,
                    base_payloads=base_payloads,
                    dependency_artifacts=runtime_artifacts,
                    registry=active_registry,
                    runtime_config=runtime_config,
                )
            else:
                skipped_artifacts.append(artifact_type)
                continue

            runtime_artifacts[artifact_type] = persisted["artifact"]
            refreshed_artifacts.append(artifact_type)
        except Exception as exc:
            logger.exception(
                "Career refresh executor failed artifact=%s player_id=%s: %s",
                artifact_type,
                player_id,
                exc,
            )
            failed_artifacts.append(
                {
                    "artifact_type": artifact_type,
                    "error": str(exc),
                }
            )

    logger.info(
        "Career refresh executor completed player_id=%s refreshed=%s skipped=%s failed=%s",
        player_id,
        refreshed_artifacts,
        skipped_artifacts,
        [item["artifact_type"] for item in failed_artifacts],
    )
    return {
        "executed": bool(refreshed_artifacts or failed_artifacts),
        "player_id": player_id,
        "requested_artifacts": requested_derived,
        "refreshed_artifacts": refreshed_artifacts,
        "skipped_artifacts": skipped_artifacts,
        "failed_artifacts": failed_artifacts,
        "base_ready": base_ready,
    }
