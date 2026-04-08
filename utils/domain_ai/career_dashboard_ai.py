# ABOUTME: Domain AI service for the career dashboard, combining deterministic football logic with shared AI validation.
# ABOUTME: Produces structured dashboard payloads while keeping rendering concerns in stage helpers and callbacks.

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List

import pandas as pd

from utils.ai_services.llm_client import (
    generate_gemini_content_with_status,
    get_dashboard_brief_model_candidates,
    gemini_is_available,
)
from utils.ai_services.orchestration import parse_structured_json, validate_payload_collection
from utils.ai_services.prompt_builders import build_career_dashboard_synthesis_prompt
from utils.ai_services.evidence_router import normalize_evidence_key
from utils.ai_services.validators import (
    InsightPayload,
    build_fallback_insight_payload,
    coerce_insight_payload,
)

_CAREER_DASHBOARD_AI_CACHE_VERSION = "v5"
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

        if recent_goal_contributions_delta_pct >= 10:
            _driver(
                abs(recent_goal_contributions_delta_pct),
                "Goal contribution",
                _format_signed_pct(recent_goal_contributions_delta_pct),
                "career_arc",
                "last5",
            )
        elif recent_goal_contributions_delta_pct <= -10:
            _risk(
                abs(recent_goal_contributions_delta_pct),
                "Goal contribution",
                _format_signed_pct(recent_goal_contributions_delta_pct),
                "career_arc",
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


def _to_dashboard_item(item_cls: Any, payload: InsightPayload) -> Any:
    metadata = payload.metadata or {}
    return item_cls(
        title=payload.label,
        body=payload.body,
        support=payload.support,
        evidence_key=payload.evidence_key,
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
    def _build_item(raw_item: Dict[str, Any]) -> Any:
        return item_cls(
            title=str(raw_item.get("title") or ""),
            body=str(raw_item.get("body") or ""),
            support=str(raw_item.get("support") or ""),
            evidence_key=normalize_evidence_key(raw_item.get("evidence_key") or ""),
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
        "gemini_models": get_dashboard_brief_model_candidates(),
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


def _merge_payload_items(items: Any, default_items: List[Any], *, source_model: str = "") -> List[Any]:
    """Returns validated synthesized items, preserving deterministic metadata by index."""
    fallback_payloads = [
        coerce_insight_payload(_dashboard_item_to_payload(item))
        for item in default_items
    ]
    fallback_payloads = [payload for payload in fallback_payloads if payload is not None]
    if not isinstance(items, list) or not validate_payload_collection(items):
        return fallback_payloads

    built: List[Any] = []
    for idx, item in enumerate(items):
        payload = coerce_insight_payload(item)
        if payload is None:
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
        built.append(payload)
    return built or fallback_payloads


def _synthesize_career_dashboard_payload(
    fallback: Any,
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
) -> tuple[Any, str]:
    """Optionally rewrites the deterministic brief through the shared LLM layer."""
    if not gemini_is_available():
        return None, ""

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
        },
    )
    for model_name in get_dashboard_brief_model_candidates():
        result = generate_gemini_content_with_status(
            prompt,
            model_name=model_name,
            temperature=0.35,
            max_output_tokens=1400,
            response_mime_type="application/json",
        )
        parsed = parse_structured_json(result.text) if result.ok else None
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
            "You are still producing above a normal post-peak curve and carrying real competitive value.",
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

    signal_payloads: List[InsightPayload] = []
    signal_payloads.append(
        build_fallback_insight_payload(
            label="Role Evolution",
            body={
                "up": "Coach trust is becoming more structural.",
                "down": "Your role is losing stability across recent seasons.",
                "stable": "Your role is staying stable, but not clearly strengthening yet.",
            }.get(direction, "Your role is staying stable, but not clearly strengthening yet."),
            support=(
                f"Minutes trend is {delta_pct:+.0f}% versus the previous season, which points to "
                f"a {coach_conf.get('label', 'stable role').lower()}."
            ),
            confidence="high" if direction in {"up", "down"} else "medium",
            evidence_key="minutes_trend",
            emphasis="positive" if direction == "up" else ("warning" if direction == "down" else "neutral"),
            metadata={
                "badge_value": f"{delta_pct:+.0f}%",
                "badge_label": "vs last season",
                "secondary_value": f"{latest_minutes:,}" if latest_minutes else "—",
                "secondary_label": "latest minutes",
            },
        )
    )
    signal_payloads.append(
        build_fallback_insight_payload(
            label="Consistency",
            body={
                "ALTA": "Your career signal is repeatable, not just seasonal.",
                "BAJA": "Your strongest versions are not stable enough yet.",
                "MODERADA": "Your level is visible, but still uneven across seasons.",
            }.get(consistency_level, "Your level is visible, but still uneven across seasons."),
            support=f"Consistency is rated {consistency_level} from your cross-season variability profile.",
            confidence="high" if consistency_level == "ALTA" else ("low" if consistency_level == "BAJA" else "medium"),
            evidence_key="career_arc",
            emphasis="positive" if consistency_level == "ALTA" else ("warning" if consistency_level == "BAJA" else "neutral"),
            metadata={
                "badge_value": consistency_level,
                "badge_label": "career level",
                "secondary_value": str(season_count or "—"),
                "secondary_label": "seasons tracked",
            },
        )
    )
    signal_payloads.append(
        build_fallback_insight_payload(
            label="Market Window",
            body={
                "ÓPTIMA": "Your market timing is at a strong strategic point.",
                "BUENA": "Your market context is improving, but still wants more consolidation.",
                "MODERADA": "Your career still benefits more from building value than forcing movement.",
                "BAJA": "This is not yet a strong market window for your profile.",
            }.get(transfer_quality, "Your career still benefits more from building value than forcing movement."),
            support=transfer_window.get("rationale")
            or "Transfer conditions are being evaluated from trajectory and market fit.",
            confidence="high" if transfer_quality in {"ÓPTIMA", "BUENA"} else "medium",
            evidence_key="projection_outlook",
            emphasis="positive" if transfer_quality == "ÓPTIMA" else ("warning" if transfer_quality == "BAJA" else "neutral"),
            metadata={
                "badge_value": transfer_quality,
                "badge_label": "window",
                "secondary_value": f"{momentum}/5",
                "secondary_label": "momentum",
            },
        )
    )

    lever_payloads: List[InsightPayload] = []
    for item in development_priorities[:3]:
        metric = str(item.get("metric") or "Key metric")
        percentile = _safe_int(item.get("percentile"))
        impact = str(item.get("impact") or "medio")
        action = str(item.get("action") or "mejorar")
        if action == "mejorar":
            lever_payloads.append(
                build_fallback_insight_payload(
                    label=metric,
                    body=f"Your next growth lever is improving {metric.lower()}.",
                    support=(
                        f"{metric} sits around the {percentile}th percentile, with {impact} estimated impact on role growth."
                    ),
                    confidence="high" if impact == "alto" else "medium",
                    evidence_key="percentile_profile",
                    emphasis="warning" if impact == "alto" else "neutral",
                    metadata={
                        "badge_value": f"P{percentile}",
                        "badge_label": "percentile",
                        "secondary_value": impact.upper(),
                        "secondary_label": "impact",
                    },
                )
            )
        else:
            lever_payloads.append(
                build_fallback_insight_payload(
                    label=metric,
                    body=f"{metric} is already supporting your long-term profile.",
                    support=(
                        f"{metric} sits around the {percentile}th percentile and is worth protecting as a stable strength."
                    ),
                    confidence="high",
                    evidence_key="tactical_dna",
                    emphasis="positive",
                    metadata={
                        "badge_value": f"P{percentile}",
                        "badge_label": "percentile",
                        "secondary_value": impact.upper(),
                        "secondary_label": "impact",
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
                evidence_key="career_arc",
                emphasis="neutral",
                metadata={
                    "badge_value": f"{momentum}/5",
                    "badge_label": "momentum",
                    "secondary_value": f"{minutes_total:,}" if minutes_total else "—",
                    "secondary_label": "career minutes",
                },
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

    fallback_outlook = {
        "label": outlook_label,
        "body": outlook_body,
        "support": f"Phase {phase.upper()} at age {age or '—'} with momentum {momentum}/5 and transfer window {transfer_quality}.",
        "evidence_key": "projection_outlook" if transfer_quality in {"ÓPTIMA", "BUENA"} else "career_arc",
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
        outlook={**fallback_outlook, "llm_generated": False},
    )


def build_career_dashboard_brief(
    brief_cls: Any,
    item_cls: Any,
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    development_priorities: List[Dict[str, Any]],
    ai_payload: Any = None,
) -> Any:
    """Builds the career dashboard brief from deterministic fallback plus validated structured AI overrides."""
    cache_key = _build_career_dashboard_cache_key(
        data,
        career_phase_data,
        career_signals,
        development_priorities,
    )
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
    if not isinstance(ai_payload, dict):
        ai_payload, resolved_model = _synthesize_career_dashboard_payload(
            fallback,
            data,
            career_phase_data,
            career_signals,
        )
    else:
        resolved_model = "structured_ai_payload"
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

        brief = brief_cls(
            career_thesis=_resolve_career_thesis_payload(fallback.career_thesis, thesis, resolved_model),
            signals=[
                _to_dashboard_item(item_cls, payload)
                for payload in _merge_payload_items(
                    ai_payload.get("signals") or [],
                    fallback.signals,
                    source_model=resolved_model,
                )
            ],
            levers=[
                _to_dashboard_item(item_cls, payload)
                for payload in _merge_payload_items(
                    ai_payload.get("levers") or [],
                    fallback.levers,
                    source_model=resolved_model,
                )
            ],
            outlook={
                "label": str(outlook.get("label") or fallback.outlook["label"]),
                "body": str(outlook.get("body") or fallback.outlook["body"]),
                "support": str(outlook.get("support") or fallback.outlook["support"]),
                "evidence_key": normalize_evidence_key(outlook.get("evidence_key") or fallback.outlook["evidence_key"]),
                "llm_generated": True,
                "llm_model": resolved_model,
            },
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
