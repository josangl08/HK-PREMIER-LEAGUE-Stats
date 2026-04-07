# ABOUTME: Pure utility for career intelligence: phase detection, signal classification, and overlay tier assignment.
# ABOUTME: No Dash or Flask imports — fully testable in isolation. Used by player_portal callbacks as a service layer.

from __future__ import annotations

import math
from dataclasses import dataclass, field
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
        ))

    # Transfer window informational (non-ÓPTIMA)
    if transfer_quality in ("BUENA", "MODERADA") and transfer_quality != "ÓPTIMA":
        signals.append(OverlaySignal(
            tier=2,
            title=f"Ventana de transferencia: {transfer_quality}",
            body=transfer_win.get("rationale", "Condiciones de mercado en rango moderado."),
            cta_label="Ver análisis →",
            urgency=0.60 if transfer_quality == "BUENA" else 0.45,
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
