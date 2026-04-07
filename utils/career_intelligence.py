# ABOUTME: Pure utility for career intelligence: phase detection, signal classification, and overlay tier assignment.
# ABOUTME: No Dash or Flask imports — fully testable in isolation. Used by player_portal callbacks as a service layer.

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


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
    emphasis: str = "neutral"
    badge_value: str = ""
    badge_label: str = ""
    secondary_value: str = ""
    secondary_label: str = ""


@dataclass
class CareerDashboardBrief:
    career_thesis: Dict[str, str]
    signals: List[DashboardInsightItem]
    levers: List[DashboardInsightItem]
    outlook: Dict[str, str]


# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

# Position peak windows: (peak_start, peak_end)
_PEAK_WINDOWS: Dict[str, Tuple[int, int]] = {
    "Forward":    (23, 27),
    "Winger":     (23, 27),
    "Midfielder": (24, 29),
    "Defender":   (25, 30),
    "Goalkeeper": (27, 33),
}

_DEFAULT_PEAK = (24, 29)  # Midfielder default for unknown positions

# Primary metric per position group (column name in history_df)
_PRIMARY_METRICS: Dict[str, str] = {
    "Forward":    "Goals",
    "Winger":     "Goals",
    "Midfielder": "Key passes",
    "Defender":   "Duels won",
    "Goalkeeper": "Save percentage",
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

EVIDENCE_DESTINATIONS: Dict[str, Dict[str, str]] = {
    "career_arc": {"title": "Career Arc", "group": "trajectory"},
    "minutes_trend": {"title": "Minutes Trend", "group": "trajectory"},
    "percentile_profile": {"title": "Percentile Profile", "group": "profile"},
    "similarity_profiles": {"title": "Similarity Profiles", "group": "comparison"},
    "projection_outlook": {"title": "Season Projection", "group": "projection"},
    "tactical_dna": {"title": "Tactical DNA", "group": "identity"},
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
        val = player.get("birth_date") or player.get("date_of_birth")
    else:
        val = getattr(player, "birth_date", None) or getattr(player, "date_of_birth", None)
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


def _compute_age(birth_date: date, reference: Optional[date] = None) -> int:
    ref = reference or date.today()
    age = ref.year - birth_date.year
    if (ref.month, ref.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


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
    pos_group = _resolve_position_group(player)
    peak_range = _PEAK_WINDOWS.get(pos_group, _DEFAULT_PEAK)

    # Age calculation
    birth = _get_birth_date(player)
    if birth is None:
        return {
            "career_phase": "unknown",
            "momentum_score": 3,
            "peak_range": peak_range,
            "age": 0,
        }

    age = _compute_age(birth)
    peak_start, peak_end = peak_range

    if age < peak_start - 3:
        career_phase = "development"
    elif age < peak_start:
        career_phase = "building"
    elif age <= peak_end:
        career_phase = "peak"
    else:
        career_phase = "post-peak"

    momentum_score = _compute_momentum_score(pos_group, history_df)

    return {
        "career_phase": career_phase,
        "momentum_score": momentum_score,
        "peak_range": peak_range,
        "age": age,
    }


def _compute_momentum_score(pos_group: str, history_df: pd.DataFrame) -> int:
    """
    Computes a 0–5 momentum score from YoY delta of the primary position metric.
    Uses exponential decay (factor 0.6) to weight recent seasons more heavily.
    Defaults to 3 when there is insufficient history or the metric is missing.
    """
    if history_df is None or history_df.empty or len(history_df) < 2:
        return 3

    metric = _PRIMARY_METRICS.get(pos_group)
    if metric is None or metric not in history_df.columns:
        return 3

    values = history_df[metric].dropna().tolist()
    if len(values) < 2:
        return 3

    # Compute weighted YoY deltas (most-recent pair gets highest weight)
    deltas: List[float] = []
    weights: List[float] = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        curr = values[i]
        if prev == 0:
            continue
        delta_pct = (curr - prev) / abs(prev) * 100
        # Decay: most recent pair has weight 1.0; each step back decays by 0.6
        w = 0.6 ** (len(values) - 1 - i)
        deltas.append(delta_pct)
        weights.append(w)

    if not deltas:
        return 3

    total_w = sum(weights)
    weighted_delta = sum(d * w for d, w in zip(deltas, weights)) / total_w

    if weighted_delta >= 30:
        return 5
    elif weighted_delta >= 15:
        return 4
    elif weighted_delta >= -5:
        return 3
    elif weighted_delta >= -15:
        return 2
    elif weighted_delta >= -30:
        return 1
    else:
        return 0


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


def normalize_evidence_key(evidence_key: str) -> str:
    key = str(evidence_key or "").strip().lower()
    return key if key in EVIDENCE_DESTINATIONS else "career_arc"


def get_evidence_destination_meta(evidence_key: str) -> Dict[str, str]:
    key = normalize_evidence_key(evidence_key)
    return {"key": key, **EVIDENCE_DESTINATIONS[key]}


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
    player_name = str(data.get("player_name") or "This player")
    history_df = data.get("history_df", pd.DataFrame())
    phase = str(career_phase_data.get("career_phase") or "unknown")
    momentum = _safe_int(career_phase_data.get("momentum_score") or 3)
    age = _safe_int(career_phase_data.get("age") or 0)
    minutes_total = _safe_int(data.get("minutes_played"))
    goals_total = _safe_int(data.get("goals"))
    assists_total = _safe_int(data.get("assists"))

    coach_conf = career_signals.get("coach_confidence") or {}
    transfer_window = career_signals.get("transfer_window") or {}
    consistency = career_signals.get("consistency_score") or {}
    direction = coach_conf.get("direction", "stable")
    delta_pct = coach_conf.get("delta_pct", 0)
    transfer_quality = str(transfer_window.get("quality") or "MODERADA")
    consistency_level = str(consistency.get("level") or "MODERADA")
    latest_season = ""
    latest_minutes = 0
    season_count = 0
    if isinstance(history_df, pd.DataFrame) and not history_df.empty:
        season_count = len(history_df)
        latest_season = str(history_df.iloc[-1].get("Season") or "")
        minutes_col = next((c for c in history_df.columns if "minute" in c.lower()), None)
        if minutes_col:
            latest_minutes = _safe_int(history_df.iloc[-1].get(minutes_col))

    trajectory_map = {
        ("up", 4): ("Consolidating Upward", "Your career is turning improvement into a more stable identity."),
        ("up", 5): ("Peak Acceleration", "Your career is building upward momentum at the strongest point of your cycle."),
        ("stable", 3): ("Stable Consolidation", "Your career is holding value, but still needs sharper differentiation."),
        ("down", 0): ("Pressure Phase", "Your career direction is under pressure and needs a clearer recovery signal."),
        ("down", 1): ("Stalled Momentum", "Your trajectory is losing force and needs a new growth lever."),
        ("down", 2): ("Stalled Momentum", "Your trajectory is losing force and needs a new growth lever."),
    }
    thesis_label, thesis_body = trajectory_map.get(
        (direction, momentum),
        ("Career Progression", "Your career trajectory is still being defined by long-term role and output trends."),
    )
    thesis_support = (
        f"Phase {phase.upper()} · Momentum {momentum}/5 · "
        f"{minutes_total} total minutes, {goals_total} goals, {assists_total} assists."
    )

    signals: List[DashboardInsightItem] = []
    coach_support = (
        f"Minutes trend is {delta_pct:+.0f}% versus the previous season, which points to a {coach_conf.get('label', 'stable role').lower()}."
    )
    coach_body = {
        "up": "Coach trust is becoming more structural.",
        "down": "Your role is losing stability across recent seasons.",
        "stable": "Your role is staying stable, but not clearly strengthening yet.",
    }.get(direction, "Your role is staying stable, but not clearly strengthening yet.")
    signals.append(
        DashboardInsightItem(
            title="Role Evolution",
            body=coach_body,
            support=coach_support,
            evidence_key="minutes_trend",
            emphasis="positive" if direction == "up" else ("warning" if direction == "down" else "neutral"),
            badge_value=f"{delta_pct:+.0f}%",
            badge_label="vs last season",
            secondary_value=f"{latest_minutes:,}" if latest_minutes else "—",
            secondary_label="latest minutes",
        )
    )

    consistency_support = (
        f"Consistency is rated {consistency_level} from your cross-season variability profile."
    )
    consistency_body = {
        "ALTA": "Your career signal is repeatable, not just seasonal.",
        "BAJA": "Your strongest versions are not stable enough yet.",
        "MODERADA": "Your level is visible, but still uneven across seasons.",
    }.get(consistency_level, "Your level is visible, but still uneven across seasons.")
    signals.append(
        DashboardInsightItem(
            title="Consistency",
            body=consistency_body,
            support=consistency_support,
            evidence_key="career_arc",
            emphasis="positive" if consistency_level == "ALTA" else ("warning" if consistency_level == "BAJA" else "neutral"),
            badge_value=consistency_level,
            badge_label="career level",
            secondary_value=str(season_count or "—"),
            secondary_label="seasons tracked",
        )
    )

    transfer_support = transfer_window.get("rationale") or "Transfer conditions are being evaluated from trajectory and market fit."
    transfer_body = {
        "ÓPTIMA": "Your market timing is at a strong strategic point.",
        "BUENA": "Your market context is improving, but still wants more consolidation.",
        "MODERADA": "Your career still benefits more from building value than forcing movement.",
        "BAJA": "This is not yet a strong market window for your profile.",
    }.get(transfer_quality, "Your career still benefits more from building value than forcing movement.")
    signals.append(
        DashboardInsightItem(
            title="Market Window",
            body=transfer_body,
            support=transfer_support,
            evidence_key="projection_outlook",
            emphasis="positive" if transfer_quality == "ÓPTIMA" else ("warning" if transfer_quality == "BAJA" else "neutral"),
            badge_value=transfer_quality,
            badge_label="window",
            secondary_value=f"{momentum}/5",
            secondary_label="momentum",
        )
    )

    levers: List[DashboardInsightItem] = []
    for item in development_priorities[:3]:
        metric = str(item.get("metric") or "Key metric")
        percentile = _safe_int(item.get("percentile"))
        impact = str(item.get("impact") or "medio")
        action = str(item.get("action") or "mejorar")
        if action == "mejorar":
            body = f"Your next growth lever is improving {metric.lower()}."
            support = (
                f"{metric} sits around the {percentile}th percentile, with {impact} estimated impact on role growth."
            )
            evidence_key = "percentile_profile"
            emphasis = "warning" if impact == "alto" else "neutral"
        else:
            body = f"{metric} is already supporting your long-term profile."
            support = (
                f"{metric} sits around the {percentile}th percentile and is worth protecting as a stable strength."
            )
            evidence_key = "tactical_dna"
            emphasis = "positive"
            levers.append(
                DashboardInsightItem(
                    title=metric,
                    body=body,
                    support=support,
                    evidence_key=evidence_key,
                    emphasis=emphasis,
                    badge_value=f"P{percentile}",
                    badge_label="percentile",
                    secondary_value=impact.upper(),
                    secondary_label="impact",
                )
            )

    if not levers:
        levers.append(
            DashboardInsightItem(
                title="Career Leverage",
                body="Your next leap will come from turning stable minutes into clearer separation.",
                support="There is not enough ranked percentile data to surface a sharper lever yet.",
                evidence_key="career_arc",
                emphasis="neutral",
                badge_value=f"{momentum}/5",
                badge_label="momentum",
                secondary_value=f"{minutes_total:,}" if minutes_total else "—",
                secondary_label="career minutes",
            )
        )

    if transfer_quality == "ÓPTIMA":
        outlook_label = "Push"
        outlook_body = "Your current trajectory supports a more aggressive next-step strategy."
    elif direction == "up" and consistency_level == "ALTA":
        outlook_label = "Consolidate"
        outlook_body = "You are in a strong value-building phase and should reinforce repeatability."
    elif direction == "down":
        outlook_label = "Reposition"
        outlook_body = "The next step is to recover role strength before treating market timing as the priority."
    else:
        outlook_label = "Build"
        outlook_body = "The next 1–2 seasons should focus on strengthening identity and separation."

    outlook_support = (
        f"Phase {phase.upper()} at age {age or '—'} with momentum {momentum}/5 and transfer window {transfer_quality}."
    )

    return CareerDashboardBrief(
        career_thesis={
            "label": thesis_label,
            "body": thesis_body,
            "support": thesis_support,
        },
        signals=signals[:3],
        levers=levers[:3],
        outlook={
            "label": outlook_label,
            "body": outlook_body,
            "support": outlook_support,
            "evidence_key": "projection_outlook" if transfer_quality in {"ÓPTIMA", "BUENA"} else "career_arc",
        },
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
    fallback = build_fallback_career_dashboard_brief(
        data,
        career_phase_data,
        career_signals,
        development_priorities,
    )
    if not isinstance(ai_payload, dict):
        return fallback

    try:
        thesis = ai_payload.get("career_thesis") or {}
        signals_payload = ai_payload.get("signals") or []
        levers_payload = ai_payload.get("levers") or []
        outlook = ai_payload.get("outlook") or {}
        if not thesis or not outlook:
            return fallback

        def _build_items(items: Any, default_items: List[DashboardInsightItem]) -> List[DashboardInsightItem]:
            built: List[DashboardInsightItem] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                body = str(item.get("body") or "").strip()
                support = str(item.get("support") or "").strip()
                evidence_key = normalize_evidence_key(item.get("evidence_key") or "")
                if not (title and body and support):
                    continue
                built.append(
                    DashboardInsightItem(
                        title=title,
                        body=body,
                        support=support,
                        evidence_key=evidence_key,
                        emphasis=str(item.get("emphasis") or "neutral"),
                        badge_value=str(item.get("badge_value") or ""),
                        badge_label=str(item.get("badge_label") or ""),
                        secondary_value=str(item.get("secondary_value") or ""),
                        secondary_label=str(item.get("secondary_label") or ""),
                    )
                )
            return built or default_items

        return CareerDashboardBrief(
            career_thesis={
                "label": str(thesis.get("label") or fallback.career_thesis["label"]),
                "body": str(thesis.get("body") or fallback.career_thesis["body"]),
                "support": str(thesis.get("support") or fallback.career_thesis["support"]),
            },
            signals=_build_items(signals_payload, fallback.signals),
            levers=_build_items(levers_payload, fallback.levers),
            outlook={
                "label": str(outlook.get("label") or fallback.outlook["label"]),
                "body": str(outlook.get("body") or fallback.outlook["body"]),
                "support": str(outlook.get("support") or fallback.outlook["support"]),
                "evidence_key": normalize_evidence_key(outlook.get("evidence_key") or fallback.outlook.get("evidence_key")),
            },
        )
    except Exception:
        return fallback


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
