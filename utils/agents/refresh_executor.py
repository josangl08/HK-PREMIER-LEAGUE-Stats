# ABOUTME: Lightweight refresh executor for season-stage derived intelligence artifacts outside the critical render path.
# ABOUTME: Rebuilds stale derived artifacts deterministically, persists them, and returns execution metadata for orchestration and logs.

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping

from utils.agents.orchestration_runtime import collect_fresh_payload_artifacts
from utils.agents.season_agent import build_season_stage_analysis
from utils.agents.signal_agent import curate_signals
from utils.insights.season_signals import build_season_signals
from utils.intelligence.artifact_registry import ArtifactRegistry
from utils.season_stage.season_intelligence import (
    SEASON_ARTIFACT_DEPENDENCIES,
    SEASON_OVERLAY_CANDIDATES_ARTIFACT,
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

DERIVED_SEASON_ARTIFACTS = [
    SEASON_SIGNALS_ARTIFACT,
    SEASON_STAGE_ANALYSIS_ARTIFACT,
    SEASON_OVERLAY_CANDIDATES_ARTIFACT,
]

_DERIVED_EXECUTION_ORDER = [
    SEASON_SIGNALS_ARTIFACT,
    SEASON_STAGE_ANALYSIS_ARTIFACT,
    SEASON_OVERLAY_CANDIDATES_ARTIFACT,
]


def _expand_requested_derived_artifacts(
    requested_artifacts: List[str],
) -> List[str]:
    """Expand requested derived artifacts to include any derived dependencies."""
    expanded = set(
        artifact_type
        for artifact_type in requested_artifacts
        if artifact_type in DERIVED_SEASON_ARTIFACTS
    )

    changed = True
    while changed:
        changed = False
        for artifact_type in list(expanded):
            for dependency in SEASON_ARTIFACT_DEPENDENCIES.get(artifact_type, []):
                if dependency in DERIVED_SEASON_ARTIFACTS and dependency not in expanded:
                    expanded.add(dependency)
                    changed = True

    return [
        artifact_type
        for artifact_type in _DERIVED_EXECUTION_ORDER
        if artifact_type in expanded
    ]


def _persist_runtime_artifact(
    artifact_type: str,
    payload: Dict[str, Any],
    *,
    player_id: str,
    season: str,
    base_payloads: Mapping[str, Mapping[str, Any]],
    dependency_artifacts: Mapping[str, Mapping[str, Any]],
    registry: ArtifactRegistry,
) -> Dict[str, Any]:
    """Persist a derived runtime artifact built during refresh execution."""
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
    stored = registry.put_artifact(record["artifact_key"], record)
    logger.info(
        "Season refresh executor persisted artifact=%s player_id=%s season=%s dependencies=%s",
        artifact_type,
        player_id,
        season,
        sorted(dependency_fingerprint_map),
    )
    return stored


def execute_season_refresh(
    stage_payload: Dict[str, Any],
    *,
    refresh_plan: List[str] | None = None,
    session_state: Mapping[str, Any] | None = None,
    registry: ArtifactRegistry | None = None,
) -> Dict[str, Any]:
    """Rebuild requested season derived artifacts without blocking the main render path."""
    active_registry = registry or ArtifactRegistry()
    state = get_season_intelligence_state(stage_payload, registry=active_registry)
    artifact_states = state.get("artifacts") or {}
    requested_artifacts = list(refresh_plan or state.get("refresh_plan") or [])
    requested_derived = _expand_requested_derived_artifacts(requested_artifacts)
    fresh_artifacts = collect_fresh_payload_artifacts(artifact_states)
    runtime_artifacts = dict(fresh_artifacts)
    player_id = str((state.get("scope") or {}).get("player_id") or "")
    season = str((state.get("scope") or {}).get("season") or "")
    base_payloads = state.get("base_payloads") or {}
    refreshed_artifacts: List[str] = []
    skipped_artifacts: List[str] = []
    failed_artifacts: List[Dict[str, str]] = []

    base_dependencies = [
        dependency
        for dependency in SEASON_ARTIFACT_DEPENDENCIES.get(SEASON_SIGNALS_ARTIFACT, [])
        if dependency not in DERIVED_SEASON_ARTIFACTS
    ]
    base_ready = all(runtime_artifacts.get(artifact_type) for artifact_type in base_dependencies)

    logger.info(
        "Season refresh executor started player_id=%s season=%s requested=%s base_ready=%s",
        player_id,
        season,
        requested_derived,
        base_ready,
    )

    if not requested_derived:
        logger.info(
            "Season refresh executor skipped player_id=%s season=%s reason=no_derived_artifacts_requested",
            player_id,
            season,
        )
        return {
            "executed": False,
            "player_id": player_id,
            "season": season,
            "requested_artifacts": [],
            "refreshed_artifacts": [],
            "skipped_artifacts": [],
            "failed_artifacts": [],
            "base_ready": base_ready,
        }

    if not base_ready:
        logger.info(
            "Season refresh executor skipped player_id=%s season=%s reason=base_artifacts_not_ready",
            player_id,
            season,
        )
        return {
            "executed": False,
            "player_id": player_id,
            "season": season,
            "requested_artifacts": requested_derived,
            "refreshed_artifacts": [],
            "skipped_artifacts": requested_derived,
            "failed_artifacts": [],
            "base_ready": False,
        }

    for artifact_type in requested_derived:
        try:
            if artifact_type == SEASON_SIGNALS_ARTIFACT:
                built_signals = build_season_signals(runtime_artifacts)
                payload = build_season_signals_payload(built_signals)
            elif artifact_type == SEASON_STAGE_ANALYSIS_ARTIFACT:
                if runtime_artifacts.get(SEASON_SIGNALS_ARTIFACT) is None:
                    skipped_artifacts.append(artifact_type)
                    continue
                payload = build_season_stage_analysis_payload(
                    build_season_stage_analysis(runtime_artifacts)
                )
            elif artifact_type == SEASON_OVERLAY_CANDIDATES_ARTIFACT:
                signals_payload = (runtime_artifacts.get(SEASON_SIGNALS_ARTIFACT) or {}).get("payload") or {}
                if not signals_payload.get("signals"):
                    skipped_artifacts.append(artifact_type)
                    continue
                selected_candidate = curate_signals(
                    signals_payload.get("signals") or [],
                    session_state=session_state,
                )
                payload = build_season_overlay_candidates_payload(
                    signals_payload.get("signals") or [],
                    selected_candidate=selected_candidate,
                )
            else:
                skipped_artifacts.append(artifact_type)
                continue

            runtime_artifacts[artifact_type] = _persist_runtime_artifact(
                artifact_type,
                payload,
                player_id=player_id,
                season=season,
                base_payloads=base_payloads,
                dependency_artifacts=runtime_artifacts,
                registry=active_registry,
            )
            refreshed_artifacts.append(artifact_type)
        except Exception as exc:
            logger.exception(
                "Season refresh executor failed artifact=%s player_id=%s season=%s: %s",
                artifact_type,
                player_id,
                season,
                exc,
            )
            failed_artifacts.append(
                {
                    "artifact_type": artifact_type,
                    "error": str(exc),
                }
            )

    logger.info(
        "Season refresh executor completed player_id=%s season=%s refreshed=%s skipped=%s failed=%s",
        player_id,
        season,
        refreshed_artifacts,
        skipped_artifacts,
        [item["artifact_type"] for item in failed_artifacts],
    )
    return {
        "executed": bool(refreshed_artifacts or failed_artifacts),
        "player_id": player_id,
        "season": season,
        "requested_artifacts": requested_derived,
        "refreshed_artifacts": refreshed_artifacts,
        "skipped_artifacts": skipped_artifacts,
        "failed_artifacts": failed_artifacts,
        "base_ready": True,
    }
