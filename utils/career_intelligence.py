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


@dataclass(frozen=True)
class CareerProgressionResolution:
    base_phase: str
    resolved_phase: str
    base_momentum: int
    resolved_momentum: int
    ai_used: bool
    ai_model: str
    adjustment_applied: bool
    adjustment_reason: str
    confidence: str
    supporting_factors: List[str]
    contradictions: List[str]


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
    if coach_delta_pct <= -45 and str(consistency_level or "MODERADA") == "BAJA":
        score = min(score, 4.0)
    return max(0, min(5, int(round(score))))


def _compute_attacking_output_trend_pct(history_df: pd.DataFrame, position_group: str) -> float:
    """Computes weighted trend for combined goals + assists in outfield roles."""
    if str(position_group or "") == "Goalkeeper":
        return 0.0
    if history_df is None or history_df.empty:
        return 0.0

    goals_col = _find_metric_column(history_df, ("Goals",))
    assists_col = _find_metric_column(history_df, ("Assists",))
    if str(position_group or "") in {"Forward", "Winger"}:
        return _compute_weighted_trend_pct(history_df, assists_col) if assists_col else 0.0
    if not goals_col and not assists_col:
        return 0.0

    combined = pd.DataFrame(index=history_df.index)
    if goals_col:
        combined["goals_value"] = pd.to_numeric(history_df[goals_col], errors="coerce").fillna(0.0)
    if assists_col:
        combined["assists_value"] = pd.to_numeric(history_df[assists_col], errors="coerce").fillna(0.0)
    combined["attacking_output"] = combined.sum(axis=1)
    return _compute_weighted_trend_pct(combined, "attacking_output")


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
        recent_goal_contributions_delta_pct=recent_goal_contributions_delta_pct,
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
        if recent_goal_contributions_delta_pct >= 10:
            evidence_flags.append("recent_output_up")
        elif recent_goal_contributions_delta_pct <= -10:
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
    features = build_career_progression_features(player, history_df)
    if features.age <= 0:
        return {
            "career_phase": "unknown",
            "momentum_score": 3,
            "peak_range": features.peak_range,
            "age": 0,
        }

    return {
        "career_phase": features.base_phase,
        "momentum_score": features.base_momentum,
        "peak_range": features.peak_range,
        "age": features.age,
        "progression_features": features,
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
    """Minutes played YoY trend → coach confidence label."""
    _default = {"label": "Rol estable", "delta_pct": 0.0, "direction": "stable"}

    if history_df is None or history_df.empty:
        return _default

    col = next((c for c in history_df.columns if "minute" in c.lower()), None)
    if col is None:
        return _default

    valid = history_df[col].dropna()
    if len(valid) < 2:
        return _default

    prev = float(valid.iloc[-2])
    curr = float(valid.iloc[-1])

    if prev == 0:
        return _default

    delta_pct = (curr - prev) / abs(prev) * 100

    if delta_pct >= 15:
        label = "Titular consolidado"
        direction = "up"
    elif delta_pct > 5:
        label = "Rol creciente"
        direction = "up"
    elif delta_pct >= -5:
        label = "Rol estable"
        direction = "stable"
    elif delta_pct >= -20:
        label = "Rol disminuyendo"
        direction = "down"
    else:
        label = "Señal de alerta"
        direction = "down"

    return {"label": label, "delta_pct": round(delta_pct, 2), "direction": direction}


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
    """CV of primary metric across seasons → consistency level."""
    _default = {"level": "MODERADA", "cv": 0.0}

    if history_df is None or history_df.empty:
        return _default

    metric = _PRIMARY_METRICS.get(pos_group)
    if metric is None or metric not in history_df.columns:
        return _default

    values = history_df[metric].dropna()
    if len(values) < 2:
        return _default

    mean_val = values.mean()
    if mean_val == 0:
        return _default

    cv = float(values.std() / mean_val)

    if cv < 0.15:
        level = "ALTA"
    elif cv <= 0.35:
        level = "MODERADA"
    else:
        level = "BAJA"

    return {"level": level, "cv": round(cv, 4)}


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
        pct = int(percentile) if percentile is not None else 50
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
