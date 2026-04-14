# ABOUTME: Season-stage intelligence integration surface for artifact contracts, registry lookup, and refresh planning.
# ABOUTME: Defines JSON-safe season artifact payload builders and logs artifact availability for non-blocking intelligence flows.

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Mapping

import pandas as pd

from utils.intelligence.artifact_keys import build_season_artifact_key
from utils.intelligence.artifact_registry import ArtifactRegistry
from utils.intelligence.freshness_manager import (
    FRESHNESS_COLD,
    FRESHNESS_FRESH,
    FRESHNESS_HOT,
    FRESHNESS_WARM,
    apply_evaluated_freshness,
    build_dependency_fingerprint_map,
    build_artifact_fingerprint,
    evaluate_artifact_freshness,
    resolve_freshness_policy,
    serialize_timestamp,
    utc_now,
)
from utils.intelligence.versioning import (
    ARTIFACT_SCHEMA_VERSION,
    PROMPT_TEMPLATE_VERSION,
    ROLE_TAXONOMY_VERSION,
    SIGNAL_RULES_VERSION,
    STAGE_ANALYSIS_LOGIC_VERSION,
    get_intelligence_version_bundle,
)
from utils.season_stage.season_context import build_season_stage_context
from utils.season_stage.season_profile import build_season_profile_context

logger = logging.getLogger(__name__)

SEASON_PROFILE_CONTEXT_ARTIFACT = "season_profile_context"
SEASON_PERFORMANCE_CONTEXT_ARTIFACT = "season_performance_context"
COMPETITION_SPLIT_CONTEXT_ARTIFACT = "competition_split_context"
PREVIOUS_SEASON_CONTEXT_ARTIFACT = "previous_season_context"
RECENT_FORM_CONTEXT_ARTIFACT = "recent_form_context"
SEASON_SIGNALS_ARTIFACT = "season_signals"
SEASON_STAGE_ANALYSIS_ARTIFACT = "season_stage_analysis"
SEASON_OVERLAY_CANDIDATES_ARTIFACT = "season_overlay_candidates"

SEASON_ARTIFACT_TYPES = [
    SEASON_PROFILE_CONTEXT_ARTIFACT,
    SEASON_PERFORMANCE_CONTEXT_ARTIFACT,
    COMPETITION_SPLIT_CONTEXT_ARTIFACT,
    PREVIOUS_SEASON_CONTEXT_ARTIFACT,
    RECENT_FORM_CONTEXT_ARTIFACT,
    SEASON_SIGNALS_ARTIFACT,
    SEASON_STAGE_ANALYSIS_ARTIFACT,
    SEASON_OVERLAY_CANDIDATES_ARTIFACT,
]

SEASON_ARTIFACT_DEPENDENCIES = {
    SEASON_PROFILE_CONTEXT_ARTIFACT: [],
    SEASON_PERFORMANCE_CONTEXT_ARTIFACT: [],
    COMPETITION_SPLIT_CONTEXT_ARTIFACT: [],
    PREVIOUS_SEASON_CONTEXT_ARTIFACT: [],
    RECENT_FORM_CONTEXT_ARTIFACT: [],
    SEASON_SIGNALS_ARTIFACT: [
        SEASON_PROFILE_CONTEXT_ARTIFACT,
        SEASON_PERFORMANCE_CONTEXT_ARTIFACT,
        COMPETITION_SPLIT_CONTEXT_ARTIFACT,
        PREVIOUS_SEASON_CONTEXT_ARTIFACT,
        RECENT_FORM_CONTEXT_ARTIFACT,
    ],
    SEASON_STAGE_ANALYSIS_ARTIFACT: [
        SEASON_PROFILE_CONTEXT_ARTIFACT,
        SEASON_PERFORMANCE_CONTEXT_ARTIFACT,
        COMPETITION_SPLIT_CONTEXT_ARTIFACT,
        PREVIOUS_SEASON_CONTEXT_ARTIFACT,
        RECENT_FORM_CONTEXT_ARTIFACT,
        SEASON_SIGNALS_ARTIFACT,
    ],
    SEASON_OVERLAY_CANDIDATES_ARTIFACT: [
        SEASON_SIGNALS_ARTIFACT,
        SEASON_STAGE_ANALYSIS_ARTIFACT,
    ],
}

