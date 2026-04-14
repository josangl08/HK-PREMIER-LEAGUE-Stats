# ABOUTME: Deterministic season-stage signal builder for contextual football insights derived from season artifacts.
# ABOUTME: Produces ranked signal contracts for Worth Noticing curation without requiring LLM calls.

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping

from utils.intelligence.versioning import SIGNAL_RULES_VERSION
from utils.season_stage.season_intelligence import (
    COMPETITION_SPLIT_CONTEXT_ARTIFACT,
    PREVIOUS_SEASON_CONTEXT_ARTIFACT,
    RECENT_FORM_CONTEXT_ARTIFACT,
    SEASON_PERFORMANCE_CONTEXT_ARTIFACT,
    SEASON_PROFILE_CONTEXT_ARTIFACT,
)

logger = logging.getLogger(__name__)

SEASON_STAGE_NAME = "season"
SEASON_SIGNAL_TYPES = {
    "milestone",
    "anomaly",
    "trend",
    "comparison",
    "curiosity",
    "risk",
    "opportunity",
}


def build_signal_contract(
    *,
    signal_id: str,
    signal_type: str,
    priority: float,
    confidence: float,
    title_hint: str,
    body_hint: str | None,
    anchor: str,
    novelty_key: str,
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the canonical deterministic season signal contract."""
    normalized_type = signal_type if signal_type in SEASON_SIGNAL_TYPES else "curiosity"
    return {
        "signal_id": signal_id,
        "stage": SEASON_STAGE_NAME,
        "type": normalized_type,
        "priority": round(float(priority), 3),
        "confidence": round(float(confidence), 3),
        "title_hint": str(title_hint or ""),
        "body_hint": str(body_hint) if body_hint is not None else None,
        "anchor": str(anchor or ""),
        "novelty_key": str(novelty_key or signal_id),
        "evidence": evidence or {},
    }


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


def _pick_top_strength(profile_payload: Mapping[str, Any]) -> Dict[str, Any] | None:
    strengths = profile_payload.get("top_strengths") or []
    if not strengths:
        return None
    return max(strengths, key=lambda item: _safe_float(item.get("percentile")))


def _pick_top_gap(profile_payload: Mapping[str, Any]) -> Dict[str, Any] | None:
    gaps = profile_payload.get("top_gaps") or []
    if not gaps:
        return None
    return min(gaps, key=lambda item: _safe_float(item.get("percentile"), 100.0))


def _build_role_cluster_mismatch_signal(profile_payload: Mapping[str, Any]) -> Dict[str, Any] | None:
    archetype_label = str(profile_payload.get("archetype_label") or "")
    cluster_label = str(profile_payload.get("cluster_archetype_label") or "")
    if not archetype_label or not cluster_label:
        return None
    if archetype_label == cluster_label:
        return None

    clarity_label = str((profile_payload.get("profile_clarity") or {}).get("label") or "")
    confidence = 0.82 if clarity_label in {"Clear profile", "Hybrid profile"} else 0.6
    return build_signal_contract(
        signal_id="role_cluster_mismatch",
        signal_type="anomaly",
        priority=0.93,
        confidence=confidence,
        title_hint="Role signal is pulling in two directions",
        body_hint=(
            f"The positional role read points to {archetype_label}, but the cluster profile is closer to {cluster_label}."
        ),
        anchor=SEASON_PROFILE_CONTEXT_ARTIFACT,
        novelty_key=f"role-cluster-mismatch:{archetype_label}:{cluster_label}",
        evidence={
            "archetype_label": archetype_label,
            "cluster_archetype_label": cluster_label,
            "profile_clarity": clarity_label,
        },
    )


def _build_elite_percentile_signal(profile_payload: Mapping[str, Any], performance_payload: Mapping[str, Any]) -> Dict[str, Any] | None:
    top_strength = _pick_top_strength(profile_payload)
    if top_strength is None:
        return None

    percentile = _safe_float(top_strength.get("percentile"))
    if percentile < 95.0:
        return None

    metric = str(top_strength.get("feature") or top_strength.get("metric") or "a metric")
    pos_group = str(performance_payload.get("pos_group") or profile_payload.get("pos_group") or "this role")
    return build_signal_contract(
        signal_id="elite_percentile_unusual_for_role",
        signal_type="opportunity",
        priority=0.91,
        confidence=0.9,
        title_hint="One metric is landing at an elite level",
        body_hint=f"{metric} is tracking at the {percentile:.0f}th percentile for a {pos_group.lower()}.",
        anchor=SEASON_PROFILE_CONTEXT_ARTIFACT,
        novelty_key=f"elite-percentile:{metric}",
        evidence={
            "metric": metric,
            "percentile": percentile,
            "pos_group": pos_group,
        },
    )


def _build_top_strength_signal(profile_payload: Mapping[str, Any]) -> Dict[str, Any] | None:
    top_strength = _pick_top_strength(profile_payload)
    if top_strength is None:
        return None

    metric = str(top_strength.get("feature") or top_strength.get("metric") or "a metric")
    percentile = _safe_float(top_strength.get("percentile"))
    if percentile < 70.0:
        return None

    return build_signal_contract(
        signal_id="top_strength",
        signal_type="curiosity",
        priority=0.58 + min(0.10, max(0.0, (percentile - 70.0) / 100.0)),
        confidence=0.84,
        title_hint="A clear strength is shaping the season profile",
        body_hint=f"{metric} stands out as the strongest current advantage at the {percentile:.0f}th percentile.",
        anchor=SEASON_PROFILE_CONTEXT_ARTIFACT,
        novelty_key=f"top-strength:{metric}",
        evidence={
            "metric": metric,
            "percentile": percentile,
        },
    )


def _build_top_gap_signal(profile_payload: Mapping[str, Any]) -> Dict[str, Any] | None:
    top_gap = _pick_top_gap(profile_payload)
    if top_gap is None:
        return None

    metric = str(top_gap.get("feature") or top_gap.get("metric") or "a metric")
    percentile = _safe_float(top_gap.get("percentile"), 100.0)
    if percentile > 35.0:
        return None

    return build_signal_contract(
        signal_id="top_gap",
        signal_type="risk",
        priority=0.68 + min(0.08, max(0.0, (35.0 - percentile) / 100.0)),
        confidence=0.86,
        title_hint="One gap is still limiting the season profile",
        body_hint=f"{metric} is sitting around the {percentile:.0f}th percentile and remains the clearest drag on the role profile.",
        anchor=SEASON_PROFILE_CONTEXT_ARTIFACT,
        novelty_key=f"top-gap:{metric}",
        evidence={
            "metric": metric,
            "percentile": percentile,
        },
    )


def _build_previous_season_role_shift_signal(
    profile_payload: Mapping[str, Any],
    performance_payload: Mapping[str, Any],
    previous_payload: Mapping[str, Any],
) -> Dict[str, Any] | None:
    if not previous_payload.get("available"):
        return None

    current_pos_group = str(performance_payload.get("pos_group") or profile_payload.get("pos_group") or "")
    previous_metrics = previous_payload.get("metrics") or {}
    previous_pos_group = str(previous_metrics.get("Position_Group") or "")
    if not previous_pos_group or not current_pos_group or previous_pos_group == current_pos_group:
        return None

    return build_signal_contract(
        signal_id="previous_season_role_shift",
        signal_type="comparison",
        priority=0.83,
        confidence=0.8,
        title_hint="This season is being played from a different role base",
        body_hint=f"The role context has shifted from {previous_pos_group} last season to {current_pos_group} this season.",
        anchor=PREVIOUS_SEASON_CONTEXT_ARTIFACT,
        novelty_key=f"role-shift:{previous_pos_group}:{current_pos_group}",
        evidence={
            "previous_pos_group": previous_pos_group,
            "current_pos_group": current_pos_group,
            "previous_season": previous_payload.get("previous_season"),
        },
    )


def _build_competition_concentration_signal(competition_payload: Mapping[str, Any]) -> Dict[str, Any] | None:
    entries = competition_payload.get("entries") or []
    total_minutes = _safe_int(competition_payload.get("total_minutes"))
    if total_minutes <= 0 or not entries:
        return None

    top_entry = max(entries, key=lambda item: _safe_int(item.get("minutes_played")))
    competition_minutes = _safe_int(top_entry.get("minutes_played"))
    concentration_pct = round((competition_minutes / total_minutes) * 100.0, 2)
    if concentration_pct < 70.0:
        return None

    competition = str(top_entry.get("competition") or "one competition")
    return build_signal_contract(
        signal_id="competition_concentration",
        signal_type="trend",
        priority=0.64 + min(0.08, max(0.0, (concentration_pct - 70.0) / 100.0)),
        confidence=0.83,
        title_hint="Most of the season load is coming from one competition",
        body_hint=f"{competition} accounts for {concentration_pct:.0f}% of the minutes so far.",
        anchor=COMPETITION_SPLIT_CONTEXT_ARTIFACT,
        novelty_key=f"competition-concentration:{competition}",
        evidence={
            "competition": competition,
            "concentration_pct": concentration_pct,
            "minutes_played": competition_minutes,
            "total_minutes": total_minutes,
        },
    )


def _build_recent_form_divergence_signal(
    recent_payload: Mapping[str, Any],
    performance_payload: Mapping[str, Any],
) -> Dict[str, Any] | None:
    comparison = (recent_payload.get("comparisons") or {}).get("last5_vs_previous5") or {}
    if not comparison:
        return None

    trend_pct = _safe_float(comparison.get("goal_contributions_trend_pct"))
    if abs(trend_pct) < 20.0:
        return None

    snapshot = performance_payload.get("snapshot") or {}
    season_contributions = _safe_int(snapshot.get("goals")) + _safe_int(snapshot.get("assists"))
    season_matches = max(_safe_int(snapshot.get("matches_played")), 1)
    season_gc_per_match = season_contributions / season_matches
    last5 = recent_payload.get("last5") or {}
    last5_gc_per_match = _safe_int(last5.get("goal_contributions_total")) / max(_safe_int(last5.get("matches")), 1)
    divergence = round(last5_gc_per_match - season_gc_per_match, 2)
    direction = "up" if trend_pct > 0 else "down"
    signal_type = "trend" if trend_pct > 0 else "risk"

    return build_signal_contract(
        signal_id="recent_form_divergence",
        signal_type=signal_type,
        priority=0.74 + min(0.06, abs(trend_pct) / 250.0),
        confidence=0.81,
        title_hint="Recent form is moving away from the season baseline",
        body_hint=(
            "The last five matches are accelerating above the season baseline."
            if direction == "up"
            else "The last five matches have cooled off relative to the season baseline."
        ),
        anchor=RECENT_FORM_CONTEXT_ARTIFACT,
        novelty_key=f"recent-form-divergence:{direction}",
        evidence={
            "direction": direction,
            "goal_contributions_trend_pct": trend_pct,
            "season_goal_contributions_per_match": round(season_gc_per_match, 2),
            "last5_goal_contributions_per_match": round(last5_gc_per_match, 2),
            "divergence_per_match": divergence,
        },
    )


def build_season_signals(artifacts: Mapping[str, Mapping[str, Any]] | None) -> List[Dict[str, Any]]:
    """Build and rank deterministic season-stage signal candidates from base artifacts only."""
    if not artifacts:
        logger.info("Season signals skipped: no artifacts provided.")
        return []

    profile_payload = (artifacts.get(SEASON_PROFILE_CONTEXT_ARTIFACT) or {}).get("payload") or {}
    performance_payload = (artifacts.get(SEASON_PERFORMANCE_CONTEXT_ARTIFACT) or {}).get("payload") or {}
    competition_payload = (artifacts.get(COMPETITION_SPLIT_CONTEXT_ARTIFACT) or {}).get("payload") or {}
    previous_payload = (artifacts.get(PREVIOUS_SEASON_CONTEXT_ARTIFACT) or {}).get("payload") or {}
    recent_payload = (artifacts.get(RECENT_FORM_CONTEXT_ARTIFACT) or {}).get("payload") or {}

    candidates = [
        _build_role_cluster_mismatch_signal(profile_payload),
        _build_elite_percentile_signal(profile_payload, performance_payload),
        _build_top_strength_signal(profile_payload),
        _build_top_gap_signal(profile_payload),
        _build_previous_season_role_shift_signal(profile_payload, performance_payload, previous_payload),
        _build_competition_concentration_signal(competition_payload),
        _build_recent_form_divergence_signal(recent_payload, performance_payload),
    ]

    signals = [candidate for candidate in candidates if candidate is not None]
    signals.sort(
        key=lambda signal: (
            -_safe_float(signal.get("priority")),
            -_safe_float(signal.get("confidence")),
            str(signal.get("signal_id") or ""),
        )
    )

    logger.info(
        "Season signals built count=%s player_id=%s season=%s rules_version=%s ids=%s",
        len(signals),
        str(performance_payload.get("player_id") or ""),
        str(performance_payload.get("season") or ""),
        SIGNAL_RULES_VERSION,
        [signal["signal_id"] for signal in signals],
    )
    logger.debug(
        "Season signals evidence=%s",
        {
            signal["signal_id"]: signal.get("evidence", {})
            for signal in signals
        },
    )
    return signals
