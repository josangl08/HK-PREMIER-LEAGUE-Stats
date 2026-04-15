# ABOUTME: Pure utility for career intelligence: phase detection, signal classification, and overlay tier assignment.
# ABOUTME: No Dash or Flask imports — fully testable in isolation. Used by player_portal callbacks as a service layer.

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from utils.ai_services.evidence_router import (
    EVIDENCE_DESTINATIONS,
    get_evidence_destination_meta,
    normalize_evidence_key,
)


# ──────────────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class OverlaySignal:
    tier: int          # 1 = Critical, 2 = Contextual
    title: str
    body: str
    cta_label: str
    urgency: float     # 0.0 – 1.0; higher = more urgent
    evidence_key: str = ""


@dataclass
class DashboardInsightItem:
    title: str
    body: str
    support: str
    evidence_key: str
    focus_metric: str = ""
    llm_generated: bool = False
    source_model: str = ""
    emphasis: str = "neutral"
    badge_value: str = ""
    badge_label: str = ""
    secondary_value: str = ""
    secondary_label: str = ""


@dataclass
class CareerDashboardBrief:
    career_thesis: Dict[str, Any]
    signals: List[DashboardInsightItem]
    levers: List[DashboardInsightItem]
    outlook: Dict[str, Any]


@dataclass(frozen=True)
class CareerProgressionFeatures:
    age: int
    position_group: str
    peak_range: Tuple[int, int]
    base_phase: str
    base_momentum: int
    minutes_trend_pct: float
    primary_metric: str
    primary_metric_trend_pct: float
    secondary_metric: str
    secondary_metric_trend_pct: float
    attacking_output_trend_pct: float
    consistency_level: str
    consistency_cv: float
    coach_confidence_label: str
    coach_confidence_direction: str
    coach_confidence_delta_pct: float
    transfer_window_quality: str
    late_peak_candidate: bool
    recent_minutes_delta_pct: float
    recent_goal_contributions_delta_pct: float
    recent_sample_size: int
    season_count: int
    latest_minutes: int
    latest_primary_metric: float
    evidence_flags: List[str]
    recent_metric_label: str = ""
    recent_metric_delta_pct: float = 0.0


@dataclass(frozen=True)
class CareerProgressionResolution:
    base_phase: str
    resolved_phase: str
    base_momentum: int
    resolved_momentum: int
    recommended_phase: str = "Find Consistency"
    ai_used: bool = False
    ai_model: str = ""
    adjustment_applied: bool = False
    adjustment_reason: str = ""
    validation_status: str = "reject"
    alignment_score: float = 0.55
    blocking_rules: List[str] = None
    context_patterns: List[str] = None
    confidence: str = "medium"
    supporting_factors: List[str] = None
    blockers: List[str] = None
    risk_flags: List[str] = None
    next_condition: str = ""
    contradictions: List[str] = None


@dataclass(frozen=True)
class ComparativeDimension:
    key: str
    label: str
    sample_size: int
    player_value: float
    average_value: float
    top_tier_value: float
    percentile: float
    average_gap: float
    top_tier_gap: float
    status: str
    available: bool = True


@dataclass(frozen=True)
class CareerComparativeScorecard:
    team_positional: ComparativeDimension
    team_overall: ComparativeDimension
    league_positional: ComparativeDimension
    league_overall: ComparativeDimension
    role_security: float
    consistency_score: float
    consistency_label: str
    team_context_score: float
    team_context_label: str
    career_timing_score: float
    career_timing_label: str
    top_tier_gap_score: float


@dataclass(frozen=True)
class CareerDecisionAudit:
    final_phase: str
    deterministic_phase: str
    validation_status: str
    alignment_score: float
    confidence: str
    main_drivers: List[str]
    blockers: List[str]
    risk_flags: List[str]
    next_condition: str
    blocking_rules: List[str]


# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

# Position peak windows calibrated for the HK context using local season-age curves.
_PEAK_WINDOWS: Dict[str, Tuple[int, int]] = {
    "Forward":    (27, 33),
    "Winger":     (26, 32),
    "Midfielder": (27, 34),
    "Defender":   (28, 35),
    "Goalkeeper": (30, 36),
}

_DEFAULT_PEAK = (27, 33)  # Broad HK outfield default for unknown positions

# Primary metric per position group (column name in history_df)
_PRIMARY_METRICS: Dict[str, str] = {
    "Forward":    "Goals",
    "Winger":     "Goals",
    "Midfielder": "Key passes",
    "Defender":   "Duels won",
    "Goalkeeper": "Save percentage",
}

_SECONDARY_METRICS: Dict[str, Tuple[str, ...]] = {
    "Forward": ("xG", "Shots on target", "Assists"),
    "Winger": ("Assists", "Key passes", "Progressive runs"),
    "Midfielder": ("Assists", "Pass accuracy", "Progressive runs"),
    "Defender": ("Interceptions", "Tackles", "Pass accuracy"),
    "Goalkeeper": ("Save percentage", "Pass accuracy", "Interceptions"),
}

_CONSISTENCY_METRICS: Dict[str, Tuple[Tuple[str, float], ...]] = {
    "Forward": (
        ("Goals", 0.35),
        ("Assists", 0.15),
        ("xG", 0.25),
        ("Minutes played", 0.25),
    ),
    "Winger": (
        ("Goals", 0.20),
        ("Assists", 0.20),
        ("Progressive runs per 90", 0.25),
        ("Minutes played", 0.35),
    ),
    "Midfielder": (
        ("Accurate passes, %", 0.25),
        ("Progressive passes per 90", 0.25),
        ("Successful attacking actions per 90", 0.20),
        ("Minutes played", 0.30),
    ),
    "Defender": (
        ("Duels won, %", 0.30),
        ("Interceptions per 90", 0.25),
        ("Accurate passes, %", 0.15),
        ("Minutes played", 0.30),
    ),
    "Goalkeeper": (
        ("Save rate, %", 0.35),
        ("Prevented goals per 90", 0.25),
        ("Accurate passes, %", 0.15),
        ("Minutes played", 0.25),
    ),
}

# Correlation table: metric → estimated Pearson correlation with minutes_played
# in the HKPL historical dataset.
METRIC_CORRELATION_TABLE: Dict[str, float] = {
    "Goals":              0.58,
    "Assists":            0.52,
    "Key passes":         0.61,
    "Progressive runs":   0.62,
    "Duels won":          0.55,
    "Save percentage":    0.48,
    "Pass accuracy":      0.45,
    "Shots on target":    0.50,
    "Tackles":            0.47,
    "Interceptions":      0.43,
    "xG":                 0.54,
    "xA":                 0.49,
    "Minutes played":     1.00,
}

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_position_group(player: Any) -> str:
    """
    Returns the position group string from a player object or dict.
    Falls back to empty string if not found.
    """
    if isinstance(player, dict):
        raw = player.get("position_main") or player.get("pos_group") or ""
    else:
        raw = getattr(player, "position_main", None) or getattr(player, "pos_group", None) or ""
    raw = str(raw).strip()
    # Normalise common codes to group names
    _CODE_TO_GROUP = {
        "FW": "Forward", "ST": "Forward", "CF": "Forward",
        "RW": "Winger", "LW": "Winger",
        "MF": "Midfielder", "CM": "Midfielder", "DM": "Midfielder",
        "AMF": "Midfielder", "RM": "Midfielder", "LM": "Midfielder",
        "DF": "Defender", "CB": "Defender", "LB": "Defender", "RB": "Defender",
        "GK": "Goalkeeper",
    }
    return _CODE_TO_GROUP.get(raw.upper(), raw.title() if raw else "")