SEASON_FRESHNESS_POLICY = {
    SEASON_PROFILE_CONTEXT_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 24},
    SEASON_PERFORMANCE_CONTEXT_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 24},
    COMPETITION_SPLIT_CONTEXT_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 24},
    PREVIOUS_SEASON_CONTEXT_ARTIFACT: {"regime": FRESHNESS_COLD, "ttl_hours": 72},
    RECENT_FORM_CONTEXT_ARTIFACT: {"regime": FRESHNESS_HOT, "ttl_hours": 6},
    SEASON_SIGNALS_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 24},
    SEASON_STAGE_ANALYSIS_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 24},
    SEASON_OVERLAY_CANDIDATES_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 24},
}

"""
Season artifact payload contracts.

Each builder returns a JSON-safe payload so the artifact registry can persist it.

`season_profile_context`
{
  "available": bool,
  "season": str,
  "pos_group": str,
  "player_name": str,
  "player_team": str,
  "archetype_label": str,
  "cluster_archetype_label": str,
  "cluster_id": int | None,
  "profile_clarity": {"label": str, "copy": str},
  "axis_labels": {"x": str, "y": str},
  "quadrant_labels": dict[str, str],
  "player_point": {"x": float, "y": float},
  "feature_cols": list[str],
  "feature_percentiles": list[dict],
  "top_strengths": list[dict],
  "top_gaps": list[dict],
  "nearest_profiles": list[dict],
}

`season_performance_context`
{
  "season": str,
  "player_id": str,
  "player_name": str,
  "pos_group": str,
  "season_team": str,
  "snapshot": dict[str, int | float],
  "season_metrics": dict[str, int | float | str | None],
}

`competition_split_context`
{
  "season": str,
  "player_id": str,
  "entries": list[dict],
  "total_matches": int,
  "total_minutes": int,
}

`previous_season_context`
{
  "available": bool,
  "season": str,
  "previous_season": str,
  "metrics": dict[str, int | float | str | None],
}

`recent_form_context`
{
  "available": bool,
  "sample_size": int,
  "last5": dict,
  "previous5": dict,
  "last10": dict,
  "comparisons": dict,
}

`season_signals`
{
  "signals": list[dict],
  "signal_count": int,
}

`season_stage_analysis`
{
  "summary": str,
  "confidence": str,
  "supporting_artifacts": list[str],
  "analysis": dict,
}

`season_overlay_candidates`
{
  "candidates": list[dict],
  "candidate_count": int,
  "selected_candidate": dict | None,
}
"""


def _safe_scalar(value: Any) -> Any:
    """Convert pandas/numpy scalars into plain JSON-safe values."""
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


def _safe_series_subset(series: pd.Series | None, keys: Iterable[str]) -> Dict[str, Any]:
    """Extract a safe subset from a pandas Series."""
    if series is None:
        return {}
    return {
        key: _safe_scalar(series.get(key))
        for key in keys
        if key in series.index
    }


