# ABOUTME: Constrained season-stage agent that summarizes only season artifacts into a primary stage analysis payload.
# ABOUTME: Applies abstention and low-evidence rules so stage analysis stays trustworthy and easy to debug.

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping

from utils.season_stage.season_intelligence import (
    COMPETITION_SPLIT_CONTEXT_ARTIFACT,
    PREVIOUS_SEASON_CONTEXT_ARTIFACT,
    RECENT_FORM_CONTEXT_ARTIFACT,
    SEASON_PERFORMANCE_CONTEXT_ARTIFACT,
    SEASON_PROFILE_CONTEXT_ARTIFACT,
)

logger = logging.getLogger(__name__)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _describe_recent_trend(recent_payload: Mapping[str, Any]) -> Dict[str, str]:
    comparison = (recent_payload.get("comparisons") or {}).get("last5_vs_previous5") or {}
    delta = _safe_float(comparison.get("goal_contributions_trend_pct"))
    if abs(delta) < 15.0:
        return {
            "label": "stable",
            "copy": "Recent form is broadly tracking the season baseline.",
        }
    if delta > 0:
        return {
            "label": "up",
            "copy": "Recent form is running ahead of the wider season baseline.",
        }
    return {
        "label": "down",
        "copy": "Recent form has cooled relative to the wider season baseline.",
    }


def build_season_stage_analysis(artifacts: Mapping[str, Mapping[str, Any]] | None) -> Dict[str, Any]:
    """Build a constrained primary stage-analysis payload from season artifacts only."""
    if not artifacts:
        logger.info("Season agent abstained: no artifacts provided.")
        return {
            "available": False,
            "abstained": True,
            "summary": "",
            "confidence": "low",
            "key_points": [],
            "tensions": [],
            "caveats": ["No season artifacts were available for analysis."],
            "supporting_artifacts": [],
        }

    profile_payload = (artifacts.get(SEASON_PROFILE_CONTEXT_ARTIFACT) or {}).get("payload") or {}
    performance_payload = (artifacts.get(SEASON_PERFORMANCE_CONTEXT_ARTIFACT) or {}).get("payload") or {}
    competition_payload = (artifacts.get(COMPETITION_SPLIT_CONTEXT_ARTIFACT) or {}).get("payload") or {}
    previous_payload = (artifacts.get(PREVIOUS_SEASON_CONTEXT_ARTIFACT) or {}).get("payload") or {}
    recent_payload = (artifacts.get(RECENT_FORM_CONTEXT_ARTIFACT) or {}).get("payload") or {}

    snapshot = performance_payload.get("snapshot") or {}
    matches_played = _safe_int(snapshot.get("matches_played"))
    profile_available = bool(profile_payload.get("available"))
    enough_recent_sample = _safe_int(recent_payload.get("sample_size")) >= 5

    supporting_artifacts = [
        artifact_name
        for artifact_name in (
            SEASON_PROFILE_CONTEXT_ARTIFACT,
            SEASON_PERFORMANCE_CONTEXT_ARTIFACT,
            COMPETITION_SPLIT_CONTEXT_ARTIFACT,
            PREVIOUS_SEASON_CONTEXT_ARTIFACT,
            RECENT_FORM_CONTEXT_ARTIFACT,
        )
        if (artifacts.get(artifact_name) or {}).get("payload")
    ]

    if matches_played < 3 and not profile_available:
        logger.info(
            "Season agent abstained: low evidence player_id=%s season=%s matches=%s profile_available=%s",
            performance_payload.get("player_id"),
            performance_payload.get("season"),
            matches_played,
            profile_available,
        )
        return {
            "available": False,
            "abstained": True,
            "summary": "",
            "confidence": "low",
            "key_points": [],
            "tensions": [],
            "caveats": ["The season sample is still too thin for a stable stage analysis."],
            "supporting_artifacts": supporting_artifacts,
        }

    archetype_label = str(profile_payload.get("archetype_label") or performance_payload.get("pos_group") or "role")
    cluster_label = str(profile_payload.get("cluster_archetype_label") or archetype_label)
    profile_clarity = (profile_payload.get("profile_clarity") or {}).get("label") or "Low-confidence profile"
    top_strengths = profile_payload.get("top_strengths") or []
    top_gaps = profile_payload.get("top_gaps") or []
    primary_strength = dict(top_strengths[0] or {}) if top_strengths else {}
    primary_gap = dict(top_gaps[0] or {}) if top_gaps else {}
    strongest_metric = str(primary_strength.get("feature") or primary_strength.get("metric") or "")
    gap_metric = str(primary_gap.get("feature") or primary_gap.get("metric") or "")
    trend = _describe_recent_trend(recent_payload)

    key_points = []
    if archetype_label:
        key_points.append(f"Role profile is currently reading as {archetype_label}.")
    if strongest_metric:
        key_points.append(f"{strongest_metric} is the clearest positive lever in the season profile.")
    if enough_recent_sample:
        key_points.append(trend["copy"])

    tensions = []
    if cluster_label and cluster_label != archetype_label:
        tensions.append(
            f"Role interpretation and cluster identity are not fully aligned ({archetype_label} vs {cluster_label})."
        )
    if gap_metric:
        tensions.append(f"{gap_metric} remains the clearest limiting factor in the current role profile.")

    caveats = []
    if not enough_recent_sample:
        caveats.append("Recent-form evidence is still limited, so short-term momentum is provisional.")
    if profile_clarity == "Low-confidence profile":
        caveats.append("Profile clarity is low, so role interpretation should be treated cautiously.")

    if matches_played >= 12 and profile_available:
        confidence = "high"
    elif matches_played >= 5:
        confidence = "medium"
    else:
        confidence = "low"

    summary_parts = [f"This season is currently reading as a {archetype_label.lower()} campaign."]
    if strongest_metric:
        summary_parts.append(f"The strongest profile edge is {strongest_metric.lower()}.")
    if tensions:
        summary_parts.append(tensions[0])
    elif enough_recent_sample:
        summary_parts.append(trend["copy"])
    summary = " ".join(summary_parts)

    result = {
        "available": True,
        "abstained": False,
        "summary": summary,
        "confidence": confidence,
        "key_points": key_points[:3],
        "tensions": tensions[:2],
        "caveats": caveats[:2],
        "supporting_artifacts": supporting_artifacts,
    }
    logger.info(
        "Season agent built analysis player_id=%s season=%s confidence=%s abstained=%s",
        performance_payload.get("player_id"),
        performance_payload.get("season"),
        confidence,
        result["abstained"],
    )
    logger.debug("Season agent analysis payload=%s", result)
    return result
