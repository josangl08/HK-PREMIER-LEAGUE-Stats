# ABOUTME: Domain AI service for the career dashboard, combining deterministic football logic with shared AI validation.
# ABOUTME: Produces structured dashboard payloads while keeping rendering concerns in stage helpers and callbacks.

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, is_dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

import pandas as pd

from utils.ai_services.llm_client import (
    generate_gemini_content_with_status,
    get_career_dashboard_model_candidates,
    gemini_is_available,
)
from utils.ai_services.orchestration import parse_structured_json, validate_payload_collection
from utils.ai_services.prompt_builders import (
    build_career_dashboard_synthesis_prompt,
)
from utils.ai_services.evidence_router import normalize_evidence_key, resolve_career_surface_evidence_key
from utils.ai_services.validators import (
    InsightPayload,
    build_fallback_insight_payload,
    coerce_insight_payload,
    normalize_career_decision_phase,
)
from utils.domain_ai.career_facts import build_career_intelligence_facts

logger = logging.getLogger(__name__)

_CAREER_DASHBOARD_AI_CACHE_VERSION = "v19"
_CAREER_DASHBOARD_LLM_CACHE_TIMEOUT_SECONDS = 60 * 60 * 24 * 30
_CAREER_DASHBOARD_FALLBACK_CACHE_TIMEOUT_SECONDS = 60 * 60
_SPECIFIC_CAREER_THESIS_LABELS = {
    "Late-Career Surge",
    "Peak Under Pressure",
    "Early Acceleration",
    "Peak Acceleration",
    "Consolidating Upward",
    "Pressure Phase",
    "Stalled Momentum",
}
_GENERIC_CAREER_THESIS_LABELS = {
    "",
    "Career Progression",
    "Career Thesis",
    "Progression",
}
_GENERIC_SIGNAL_TITLES = {
    "proven track record",
    "maintaining momentum",
    "recent performance dip",
    "career stability",
    "career value",
    "career role",
    "career phase",
    "recent warning",
}
_BANNED_COPY_FRAGMENTS = {
    "actively influencing matches",
    "vital to regain your rhythm quickly",
    "overall career stats",
    "competitive settings",
    "stronger next step",
    "profile separation",
    "trajectory",
    "volatility",
    "defensive_wall",
    "this is the clearest area to work on if you want the next step to come faster",
    "beyond the usual peak window",
    "holding real competitive value",
    "the role side needs to recover first",
    "threatens to undermine the progress",
    "throughout the rest of the season",
    "defying the typical post-peak decline",
    "significant output and influence on the pitch",
    "plenty to offer",
    "maintain your current standing",
    "get your footing back before thinking bigger",
    "real weight",
    "carries enough weight",
    "reliable track record",
}
_GENERIC_UNLOCKS = {
    "more trust, more starts, and a stronger next step",
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_dashboard_item_payload(raw_item: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_item, dict):
        return None

    metadata = raw_item.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    title = _safe_text(raw_item.get("title") or raw_item.get("label") or raw_item.get("headline"))
    body = _safe_text(
        raw_item.get("body")
        or raw_item.get("summary")
        or raw_item.get("plain_fact")
        or raw_item.get("what_this_means_now")
    )
    support = _safe_text(
        raw_item.get("support")
        or raw_item.get("why_it_matters")
        or raw_item.get("why_now")
        or raw_item.get("what_changes")
        or raw_item.get("what_changes_status")
        or raw_item.get("explanation")
    )
    if not title and not body and not support:
        return None

    return {
        "title": title or "Insight",
        "body": body,
        "support": support,
        "evidence_key": normalize_evidence_key(
            raw_item.get("evidence_key")
            or metadata.get("evidence_key")
            or raw_item.get("metric_key")
            or "career_arc"
        ),
        "focus_metric": _safe_text(
            raw_item.get("focus_metric")
            or raw_item.get("metric")
            or metadata.get("focus_metric")
        ),
        "llm_generated": bool(
            raw_item.get("llm_generated")
            if raw_item.get("llm_generated") is not None
            else metadata.get("llm_generated", False)
        ),
        "source_model": _safe_text(raw_item.get("source_model") or metadata.get("source_model")),
        "emphasis": _safe_text(raw_item.get("emphasis") or metadata.get("emphasis") or "neutral") or "neutral",
        "badge_value": _safe_text(raw_item.get("badge_value") or metadata.get("badge_value")),
        "badge_label": _safe_text(raw_item.get("badge_label") or metadata.get("badge_label")),
        "secondary_value": _safe_text(raw_item.get("secondary_value") or metadata.get("secondary_value")),
        "secondary_label": _safe_text(raw_item.get("secondary_label") or metadata.get("secondary_label")),
    }


def normalize_career_dashboard_brief_payload(raw_payload: Any) -> Dict[str, Any]:
    """Normalizes cached or persisted dashboard payloads across contract revisions."""
    if isinstance(raw_payload, dict) and isinstance(raw_payload.get("payload"), dict):
        payload = dict(raw_payload.get("payload") or {})
        payload.setdefault("model", _safe_text(raw_payload.get("model")))
    elif isinstance(raw_payload, dict):
        payload = dict(raw_payload)
    else:
        return {}

    career_thesis = payload.get("career_thesis")
    if not isinstance(career_thesis, dict):
        career_thesis = payload.get("thesis") if isinstance(payload.get("thesis"), dict) else {}
    normalized_thesis = {
        "label": _safe_text(career_thesis.get("label") or career_thesis.get("title") or "Career Progression"),
        "body": _safe_text(career_thesis.get("body") or career_thesis.get("summary")),
        "support": _safe_text(career_thesis.get("support") or career_thesis.get("why_it_matters")),
        "explanation": _safe_text(career_thesis.get("explanation") or career_thesis.get("what_this_means_now")),
        "drivers": _normalize_fact_items(career_thesis.get("drivers"), fallback=[], max_items=3),
        "risks": _normalize_fact_items(career_thesis.get("risks"), fallback=[], max_items=2),
        "llm_generated": bool(career_thesis.get("llm_generated", False)),
        "llm_model": _safe_text(career_thesis.get("llm_model") or payload.get("model")),
    }

    raw_outlook = payload.get("outlook")
    if not isinstance(raw_outlook, dict):
        raw_outlook = payload.get("recommendation") if isinstance(payload.get("recommendation"), dict) else {}
    fallback_outlook = {
        "label": normalize_career_decision_phase(
            raw_outlook.get("label")
            or raw_outlook.get("phase")
            or raw_outlook.get("recommended_phase")
            or raw_outlook.get("recommendation")
            or payload.get("recommended_phase")
            or payload.get("career_decision_phase")
            or payload.get("phase")
            or "Keep Pushing"
        ),
        "body": _safe_text(
            raw_outlook.get("body")
            or raw_outlook.get("headline")
            or raw_outlook.get("plain_fact")
            or raw_outlook.get("what_this_means_now")
        ),
        "support": _safe_text(
            raw_outlook.get("support")
            or raw_outlook.get("why_now")
            or raw_outlook.get("what_changes")
            or raw_outlook.get("what_changes_status")
        ),
        "evidence_key": resolve_career_surface_evidence_key(
            raw_outlook.get("evidence_key") or payload.get("evidence_key") or "career_phase_resolution",
            label=normalize_career_decision_phase(
                raw_outlook.get("label")
                or raw_outlook.get("phase")
                or raw_outlook.get("recommended_phase")
                or raw_outlook.get("recommendation")
                or payload.get("recommended_phase")
                or payload.get("career_decision_phase")
                or payload.get("phase")
                or "Keep Pushing"
            ),
        ),
    }
    normalized_outlook = _normalize_outlook_payload(
        raw_outlook if isinstance(raw_outlook, dict) else {},
        fallback_outlook,
        llm_generated=bool(raw_outlook.get("llm_generated", False)),
        llm_model=_safe_text(raw_outlook.get("llm_model") or payload.get("model")),
    )

    signals: List[Dict[str, Any]] = []
    for item in payload.get("signals") or payload.get("recommendations") or []:
        normalized = _normalize_dashboard_item_payload(item)
        if normalized:
            signals.append(normalized)

    levers: List[Dict[str, Any]] = []
    for item in payload.get("levers") or payload.get("priorities") or []:
        normalized = _normalize_dashboard_item_payload(item)
        if normalized:
            levers.append(normalized)

    return {
        "career_thesis": normalized_thesis,
        "signals": signals,
        "levers": levers,
        "outlook": normalized_outlook,
    }


def _safe_int(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _format_signed_pct(value: float) -> str:
    return f"{value:+.1f}%"


def _format_ordinal(value: Any) -> str:
    number = _safe_int(value)
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def _normalize_legacy_outlook_label(value: Any) -> str:
    return normalize_career_decision_phase(value)


def _normalize_outlook_payload(outlook: Dict[str, Any], fallback_outlook: Dict[str, Any], *, llm_generated: bool, llm_model: str) -> Dict[str, Any]:
    label = _normalize_legacy_outlook_label(outlook.get("label") or fallback_outlook["label"])
    return {
        "label": label,
        "body": str(outlook.get("body") or fallback_outlook["body"]),
        "support": str(outlook.get("support") or fallback_outlook["support"]),
        "evidence_key": resolve_career_surface_evidence_key(
            outlook.get("evidence_key") or fallback_outlook["evidence_key"],
            label=label,
        ),
        "llm_generated": llm_generated,
        "llm_model": llm_model,
    }


def _normalize_rewrite_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _contains_banned_copy(value: Any) -> bool:
    normalized = _normalize_rewrite_text(value)
    return any(fragment in normalized for fragment in _BANNED_COPY_FRAGMENTS)


def _contains_bad_ordinal(value: Any) -> bool:
    normalized = _normalize_rewrite_text(value)
    return bool(re.search(r"\b\d+th percentile\b", normalized) and not re.search(r"\b(?:4|5|6|7|8|9|0|11|12|13)th percentile\b", normalized))


def _is_generic_signal_title(value: Any) -> bool:
    return _normalize_rewrite_text(value) in _GENERIC_SIGNAL_TITLES


def _payload_passes_quality_gate(payload: InsightPayload, fallback_payload: InsightPayload, *, item_kind: str) -> bool:
    texts = [payload.label, payload.body, payload.support]
    if any(not str(text or "").strip() for text in texts):
        return False
    if any(_contains_banned_copy(text) for text in texts):
        return False
    if any(_contains_bad_ordinal(text) for text in texts):
        return False
    if item_kind == "signal":
        if _is_generic_signal_title(payload.label):
            return False
    if item_kind == "lever":
        if str(payload.label or "").strip().lower().startswith("career lever"):
            return False
        if _normalize_rewrite_text(payload.support) in _GENERIC_UNLOCKS:
            return False
        metadata = payload.metadata or {}
        secondary_value = str(metadata.get("secondary_value") or "")
        if secondary_value and _normalize_rewrite_text(secondary_value) in _GENERIC_UNLOCKS:
            return False
    similarity = _rewrite_similarity(payload.body, fallback_payload.body)
    if similarity > 0.96:
        return False
    return True


def _outlook_passes_quality_gate(ai_outlook: Dict[str, Any], fallback_outlook: Dict[str, Any]) -> bool:
    texts = [
        ai_outlook.get("label"),
        ai_outlook.get("body"),
        ai_outlook.get("support"),
    ]
    if any(not str(text or "").strip() for text in texts):
        return False
    if any(_contains_banned_copy(text) for text in texts):
        return False
    if _rewrite_similarity(ai_outlook.get("body"), fallback_outlook.get("body")) > 0.96:
        return False
    if _rewrite_similarity(ai_outlook.get("support"), fallback_outlook.get("support")) > 0.96:
        return False
    return True


def _career_thesis_passes_quality_gate(ai_thesis: Dict[str, Any], fallback_thesis: Dict[str, Any]) -> bool:
    texts = [
        ai_thesis.get("label"),
        ai_thesis.get("body"),
        ai_thesis.get("support"),
        ai_thesis.get("explanation"),
    ]
    if any(not str(text or "").strip() for text in texts[:3]):
        return False
    if any(_contains_banned_copy(text) for text in texts if text is not None):
        return False
    if _rewrite_similarity(ai_thesis.get("body"), fallback_thesis.get("body")) > 0.96:
        return False
    return True


def _rewrite_similarity(left: Any, right: Any) -> float:
    normalized_left = _normalize_rewrite_text(left)
    normalized_right = _normalize_rewrite_text(right)
    if not normalized_left or not normalized_right:
        return 0.0
    return SequenceMatcher(None, normalized_left, normalized_right).ratio()


def _log_rewrite_similarity(player_name: str, fallback: Any, ai_payload: Dict[str, Any]) -> None:
    thesis = ai_payload.get("career_thesis") if isinstance(ai_payload.get("career_thesis"), dict) else {}
    thesis_similarity = _rewrite_similarity(
        (fallback.career_thesis or {}).get("body"),
        thesis.get("body"),
    )

    signal_scores: List[float] = []
    raw_signals = ai_payload.get("signals") if isinstance(ai_payload.get("signals"), list) else []
    for idx, raw_signal in enumerate(raw_signals):
        if idx >= len(getattr(fallback, "signals", [])) or not isinstance(raw_signal, dict):
            continue
        signal_scores.append(
            _rewrite_similarity(
                getattr(fallback.signals[idx], "body", ""),
                raw_signal.get("body"),
            )
        )

    lever_scores: List[float] = []
    raw_levers = ai_payload.get("levers") if isinstance(ai_payload.get("levers"), list) else []
    for idx, raw_lever in enumerate(raw_levers):
        if idx >= len(getattr(fallback, "levers", [])) or not isinstance(raw_lever, dict):
            continue
        lever_scores.append(
            _rewrite_similarity(
                getattr(fallback.levers[idx], "body", ""),
                raw_lever.get("body"),
            )
        )

    outlook = ai_payload.get("outlook") if isinstance(ai_payload.get("outlook"), dict) else {}
    outlook_similarity = _rewrite_similarity(
        (fallback.outlook or {}).get("body"),
        outlook.get("body"),
    )

    logger.info(
        "[CAREER_DASHBOARD_AI_REWRITE] player=%s thesis_similarity=%.2f signals_avg_similarity=%.2f levers_avg_similarity=%.2f outlook_similarity=%.2f",
        player_name or "unknown",
        thesis_similarity,
        (sum(signal_scores) / len(signal_scores)) if signal_scores else 0.0,
        (sum(lever_scores) / len(lever_scores)) if lever_scores else 0.0,
        outlook_similarity,
    )


def _translate_consistency_level(value: str) -> str:
    normalized = str(value or "").strip().upper()
    return {
        "ALTA": "HIGH",
        "MODERADA": "MODERATE",
        "BAJA": "LOW",
    }.get(normalized, normalized.title() if normalized else "")


def _normalize_fact_items(raw_items: Any, *, fallback: List[Dict[str, Any]], max_items: int) -> List[Dict[str, Any]]:
    """Normalizes optional structured thesis factors while keeping deterministic fallback."""
    if not isinstance(raw_items, list):
        return fallback[:max_items]
    normalized: List[Dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        value = str(item.get("value") or "").strip()
        tone = str(item.get("tone") or "neutral").strip().lower()
        horizon = str(item.get("horizon") or "career").strip().lower()
        evidence_key = normalize_evidence_key(item.get("evidence_key") or "")
        if not label or not value:
            continue
        if tone not in {"positive", "warning", "neutral"}:
            tone = "neutral"
        if horizon not in {"career", "season", "last5"}:
            horizon = "career"
        normalized.append(
            {
                "label": label,
                "value": value,
                "tone": tone,
                "horizon": horizon,
                "evidence_key": evidence_key,
            }
        )
        if len(normalized) >= max_items:
            break
    return normalized or fallback[:max_items]


def _extract_progression_features(career_phase_data: Dict[str, Any]) -> Dict[str, Any]:
    raw_features = career_phase_data.get("progression_features")
    if raw_features is None:
        return {}
    if is_dataclass(raw_features):
        return asdict(raw_features)
    if isinstance(raw_features, dict):
        return dict(raw_features)
    return {}


def _build_career_thesis_factors(
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    """Selects the most relevant drivers and risks behind the progression headline."""
    features = _extract_progression_features(career_phase_data)
    phase = str(career_phase_data.get("career_phase") or "unknown")
    peak_range = career_phase_data.get("peak_range") or features.get("peak_range") or []
    age = _safe_int(career_phase_data.get("age") or features.get("age") or data.get("age"))
    coach_conf = career_signals.get("coach_confidence") or {}
    consistency = career_signals.get("consistency_score") or {}

    driver_candidates: List[tuple[float, Dict[str, Any]]] = []
    risk_candidates: List[tuple[float, Dict[str, Any]]] = []

    def _driver(weight: float, label: str, value: str, evidence_key: str, horizon: str) -> None:
        driver_candidates.append(
            (
                weight,
                {
                    "label": label,
                    "value": value,
                    "tone": "positive",
                    "horizon": horizon,
                    "evidence_key": normalize_evidence_key(evidence_key),
                },
            )
        )

    def _risk(weight: float, label: str, value: str, evidence_key: str, horizon: str) -> None:
        risk_candidates.append(
            (
                weight,
                {
                    "label": label,
                    "value": value,
                    "tone": "warning",
                    "horizon": horizon,
                    "evidence_key": normalize_evidence_key(evidence_key),
                },
            )
        )

    primary_metric = str(features.get("primary_metric") or "")
    secondary_metric = str(features.get("secondary_metric") or "")
    primary_metric_trend_pct = _safe_float(features.get("primary_metric_trend_pct"))
    secondary_metric_trend_pct = _safe_float(features.get("secondary_metric_trend_pct"))
    attacking_output_trend_pct = _safe_float(features.get("attacking_output_trend_pct"))
    minutes_trend_pct = _safe_float(features.get("minutes_trend_pct"))
    coach_delta_pct = _safe_float(features.get("coach_confidence_delta_pct") or coach_conf.get("delta_pct"))
    consistency_level = str(consistency.get("level") or features.get("consistency_level") or "MODERADA")
    recent_minutes_delta_pct = _safe_float(features.get("recent_minutes_delta_pct"))
    recent_goal_contributions_delta_pct = _safe_float(features.get("recent_goal_contributions_delta_pct"))
    recent_metric_label = str(features.get("recent_metric_label") or "Goal contribution")
    recent_metric_delta_pct = _safe_float(features.get("recent_metric_delta_pct") or recent_goal_contributions_delta_pct)
    recent_sample_size = _safe_int(features.get("recent_sample_size"))

    if primary_metric and primary_metric_trend_pct >= 12:
        _driver(abs(primary_metric_trend_pct), f"{primary_metric} trend", _format_signed_pct(primary_metric_trend_pct), "career_arc", "career")
    elif primary_metric and primary_metric_trend_pct <= -10:
        _risk(abs(primary_metric_trend_pct), f"{primary_metric} trend", _format_signed_pct(primary_metric_trend_pct), "career_arc", "career")

    if secondary_metric and secondary_metric_trend_pct >= 10:
        _driver(abs(secondary_metric_trend_pct), f"{secondary_metric} trend", _format_signed_pct(secondary_metric_trend_pct), "career_arc", "career")
    elif secondary_metric and secondary_metric_trend_pct <= -10:
        _risk(abs(secondary_metric_trend_pct), f"{secondary_metric} trend", _format_signed_pct(secondary_metric_trend_pct), "career_arc", "career")

    if attacking_output_trend_pct >= 10:
        _driver(abs(attacking_output_trend_pct), "Attacking output", _format_signed_pct(attacking_output_trend_pct), "career_arc", "career")
    elif attacking_output_trend_pct <= -10:
        _risk(abs(attacking_output_trend_pct), "Attacking output", _format_signed_pct(attacking_output_trend_pct), "career_arc", "career")

    if minutes_trend_pct >= 10:
        _driver(abs(minutes_trend_pct), "Minutes trend", _format_signed_pct(minutes_trend_pct), "minutes_trend", "career")
    elif minutes_trend_pct <= -10:
        _risk(abs(minutes_trend_pct), "Minutes trend", _format_signed_pct(minutes_trend_pct), "minutes_trend", "career")

    if coach_delta_pct >= 10:
        _driver(abs(coach_delta_pct), "Role signal", _format_signed_pct(coach_delta_pct), "minutes_trend", "season")
    elif coach_delta_pct <= -10:
        _risk(abs(coach_delta_pct), "Role signal", _format_signed_pct(coach_delta_pct), "minutes_trend", "season")

    if recent_sample_size >= 10:
        if recent_minutes_delta_pct >= 10:
            _driver(abs(recent_minutes_delta_pct), "Minutes trend", _format_signed_pct(recent_minutes_delta_pct), "minutes_trend", "last5")
        elif recent_minutes_delta_pct <= -10:
            _risk(abs(recent_minutes_delta_pct), "Minutes trend", _format_signed_pct(recent_minutes_delta_pct), "minutes_trend", "last5")

        if recent_metric_label and recent_metric_delta_pct >= 10:
            _driver(
                abs(recent_metric_delta_pct),
                recent_metric_label,
                _format_signed_pct(recent_metric_delta_pct),
                "recent_form",
                "last5",
            )
        elif recent_metric_label and recent_metric_delta_pct <= -10:
            _risk(
                abs(recent_metric_delta_pct),
                recent_metric_label,
                _format_signed_pct(recent_metric_delta_pct),
                "recent_form",
                "last5",
            )

    if consistency_level == "ALTA":
        _driver(18.0, "Consistency", "HIGH", "career_arc", "season")
    elif consistency_level == "BAJA":
        _risk(18.0, "Consistency", "LOW", "career_arc", "season")

    if phase in {"peak", "building"} and len(peak_range) == 2 and age > 0:
        _driver(
            14.0,
            "Peak-age window" if phase == "peak" else "Growth window",
            f"{age} in {peak_range[0]}-{peak_range[1]}",
            "projection_outlook",
            "career",
        )

    drivers = [item for _, item in sorted(driver_candidates, key=lambda entry: entry[0], reverse=True)[:3]]
    risks = [item for _, item in sorted(risk_candidates, key=lambda entry: entry[0], reverse=True)[:2]]
    return {"drivers": drivers, "risks": risks}


def _format_count(value: Any) -> str:
    return f"{_safe_int(value):,}"


def _format_pct_value(value: float) -> str:
    return f"{abs(value):.0f}%"


def _is_meaningful_total(value: int, threshold: int) -> bool:
    return value >= threshold


def _format_season_span(season_count: int) -> str:
    if season_count <= 1:
        return "your tracked career"
    return f"{season_count} tracked seasons"


def _format_regular_seasons(regular_seasons: int, season_count: int) -> str:
    if not season_count:
        return "your tracked seasons"
    return f"{regular_seasons} of {season_count} tracked seasons"


def _season_span_weight_label(season_count: int) -> str:
    if season_count >= 8:
        return "More than one good year"
    if season_count >= 5:
        return "Built over time"
    if season_count >= 3:
        return "A base worth building on"
    return "Early body of work"


def _build_career_signal_candidates(
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    development_priorities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Builds a ranked pool of career-facing signal candidates."""
    history_df = data.get("history_df", pd.DataFrame())
    features = _extract_progression_features(career_phase_data)
    phase = str(career_phase_data.get("career_phase") or "unknown")
    momentum = _safe_int(career_phase_data.get("momentum_score") or 3)
    age = _safe_int(career_phase_data.get("age") or features.get("age") or data.get("age"))
    goals_total = _safe_int(data.get("goals"))
    assists_total = _safe_int(data.get("assists"))
    minutes_total = _safe_int(data.get("minutes_played"))
    season_count = _safe_int(features.get("season_count") or (len(history_df) if isinstance(history_df, pd.DataFrame) else 0))

    coach_conf = career_signals.get("coach_confidence") or {}
    transfer_window = career_signals.get("transfer_window") or {}
    consistency = career_signals.get("consistency_score") or {}

    direction = str(coach_conf.get("direction") or "stable")
    delta_pct = _safe_float(coach_conf.get("delta_pct") or 0)
    regular_share = _safe_float(coach_conf.get("season_regular_share") or 0.0)
    regular_seasons = _safe_int(coach_conf.get("regular_seasons") or 0)
    baseline_minutes = _safe_int(coach_conf.get("baseline_minutes") or 0)
    transfer_quality = str(transfer_window.get("quality") or "MODERADA")
    consistency_level = str(consistency.get("level") or "MODERADA")
    recent_sample_size = _safe_int(features.get("recent_sample_size"))
    recent_minutes_delta_pct = _safe_float(features.get("recent_minutes_delta_pct"))
    recent_output_delta_pct = _safe_float(features.get("recent_goal_contributions_delta_pct"))
    recent_metric_label = str(features.get("recent_metric_label") or "")
    recent_metric_delta_pct = _safe_float(features.get("recent_metric_delta_pct"))
    if not recent_metric_label and abs(recent_output_delta_pct) > 0:
        recent_metric_label = "Goal contribution"
        recent_metric_delta_pct = recent_output_delta_pct
    latest_minutes = _safe_int(features.get("latest_minutes"))
    peak_range = career_phase_data.get("peak_range") or features.get("peak_range") or []
    position_group = str(data.get("pos_group") or features.get("position_group") or "").strip()
    latest_season = ""
    if isinstance(history_df, pd.DataFrame) and not history_df.empty and "Season" in history_df.columns:
        latest_season = str(history_df.iloc[-1].get("Season") or "")
    season_span_text = _format_season_span(season_count)
    regular_seasons_text = _format_regular_seasons(regular_seasons, season_count)
    player_context = f"as a {position_group.lower()}" if position_group else ""

    candidates: List[Dict[str, Any]] = []

    def _candidate(
        *,
        score: float,
        family: str,
        horizon: str,
        label: str,
        body: str,
        support: str,
        evidence_key: str,
        emphasis: str,
        badge_value: str = "",
        badge_label: str = "",
        secondary_value: str = "",
        secondary_label: str = "",
        confidence: str = "medium",
        framing_hint: str = "",
        focus_metric: str = "",
    ) -> None:
        candidates.append(
            {
                "score": score,
                "family": family,
                "horizon": horizon,
                "payload": build_fallback_insight_payload(
                    label=label,
                    body=body,
                    support=support,
                    confidence=confidence,
                    evidence_key=evidence_key,
                    emphasis=emphasis,
                    metadata={
                        "badge_value": badge_value,
                        "badge_label": badge_label,
                        "secondary_value": secondary_value,
                        "secondary_label": secondary_label,
                        "framing_hint": framing_hint,
                        "focus_metric": focus_metric,
                    },
                ),
            }
        )

    if direction == "up" and delta_pct >= 10:
        _candidate(
            score=0.88,
            family="role",
            horizon="season",
            label="Role growing again",
            body=(
                f"Your role is strengthening again {player_context}, and that gives the next part of your career more backing."
            ),
            support=(
                f"You have held regular playing time in {regular_seasons_text}, and your latest season"
                f"{' (' + latest_season + ')' if latest_season else ''} sits {_format_pct_value(delta_pct)} above your usual career minutes."
            ),
            evidence_key="minutes_trend",
            emphasis="positive",
            badge_value=f"+{_format_pct_value(delta_pct)}",
            badge_label="vs career baseline",
            secondary_value=_format_count(latest_minutes) if latest_minutes else "—",
            secondary_label="latest minutes",
            confidence="high",
            framing_hint="opportunity",
        )
    elif direction == "down" and delta_pct <= -10:
        _candidate(
            score=0.90,
            family="role",
            horizon="season",
            label="Role has slipped",
            body=(
                f"Your minutes have dropped away from the level you had built across {season_span_text}, and that puts more pressure on your next step."
            ),
            support=(
                f"You have been a regular in {regular_seasons_text}, but your latest season"
                f"{' (' + latest_season + ')' if latest_season else ''} now sits {_format_pct_value(delta_pct)} below your usual career minutes."
            ),
            evidence_key="minutes_trend",
            emphasis="warning",
            badge_value=f"-{_format_pct_value(delta_pct)}",
            badge_label="vs career baseline",
            secondary_value=_format_count(latest_minutes) if latest_minutes else "—",
            secondary_label="latest minutes",
            confidence="high",
            framing_hint="warning",
        )
    else:
        _candidate(
            score=0.55,
            family="role",
            horizon="season",
            label="Role holding steady",
            body=(
                "Your role is holding close to its usual level, but it is not yet pushing your career forward again."
            ),
            support=(
                f"You have held regular minutes in {max(regular_seasons, 1)} of {season_count or 'multiple'} tracked seasons, "
                f"with {baseline_minutes:,} as your usual career baseline."
            ) if baseline_minutes else "Your playing time is holding close to its usual career level.",
            evidence_key="minutes_trend",
            emphasis="neutral",
            badge_value=coach_conf.get("label") or "Stable",
            badge_label="role signal",
            secondary_value=_format_count(latest_minutes) if latest_minutes else "—",
            secondary_label="latest minutes",
            framing_hint="checkpoint",
        )

    if consistency_level == "ALTA":
        _candidate(
            score=0.86,
            family="consistency",
            horizon="career",
            label="Level you can rely on",
            body=(
                f"Across {season_span_text}, your level has stayed steady instead of coming from one short spell."
            ),
            support=f"Your performance profile has held steady across {season_span_text}.",
            evidence_key="career_trend",
            emphasis="positive",
            badge_value="HIGH",
            badge_label="stability",
            secondary_value=str(season_count or "—"),
            secondary_label="seasons tracked",
            confidence="high",
            framing_hint="recognition",
        )
    elif consistency_level == "BAJA":
        _candidate(
            score=0.74,
            family="consistency",
            horizon="career",
            label="Too many swings",
            body=(
                f"Across {season_span_text}, you have shown good highs, but the overall level has moved around too much."
            ),
            support=f"Your performance profile has moved up and down across {season_span_text}.",
            evidence_key="career_trend",
            emphasis="warning",
            badge_value="LOW",
            badge_label="stability",
            secondary_value=str(season_count or "—"),
            secondary_label="seasons tracked",
            confidence="medium",
            framing_hint="checkpoint",
        )

    if recent_sample_size >= 10 and recent_metric_label and recent_metric_delta_pct >= 15:
        _candidate(
            score=0.82,
            family="recent_form",
            horizon="last5",
            label="Recent push",
            body=(
                f"Your last 5 matches are giving your career trend fresh energy through stronger {recent_metric_label.lower()}."
            ),
            support=f"{recent_metric_label} is up {_format_pct_value(recent_metric_delta_pct)} per 90 across your last 5 matches compared with the previous 5.",
            evidence_key="recent_form",
            emphasis="positive",
            badge_value=f"+{_format_pct_value(recent_metric_delta_pct)}",
            badge_label="last 5 impact",
            secondary_value=str(recent_sample_size),
            secondary_label="matches compared",
            confidence="medium",
            framing_hint="opportunity",
        )
    elif recent_sample_size >= 10 and recent_metric_label and recent_metric_delta_pct <= -15:
        _candidate(
            score=0.80,
            family="recent_form",
            horizon="last5",
            label="Recent dip to watch",
            body=(
                f"The last 5 matches have dipped in {recent_metric_label.lower()}, and that matters because your recent level is now below your usual standard."
            ),
            support=f"{recent_metric_label} is down {_format_pct_value(recent_metric_delta_pct)} per 90 across your last 5 matches compared with the previous 5.",
            evidence_key="recent_form",
            emphasis="warning",
            badge_value=f"-{_format_pct_value(recent_metric_delta_pct)}",
            badge_label="last 5 impact",
            secondary_value=str(recent_sample_size),
            secondary_label="matches compared",
            confidence="medium",
            framing_hint="warning",
        )

    if recent_sample_size >= 10 and recent_minutes_delta_pct >= 15:
        _candidate(
            score=0.78,
            family="recent_role",
            horizon="last5",
            label="Recent Role Lift",
            body=(
                "Your last 5 matches show stronger involvement, which can help push your career back into a better rhythm."
            ),
            support=f"Minutes are up {_format_pct_value(recent_minutes_delta_pct)} across your last 5 matches compared with the previous 5.",
            evidence_key="recent_form",
            emphasis="positive",
            badge_value=f"+{_format_pct_value(recent_minutes_delta_pct)}",
            badge_label="last 5 minutes",
            secondary_value=str(recent_sample_size),
            secondary_label="matches compared",
            confidence="medium",
            framing_hint="opportunity",
        )
    elif recent_sample_size >= 10 and recent_minutes_delta_pct <= -15:
        _candidate(
            score=0.76,
            family="recent_role",
            horizon="last5",
            label="Recent Role Dip",
            body=(
                "Your last 5 matches show less involvement, and that can weaken the direction of your career if it starts to stick."
            ),
            support=f"Minutes are down {_format_pct_value(recent_minutes_delta_pct)} across your last 5 matches compared with the previous 5.",
            evidence_key="recent_form",
            emphasis="warning",
            badge_value=f"-{_format_pct_value(recent_minutes_delta_pct)}",
            badge_label="last 5 minutes",
            secondary_value=str(recent_sample_size),
            secondary_label="matches compared",
            confidence="medium",
            framing_hint="warning",
        )

    career_support_parts: List[str] = []
    if _is_meaningful_total(goals_total, 20):
        career_support_parts.append(f"{_format_count(goals_total)} goals")
    if _is_meaningful_total(assists_total, 10):
        career_support_parts.append(f"{_format_count(assists_total)} assists")
    if _is_meaningful_total(minutes_total, 3000):
        career_support_parts.append(f"{_format_count(minutes_total)} minutes")
    if career_support_parts:
        _candidate(
            score=0.78 + min(len(career_support_parts) * 0.03, 0.08),
            family="career_value",
            horizon="career",
            label="Not just one good spell" if season_count >= 5 else _season_span_weight_label(season_count),
            body=(
                f"This is not just one good spell. Across {season_span_text}, you have kept producing over time."
            ),
            support="Your career already includes " + ", ".join(career_support_parts[:3]) + ".",
            evidence_key="career_value_summary",
            emphasis="positive",
            badge_value=str(season_count or "—"),
            badge_label="seasons tracked",
            secondary_value=_format_count(minutes_total) if minutes_total else "—",
            secondary_label="career minutes",
            confidence="medium",
            framing_hint="recognition",
        )

    if phase == "post-peak" and momentum >= 4:
        _candidate(
            score=0.91,
            family="phase_tension",
            horizon="career",
            label=f"Still going strong at {age or '—'}",
            body=f"At {age or '—'}, the challenge is no longer proving your level. It is keeping this level and these minutes going.",
            support=f"You are {age or '—'} and still carrying momentum at {momentum}/5.",
            evidence_key="career_phase_resolution",
            emphasis="positive",
            badge_value=f"{momentum}/5",
            badge_label="momentum",
            secondary_value=f"{age}" if age else "—",
            secondary_label="age",
            confidence="high",
            framing_hint="recognition",
        )
    elif phase == "peak" and momentum <= 2:
        _candidate(
            score=0.87,
            family="phase_tension",
            horizon="career",
            label=f"Peak years under pressure",
            body=f"At {age or '—'}, you are still in the part of your career where more should be happening, but the current trend is not matching that window.",
            support=f"You are {age or '—'} with momentum at {momentum}/5.",
            evidence_key="career_phase_resolution",
            emphasis="warning",
            badge_value=f"{momentum}/5",
            badge_label="momentum",
            secondary_value=f"{age}" if age else "—",
            secondary_label="age",
            confidence="high",
            framing_hint="tension",
        )
    elif phase == "building" and momentum >= 4:
        _candidate(
            score=0.81,
            family="phase_tension",
            horizon="career",
            label=f"Building with real force",
            body=f"At {age or '—'}, you are still building your career, but the trend is starting to move with more force.",
            support=f"You are {age or '—'} with momentum at {momentum}/5.",
            evidence_key="career_phase_resolution",
            emphasis="positive",
            badge_value=f"{momentum}/5",
            badge_label="momentum",
            secondary_value=f"{age}" if age else "—",
            secondary_label="age",
            confidence="medium",
            framing_hint="opportunity",
        )
    elif phase == "building" and momentum <= 2:
        _candidate(
            score=0.77,
            family="phase_tension",
            horizon="career",
            label=f"Building phase, slow push",
            body=f"At {age or '—'}, you are still building your career, but the current trend is not yet giving it enough force.",
            support=f"You are {age or '—'} with momentum at {momentum}/5.",
            evidence_key="career_phase_resolution",
            emphasis="warning",
            badge_value=f"{momentum}/5",
            badge_label="momentum",
            secondary_value=f"{age}" if age else "—",
            secondary_label="age",
            confidence="medium",
            framing_hint="tension",
        )

    if transfer_quality in {"ÓPTIMA", "BAJA"}:
        transfer_map = {
            "ÓPTIMA": (
                0.67,
                "positive",
                "Market Timing",
                "Your career is entering a stronger moment to explore a move if the right opportunity appears.",
            ),
            "BAJA": (
                0.63,
                "warning",
                "Market Timing",
                "Your career may benefit more from building value first than from forcing a move now.",
            ),
        }
        score, emphasis, label, body = transfer_map[transfer_quality]
        _candidate(
            score=score,
            family="market",
            horizon="career",
            label=label,
            body=body,
            support=transfer_window.get("rationale") or "Your market timing is being read from phase, momentum and transfer fit.",
            evidence_key="projection_outlook",
            emphasis=emphasis,
            badge_value=transfer_quality,
            badge_label="window",
            secondary_value=f"{momentum}/5",
            secondary_label="momentum",
            confidence="medium",
        )

    improve_items = [item for item in development_priorities if str(item.get("action") or "") == "mejorar"]
    if improve_items:
        top_priority = improve_items[0]
        metric = str(top_priority.get("metric") or "key area")
        percentile = _safe_int(top_priority.get("percentile"))
        impact = str(top_priority.get("impact") or "medio")
        _candidate(
            score=0.58 if impact == "alto" else 0.48,
            family="development",
            horizon="career",
            label=f"Work on {metric.lower()}",
            body=f"The clearest way to strengthen your career from here is to improve {metric.lower()}.",
            support=f"{metric} is around the {percentile}th percentile in your profile.",
            evidence_key="percentile_profile",
            emphasis="warning" if impact == "alto" else "neutral",
            badge_value=f"P{percentile}",
            badge_label="current level",
            secondary_value=impact.upper(),
            secondary_label="impact",
            confidence="medium",
            focus_metric=metric,
        )

    return sorted(candidates, key=lambda item: item["score"], reverse=True)


def _select_career_signal_payloads(candidates: List[Dict[str, Any]], max_items: int = 3) -> List[InsightPayload]:
    """Keeps the signal mix relevant, varied, and career-focused."""
    selected: List[InsightPayload] = []
    used_families = set()
    used_horizons = set()
    selected_candidates: List[Dict[str, Any]] = []

    structural_families = {"career_value", "consistency"}
    role_families = {"role", "recent_role"}
    phase_families = {"phase_tension"}

    structural_candidates = [candidate for candidate in candidates if candidate["family"] in structural_families]
    if structural_candidates:
        first_structural = max(structural_candidates, key=lambda item: item["score"])
        selected.append(first_structural["payload"])
        used_families.add(first_structural["family"])
        used_horizons.add(first_structural["horizon"])
        selected_candidates.append(first_structural)

    for candidate in candidates:
        family = candidate["family"]
        horizon = candidate["horizon"]
        if candidate in selected_candidates:
            continue
        if family in used_families:
            continue
        if family in role_families and used_families.intersection(role_families):
            continue
        if family in phase_families and used_families.intersection(phase_families):
            continue
        if family in role_families and used_families.intersection(phase_families):
            alternative = any(
                other["family"] not in role_families.union(phase_families)
                and other["family"] not in used_families
                for other in candidates
            )
            if alternative and candidate["score"] < 0.94:
                continue
        if family in phase_families and used_families.intersection(role_families):
            alternative = any(
                other["family"] not in role_families.union(phase_families)
                and other["family"] not in used_families
                for other in candidates
            )
            if alternative and candidate["score"] < 0.94:
                continue
        if len(selected) < 2 and horizon in used_horizons and candidate["score"] < 0.88:
            continue
        selected.append(candidate["payload"])
        used_families.add(family)
        used_horizons.add(horizon)
        selected_candidates.append(candidate)
        if len(selected) >= max_items:
            return selected

    for candidate in candidates:
        payload = candidate["payload"]
        if payload in selected:
            continue
        family = candidate["family"]
        if family in role_families and used_families.intersection(role_families):
            continue
        selected.append(payload)
        used_families.add(family)
        if len(selected) >= max_items:
            break
    return selected[:max_items]


def _to_dashboard_item(item_cls: Any, payload: InsightPayload) -> Any:
    metadata = payload.metadata or {}
    return item_cls(
        title=payload.label,
        body=payload.body,
        support=payload.support,
        evidence_key=payload.evidence_key,
        focus_metric=str(metadata.get("focus_metric") or ""),
        llm_generated=bool(metadata.get("llm_generated", False)),
        source_model=str(metadata.get("source_model") or ""),
        emphasis=payload.emphasis,
        badge_value=str(metadata.get("badge_value") or ""),
        badge_label=str(metadata.get("badge_label") or ""),
        secondary_value=str(metadata.get("secondary_value") or ""),
        secondary_label=str(metadata.get("secondary_label") or ""),
    )


def _serialize_brief_for_cache(brief: Any) -> Dict[str, Any]:
    """Converts a brief object into a cache-safe dict."""
    return {
        "career_thesis": dict(brief.career_thesis or {}),
        "signals": [
            {
                "title": item.title,
                "body": item.body,
                "support": item.support,
                "evidence_key": item.evidence_key,
                "focus_metric": getattr(item, "focus_metric", ""),
                "llm_generated": bool(getattr(item, "llm_generated", False)),
                "source_model": str(getattr(item, "source_model", "") or ""),
                "emphasis": item.emphasis,
                "badge_value": item.badge_value,
                "badge_label": item.badge_label,
                "secondary_value": item.secondary_value,
                "secondary_label": item.secondary_label,
            }
            for item in brief.signals
        ],
        "levers": [
            {
                "title": item.title,
                "body": item.body,
                "support": item.support,
                "evidence_key": item.evidence_key,
                "focus_metric": getattr(item, "focus_metric", ""),
                "llm_generated": bool(getattr(item, "llm_generated", False)),
                "source_model": str(getattr(item, "source_model", "") or ""),
                "emphasis": item.emphasis,
                "badge_value": item.badge_value,
                "badge_label": item.badge_label,
                "secondary_value": item.secondary_value,
                "secondary_label": item.secondary_label,
            }
            for item in brief.levers
        ],
        "outlook": dict(brief.outlook or {}),
    }


def _deserialize_brief_from_cache(brief_cls: Any, item_cls: Any, payload: Dict[str, Any]) -> Any:
    """Rebuilds a brief object from cached raw data."""
    payload = normalize_career_dashboard_brief_payload(payload)

    def _build_item(raw_item: Dict[str, Any]) -> Any:
        return item_cls(
            title=str(raw_item.get("title") or ""),
            body=str(raw_item.get("body") or ""),
            support=str(raw_item.get("support") or ""),
            evidence_key=normalize_evidence_key(raw_item.get("evidence_key") or ""),
            focus_metric=str(raw_item.get("focus_metric") or ""),
            llm_generated=bool(raw_item.get("llm_generated", False)),
            source_model=str(raw_item.get("source_model") or ""),
            emphasis=str(raw_item.get("emphasis") or "neutral"),
            badge_value=str(raw_item.get("badge_value") or ""),
            badge_label=str(raw_item.get("badge_label") or ""),
            secondary_value=str(raw_item.get("secondary_value") or ""),
            secondary_label=str(raw_item.get("secondary_label") or ""),
        )

    return brief_cls(
        career_thesis=dict(payload.get("career_thesis") or {}),
        signals=[_build_item(item) for item in (payload.get("signals") or []) if isinstance(item, dict)],
        levers=[_build_item(item) for item in (payload.get("levers") or []) if isinstance(item, dict)],
        outlook=dict(payload.get("outlook") or {}),
    )


def _build_career_dashboard_cache_key(
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    development_priorities: List[Dict[str, Any]],
) -> str:
    """Builds a deterministic cache key that changes only when underlying career data changes."""
    history_df = data.get("history_df", pd.DataFrame())
    if isinstance(history_df, pd.DataFrame) and not history_df.empty:
        history_snapshot = history_df.fillna("").to_dict("records")
    else:
        history_snapshot = []

    payload = {
        "ai_cache_version": _CAREER_DASHBOARD_AI_CACHE_VERSION,
        "gemini_models": get_career_dashboard_model_candidates(),
        "player_id": data.get("player_id"),
        "player_name": data.get("player_name"),
        "current_season": data.get("current_season"),
        "minutes_played": data.get("minutes_played"),
        "goals": data.get("goals"),
        "assists": data.get("assists"),
        "percentiles_data": data.get("percentiles_data") or {},
        "history_snapshot": history_snapshot,
        "career_phase_data": career_phase_data or {},
        "career_signals": career_signals or {},
        "development_priorities": development_priorities or [],
    }
    serialized = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=True)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"career-dashboard-brief:{data.get('player_id') or data.get('player_name') or 'unknown'}:{digest}"


def _get_cached_career_dashboard_brief(
    brief_cls: Any,
    item_cls: Any,
    cache_key: str,
) -> Any:
    """Returns a cached career dashboard brief when available."""
    try:
        from utils.cache import cache

        cached_payload = cache.get(cache_key)
        if isinstance(cached_payload, dict):
            return _deserialize_brief_from_cache(brief_cls, item_cls, cached_payload)
    except Exception:
        return None
    return None


def _build_career_dashboard_ai_payload_cache_key(cache_key: str) -> str:
    return f"{cache_key}:ai-payload"


def _get_cached_career_dashboard_ai_payload(cache_key: str) -> Dict[str, Any]:
    try:
        from utils.cache import cache

        cached_payload = cache.get(_build_career_dashboard_ai_payload_cache_key(cache_key))
        if not isinstance(cached_payload, dict):
            return {}
        normalized_payload = normalize_career_dashboard_brief_payload(cached_payload)
        if normalized_payload:
            return {
                "payload": normalized_payload,
                "model": _safe_text(cached_payload.get("model")),
            }
        return {}
    except Exception:
        return {}
def _set_cached_career_dashboard_ai_payload(cache_key: str, payload: Dict[str, Any]) -> None:
    try:
        from utils.cache import cache

        cache.set(
            _build_career_dashboard_ai_payload_cache_key(cache_key),
            payload,
            timeout=_CAREER_DASHBOARD_LLM_CACHE_TIMEOUT_SECONDS,
        )
    except Exception:
        return
def _set_cached_career_dashboard_brief(
    cache_key: str,
    brief: Any,
    *,
    synthesized_by_llm: bool,
) -> None:
    """Stores the rendered career dashboard brief in cache."""
    try:
        from utils.cache import cache

        cache.set(
            cache_key,
            _serialize_brief_for_cache(brief),
            timeout=(
                _CAREER_DASHBOARD_LLM_CACHE_TIMEOUT_SECONDS
                if synthesized_by_llm
                else _CAREER_DASHBOARD_FALLBACK_CACHE_TIMEOUT_SECONDS
            ),
        )
    except Exception:
        return


def _dashboard_item_to_payload(item: Any, confidence: str = "medium") -> Dict[str, Any]:
    """Converts a dashboard item back into the shared payload schema for synthesis."""
    return {
        "label": str(getattr(item, "title", "") or "").strip(),
        "body": str(getattr(item, "body", "") or "").strip(),
        "support": str(getattr(item, "support", "") or "").strip(),
        "confidence": confidence,
        "evidence_key": normalize_evidence_key(getattr(item, "evidence_key", "") or ""),
        "emphasis": str(getattr(item, "emphasis", "neutral") or "neutral"),
        "metadata": {
            "focus_metric": str(getattr(item, "focus_metric", "") or ""),
            "badge_value": str(getattr(item, "badge_value", "") or ""),
            "badge_label": str(getattr(item, "badge_label", "") or ""),
            "secondary_value": str(getattr(item, "secondary_value", "") or ""),
            "secondary_label": str(getattr(item, "secondary_label", "") or ""),
            "llm_generated": bool(getattr(item, "llm_generated", False)),
            "source_model": str(getattr(item, "source_model", "") or ""),
        },
    }


def _resolve_career_thesis_payload(fallback_thesis: Dict[str, Any], ai_thesis: Dict[str, Any], resolved_model: str) -> Dict[str, Any]:
    """Keeps specific deterministic theses when AI output becomes flatter or more generic."""
    fallback_label = str(fallback_thesis.get("label") or "").strip()
    ai_label = str(ai_thesis.get("label") or "").strip()
    ai_body = str(ai_thesis.get("body") or "").strip()
    ai_support = str(ai_thesis.get("support") or "").strip()

    if not _career_thesis_passes_quality_gate(ai_thesis, fallback_thesis):
        return {
            **fallback_thesis,
            "llm_generated": False,
            "llm_model": "",
        }

    ai_is_generic = ai_label in _GENERIC_CAREER_THESIS_LABELS or ai_body == "Your career trajectory is still being defined by long-term role and output trends."
    should_keep_fallback_label = fallback_label in _SPECIFIC_CAREER_THESIS_LABELS and (ai_is_generic or ai_label in _GENERIC_CAREER_THESIS_LABELS)
    fallback_drivers = list(fallback_thesis.get("drivers") or [])
    fallback_risks = list(fallback_thesis.get("risks") or [])

    return {
        "label": fallback_label if should_keep_fallback_label else (ai_label or fallback_label),
        "body": ai_body or str(fallback_thesis.get("body") or ""),
        "support": ai_support or str(fallback_thesis.get("support") or ""),
        "explanation": str(ai_thesis.get("explanation") or fallback_thesis.get("explanation") or "").strip(),
        "drivers": _normalize_fact_items(ai_thesis.get("drivers"), fallback=fallback_drivers, max_items=3),
        "risks": _normalize_fact_items(ai_thesis.get("risks"), fallback=fallback_risks, max_items=2),
        "llm_generated": True,
        "llm_model": resolved_model,
    }
def _merge_payload_items(
    items: Any,
    default_items: List[Any],
    *,
    source_model: str = "",
    item_kind: str = "signal",
) -> List[Any]:
    """Returns validated synthesized items, preserving deterministic metadata by index."""
    fallback_payloads: List[InsightPayload] = []
    for item in default_items:
        payload = coerce_insight_payload(_dashboard_item_to_payload(item))
        if payload is None:
            continue
        fallback_payloads.append(payload)
    fallback_payloads = [payload for payload in fallback_payloads if payload is not None]
    if not isinstance(items, list) or not validate_payload_collection(items):
        return fallback_payloads

    built: List[Any] = []
    for idx, item in enumerate(items):
        payload = coerce_insight_payload(item)
        if payload is None:
            if idx < len(fallback_payloads):
                built.append(fallback_payloads[idx])
            continue
        metadata = dict(getattr(default_items[idx], "__dict__", {})) if idx < len(default_items) else {}
        metadata = {
            "badge_value": str(metadata.get("badge_value", "") or ""),
            "badge_label": str(metadata.get("badge_label", "") or ""),
            "secondary_value": str(metadata.get("secondary_value", "") or ""),
            "secondary_label": str(metadata.get("secondary_label", "") or ""),
            "llm_generated": True,
            "source_model": source_model,
        }
        payload = InsightPayload(
            label=payload.label,
            body=payload.body,
            support=payload.support,
            confidence=payload.confidence,
            evidence_key=payload.evidence_key,
            emphasis=payload.emphasis,
            metadata=metadata,
        )
        fallback_payload = fallback_payloads[idx] if idx < len(fallback_payloads) else payload
        if not _payload_passes_quality_gate(payload, fallback_payload, item_kind=item_kind):
            built.append(fallback_payload)
            continue
        built.append(payload)
    return built or fallback_payloads


def _synthesize_career_dashboard_payload(
    fallback: Any,
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    development_priorities: List[Dict[str, Any]],
) -> tuple[Any, str]:
    """Optionally rewrites the deterministic brief through the shared LLM layer."""
    if not gemini_is_available():
        return None, ""

    career_facts = build_career_intelligence_facts(
        data,
        career_phase_data,
        career_signals,
        development_priorities=development_priorities,
    )

    prompt = build_career_dashboard_synthesis_prompt(
        player_name=str(data.get("player_name") or "This player"),
        career_thesis=fallback.career_thesis,
        signals=[_dashboard_item_to_payload(item, confidence="medium") for item in fallback.signals],
        levers=[_dashboard_item_to_payload(item, confidence="medium") for item in fallback.levers],
        outlook=fallback.outlook,
        context={
            "career_phase": career_phase_data.get("career_phase"),
            "momentum_score": career_phase_data.get("momentum_score"),
            "coach_confidence": (career_signals.get("coach_confidence") or {}).get("label"),
            "transfer_window": (career_signals.get("transfer_window") or {}).get("quality"),
            "consistency": (career_signals.get("consistency_score") or {}).get("level"),
            "career_facts": {
                "career_summary": career_facts.get("career_summary") or {},
                "role_facts": career_facts.get("role_facts") or [],
                "pattern_facts": career_facts.get("pattern_facts") or [],
                "tension_facts": career_facts.get("tension_facts") or [],
                "lever_facts": career_facts.get("lever_facts") or [],
                "outlook_facts": career_facts.get("outlook_facts") or [],
            },
        },
    )
    for model_name in get_career_dashboard_model_candidates():
        result = generate_gemini_content_with_status(
            prompt,
            model_name=model_name,
            temperature=0.35,
            max_output_tokens=1400,
            response_mime_type="application/json",
        )
        parsed = parse_structured_json(result.text) if result.ok else None
        if result.ok:
            parsed_keys = sorted(parsed.keys()) if isinstance(parsed, dict) else []
            logger.info(
                "[CAREER_DASHBOARD_AI_SYNTHESIS] player=%s model=%s ok=%s parsed_dict=%s keys=%s signals_type=%s levers_type=%s outlook_type=%s",
                data.get("player_name") or data.get("player_id") or "unknown",
                result.model,
                result.ok,
                isinstance(parsed, dict),
                parsed_keys,
                type(parsed.get("signals")).__name__ if isinstance(parsed, dict) and "signals" in parsed else "missing",
                type(parsed.get("levers")).__name__ if isinstance(parsed, dict) and "levers" in parsed else "missing",
                type(parsed.get("outlook")).__name__ if isinstance(parsed, dict) and "outlook" in parsed else "missing",
            )
        else:
            logger.info(
                "[CAREER_DASHBOARD_AI_SYNTHESIS] player=%s model=%s ok=%s status=%s",
                data.get("player_name") or data.get("player_id") or "unknown",
                result.model,
                result.ok,
                result.status,
            )
        if isinstance(parsed, dict):
            return parsed, result.model
    return None, ""


def build_fallback_career_dashboard_brief(
    brief_cls: Any,
    item_cls: Any,
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    development_priorities: List[Dict[str, Any]],
) -> Any:
    """Builds deterministic, evidence-linked dashboard content with the shared payload contract."""
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
    career_facts = build_career_intelligence_facts(
        data,
        career_phase_data,
        career_signals,
        development_priorities,
    )
    latest_season = ""
    latest_minutes = 0
    season_count = 0
    if isinstance(history_df, pd.DataFrame) and not history_df.empty:
        season_count = len(history_df)
        latest_season = str(history_df.iloc[-1].get("Season") or "")
        minutes_col = next((c for c in history_df.columns if "minute" in c.lower()), None)
        if minutes_col:
            latest_minutes = _safe_int(history_df.iloc[-1].get(minutes_col))

    if phase == "post-peak" and momentum >= 4:
        thesis_label, thesis_body = (
            "Late-Career Surge",
            f"At {age or '—'}, your career still matters, but the challenge now is to keep this level of performance and minutes going.",
        )
    elif phase == "peak" and momentum <= 2:
        thesis_label, thesis_body = (
            "Peak Under Pressure",
            "You are still in your peak-age window, but the current trend is losing force and needs a fresh growth signal.",
        )
    elif phase == "building" and momentum >= 4:
        thesis_label, thesis_body = (
            "Early Acceleration",
            "Your trajectory is moving faster than a normal building phase and is starting to look structurally stronger.",
        )
    elif phase == "peak" and momentum >= 4:
        thesis_label, thesis_body = (
            "Peak Acceleration",
            "You are in a true peak-phase run: your output is still strong and the broader profile is holding up.",
        )
    elif phase == "building" and momentum <= 2:
        thesis_label, thesis_body = (
            "Building Under Pressure",
            "You are still in a growth-stage window, but the recent trend is not yet turning into stronger momentum.",
        )
    elif phase == "building" and momentum == 3:
        thesis_label, thesis_body = (
            "Emerging Foundation",
            "Your progression is still being shaped, but the base of your profile has room to become more structurally valuable.",
        )
    else:
        trajectory_map = {
            ("up", 3): ("Emerging Upside", "Your career is creating stronger upward signals, but not all of them are consolidated yet."),
            ("up", 4): ("Consolidating Upward", "Your career is turning improvement into a more stable identity."),
            ("up", 5): ("Peak Acceleration", "Your career is building upward momentum at the strongest point of your cycle."),
            ("stable", 4): ("Strong Consolidation", "Your profile is stable at a high level and is strengthening through repeatable output."),
            ("stable", 3): ("Stable Consolidation", "Your career is holding value, but still needs sharper differentiation."),
            ("stable", 2): ("Fragile Hold", "Your current level is still visible, but the trajectory is no longer fully secure."),
            ("down", 0): ("Pressure Phase", "Your career direction is under pressure and needs a clearer recovery signal."),
            ("down", 1): ("Stalled Momentum", "Your trajectory is losing force and needs a new growth lever."),
            ("down", 2): ("Stalled Momentum", "Your trajectory is losing force and needs a new growth lever."),
        }
        thesis_label, thesis_body = trajectory_map.get(
            (direction, momentum),
            ("Career Progression", "Your career trajectory is still being defined by long-term role and output trends."),
        )
    thesis_support = (
        f"{player_name}: Phase {phase.upper()} · Momentum {momentum}/5 · "
        f"{minutes_total} total minutes, {goals_total} goals, {assists_total} assists."
    )
    thesis_factors = _build_career_thesis_factors(data, career_phase_data, career_signals)
    thesis_drivers = thesis_factors["drivers"]
    thesis_risks = thesis_factors["risks"]
    explanation_clauses: List[str] = []
    if thesis_drivers:
        explanation_clauses.append(
            "driven by " + ", ".join(f"{item['label'].lower()} {item['value']}" for item in thesis_drivers)
        )
    if thesis_risks:
        explanation_clauses.append(
            "checked by " + ", ".join(f"{item['label'].lower()} {item['value']}" for item in thesis_risks)
        )
    if explanation_clauses:
        if thesis_drivers and thesis_risks:
            thesis_explanation = (
                "Across the tracked seasons, "
                + ", ".join(f"{item['label'].lower()} {item['value']}" for item in thesis_drivers)
                + ", but "
                + " and ".join(f"{item['label'].lower()} {item['value']}" for item in thesis_risks)
                + "."
            )
        elif thesis_drivers:
            thesis_explanation = (
                "Across the tracked seasons, "
                + ", ".join(f"{item['label'].lower()} {item['value']}" for item in thesis_drivers)
                + "."
            )
        else:
            thesis_explanation = (
                "The main pressure points are "
                + " and ".join(f"{item['label'].lower()} {item['value']}" for item in thesis_risks)
                + "."
            )
    else:
        thesis_explanation = "This read is based on the strongest role, output, and trajectory signals available."

    signal_payloads = _select_career_signal_payloads(
        _build_career_signal_candidates(
            data,
            career_phase_data,
            career_signals,
            development_priorities,
        ),
        max_items=3,
    )

    lever_payloads: List[InsightPayload] = []
    for idx, fact in enumerate((career_facts.get("lever_facts") or [])[:3]):
        support_values = (career_facts.get("profile_limits") or []) + (career_facts.get("profile_strengths") or [])
        linked_metric = ""
        linked_percentile = 0
        for item in support_values:
            metric = str(item.get("metric") or "")
            focus_area = str(fact.get("focus_area") or "").lower()
            if metric and metric.lower() in focus_area:
                linked_metric = metric
                linked_percentile = _safe_int(item.get("percentile"))
                break
        title = str(fact.get("focus_area") or f"Career lever {idx + 1}").strip().capitalize()
        support = str(fact.get("support_text") or fact.get("why_it_matters") or "")
        if linked_metric and linked_percentile and not str(fact.get("support_text") or "").strip():
            percentile_text = _format_ordinal(linked_percentile)
            support = f"{support} It sits around the {percentile_text} percentile in your profile.".strip()
        lever_payloads.append(
            build_fallback_insight_payload(
                label=title,
                body=str(fact.get("why_it_matters") or fact.get("why_now") or "This is the clearest area to work on next."),
                support=support or "This is one of the clearest areas shaping your next step.",
                confidence="high" if _safe_float(fact.get("priority_score")) >= 0.8 else "medium",
                evidence_key=str(fact.get("evidence_key") or "percentile_profile"),
                emphasis="warning" if str(fact.get("lever_kind") or "") == "growth" else "positive",
                metadata={
                    "focus_metric": linked_metric,
                    "badge_value": f"P{linked_percentile}" if linked_percentile else "",
                    "badge_label": "percentile" if linked_percentile else "",
                    "secondary_value": str(fact.get("what_it_unlocks") or ""),
                    "secondary_label": "unlocks",
                },
            )
        )

    if not lever_payloads:
        lever_payloads.append(
            build_fallback_insight_payload(
                label="Career Leverage",
                body="Your next leap will come from turning stable minutes into clearer separation.",
                support="There is not enough ranked percentile data to surface a sharper lever yet.",
                confidence="medium",
                evidence_key="career_value_summary",
                emphasis="neutral",
                metadata={
                    "badge_value": f"{momentum}/5",
                    "badge_label": "momentum",
                    "secondary_value": f"{minutes_total:,}" if minutes_total else "—",
                    "secondary_label": "career minutes",
                },
            )
        )

    outlook_facts = career_facts.get("outlook_facts") or []
    if outlook_facts:
        primary_outlook = outlook_facts[0]
        outlook_label = _normalize_legacy_outlook_label(primary_outlook.get("mode") or "Keep Pushing")
        outlook_body = str(primary_outlook.get("plain_fact") or "The next phase needs a clearer football case before you force something bigger.")
        outlook_support = str(primary_outlook.get("why_now") or "")
        outlook_evidence_key = str(primary_outlook.get("evidence_key") or "career_phase_resolution")
    elif transfer_quality == "ÓPTIMA":
        outlook_label = "Ambitious"
        outlook_body = "Your current level gives you a case to aim higher, not just hold ground."
        outlook_support = f"Phase {phase.upper()} at age {age or '—'} with momentum {momentum}/5 and transfer window {transfer_quality}."
        outlook_evidence_key = "top_tier_gap"
    elif direction == "up" and consistency_level == "ALTA":
        outlook_label = "Maintain Consistency"
        outlook_body = "The level is strong enough to respect, so the next job is proving it holds."
        outlook_support = f"Phase {phase.upper()} at age {age or '—'} with momentum {momentum}/5 and transfer window {transfer_quality}."
        outlook_evidence_key = "consistency_profile"
    elif direction == "down":
        outlook_label = "Find Consistency"
        if phase == "post-peak":
            outlook_body = "Focus on getting your level and minutes steady again before thinking about something bigger."
        else:
            outlook_body = "Focus on getting your role steady again before pushing for more."
        outlook_support = (
            f"Your role trend has softened, so the priority is to steady your level first. If the next run is strong again, you can think bigger after that."
        )
        outlook_evidence_key = "team_context"
    else:
        outlook_label = "Keep Pushing"
        outlook_body = "The signs are moving, but you still need more weight before the next step becomes obvious."
        outlook_support = f"Phase {phase.upper()} at age {age or '—'} with momentum {momentum}/5 and transfer window {transfer_quality}."
        outlook_evidence_key = "league_positional_standing"

    fallback_outlook = {
        "label": outlook_label,
        "body": outlook_body,
        "support": outlook_support,
        "evidence_key": outlook_evidence_key,
    }

    return brief_cls(
        career_thesis={
            "label": thesis_label,
            "body": thesis_body,
            "support": thesis_support,
            "explanation": thesis_explanation,
            "drivers": thesis_drivers,
            "risks": thesis_risks,
            "llm_generated": False,
        },
        signals=[_to_dashboard_item(item_cls, payload) for payload in signal_payloads[:3]],
        levers=[_to_dashboard_item(item_cls, payload) for payload in lever_payloads[:3]],
        outlook=_normalize_outlook_payload(fallback_outlook, fallback_outlook, llm_generated=False, llm_model=""),
    )


def synthesize_career_dashboard_ai_payload(
    brief_cls: Any,
    item_cls: Any,
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    development_priorities: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Builds only the structured AI override payload without blocking deterministic render paths."""
    cache_key = _build_career_dashboard_cache_key(
        data,
        career_phase_data,
        career_signals,
        development_priorities,
    )
    cached_payload = _get_cached_career_dashboard_ai_payload(cache_key)
    if cached_payload:
        logger.info(
            "[CAREER_DASHBOARD_AI_PAYLOAD] player=%s source=cache keys=%s",
            data.get("player_name") or data.get("player_id") or "unknown",
            sorted(cached_payload.keys()),
        )
        return cached_payload

    fallback = build_fallback_career_dashboard_brief(
        brief_cls,
        item_cls,
        data,
        career_phase_data,
        career_signals,
        development_priorities,
    )
    ai_payload, resolved_model = _synthesize_career_dashboard_payload(
        fallback,
        data,
        career_phase_data,
        career_signals,
        development_priorities,
    )
    if not isinstance(ai_payload, dict):
        logger.info(
            "[CAREER_DASHBOARD_AI_PAYLOAD] player=%s source=model payload=invalid",
            data.get("player_name") or data.get("player_id") or "unknown",
        )
        return {}
    payload = {
        "payload": normalize_career_dashboard_brief_payload(ai_payload),
        "model": resolved_model,
    }
    logger.info(
        "[CAREER_DASHBOARD_AI_PAYLOAD] player=%s source=model keys=%s model=%s",
        data.get("player_name") or data.get("player_id") or "unknown",
        sorted(ai_payload.keys()),
        resolved_model,
    )
    _set_cached_career_dashboard_ai_payload(cache_key, payload)
    return payload
def build_career_dashboard_brief(
    brief_cls: Any,
    item_cls: Any,
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    development_priorities: List[Dict[str, Any]],
    ai_payload: Any = None,
    synthesize_with_ai: bool = True,
) -> Any:
    """Builds the career dashboard brief from deterministic fallback plus validated structured AI overrides."""
    normalized_ai_payload = normalize_career_dashboard_brief_payload(ai_payload)
    cache_key = _build_career_dashboard_cache_key(
        data,
        career_phase_data,
        career_signals,
        development_priorities,
    )
    has_structured_ai_payload = (
        bool(normalized_ai_payload)
        and any(key in normalized_ai_payload for key in ("career_thesis", "signals", "levers", "outlook"))
    )
    if not has_structured_ai_payload:
        cached_brief = _get_cached_career_dashboard_brief(brief_cls, item_cls, cache_key)
        if cached_brief is not None:
            return cached_brief

    fallback = build_fallback_career_dashboard_brief(
        brief_cls,
        item_cls,
        data,
        career_phase_data,
        career_signals,
        development_priorities,
    )
    if not has_structured_ai_payload and synthesize_with_ai:
        ai_payload, resolved_model = _synthesize_career_dashboard_payload(
            fallback,
            data,
            career_phase_data,
            career_signals,
            development_priorities,
        )
    elif has_structured_ai_payload:
        ai_payload = normalized_ai_payload
        resolved_model = "structured_ai_payload"
    else:
        resolved_model = ""
        _set_cached_career_dashboard_brief(
            cache_key,
            fallback,
            synthesized_by_llm=False,
        )
        return fallback
    if not isinstance(ai_payload, dict):
        _set_cached_career_dashboard_brief(
            cache_key,
            fallback,
            synthesized_by_llm=False,
        )
        return fallback

    try:
        thesis = ai_payload.get("career_thesis") or {}
        outlook = ai_payload.get("outlook") or {}
        if not isinstance(thesis, dict) or not isinstance(outlook, dict):
            return fallback

        raw_signals = ai_payload.get("signals") or []
        raw_levers = ai_payload.get("levers") or []
        signals_rewritten = isinstance(raw_signals, list) and validate_payload_collection(raw_signals)
        levers_rewritten = isinstance(raw_levers, list) and validate_payload_collection(raw_levers)
        thesis_rewritten = bool(str(thesis.get("body") or "").strip())
        outlook_rewritten = bool(str(outlook.get("body") or "").strip())

        logger.info(
            "[CAREER_DASHBOARD_AI] player=%s model=%s thesis=%s signals=%s levers=%s outlook=%s",
            data.get("player_name") or data.get("player_id") or "unknown",
            resolved_model,
            "ai" if thesis_rewritten else "fallback",
            "ai" if signals_rewritten else "fallback",
            "ai" if levers_rewritten else "fallback",
            "ai" if outlook_rewritten else "fallback",
        )
        _log_rewrite_similarity(
            str(data.get("player_name") or data.get("player_id") or "unknown"),
            fallback,
            ai_payload,
        )

        brief = brief_cls(
            career_thesis=_resolve_career_thesis_payload(fallback.career_thesis, thesis, resolved_model),
            signals=[
                _to_dashboard_item(item_cls, payload)
                for payload in _merge_payload_items(
                    raw_signals,
                    fallback.signals,
                    source_model=resolved_model,
                    item_kind="signal",
                )
            ],
            levers=[
                _to_dashboard_item(item_cls, payload)
                for payload in _merge_payload_items(
                    raw_levers,
                    fallback.levers,
                    source_model=resolved_model,
                    item_kind="lever",
                )
            ],
            outlook=(
                _normalize_outlook_payload(outlook, fallback.outlook, llm_generated=True, llm_model=resolved_model)
                if _outlook_passes_quality_gate(outlook, fallback.outlook)
                else _normalize_outlook_payload(fallback.outlook, fallback.outlook, llm_generated=False, llm_model="")
            ),
        )
        _set_cached_career_dashboard_brief(
            cache_key,
            brief,
            synthesized_by_llm=bool(brief.career_thesis.get("llm_generated", False)),
        )
        return brief
    except Exception:
        _set_cached_career_dashboard_brief(
            cache_key,
            fallback,
            synthesized_by_llm=False,
        )
        return fallback