def _summarize_recent_window(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a compact recent-form summary for a set of matches."""
    minutes_total = sum(int(match.get("minutes_played", 0) or 0) for match in matches)
    goals_total = sum(int(match.get("goals", 0) or 0) for match in matches)
    assists_total = sum(int(match.get("assists", 0) or 0) for match in matches)
    contributions_total = goals_total + assists_total

    return {
        "matches": len(matches),
        "minutes_total": minutes_total,
        "goals_total": goals_total,
        "assists_total": assists_total,
        "goal_contributions_total": contributions_total,
    }


def _compute_window_delta_pct(current_total: float, previous_total: float) -> float:
    """Return a stable percentage delta between windows."""
    if previous_total == 0:
        return 0.0
    return round(((current_total - previous_total) / abs(previous_total)) * 100.0, 2)


def build_recent_form_context_payload(matches: List[Dict[str, Any]] | None) -> Dict[str, Any]:
    """Build the season recent-form artifact payload from match rows."""
    ordered_matches = list(matches or [])[:10]
    last5 = _summarize_recent_window(ordered_matches[:5])
    previous5 = _summarize_recent_window(ordered_matches[5:10])
    last10 = _summarize_recent_window(ordered_matches)
    comparisons: Dict[str, Any] = {}

    if len(ordered_matches[:5]) == 5 and len(ordered_matches[5:10]) == 5:
        comparisons["last5_vs_previous5"] = {
            "matches": 10,
            "minutes_trend_pct": _compute_window_delta_pct(
                last5["minutes_total"],
                previous5["minutes_total"],
            ),
            "goals_trend_pct": _compute_window_delta_pct(
                last5["goals_total"],
                previous5["goals_total"],
            ),
            "assists_trend_pct": _compute_window_delta_pct(
                last5["assists_total"],
                previous5["assists_total"],
            ),
            "goal_contributions_trend_pct": _compute_window_delta_pct(
                last5["goal_contributions_total"],
                previous5["goal_contributions_total"],
            ),
        }

    return {
        "available": bool(ordered_matches),
        "sample_size": len(ordered_matches),
        "last5": last5,
        "previous5": previous5,
        "last10": last10,
        "comparisons": comparisons,
    }


def build_season_profile_context_payload(profile_context: Dict[str, Any]) -> Dict[str, Any]:
    """Strip non-serializable profile internals and keep the contract fields only."""
    return {
        "available": bool(profile_context.get("available")),
        "season": str(profile_context.get("season") or ""),
        "pos_group": str(profile_context.get("pos_group") or ""),
        "player_name": str(profile_context.get("player_name") or ""),
        "player_team": str(profile_context.get("player_team") or ""),
        "archetype_label": str(profile_context.get("archetype_label") or ""),
        "cluster_archetype_label": str(profile_context.get("cluster_archetype_label") or ""),
        "cluster_id": profile_context.get("cluster_id"),
        "profile_clarity": deepcopy(profile_context.get("profile_clarity") or {}),
        "axis_labels": deepcopy(profile_context.get("axis_labels") or {}),
        "quadrant_labels": deepcopy(profile_context.get("quadrant_labels") or {}),
        "player_point": deepcopy(profile_context.get("player_point") or {}),
        "feature_cols": list(profile_context.get("feature_cols") or []),
        "feature_percentiles": deepcopy(profile_context.get("feature_percentiles") or []),
        "top_strengths": deepcopy(profile_context.get("top_strengths") or []),
        "top_gaps": deepcopy(profile_context.get("top_gaps") or []),
        "nearest_profiles": deepcopy(profile_context.get("nearest_profiles") or []),
    }


def build_season_performance_context_payload(context: Dict[str, Any]) -> Dict[str, Any]:
    """Build the compact performance artifact payload from stage context."""
    season_row = context.get("season_row")
    metric_keys = [
        "Matches played",
        "Minutes played",
        "Goals",
        "Assists",
        "xG per 90",
        "xA per 90",
        "Shots per 90",
        "Key passes per 90",
        "Interceptions per 90",
        "Passes per 90",
        "Accurate passes, %",
        "Position_Group",
    ]
    return {
        "season": str(context.get("season") or ""),
        "player_id": str(context.get("player_id") or ""),
        "player_name": str(context.get("player_name") or ""),
        "pos_group": str(context.get("pos_group") or ""),
        "season_team": str(context.get("season_team") or ""),
        "snapshot": _safe_mapping(context.get("snapshot") or {}),
        "season_metrics": _safe_series_subset(season_row, metric_keys),
    }


def build_competition_split_context_payload(context: Dict[str, Any]) -> Dict[str, Any]:
    """Build the competition split artifact payload from stage context."""
    entries = deepcopy(context.get("competition_split") or [])
    return {
        "season": str(context.get("season") or ""),
        "player_id": str(context.get("player_id") or ""),
        "entries": entries,
        "total_matches": sum(int(item.get("matches_played", 0) or 0) for item in entries),
        "total_minutes": sum(int(item.get("minutes_played", 0) or 0) for item in entries),
    }


def build_previous_season_context_payload(context: Dict[str, Any]) -> Dict[str, Any]:
    """Build the previous-season comparison artifact payload from stage context."""
    previous_season = context.get("previous_season") or {}
    previous_row = previous_season.get("row")
    return {
        "available": previous_row is not None,
        "season": str(context.get("season") or ""),
        "previous_season": str(previous_season.get("season") or ""),
        "metrics": _safe_series_subset(
            previous_row,
            [
                "Season",
                "Team",
                "Position_Group",
                "Matches played",
                "Minutes played",
                "Goals",
                "Assists",
                "xG per 90",
                "xA per 90",
            ],
        ),
    }


def build_season_signals_payload(signals: List[Dict[str, Any]] | None) -> Dict[str, Any]:
    """Build the signal artifact payload."""
    safe_signals = deepcopy(signals or [])
    return {
        "signals": safe_signals,
        "signal_count": len(safe_signals),
    }


def build_season_stage_analysis_payload(analysis: Dict[str, Any] | None) -> Dict[str, Any]:
    """Build the season-stage analysis artifact payload."""
    analysis = deepcopy(analysis or {})
    return {
        "summary": str(analysis.get("summary") or ""),
        "confidence": str(analysis.get("confidence") or ""),
        "supporting_artifacts": list(analysis.get("supporting_artifacts") or []),
        "analysis": analysis,
    }


def build_season_overlay_candidates_payload(
    candidates: List[Dict[str, Any]] | None,
    *,
    selected_candidate: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build the overlay-candidate artifact payload."""
    safe_candidates = deepcopy(candidates or [])
    safe_selected = deepcopy(selected_candidate) if selected_candidate else None
    return {
        "candidates": safe_candidates,
        "candidate_count": len(safe_candidates),
        "selected_candidate": safe_selected,
    }


def build_season_artifact_scope(player_id: str, season: str) -> Dict[str, str]:
    """Return the canonical season artifact scope."""
    return {
        "player_id": str(player_id or ""),
        "season": str(season or ""),
        "stage": "season",
    }


def build_season_artifact_payloads(context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build JSON-safe deterministic payloads for the season base artifacts."""
    profile_context = build_season_profile_context(
        context.get("season_df"),
        str(context.get("player_name") or ""),
        str(context.get("pos_group") or "Midfielder"),
        str(context.get("season") or ""),
    )
    return {
        SEASON_PROFILE_CONTEXT_ARTIFACT: build_season_profile_context_payload(profile_context),
        SEASON_PERFORMANCE_CONTEXT_ARTIFACT: build_season_performance_context_payload(context),
        COMPETITION_SPLIT_CONTEXT_ARTIFACT: build_competition_split_context_payload(context),
        PREVIOUS_SEASON_CONTEXT_ARTIFACT: build_previous_season_context_payload(context),
        RECENT_FORM_CONTEXT_ARTIFACT: build_recent_form_context_payload(context.get("matches") or []),
    }


def build_season_source_checksum(payload: Mapping[str, Any] | None) -> str:
    """Build a deterministic checksum for the season source payload."""
    return build_artifact_fingerprint(payload or {})


def build_relevant_season_source_checksum(
    artifact_type: str,
    base_payloads: Mapping[str, Mapping[str, Any]],
) -> str:
    """Build the source checksum relevant to a given season artifact type."""
    if artifact_type in base_payloads:
        return build_season_source_checksum(base_payloads.get(artifact_type) or {})
    return build_season_source_checksum(base_payloads)


def get_season_freshness_policy(artifact_type: str) -> Dict[str, Any]:
    """Return the hot/warm/cold freshness policy for a season artifact."""
    return resolve_freshness_policy(artifact_type, SEASON_FRESHNESS_POLICY)


def build_season_artifact_fingerprint_inputs(
    artifact_type: str,
    *,
    player_id: str,
    season: str,
    source_checksum: str,
    dependency_fingerprint_map: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """Build the canonical season fingerprint inputs for a given artifact type."""
    policy = get_season_freshness_policy(artifact_type)
    version_bundle = get_intelligence_version_bundle()
    inputs = {
        "artifact_type": artifact_type,
        "player_id": str(player_id or ""),
        "season": str(season or ""),
        "stage": "season",
        "source_checksum": source_checksum,
        "taxonomy_version": ROLE_TAXONOMY_VERSION,
        "signal_version": SIGNAL_RULES_VERSION,
        "prompt_version": PROMPT_TEMPLATE_VERSION,
        "stage_analysis_version": STAGE_ANALYSIS_LOGIC_VERSION,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "regime": policy["regime"],
        "ttl_hours": policy["ttl_hours"],
        "version_bundle": version_bundle,
    }
    if dependency_fingerprint_map:
        inputs["dependency_fingerprints"] = dict(sorted(dependency_fingerprint_map.items()))
    return inputs


def build_season_artifact_record(
    artifact_type: str,
    payload: Dict[str, Any],
    *,
    player_id: str,
    season: str,
    fingerprint_inputs: Dict[str, Any] | None = None,
    dependencies: List[str] | None = None,
    dependency_fingerprint_map: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """Build a persisted artifact envelope for a season artifact type."""
    scope = build_season_artifact_scope(player_id, season)
    policy = get_season_freshness_policy(artifact_type)
    dependency_fingerprint_map = dict(dependency_fingerprint_map or {})
    resolved_fingerprint_inputs = fingerprint_inputs or build_season_artifact_fingerprint_inputs(
        artifact_type,
        player_id=player_id,
        season=season,
        source_checksum=build_season_source_checksum(payload),
        dependency_fingerprint_map=dependency_fingerprint_map,
    )
    fingerprint = build_artifact_fingerprint(resolved_fingerprint_inputs)
    artifact_key = build_season_artifact_key(
        artifact_type,
        player_id=player_id,
        season=season,
    )
    current_time = utc_now()
    ttl_hours = int(policy["ttl_hours"])
    expires_at = current_time + pd.Timedelta(hours=ttl_hours)
    return {
        "artifact_key": artifact_key,
        "artifact_type": artifact_type,
        "scope": scope,
        "version": ARTIFACT_SCHEMA_VERSION,
        "computed_at": serialize_timestamp(current_time),
        "expires_at": serialize_timestamp(expires_at.to_pydatetime() if hasattr(expires_at, "to_pydatetime") else expires_at),
        "freshness_status": FRESHNESS_FRESH,
        "fingerprint": fingerprint,
        "dependencies": list(dependencies or SEASON_ARTIFACT_DEPENDENCIES.get(artifact_type, [])),
        "dependency_fingerprints": dependency_fingerprint_map,
        "freshness_policy": policy,
        "payload": deepcopy(payload),
    }


def persist_base_season_artifact(
    artifact_type: str,
    payload: Dict[str, Any],
    *,
    player_id: str,
    season: str,
    base_payloads: Mapping[str, Mapping[str, Any]],
    registry: ArtifactRegistry,
) -> Dict[str, Any]:
    """Persist a deterministic base season artifact using the current freshness policy."""
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
        ),
    )
    stored = registry.put_artifact(record["artifact_key"], record)
    logger.info(
        "Season intelligence persisted base artifact=%s player_id=%s season=%s",
        artifact_type,
        player_id,
        season,
    )
    return stored


def get_season_intelligence_state(
    stage_payload: Dict[str, Any],
    *,
    registry: ArtifactRegistry | None = None,
) -> Dict[str, Any]:
    """Load season artifacts from the registry and decide which ones need refresh."""
    context = build_season_stage_context(stage_payload)
    player_id = str(context.get("player_id") or "")
    season = str(context.get("season") or "")
    scope = build_season_artifact_scope(player_id, season)
    registry = registry or ArtifactRegistry()

    base_payloads = build_season_artifact_payloads(context)
    artifact_states: Dict[str, Any] = {}
    refresh_plan: List[str] = []
    persisted_base_artifacts: List[str] = []

    for artifact_type in SEASON_ARTIFACT_TYPES:
        artifact_key = build_season_artifact_key(
            artifact_type,
            player_id=player_id,
            season=season,
        )
        dependency_artifacts = {
            dependency: apply_evaluated_freshness(
                artifact_states[dependency]["artifact"],
                artifact_states[dependency]["freshness"]["status"],
            )
            for dependency in SEASON_ARTIFACT_DEPENDENCIES.get(artifact_type, [])
            if dependency in artifact_states
        }
        dependency_fingerprint_map = build_dependency_fingerprint_map(
            {
                dependency: artifact_states[dependency]["artifact"]
                for dependency in SEASON_ARTIFACT_DEPENDENCIES.get(artifact_type, [])
                if dependency in artifact_states
            }
        )
        expected_fingerprint = build_artifact_fingerprint(
            build_season_artifact_fingerprint_inputs(
                artifact_type,
                player_id=player_id,
                season=season,
                source_checksum=build_relevant_season_source_checksum(artifact_type, base_payloads),
                dependency_fingerprint_map=dependency_fingerprint_map,
            )
        )
        stored_artifact = registry.get_artifact(artifact_key)
        freshness = evaluate_artifact_freshness(
            stored_artifact,
            expected_fingerprint=expected_fingerprint,
            dependency_artifacts=dependency_artifacts.values(),
            dependency_fingerprint_map=dependency_fingerprint_map,
        )

        if artifact_type in base_payloads and freshness["status"] != FRESHNESS_FRESH:
            stored_artifact = persist_base_season_artifact(
                artifact_type,
                deepcopy(base_payloads[artifact_type]),
                player_id=player_id,
                season=season,
                base_payloads=base_payloads,
                registry=registry,
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
            "freshness_policy": get_season_freshness_policy(artifact_type),
            "expected_fingerprint": expected_fingerprint,
            "payload_contract": deepcopy(base_payloads.get(artifact_type)),
        }

    logger.info(
        "Season intelligence state player_id=%s season=%s fresh=%s refresh=%s",
        player_id or "unknown",
        season or "unknown",
        sorted(
            artifact_type
            for artifact_type, state in artifact_states.items()
            if state["freshness"]["status"] == FRESHNESS_FRESH
        ),
        refresh_plan,
    )
    logger.debug(
        "Season intelligence artifact details scope=%s statuses=%s",
        scope,
        {
            artifact_type: state["freshness"]
            for artifact_type, state in artifact_states.items()
        },
    )

    return {
        "scope": scope,
        "context": context,
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