def _get_birth_date(player: Any) -> Optional[date]:
    """Returns the player's birth date from a dict or ORM object."""
    val = None
    if isinstance(player, dict):
        val = player.get("birth_date") or player.get("date_of_birth") or player.get("Birthday") or player.get("birthday")
        if val is None:
            history_df = player.get("history_df")
            if isinstance(history_df, pd.DataFrame) and not history_df.empty:
                for column in ("Birthday", "birth_date", "date_of_birth", "birthday"):
                    if column in history_df.columns:
                        series = history_df[column].dropna()
                        if not series.empty:
                            val = series.iloc[0]
                            break
    else:
        val = (
            getattr(player, "birth_date", None)
            or getattr(player, "date_of_birth", None)
            or getattr(player, "Birthday", None)
            or getattr(player, "birthday", None)
        )
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    try:
        return datetime.fromisoformat(str(val)).date()
    except (ValueError, TypeError):
        return None


def _get_player_age(player: Any) -> Optional[int]:
    """Returns the player's age from a dict or ORM object when available."""
    if isinstance(player, dict):
        raw_age = player.get("age")
    else:
        raw_age = getattr(player, "age", None)
    try:
        age = int(raw_age)
    except (TypeError, ValueError):
        return None
    return age if age > 0 else None


def _compute_age(birth_date: date, reference: Optional[date] = None) -> int:
    ref = reference or date.today()
    age = ref.year - birth_date.year
    if (ref.month, ref.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def _resolve_age_and_peak_range(player: Any) -> Tuple[Optional[int], Tuple[int, int], str]:
    """Returns resolved age, peak range, and normalized position group."""
    pos_group = _resolve_position_group(player)
    peak_range = _PEAK_WINDOWS.get(pos_group, _DEFAULT_PEAK)
    birth = _get_birth_date(player)
    age = _compute_age(birth) if birth is not None else _get_player_age(player)
    return age, peak_range, pos_group


def _compute_base_career_phase(age: Optional[int], peak_range: Tuple[int, int]) -> str:
    """Returns the base phase from age and the positional peak window."""
    if age is None:
        return "unknown"
    peak_start, peak_end = peak_range
    if age < peak_start - 3:
        return "development"
    if age < peak_start:
        return "building"
    if age <= peak_end:
        return "peak"
    return "post-peak"


def _find_metric_column(history_df: pd.DataFrame, candidates: Tuple[str, ...]) -> Optional[str]:
    """Finds the first available metric column matching the candidates."""
    for candidate in candidates:
        if candidate in history_df.columns:
            return candidate
    lowered = {str(col).strip().lower(): col for col in history_df.columns}
    for candidate in candidates:
        matched = lowered.get(candidate.strip().lower())
        if matched:
            return str(matched)
    return None


def _compute_weighted_trend_pct(history_df: pd.DataFrame, metric: str) -> float:
    """Computes weighted YoY trend percentage for a metric."""
    if history_df is None or history_df.empty or metric not in history_df.columns:
        return 0.0
    values = history_df[metric].dropna().tolist()
    if len(values) < 2:
        return 0.0

    deltas: List[float] = []
    weights: List[float] = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        curr = values[i]
        if prev in (None, 0):
            continue
        try:
            delta_pct = (float(curr) - float(prev)) / abs(float(prev)) * 100
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        weight = 0.6 ** (len(values) - 1 - i)
        deltas.append(delta_pct)
        weights.append(weight)

    if not deltas or not weights:
        return 0.0
    total_weight = sum(weights)
    return round(sum(delta * weight for delta, weight in zip(deltas, weights)) / total_weight, 2)


def _get_latest_metric_value(history_df: pd.DataFrame, metric: str) -> float:
    """Returns the most recent metric value."""
    if history_df is None or history_df.empty or metric not in history_df.columns:
        return 0.0
    try:
        return float(history_df[metric].dropna().iloc[-1])
    except (IndexError, TypeError, ValueError):
        return 0.0


def _extract_recent_form_comparison(player: Any) -> Dict[str, Any]:
    """Returns last-5-vs-previous-5 comparison data when available."""
    if isinstance(player, dict):
        recent_windows = player.get("recent_form_windows") or {}
    else:
        recent_windows = getattr(player, "recent_form_windows", None) or {}
    if not isinstance(recent_windows, dict):
        return {}
    comparisons = recent_windows.get("comparisons") or {}
    if not isinstance(comparisons, dict):
        return {}
    comparison = comparisons.get("last5_vs_previous5") or {}
    return comparison if isinstance(comparison, dict) else {}


def _extract_recent_form_windows(player: Any) -> Dict[str, Any]:
    """Returns recent form windows when available."""
    if isinstance(player, dict):
        recent_windows = player.get("recent_form_windows") or {}
    else:
        recent_windows = getattr(player, "recent_form_windows", None) or {}
    return recent_windows if isinstance(recent_windows, dict) else {}


def _compute_window_per90(total: Any, minutes: Any) -> float:
    try:
        total_val = float(total)
        minutes_val = float(minutes)
    except (TypeError, ValueError):
        return 0.0
    if minutes_val <= 0:
        return 0.0
    return (total_val * 90.0) / minutes_val


def _compute_recent_metric_signal(player: Any, position_group: str) -> Tuple[str, float]:
    """Returns the recent position-aware metric label and delta percentage."""
    recent_windows = _extract_recent_form_windows(player)
    comparison = (recent_windows.get("comparisons") or {}).get("last5_vs_previous5") or {}
    last5 = recent_windows.get("last5") or {}
    previous5 = recent_windows.get("previous5") or {}

    def _delta(current_value: float, previous_value: float) -> float:
        if previous_value <= 0:
            return 0.0
        return round(((current_value - previous_value) / abs(previous_value)) * 100.0, 2)

    def _fallback_from_comparison() -> Tuple[str, float]:
        if int(comparison.get("matches") or 0) < 10:
            return "", 0.0
        if position_group in {"Forward", "Winger"}:
            return "Goal contribution", float(comparison.get("goal_contributions_trend_pct") or 0.0)
        if position_group == "Midfielder":
            return "Attacking contribution", float(comparison.get("goal_contributions_trend_pct") or 0.0)
        return "", 0.0

    if not isinstance(last5, dict) or not isinstance(previous5, dict):
        return _fallback_from_comparison()
    if int(last5.get("matches") or 0) != 5 or int(previous5.get("matches") or 0) != 5:
        return _fallback_from_comparison()

    if position_group in {"Forward", "Winger"}:
        label = "Goal contribution"
        current = _compute_window_per90(last5.get("goal_contributions_total"), last5.get("minutes_total"))
        previous = _compute_window_per90(previous5.get("goal_contributions_total"), previous5.get("minutes_total"))
        return label, _delta(current, previous)

    if position_group == "Midfielder":
        label = "Attacking contribution"
        current = _compute_window_per90(last5.get("goal_contributions_total"), last5.get("minutes_total"))
        previous = _compute_window_per90(previous5.get("goal_contributions_total"), previous5.get("minutes_total"))
        return label, _delta(current, previous)

    if position_group == "Defender":
        total_actions = int(last5.get("goal_contributions_total") or 0) + int(previous5.get("goal_contributions_total") or 0)
        if total_actions < 2:
            return "", 0.0
        label = "Attacking contribution"
        current = _compute_window_per90(last5.get("goal_contributions_total"), last5.get("minutes_total"))
        previous = _compute_window_per90(previous5.get("goal_contributions_total"), previous5.get("minutes_total"))
        return label, _delta(current, previous)

    return "", 0.0


def _compute_composite_momentum_score(
    primary_trend_pct: float,
    secondary_trend_pct: float,
    attacking_output_trend_pct: float,
    minutes_trend_pct: float,
    consistency_level: str,
    coach_direction: str,
    coach_delta_pct: float,
    recent_minutes_delta_pct: float = 0.0,
    recent_goal_contributions_delta_pct: float = 0.0,
    position_group: str = "",
) -> int:
    """Builds a 0-5 momentum score from multiple deterministic signals."""
    score = 3.0
    attacking_weight = 0.0 if str(position_group or "") == "Goalkeeper" else 0.25
    score += max(-1.0, min(1.0, primary_trend_pct / 25.0)) * 1.15
    score += max(-1.0, min(1.0, secondary_trend_pct / 25.0)) * 0.55
    score += max(-1.0, min(1.0, attacking_output_trend_pct / 25.0)) * attacking_weight
    score += max(-1.0, min(1.0, minutes_trend_pct / 20.0)) * 0.95
    score += max(-1.0, min(1.0, recent_minutes_delta_pct / 22.0)) * 0.3
    if attacking_weight:
        score += max(-1.0, min(1.0, recent_goal_contributions_delta_pct / 30.0)) * 0.35
    score += {"ALTA": 0.35, "MODERADA": 0.0, "BAJA": -0.45}.get(str(consistency_level or "MODERADA"), 0.0)
    score += {"up": 0.35, "stable": 0.0, "down": -0.4}.get(str(coach_direction or "stable"), 0.0)
    if coach_delta_pct <= -45:
        score -= 1.0
    elif coach_delta_pct <= -35:
        score -= 0.75
    elif coach_delta_pct <= -25:
        score -= 0.55
    elif coach_delta_pct >= 20:
        score += 0.15
    if primary_trend_pct >= 35:
        score += 0.45
    elif primary_trend_pct <= -30:
        score -= 0.3
    if attacking_weight and attacking_output_trend_pct >= 25:
        score += 0.2
    elif attacking_weight and attacking_output_trend_pct <= -25:
        score -= 0.2
    if minutes_trend_pct <= -15 and recent_minutes_delta_pct <= -10:
        score -= 0.35
    if attacking_weight and recent_goal_contributions_delta_pct <= -15:
        score -= 0.4
    if attacking_weight and recent_goal_contributions_delta_pct <= -15 and minutes_trend_pct <= -15:
        score -= 0.35
    if coach_delta_pct <= -35 and str(coach_direction or "stable") == "down":
        score = min(score, 4.0)
    if coach_delta_pct <= -45 and str(consistency_level or "MODERADA") == "BAJA":
        score = min(score, 4.0)
    if str(coach_direction or "stable") == "down" and recent_minutes_delta_pct <= -10:
        score = min(score, 3.0)
    return max(0, min(5, int(round(score))))


def _compute_attacking_output_trend_pct(history_df: pd.DataFrame, position_group: str) -> float:
    """Computes weighted trend for combined goals + assists in outfield roles."""
    if str(position_group or "") == "Goalkeeper":
        return 0.0
    if history_df is None or history_df.empty:
        return 0.0

    goals_col = _find_metric_column(history_df, ("Goals",))
    assists_col = _find_metric_column(history_df, ("Assists",))
    if not goals_col and not assists_col:
        return 0.0

    combined = pd.DataFrame(index=history_df.index)
    if goals_col:
        combined["goals_value"] = pd.to_numeric(history_df[goals_col], errors="coerce").fillna(0.0)
    if assists_col:
        combined["assists_value"] = pd.to_numeric(history_df[assists_col], errors="coerce").fillna(0.0)
    combined["attacking_output"] = combined.sum(axis=1)
    return _compute_weighted_trend_pct(combined, "attacking_output")


def _compute_consistency_cv(series: pd.Series) -> Optional[float]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if len(values) < 2:
        return None
    mean_val = float(values.mean())
    if mean_val == 0:
        return None
    cv = float(values.std() / abs(mean_val))
    return cv if not math.isnan(cv) else None


def _safe_float(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(result) else result


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _build_unavailable_dimension(key: str, label: str) -> ComparativeDimension:
    return ComparativeDimension(
        key=key,
        label=label,
        sample_size=0,
        player_value=0.0,
        average_value=0.0,
        top_tier_value=0.0,
        percentile=0.0,
        average_gap=0.0,
        top_tier_gap=0.0,
        status="unavailable",
        available=False,
    )


def _resolve_comparison_metric(history_df: pd.DataFrame, position_group: str) -> str:
    primary_metric = _PRIMARY_METRICS.get(position_group) or ""
    if primary_metric and primary_metric in history_df.columns:
        return primary_metric
    if "Minutes played" in history_df.columns:
        return "Minutes played"
    return next((str(col) for col in history_df.columns if str(col).lower() != "season"), "")


def _extract_latest_player_value(history_df: pd.DataFrame, metric: str) -> float:
    if not isinstance(history_df, pd.DataFrame) or history_df.empty or metric not in history_df.columns:
        return 0.0
    values = pd.to_numeric(history_df[metric], errors="coerce").dropna()
    if values.empty:
        return 0.0
    return float(values.iloc[-1])


def _build_comparative_dimension(
    key: str,
    label: str,
    player_value: float,
    comparison_values: List[float],
) -> ComparativeDimension:
    clean_values = [float(value) for value in comparison_values if value is not None and not math.isnan(float(value))]
    if not clean_values:
        return _build_unavailable_dimension(key, label)
    average_value = float(np.mean(clean_values))
    top_tier_value = float(np.percentile(clean_values, 75))
    rank = sum(1 for value in clean_values if value <= player_value)
    percentile = round((rank / len(clean_values)) * 100.0, 1)
    average_gap = round(player_value - average_value, 2)
    top_tier_gap = round(top_tier_value - player_value, 2)
    if percentile >= 80:
        status = "above_top_tier"
    elif percentile >= 60:
        status = "above_average"
    elif percentile >= 40:
        status = "near_average"
    else:
        status = "below_average"
    return ComparativeDimension(
        key=key,
        label=label,
        sample_size=len(clean_values),
        player_value=round(player_value, 2),
        average_value=round(average_value, 2),
        top_tier_value=round(top_tier_value, 2),
        percentile=percentile,
        average_gap=average_gap,
        top_tier_gap=top_tier_gap,
        status=status,
    )


def build_career_comparative_scorecard(
    player: Any,
    history_df: pd.DataFrame,
    career_signals: Optional[Dict[str, Any]] = None,
) -> CareerComparativeScorecard:
    """Builds the comparative scorecard used by the decision engine and evidence layer."""
    history_df = history_df if isinstance(history_df, pd.DataFrame) else pd.DataFrame()
    _, peak_range, position_group = _resolve_age_and_peak_range(player)
    metric = _resolve_comparison_metric(history_df, position_group)
    player_value = _extract_latest_player_value(history_df, metric)

    if history_df.empty or not metric:
        unavailable = _build_unavailable_dimension("unavailable", "Unavailable")
        return CareerComparativeScorecard(
            team_positional=unavailable,
            team_overall=unavailable,
            league_positional=unavailable,
            league_overall=unavailable,
            role_security=50.0,
            consistency_score=50.0,
            consistency_label="moderate",
            team_context_score=50.0,
            team_context_label="balanced",
            career_timing_score=50.0,
            career_timing_label="unclear",
            top_tier_gap_score=50.0,
        )

    metric_values = pd.to_numeric(history_df.get(metric), errors="coerce").dropna().tolist()
    minutes_values = pd.to_numeric(history_df.get("Minutes played"), errors="coerce").dropna().tolist() if "Minutes played" in history_df.columns else []
    recent_values = metric_values[-3:] if len(metric_values) >= 3 else metric_values
    position_values = recent_values or metric_values
    overall_values = minutes_values or metric_values
    league_values = metric_values
    league_overall_values = [
        0.7 * float(metric_value) + 0.3 * float(minutes_values[idx])
        for idx, metric_value in enumerate(metric_values[: len(minutes_values)])
    ] if minutes_values else metric_values

    team_positional = _build_comparative_dimension(
        "team_positional_rank",
        "Team Positional Rank",
        player_value,
        position_values,
    )
    team_overall = _build_comparative_dimension(
        "team_global_rank",
        "Team Overall Rank",
        player_value,
        overall_values,
    )
    league_positional = _build_comparative_dimension(
        "league_positional_standing",
        "League Positional Standing",
        player_value,
        league_values,
    )
    league_overall = _build_comparative_dimension(
        "league_global_standing",
        "League Overall Standing",
        player_value,
        league_overall_values,
    )

    coach_conf = (career_signals or {}).get("coach_confidence") or _compute_coach_confidence(history_df)
    consistency = (career_signals or {}).get("consistency_score") or _compute_consistency_score(position_group, history_df)
    age, _, _ = _resolve_age_and_peak_range(player)
    peak_start, peak_end = peak_range

    role_security = _clamp(50.0 + _safe_float(coach_conf.get("latest_vs_average_pct")) * 1.2, 0.0, 100.0)
    consistency_score = _clamp(
        {"ALTA": 82.0, "MODERADA": 58.0, "BAJA": 34.0}.get(str(consistency.get("level") or "MODERADA"), 50.0),
        0.0,
        100.0,
    )
    team_context_score = _clamp(
        (team_positional.percentile * 0.45)
        + (team_overall.percentile * 0.20)
        + (role_security * 0.35),
        0.0,
        100.0,
    )
    if age:
        if age < peak_start:
            timing_score = _clamp(45.0 + ((age - max(18, peak_start - 6)) * 6.0), 0.0, 100.0)
            timing_label = "early_window"
        elif age <= peak_end:
            timing_score = 82.0
            timing_label = "prime_window"
        elif age <= peak_end + 2:
            timing_score = 62.0
            timing_label = "late_prime"
        else:
            timing_score = 40.0
            timing_label = "late_cycle"
    else:
        timing_score = 50.0
        timing_label = "unclear"

    top_tier_gap_score = _clamp(
        100.0 - np.mean(
            [
                max(team_positional.top_tier_gap, 0.0),
                max(team_overall.top_tier_gap, 0.0),
                max(league_positional.top_tier_gap, 0.0),
                max(league_overall.top_tier_gap, 0.0),
            ]
        )
        * 4.0,
        0.0,
        100.0,
    )

    return CareerComparativeScorecard(
        team_positional=team_positional,
        team_overall=team_overall,
        league_positional=league_positional,
        league_overall=league_overall,
        role_security=round(role_security, 1),
        consistency_score=round(consistency_score, 1),
        consistency_label=str(consistency.get("level") or "MODERADA").lower(),
        team_context_score=round(team_context_score, 1),
        team_context_label=(
            "driving_team_context"
            if team_context_score >= 72
            else ("outperforming_team" if team_context_score >= 56 else ("balanced" if team_context_score >= 42 else "carried_by_team"))
        ),
        career_timing_score=round(timing_score, 1),
        career_timing_label=timing_label,
        top_tier_gap_score=round(top_tier_gap_score, 1),
    )


def _deterministic_decision_phase(scorecard: CareerComparativeScorecard) -> str:
    if (
        scorecard.league_positional.percentile >= 75
        and scorecard.league_overall.percentile >= 70
        and scorecard.top_tier_gap_score >= 60
        and scorecard.consistency_score >= 55
    ):
        return "Ambitious"
    if (
        scorecard.league_positional.percentile >= 55
        and scorecard.role_security >= 50
        and scorecard.team_context_score >= 45
    ):
        return "Keep Pushing"
    if (
        scorecard.consistency_score >= 68
        and scorecard.role_security >= 60
        and scorecard.top_tier_gap_score < 60
    ):
        return "Maintain Consistency"
    return "Find Consistency"


def validate_career_decision_phase(
    scorecard: CareerComparativeScorecard,
    assessment: Optional[Any],
) -> CareerDecisionAudit:
    """Validates the AI proposal against deterministic comparative guardrails."""
    deterministic_phase = _deterministic_decision_phase(scorecard)
    if assessment is None:
        return CareerDecisionAudit(
            final_phase=deterministic_phase,
            deterministic_phase=deterministic_phase,
            validation_status="reject",
            alignment_score=0.55,
            confidence="medium",
            main_drivers=["deterministic_fallback"],
            blockers=[],
            risk_flags=[],
            next_condition="Build stronger comparative evidence across the next run.",
            blocking_rules=["ai_unavailable"],
        )

    ai_phase = str(getattr(assessment, "recommended_phase", "") or deterministic_phase)
    blockers = list(getattr(assessment, "blockers", ()) or ())
    risk_flags = list(getattr(assessment, "risk_flags", ()) or ())
    drivers = list(getattr(assessment, "supporting_factors", ()) or ())
    blocking_rules: List[str] = []
    alignment_score = 0.72
    validation_status = "accept"
    final_phase = ai_phase

    if ai_phase == "Ambitious" and (
        scorecard.league_positional.percentile < 60
        or scorecard.top_tier_gap_score < 45
        or scorecard.consistency_score < 45
    ):
        validation_status = "soft_adjust" if deterministic_phase == "Keep Pushing" else "reject"
        final_phase = deterministic_phase if validation_status == "reject" else "Keep Pushing"
        blocking_rules.append("ambitious_threshold_not_met")
        alignment_score = 0.38
    elif ai_phase == "Maintain Consistency" and scorecard.consistency_score < 55:
        validation_status = "soft_adjust"
        final_phase = "Find Consistency"
        blocking_rules.append("consistency_not_stable")
        alignment_score = 0.48
    elif ai_phase == "Keep Pushing" and scorecard.role_security < 35 and scorecard.consistency_score < 45:
        validation_status = "soft_adjust"
        final_phase = "Find Consistency"
        blocking_rules.append("role_and_consistency_too_weak")
        alignment_score = 0.45
    elif ai_phase == "Find Consistency" and deterministic_phase == "Ambitious":
        validation_status = "soft_adjust"
        final_phase = "Keep Pushing"
        blocking_rules.append("floor_too_conservative")
        alignment_score = 0.5

    return CareerDecisionAudit(
        final_phase=final_phase,
        deterministic_phase=deterministic_phase,
        validation_status=validation_status,
        alignment_score=alignment_score,
        confidence=str(getattr(assessment, "confidence", "medium") or "medium"),
        main_drivers=drivers[:4],
        blockers=blockers[:4],
        risk_flags=risk_flags[:4],
        next_condition=str(getattr(assessment, "next_condition", "") or "Build stronger comparative evidence across the next run."),
        blocking_rules=blocking_rules,
    )


def build_career_progression_features(
    player: Any,
    history_df: pd.DataFrame,
    career_signals: Optional[Dict[str, Any]] = None,
) -> CareerProgressionFeatures:
    """Builds deterministic progression features for downstream AI assessment and resolution."""
    age, peak_range, pos_group = _resolve_age_and_peak_range(player)
    base_phase = _compute_base_career_phase(age, peak_range)
    history_df = history_df if isinstance(history_df, pd.DataFrame) else pd.DataFrame()
    season_count = len(history_df) if not history_df.empty else 0

    minutes_col = next((col for col in history_df.columns if "minute" in str(col).lower()), None)
    minutes_trend_pct = _compute_weighted_trend_pct(history_df, minutes_col) if minutes_col else 0.0
    latest_minutes = _safe_int(history_df.iloc[-1].get(minutes_col)) if minutes_col and not history_df.empty else 0

    primary_metric = _PRIMARY_METRICS.get(pos_group) or "Minutes played"
    primary_metric = primary_metric if primary_metric in history_df.columns else (minutes_col or primary_metric)
    secondary_metric = _find_metric_column(history_df, _SECONDARY_METRICS.get(pos_group, tuple()))
    if not secondary_metric and minutes_col and minutes_col != primary_metric:
        secondary_metric = minutes_col
    if secondary_metric == primary_metric:
        secondary_metric = ""

    primary_metric_trend_pct = _compute_weighted_trend_pct(history_df, primary_metric) if primary_metric else 0.0
    secondary_metric_trend_pct = _compute_weighted_trend_pct(history_df, secondary_metric) if secondary_metric else 0.0
    attacking_output_trend_pct = _compute_attacking_output_trend_pct(history_df, pos_group)
    latest_primary_metric = _get_latest_metric_value(history_df, primary_metric) if primary_metric else 0.0
    recent_comparison = _extract_recent_form_comparison(player)
    recent_minutes_delta_pct = float(recent_comparison.get("minutes_trend_pct") or 0.0)
    recent_goal_contributions_delta_pct = float(recent_comparison.get("goal_contributions_trend_pct") or 0.0)
    recent_metric_label, recent_metric_delta_pct = _compute_recent_metric_signal(player, pos_group)
    recent_sample_size = int(recent_comparison.get("matches") or 0)

    coach_conf = (career_signals or {}).get("coach_confidence") or _compute_coach_confidence(history_df)
    consistency = (career_signals or {}).get("consistency_score") or _compute_consistency_score(pos_group, history_df)
    transfer_window = (career_signals or {}).get("transfer_window") or {"quality": "MODERADA"}

    base_momentum = _compute_composite_momentum_score(
        primary_trend_pct=primary_metric_trend_pct,
        secondary_trend_pct=secondary_metric_trend_pct,
        attacking_output_trend_pct=attacking_output_trend_pct,
        minutes_trend_pct=minutes_trend_pct,
        consistency_level=str(consistency.get("level") or "MODERADA"),
        coach_direction=str(coach_conf.get("direction") or "stable"),
        coach_delta_pct=float(coach_conf.get("delta_pct") or 0.0),
        recent_minutes_delta_pct=recent_minutes_delta_pct,
        recent_goal_contributions_delta_pct=recent_metric_delta_pct,
        position_group=pos_group,
    )

    evidence_flags: List[str] = []
    if minutes_trend_pct >= 10:
        evidence_flags.append("minutes_up")
    elif minutes_trend_pct <= -10:
        evidence_flags.append("minutes_down")
    if primary_metric_trend_pct >= 10:
        evidence_flags.append("primary_metric_up")
    elif primary_metric_trend_pct <= -10:
        evidence_flags.append("primary_metric_down")
    if secondary_metric_trend_pct >= 10:
        evidence_flags.append("secondary_metric_up")
    elif secondary_metric_trend_pct <= -10:
        evidence_flags.append("secondary_metric_down")
    if attacking_output_trend_pct >= 10:
        evidence_flags.append("attacking_output_up")
    elif attacking_output_trend_pct <= -10:
        evidence_flags.append("attacking_output_down")
    if str(consistency.get("level") or "MODERADA") == "ALTA":
        evidence_flags.append("consistency_high")
    if str(coach_conf.get("direction") or "stable") == "up":
        evidence_flags.append("coach_trust_up")
    elif str(coach_conf.get("direction") or "stable") == "down":
        evidence_flags.append("coach_trust_down")
    if recent_sample_size >= 10:
        if recent_minutes_delta_pct >= 10:
            evidence_flags.append("recent_minutes_up")
        elif recent_minutes_delta_pct <= -10:
            evidence_flags.append("recent_minutes_down")
        if recent_metric_delta_pct >= 10:
            evidence_flags.append("recent_output_up")
        elif recent_metric_delta_pct <= -10:
            evidence_flags.append("recent_output_down")

    return CareerProgressionFeatures(
        age=int(age or 0),
        position_group=pos_group or "",
        peak_range=peak_range,
        base_phase=base_phase,
        base_momentum=base_momentum,
        minutes_trend_pct=minutes_trend_pct,
        primary_metric=primary_metric or "",
        primary_metric_trend_pct=primary_metric_trend_pct,
        secondary_metric=secondary_metric or "",
        secondary_metric_trend_pct=secondary_metric_trend_pct,
        attacking_output_trend_pct=attacking_output_trend_pct,
        consistency_level=str(consistency.get("level") or "MODERADA"),
        consistency_cv=float(consistency.get("cv") or 0.0),
        coach_confidence_label=str(coach_conf.get("label") or "Rol estable"),
        coach_confidence_direction=str(coach_conf.get("direction") or "stable"),
        coach_confidence_delta_pct=float(coach_conf.get("delta_pct") or 0.0),
        transfer_window_quality=str(transfer_window.get("quality") or "MODERADA"),
        late_peak_candidate=bool(
            base_phase == "post-peak"
            and int(age or 0) <= (peak_range[1] + 2)
            and base_momentum >= 4
            and str(coach_conf.get("direction") or "stable") == "up"
        ),
        recent_minutes_delta_pct=recent_minutes_delta_pct,
        recent_goal_contributions_delta_pct=recent_goal_contributions_delta_pct,
        recent_metric_label=recent_metric_label,
        recent_metric_delta_pct=recent_metric_delta_pct,
        recent_sample_size=recent_sample_size,
        season_count=season_count,
        latest_minutes=latest_minutes,
        latest_primary_metric=latest_primary_metric,
        evidence_flags=evidence_flags,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 1. Career Phase Engine
# ──────────────────────────────────────────────────────────────────────────────

def get_career_phase_data(player: Any, history_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Returns career phase and momentum score for a player.

    Parameters
    ----------
    player : Player ORM object or dict with position_main and birth_date keys.
    history_df : DataFrame with one row per season (sorted oldest → newest).
                 Expected columns depend on position; 'Minutes played' for fallback.

    Returns
    -------
    dict with keys: career_phase, momentum_score, peak_range, age
    """
    career_signals = get_career_signals(player, history_df, {})
    features = build_career_progression_features(player, history_df, career_signals)
    scorecard = build_career_comparative_scorecard(player, history_df, career_signals)
    if features.age <= 0:
        return {
            "career_phase": "unknown",
            "recommended_phase": "Find Consistency",
            "momentum_score": 3,
            "peak_range": features.peak_range,
            "age": 0,
            "comparative_scorecard": scorecard,
        }

    if isinstance(player, dict):
        player_identifier = str(
            player.get("player_id")
            or player.get("id")
            or player.get("player_name")
            or player.get("name")
            or "unknown"
        )
        player_name = str(player.get("player_name") or player.get("name") or "Unknown player")
    else:
        player_identifier = str(
            getattr(player, "player_id", None)
            or getattr(player, "id", None)
            or getattr(player, "player_name", None)
            or getattr(player, "name", None)
            or "unknown"
        )
        player_name = str(getattr(player, "player_name", None) or getattr(player, "name", None) or "Unknown player")

    resolution_payload = {
        "base_phase": features.base_phase,
        "resolved_phase": features.base_phase,
        "base_momentum": features.base_momentum,
        "resolved_momentum": features.base_momentum,
        "recommended_phase": _deterministic_decision_phase(scorecard),
        "ai_used": False,
        "ai_model": "",
        "adjustment_applied": False,
        "adjustment_reason": "Deterministic baseline only.",
        "validation_status": "reject",
        "alignment_score": 0.55,
        "blocking_rules": ["ai_unavailable"],
        "context_patterns": [],
        "confidence": "medium",
        "supporting_factors": [],
        "blockers": [],
        "risk_flags": [],
        "next_condition": "Build stronger comparative evidence across the next run.",
        "contradictions": [],
    }
    resolved_phase = features.base_phase
    resolved_momentum = features.base_momentum
    recommended_phase = _deterministic_decision_phase(scorecard)

    try:
        from utils.domain_ai.career_progression_assessor_ai import resolve_career_progression_cached

        resolution = resolve_career_progression_cached(
            player_identifier=player_identifier,
            player_name=player_name,
            features=features,
            scorecard=scorecard,
        )
        resolved_phase = resolution.resolved_phase
        resolved_momentum = resolution.resolved_momentum
        recommended_phase = resolution.recommended_phase
        resolution_payload = {
            "base_phase": resolution.base_phase,
            "resolved_phase": resolution.resolved_phase,
            "base_momentum": resolution.base_momentum,
            "resolved_momentum": resolution.resolved_momentum,
            "recommended_phase": resolution.recommended_phase,
            "ai_used": resolution.ai_used,
            "ai_model": resolution.ai_model,
            "adjustment_applied": resolution.adjustment_applied,
            "adjustment_reason": resolution.adjustment_reason,
            "validation_status": resolution.validation_status,
            "alignment_score": resolution.alignment_score,
            "blocking_rules": list(resolution.blocking_rules or []),
            "context_patterns": list(resolution.context_patterns or []),
            "confidence": resolution.confidence,
            "supporting_factors": list(resolution.supporting_factors or []),
            "blockers": list(resolution.blockers or []),
            "risk_flags": list(resolution.risk_flags or []),
            "next_condition": resolution.next_condition,
            "contradictions": list(resolution.contradictions or []),
        }
    except Exception:
        pass

    return {
        "career_phase": resolved_phase,
        "recommended_phase": recommended_phase,
        "momentum_score": resolved_momentum,
        "peak_range": features.peak_range,
        "age": features.age,
        "progression_features": features,
        "progression_resolution": resolution_payload,
        "comparative_scorecard": scorecard,
    }


def _compute_momentum_score(pos_group: str, history_df: pd.DataFrame) -> int:
    """
    Computes a 0–5 momentum score from YoY delta of the primary position metric.
    Uses exponential decay (factor 0.6) to weight recent seasons more heavily.
    Defaults to 3 when there is insufficient history or the metric is missing.
    """
    features = build_career_progression_features({"position_main": pos_group}, history_df)
    return features.base_momentum


# ──────────────────────────────────────────────────────────────────────────────
# 2. Career Signal Panel
# ──────────────────────────────────────────────────────────────────────────────

def get_career_signals(
    player: Any,
    history_df: pd.DataFrame,
    career_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Returns structured career signals: coach_confidence, transfer_window, consistency_score.

    Parameters
    ----------
    player      : Player ORM object or dict.
    history_df  : DataFrame with season rows (oldest → newest). Must include 'Minutes played'.
    career_data : Dict already containing career_phase and momentum_score
                  (e.g. output of get_career_phase_data), plus optional 'transferability' key.

    Returns
    -------
    dict with keys: coach_confidence, transfer_window, consistency_score
    """
    coach_conf = _compute_coach_confidence(history_df)
    transfer_win = _compute_transfer_window(career_data)
    consistency = _compute_consistency_score(_resolve_position_group(player), history_df)

    return {
        "coach_confidence": coach_conf,
        "transfer_window": transfer_win,
        "consistency_score": consistency,
    }


def _compute_coach_confidence(history_df: pd.DataFrame) -> Dict[str, Any]:
    """Career-long role regularity with a short-term directional adjustment."""
    _default = {
        "label": "Rol estable",
        "delta_pct": 0.0,
        "direction": "stable",
        "season_regular_share": 0.0,
        "regular_seasons": 0,
        "relevant_minutes_threshold": 900,
        "latest_minutes": 0.0,
        "baseline_minutes": 0.0,
    }

    if history_df is None or history_df.empty:
        return _default

    col = next((c for c in history_df.columns if "minute" in c.lower()), None)
    if col is None:
        return _default

    valid = history_df[col].dropna()
    if len(valid) < 1:
        return _default

    curr = float(valid.iloc[-1])
    baseline = float(valid.mean()) if len(valid) else 0.0
    threshold = int(max(600, min(1200, round((float(valid.median()) if len(valid) else 900) * 0.65))))
    regular_seasons = int((valid >= threshold).sum())
    season_regular_share = round(regular_seasons / len(valid), 2) if len(valid) else 0.0
    latest_vs_average_pct = ((curr - baseline) / abs(baseline) * 100.0) if baseline else 0.0

    prev = float(valid.iloc[-2]) if len(valid) >= 2 else 0.0
    yoy_delta_pct = ((curr - prev) / abs(prev) * 100.0) if prev else 0.0
    delta_pct = (latest_vs_average_pct * 0.7) + (yoy_delta_pct * 0.3)

    if season_regular_share >= 0.75 and curr >= threshold:
        label = "Titular consolidado"
    elif season_regular_share >= 0.55 and curr >= threshold * 0.8:
        label = "Rol creciente" if delta_pct >= 8 else "Rol estable"
    elif season_regular_share >= 0.35 or curr >= threshold * 0.6:
        label = "Rol disminuyendo"
    else:
        label = "Señal de alerta"

    if delta_pct >= 12:
        direction = "up"
    elif delta_pct <= -12:
        direction = "down"
    else:
        direction = "stable"

    return {
        "label": label,
        "delta_pct": round(delta_pct, 2),
        "direction": direction,
        "season_regular_share": season_regular_share,
        "regular_seasons": regular_seasons,
        "relevant_minutes_threshold": threshold,
        "latest_minutes": round(curr, 2),
        "baseline_minutes": round(baseline, 2),
        "latest_vs_average_pct": round(latest_vs_average_pct, 2),
        "yoy_delta_pct": round(yoy_delta_pct, 2),
    }


def _compute_transfer_window(career_data: Dict[str, Any]) -> Dict[str, Any]:
    """Transfer window quality from transferability score + career phase + momentum."""
    career_phase = career_data.get("career_phase", "unknown")
    momentum = career_data.get("momentum_score", 3)
    t_data = career_data.get("transferability") or {}
    score = t_data.get("score", 0.5) if isinstance(t_data, dict) else 0.5

    if score > 0.65 and career_phase == "peak" and momentum >= 4:
        quality = "ÓPTIMA"
        rationale = (
            f"Transferability {round(score*100)}%, fase peak y momentum {momentum}/5 "
            "configuran la ventana óptima para una transferencia."
        )
    elif score > 0.5 and career_phase in ("peak", "building") and momentum >= 3:
        quality = "BUENA"
        rationale = (
            f"Transferability {round(score*100)}% con fase {career_phase} "
            "ofrece una ventana favorable."
        )
    elif score > 0.35:
        quality = "MODERADA"
        rationale = (
            f"Transferability {round(score*100)}% dentro del rango moderado. "
            "Condiciones de mercado aceptables."
        )
    else:
        quality = "BAJA"
        rationale = (
            f"Transferability {round(score*100)}% por debajo del umbral competitivo."
        )

    return {"quality": quality, "rationale": rationale}


def _compute_consistency_score(pos_group: str, history_df: pd.DataFrame) -> Dict[str, Any]:
    """Composite cross-season stability score using position-relevant metrics."""
    _default = {"level": "MODERADA", "cv": 0.0, "metrics_used": []}

    if history_df is None or history_df.empty:
        return _default

    metric_specs = _CONSISTENCY_METRICS.get(pos_group)
    if not metric_specs:
        return _default

    weighted_cvs: List[Tuple[float, float]] = []
    metrics_used: List[str] = []
    for metric_name, weight in metric_specs:
        if metric_name not in history_df.columns:
            continue
        cv = _compute_consistency_cv(history_df[metric_name])
        if cv is None:
            continue
        weighted_cvs.append((cv, weight))
        metrics_used.append(metric_name)

    if not weighted_cvs:
        return _default

    total_weight = sum(weight for _, weight in weighted_cvs)
    composite_cv = sum(cv * weight for cv, weight in weighted_cvs) / total_weight if total_weight else 0.0

    if composite_cv < 0.22:
        level = "ALTA"
    elif composite_cv <= 0.42:
        level = "MODERADA"
    else:
        level = "BAJA"

    return {"level": level, "cv": round(composite_cv, 4), "metrics_used": metrics_used}


# ──────────────────────────────────────────────────────────────────────────────
# 3. Development Priority Board
# ──────────────────────────────────────────────────────────────────────────────

def get_development_priorities(percentiles_data: Dict[str, int]) -> List[Dict[str, Any]]:
    """
    Returns ranked development priorities (max 5: up to 3 'mejorar' + 2 'mantener').

    Parameters
    ----------
    percentiles_data : dict mapping metric_name → percentile (int 0–100).

    Returns
    -------
    list of dicts: {metric, percentile, impact, action}
    """
    if not percentiles_data:
        return []

    mejorar: List[Dict[str, Any]] = []
    mantener: List[Dict[str, Any]] = []

    for metric, percentile in percentiles_data.items():
        extracted_percentile = _extract_percentile(percentile)
        pct = extracted_percentile if extracted_percentile is not None else 50
        corr = METRIC_CORRELATION_TABLE.get(metric, 0.2)

        if pct < 50:
            rank_score = corr * (50 - pct)
            if corr > 0.5:
                impact = "alto"
            elif corr >= 0.3:
                impact = "medio"
            else:
                impact = "bajo"
            mejorar.append({
                "metric": metric,
                "percentile": pct,
                "impact": impact,
                "action": "mejorar",
                "_rank": rank_score,
            })
        else:
            mantener.append({
                "metric": metric,
                "percentile": pct,
                "impact": "alto" if METRIC_CORRELATION_TABLE.get(metric, 0.2) > 0.5 else "medio",
                "action": "mantener",
                "_rank": pct,
            })

    mejorar.sort(key=lambda x: x["_rank"], reverse=True)
    mantener.sort(key=lambda x: x["_rank"], reverse=True)

    result = mejorar[:3] + mantener[:2]
    # Remove internal rank key
    for entry in result:
        entry.pop("_rank", None)

    return result


def _extract_percentile(metric_obj: Any) -> Optional[int]:
    if isinstance(metric_obj, dict):
        value = metric_obj.get("percentile")
    else:
        value = metric_obj
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def build_fallback_career_dashboard_brief(
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    development_priorities: List[Dict[str, Any]],
) -> CareerDashboardBrief:
    """Builds a concise, evidence-linked dashboard brief with no AI dependency."""
    from utils.domain_ai.career_dashboard_ai import build_fallback_career_dashboard_brief as _build_fallback

    return _build_fallback(
        CareerDashboardBrief,
        DashboardInsightItem,
        data,
        career_phase_data,
        career_signals,
        development_priorities,
    )


def build_career_dashboard_brief(
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    development_priorities: List[Dict[str, Any]],
    ai_payload: Any = None,
    synthesize_with_ai: bool = True,
) -> CareerDashboardBrief:
    """
    Builds a structured dashboard brief.

    The current implementation always falls back to deterministic synthesis unless a
    future AI payload cleanly matches the expected shape.
    """
    from utils.domain_ai.career_dashboard_ai import build_career_dashboard_brief as _build_brief

    return _build_brief(
        CareerDashboardBrief,
        DashboardInsightItem,
        data,
        career_phase_data,
        career_signals,
        development_priorities,
        ai_payload=ai_payload,
        synthesize_with_ai=synthesize_with_ai,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 4. Overlay Signal Classifier
# ──────────────────────────────────────────────────────────────────────────────

def classify_overlay_signals(
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    development_priorities: List[Dict[str, Any]],
) -> List[OverlaySignal]:
    """
    Classifies inputs into a list of OverlaySignal (T1/T2), sorted by urgency descending.
    Only the single highest-urgency signal keeps tier=1; all others are downgraded to tier=2.

    Parameters
    ----------
    career_phase_data     : output of get_career_phase_data()
    career_signals        : output of get_career_signals()
    development_priorities: output of get_development_priorities()

    Returns
    -------
    list[OverlaySignal] sorted by urgency descending
    """
    if not career_phase_data and not career_signals:
        return []

    signals: List[OverlaySignal] = []

    career_phase = career_phase_data.get("career_phase", "unknown")
    momentum = career_phase_data.get("momentum_score", 3)
    age = career_phase_data.get("age", 0)

    coach_conf = career_signals.get("coach_confidence", {})
    transfer_win = career_signals.get("transfer_window", {})
    consistency = career_signals.get("consistency_score", {})

    transfer_quality = transfer_win.get("quality", "")
    coach_label = coach_conf.get("label", "")
    coach_direction = coach_conf.get("direction", "stable")
    consistency_level = consistency.get("level", "MODERADA")

    # ── T1 candidate conditions ─────────────────────────────────────────────

    # Transfer window ÓPTIMA
    if transfer_quality == "ÓPTIMA":
        signals.append(OverlaySignal(
            tier=1,
            title="Ventana de transferencia óptima",
            body=(
                f"Tu perfil actual ({transfer_win.get('rationale', '')}) señala que "
                "este es un momento estratégico para explorar oportunidades de mercado."
            ),
            cta_label="Ver análisis →",
            urgency=0.95,
            evidence_key="projection_outlook",
        ))

    # Coach confidence Señal de alerta
    if coach_label == "Señal de alerta":
        signals.append(OverlaySignal(
            tier=1,
            title="Señal de alerta: minutos en caída",
            body=(
                f"Tus minutos han caído un {abs(coach_conf.get('delta_pct', 0)):.0f}% "
                "respecto a la temporada anterior. Conviene analizar el impacto en tu "
                "proyección y explorar opciones de forma proactiva."
            ),
            cta_label="Ver análisis →",
            urgency=0.90,
            evidence_key="minutes_trend",
        ))

    # Post-peak + low momentum
    if career_phase == "post-peak" and momentum <= 2:
        signals.append(OverlaySignal(
            tier=1,
            title="Transición de carrera detectada",
            body=(
                "Tu fase de carrera actual combinada con una tendencia de rendimiento "
                "descendente sugiere que es momento de planificar la siguiente etapa."
            ),
            cta_label="Ver análisis →",
            urgency=0.85,
            evidence_key="career_arc",
        ))

    # Peak momentum (score 5)
    if momentum == 5:
        signals.append(OverlaySignal(
            tier=1,
            title="Mejor momento de tu carrera",
            body=(
                "Estás en el pico de tu rendimiento esta temporada. "
                "Es el momento ideal para capitalizar tu forma con decisiones estratégicas."
            ),
            cta_label="Ver análisis →",
            urgency=0.80,
            evidence_key="career_arc",
        ))

    # ── T2 signals ──────────────────────────────────────────────────────────

    # Consistency signal (if not already covered by a T1)
    if consistency_level == "BAJA":
        signals.append(OverlaySignal(
            tier=2,
            title="Consistencia variable detectada",
            body=(
                "Tu rendimiento muestra alta variabilidad entre temporadas. "
                "Trabajar en consistencia puede mejorar tu valoración de mercado."
            ),
            cta_label="Ver análisis →",
            urgency=0.55,
            evidence_key="career_arc",
        ))
    elif consistency_level == "ALTA":
        signals.append(OverlaySignal(
            tier=2,
            title="Alto nivel de consistencia",
            body=(
                "Tu rendimiento es muy consistente entre temporadas. "
                "Este es un diferenciador clave frente a la competencia."
            ),
            cta_label="Ver análisis →",
            urgency=0.40,
            evidence_key="career_arc",
        ))

    # Transfer window informational (non-ÓPTIMA)
    if transfer_quality in ("BUENA", "MODERADA") and transfer_quality != "ÓPTIMA":
        signals.append(OverlaySignal(
            tier=2,
            title=f"Ventana de transferencia: {transfer_quality}",
            body=transfer_win.get("rationale", "Condiciones de mercado en rango moderado."),
            cta_label="Ver análisis →",
            urgency=0.60 if transfer_quality == "BUENA" else 0.45,
            evidence_key="projection_outlook",
        ))

    # Development priorities (top weakness)
    mejorar_items = [p for p in development_priorities if p.get("action") == "mejorar"]
    if mejorar_items:
        top = mejorar_items[0]
        signals.append(OverlaySignal(
            tier=2,
            title=f"Prioridad de desarrollo: {top['metric']}",
            body=(
                f"Tu {top['metric']} está en el percentil {top['percentile']}. "
                f"Impacto estimado: {top['impact']}. Mejorar este indicador tiene alta "
                "correlación con incremento de minutos."
            ),
            cta_label="Ver análisis →",
            urgency=0.50,
            evidence_key="percentile_profile",
        ))

    # Coach confidence upward (informational T2)
    if coach_label in ("Titular consolidado", "Rol creciente"):
        signals.append(OverlaySignal(
            tier=2,
            title=f"Confianza del entrenador: {coach_label}",
            body=(
                f"Tus minutos han crecido un {coach_conf.get('delta_pct', 0):.0f}% esta "
                "temporada, reflejando una posición sólida en el equipo."
            ),
            cta_label="Ver análisis →",
            urgency=0.35,
            evidence_key="minutes_trend",
        ))

    # Sort by urgency descending
    signals.sort(key=lambda s: s.urgency, reverse=True)

    # Single-T1 enforcement: only highest-urgency keeps tier=1
    t1_seen = False
    for sig in signals:
        if sig.tier == 1:
            if t1_seen:
                sig.tier = 2
            else:
                t1_seen = True

    return signals
