# ABOUTME: Deterministic career-intelligence fact assembly for command-center synthesis and evidence explanation.
# ABOUTME: Converts dashboard data, career signals, and development priorities into reusable structured fact groups.

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

from utils.ai_services.evidence_router import normalize_evidence_key


_METRIC_DISPLAY_OVERRIDES = {
    "defensive_wall": "defensive positioning",
    "aerial duels won, %": "aerial duels",
    "interceptions per 90": "interceptions",
    "duels won, %": "duels",
    "accurate passes, %": "passing",
    "progressive passes per 90": "forward passing",
    "successful attacking actions per 90": "attacking actions",
    "progressive runs per 90": "forward runs",
    "shots on target, %": "shot accuracy",
}


def _metric_unlock_text(metric: str) -> str:
    normalized = str(metric or "").lower()
    if "position" in normalized:
        return "helps you look more dependable over full matches"
    if "interception" in normalized:
        return "helps you look safer and more complete in your role"
    if "aerial" in normalized:
        return "helps you stay stronger in direct moments"
    if "pass" in normalized:
        return "helps you keep the game moving and look calmer in possession"
    if "duel" in normalized:
        return "helps you hold your ground better when games get physical"
    return "helps you support a bigger role more clearly"


def _metric_lever_body(metric: str) -> str:
    normalized = str(metric or "").lower()
    if "position" in normalized:
        return "You need to be in the right spot more often so fewer moments get away from you."
    if "interception" in normalized:
        return "Reading passes earlier will help you stop danger before it grows."
    if "aerial" in normalized:
        return "Winning more of the direct moments will make you easier to trust when games get scrappy."
    if "pass" in normalized:
        return "This can help you look calmer and more useful when the ball needs moving quickly."
    if "duel" in normalized:
        return "This can help you hold your ground better when opponents try to force the game."
    return f"This part of your game can still do more to support a stronger role."


def _metric_support_text(metric: str, percentile: int) -> str:
    normalized = str(metric or "").lower()
    ordinal = _format_ordinal(percentile)
    if "position" in normalized:
        return f"Your {metric} is currently in the bottom {percentile}% of your profile, making it a key area for improvement."
    if "interception" in normalized:
        return f"Your {metric} sit at the {ordinal} percentile, which is lower than what is required for the next step in your career."
    if "aerial" in normalized:
        return f"Aerial duels are still behind where they need to be for your role and sit around the {ordinal} percentile in your profile."
    if "duel" in normalized:
        return f"Your {metric} are still behind the level you want for a bigger step. They sit around the {ordinal} percentile in your profile."
    return f"Your {metric} is still behind the level you want for a bigger step. It sits around the {ordinal} percentile in your profile."


def _metric_why_now(metric: str, role_direction: str) -> str:
    normalized = str(metric or "").lower()
    if role_direction == "up":
        return "Your role is improving, so this is the right moment to make that growth stick."
    if "position" in normalized:
        return "This matters now because it can remove the small moments that make your role look less secure."
    if "interception" in normalized:
        return "This matters now because spotting danger earlier can make your whole role look safer."
    if "aerial" in normalized:
        return "This matters now because direct moments often decide whether you look dependable or vulnerable."
    return "This is one of the clearest areas that can still move your career forward."


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


def _format_ordinal(value: Any) -> str:
    number = _safe_int(value)
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def _extract_percentile(value: Any) -> int:
    if isinstance(value, dict):
        value = value.get("percentile")
    return max(0, min(100, _safe_int(value)))


def _history_season_count(data: Dict[str, Any]) -> int:
    history_df = data.get("history_df", pd.DataFrame())
    return len(history_df) if isinstance(history_df, pd.DataFrame) and not history_df.empty else 0


def _latest_season_label(data: Dict[str, Any]) -> str:
    history_df = data.get("history_df", pd.DataFrame())
    if isinstance(history_df, pd.DataFrame) and not history_df.empty and "Season" in history_df.columns:
        return str(history_df.iloc[-1].get("Season") or "")
    return ""


def humanize_metric_name(metric: Any) -> str:
    """Returns a player-friendly metric label instead of an internal or analyst-style raw name."""
    raw_metric = str(metric or "").strip()
    if not raw_metric:
        return "key area"
    lowered = raw_metric.lower()
    if lowered in _METRIC_DISPLAY_OVERRIDES:
        return _METRIC_DISPLAY_OVERRIDES[lowered]
    cleaned = raw_metric.replace("_", " ").strip()
    if cleaned.endswith(", %"):
        cleaned = cleaned[:-3]
    if cleaned.endswith(" per 90"):
        cleaned = cleaned[:-7]
    cleaned = " ".join(cleaned.split())
    return cleaned[:1].lower() + cleaned[1:] if cleaned else "key area"


def _sort_profile_items(percentiles_data: Dict[str, Any], *, reverse: bool) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for metric, raw_value in (percentiles_data or {}).items():
        percentile = _extract_percentile(raw_value)
        items.append({"metric": humanize_metric_name(metric), "percentile": percentile})
    items.sort(key=lambda item: item["percentile"], reverse=reverse)
    return items


def _build_role_facts(career_signals: Dict[str, Any]) -> List[Dict[str, Any]]:
    coach_conf = (career_signals or {}).get("coach_confidence") or {}
    if not coach_conf:
        return []

    direction = str(coach_conf.get("direction") or "stable")
    latest_vs_average_pct = _safe_float(coach_conf.get("latest_vs_average_pct"))
    regular_seasons = _safe_int(coach_conf.get("regular_seasons"))
    season_regular_share = _safe_float(coach_conf.get("season_regular_share"))

    if direction == "up":
        label = "role_is_growing"
        plain_fact = "You are playing more than your usual level."
        why = "More minutes can turn into a stronger role if your level holds."
    elif direction == "down":
        label = "role_is_under_pressure"
        plain_fact = "Your role has dropped below the level you had built before."
        why = "If that keeps going, it can slow the next step in your career."
    else:
        label = "role_is_holding"
        plain_fact = "Your role is close to its usual level."
        why = "This keeps your position steady, but it does not change the bigger picture yet."

    return [
        {
            "label": label,
            "plain_fact": plain_fact,
            "strength": min(1.0, max(0.0, abs(latest_vs_average_pct) / 25.0)),
            "why_it_matters": why,
            "evidence_key": "minutes_trend",
            "supporting_values": {
                "coach_confidence_label": str(coach_conf.get("label") or ""),
                "latest_vs_average_pct": round(latest_vs_average_pct, 2),
                "regular_seasons": regular_seasons,
                "season_regular_share": round(season_regular_share, 2),
            },
        }
    ]


def _build_pattern_facts(data: Dict[str, Any], career_phase_data: Dict[str, Any], career_signals: Dict[str, Any]) -> List[Dict[str, Any]]:
    facts: List[Dict[str, Any]] = []
    features = career_phase_data.get("progression_features")
    recent_windows = data.get("recent_form_windows") or {}
    comparison = (recent_windows.get("comparisons") or {}).get("last5_vs_previous5") or {}

    if features is not None:
        recent_metric_label = str(getattr(features, "recent_metric_label", "") or "")
        recent_metric_delta_pct = _safe_float(getattr(features, "recent_metric_delta_pct", 0.0))
        recent_sample_size = _safe_int(getattr(features, "recent_sample_size", 0))
        consistency_level = str(getattr(features, "consistency_level", "MODERADA") or "MODERADA")
        if recent_sample_size >= 10 and recent_metric_label and abs(recent_metric_delta_pct) >= 10:
            direction = "up" if recent_metric_delta_pct > 0 else "down"
            facts.append(
                {
                    "label": f"recent_form_{direction}",
                    "plain_fact": (
                        f"Your recent {recent_metric_label.lower()} is moving up."
                        if direction == "up"
                        else f"Your recent {recent_metric_label.lower()} has cooled off."
                    ),
                    "strength": min(1.0, abs(recent_metric_delta_pct) / 30.0),
                    "why_it_matters": (
                        "This supports the wider career trend."
                        if direction == "up"
                        else "This deserves watching before it starts to change the wider career picture."
                    ),
                    "evidence_key": "recent_form",
                    "supporting_values": {
                        "recent_metric_label": recent_metric_label,
                        "recent_metric_delta_pct": round(recent_metric_delta_pct, 2),
                        "recent_sample_size": recent_sample_size,
                    },
                }
            )
        if consistency_level == "ALTA":
            facts.append(
                {
                    "label": "career_is_stable",
                    "plain_fact": "Your level has stayed fairly steady across seasons.",
                    "strength": 0.72,
                    "why_it_matters": "This makes your career progress look more trustworthy.",
                    "evidence_key": "career_arc",
                    "supporting_values": {
                        "consistency_level": consistency_level,
                    },
                }
            )
        elif consistency_level == "BAJA":
            facts.append(
                {
                    "label": "career_swings_too_much",
                    "plain_fact": "Your level still changes too much from one period to another.",
                    "strength": 0.72,
                    "why_it_matters": "That makes it harder to turn good spells into lasting progress.",
                    "evidence_key": "career_arc",
                    "supporting_values": {
                        "consistency_level": consistency_level,
                    },
                }
            )

    if not facts and comparison:
        matches = _safe_int(comparison.get("matches"))
        if matches >= 10:
            goal_delta = _safe_float(comparison.get("goal_contributions_trend_pct"))
            facts.append(
                {
                    "label": "recent_form_checkpoint",
                    "plain_fact": "Your recent games give a useful checkpoint on where your form is going.",
                    "strength": min(1.0, abs(goal_delta) / 30.0),
                    "why_it_matters": "Short-term form can confirm or question the wider career trend.",
                    "evidence_key": "recent_form",
                    "supporting_values": {"goal_contributions_trend_pct": round(goal_delta, 2)},
                }
            )
    return facts[:3]


def _build_profile_groups(percentiles_data: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    strengths: List[Dict[str, Any]] = []
    limits: List[Dict[str, Any]] = []

    sorted_high = _sort_profile_items(percentiles_data, reverse=True)
    sorted_low = _sort_profile_items(percentiles_data, reverse=False)

    for item in sorted_high[:3]:
        if item["percentile"] < 55:
            continue
        strengths.append(
            {
                "metric": item["metric"],
                "percentile": item["percentile"],
                "importance": "high" if item["percentile"] >= 75 else "medium",
                "status": "stable" if item["percentile"] >= 70 else "emerging",
                "plain_fact": "This is one of the clearest parts of your game.",
                "evidence_key": "percentile_profile",
            }
        )

    for item in sorted_low[:3]:
        if item["percentile"] >= 50:
            continue
        limits.append(
            {
                "metric": item["metric"],
                "percentile": item["percentile"],
                "impact": "high" if item["percentile"] < 35 else "medium",
                "growth_cost": "limits role growth" if item["percentile"] < 35 else "holds back your next step",
                "plain_fact": "This part of your game is still holding back a bigger step.",
                "evidence_key": "percentile_profile",
            }
        )
    return strengths, limits


def _build_tension_facts(
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    development_priorities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    facts: List[Dict[str, Any]] = []
    coach_conf = (career_signals or {}).get("coach_confidence") or {}
    direction = str(coach_conf.get("direction") or "stable")
    latest_vs_average_pct = _safe_float(coach_conf.get("latest_vs_average_pct"))
    top_priority = (development_priorities or [None])[0] if development_priorities else None
    if direction == "up" and latest_vs_average_pct >= 10 and isinstance(top_priority, dict) and str(top_priority.get("action") or "") == "mejorar":
        facts.append(
            {
                "label": "minutes_up_but_profile_still_needs_work",
                "plain_fact": "You are playing more, but there is still a part of your game that needs work.",
                "severity": "medium",
                "why_it_matters": "More minutes help most when they come with a clear improvement in your game.",
                "evidence_key": "career_arc",
                "supporting_values": {
                    "latest_vs_average_pct": round(latest_vs_average_pct, 2),
                    "top_priority_metric": str(top_priority.get("metric") or ""),
                },
            }
        )

    momentum_score = _safe_int(career_phase_data.get("momentum_score"))
    phase = str(career_phase_data.get("career_phase") or "")
    if phase in {"building", "peak"} and momentum_score <= 2:
        facts.append(
            {
                "label": "good_window_but_not_enough_force",
                "plain_fact": "You are still in a good age window, but the current push is not strong enough yet.",
                "severity": "medium",
                "why_it_matters": "This is a period where stronger signs should start to show.",
                "evidence_key": "projection_outlook",
                "supporting_values": {"career_phase": phase, "momentum_score": momentum_score},
            }
        )
    return facts[:3]


def _build_lever_facts(
    development_priorities: List[Dict[str, Any]],
    career_signals: Dict[str, Any],
) -> List[Dict[str, Any]]:
    coach_conf = (career_signals or {}).get("coach_confidence") or {}
    role_direction = str(coach_conf.get("direction") or "stable")
    lever_facts: List[Dict[str, Any]] = []
    for item in (development_priorities or [])[:3]:
        if not isinstance(item, dict):
            continue
        metric = humanize_metric_name(item.get("metric") or "key area")
        action = str(item.get("action") or "mejorar")
        percentile = _safe_int(item.get("percentile"))
        impact = str(item.get("impact") or "medio")
        if action == "mejorar":
            why_now = _metric_why_now(metric, role_direction)
            why_it_matters = _metric_lever_body(metric)
            unlock_text = _metric_unlock_text(metric)
            lever_facts.append(
                {
                    "focus_area": f"improve {metric}",
                    "priority_score": 0.84 if impact == "alto" else 0.68,
                    "lever_kind": "growth",
                    "why_now": why_now,
                    "why_it_matters": why_it_matters,
                    "what_it_unlocks": unlock_text,
                    "evidence_key": "percentile_profile",
                    "support_text": _metric_support_text(metric, percentile),
                }
            )
        else:
            lever_facts.append(
                {
                    "focus_area": f"protect {metric}",
                    "priority_score": 0.55,
                    "lever_kind": "protection",
                    "why_now": "This is already helping your profile and is worth protecting.",
                    "why_it_matters": f"{metric} is one of the stronger parts of your game.",
                    "what_it_unlocks": "a more stable level and a clearer identity",
                    "evidence_key": "tactical_dna",
                }
            )
    return lever_facts


def _build_outlook_facts(career_phase_data: Dict[str, Any], career_signals: Dict[str, Any]) -> List[Dict[str, Any]]:
    resolution = dict(career_phase_data.get("progression_resolution") or {})
    mode = str(
        career_phase_data.get("recommended_phase")
        or resolution.get("recommended_phase")
        or "Find Consistency"
    )
    why_now = str(
        resolution.get("next_condition")
        or "The next stretch will decide whether this recommendation strengthens."
    )
    if mode == "Ambitious":
        plain_fact = "Your comparative level says it is reasonable to aim higher now."
        risk_condition = "If consistency drops or the gap to top-tier level widens, the push needs rechecking."
        evidence_key = "top_tier_gap"
    elif mode == "Keep Pushing":
        plain_fact = "The signs are moving the right way, but the case still needs more weight."
        risk_condition = "If role security softens again, the next step becomes harder to force."
        evidence_key = "league_positional_standing"
    elif mode == "Maintain Consistency":
        plain_fact = "The level is credible now, and the priority is proving it holds."
        risk_condition = "If the level swings too much, the recommendation will soften."
        evidence_key = "consistency_profile"
    else:
        plain_fact = "The next priority is making your level and role feel more reliable."
        risk_condition = "If the same instability continues, the bigger move conversation stays on hold."
        evidence_key = "team_context"

    if not str(why_now or "").strip() and mode == "Find Consistency":
        why_now = "Steadier minutes and more stable end-product are the clearest triggers for a stronger recommendation."

    return [
        {
            "mode": mode,
            "plain_fact": plain_fact,
            "why_now": why_now,
            "upgrade_condition": why_now,
            "risk_condition": risk_condition,
            "evidence_key": evidence_key,
        }
    ]


def _build_evidence_facts(
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    profile_strengths: List[Dict[str, Any]],
    profile_limits: List[Dict[str, Any]],
    lever_facts: List[Dict[str, Any]],
    outlook_facts: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    recent_windows = data.get("recent_form_windows") or {}
    comparison = (recent_windows.get("comparisons") or {}).get("last5_vs_previous5") or {}
    coach_conf = (career_signals or {}).get("coach_confidence") or {}
    features = career_phase_data.get("progression_features")
    scorecard = career_phase_data.get("comparative_scorecard")

    season_minutes: List[int] = []
    history_df = data.get("history_df", pd.DataFrame())
    if isinstance(history_df, pd.DataFrame) and not history_df.empty:
        minutes_col = next((col for col in history_df.columns if "minute" in str(col).lower()), None)
        if minutes_col:
            season_minutes = [_safe_int(value) for value in history_df[minutes_col].tolist()]

    latest_metric_label = str(getattr(features, "recent_metric_label", "") or "") if features is not None else ""
    latest_metric_delta_pct = _safe_float(getattr(features, "recent_metric_delta_pct", 0.0)) if features is not None else 0.0
    team_positional = getattr(scorecard, "team_positional", None)
    team_overall = getattr(scorecard, "team_overall", None)
    league_positional = getattr(scorecard, "league_positional", None)
    league_overall = getattr(scorecard, "league_overall", None)

    def _serialize_dimension(value: Any) -> Dict[str, Any]:
        if value is None:
            return {}
        return asdict(value) if is_dataclass(value) else dict(value)

    def _context_row(key: str, label: str, dimension: Any) -> Dict[str, Any]:
        payload = _serialize_dimension(dimension)
        if not payload:
            return {"key": key, "label": label, "available": False}
        return {
            "key": key,
            "label": label,
            "available": bool(payload.get("available", True)),
            "sample_size": _safe_int(payload.get("sample_size")),
            "player_value": round(_safe_float(payload.get("player_value")), 2),
            "average_value": round(_safe_float(payload.get("average_value")), 2),
            "top_tier_value": round(_safe_float(payload.get("top_tier_value")), 2),
            "percentile": round(_safe_float(payload.get("percentile")), 1),
            "average_gap": round(_safe_float(payload.get("average_gap")), 2),
            "top_tier_gap": round(_safe_float(payload.get("top_tier_gap")), 2),
            "status": str(payload.get("status") or ""),
        }

    comparison_rows = [
        _context_row("team_positional_rank", "Team Role Group", team_positional),
        _context_row("team_global_rank", "Team Overall", team_overall),
        _context_row("league_positional_standing", "League Role Group", league_positional),
        _context_row("league_global_standing", "League Overall", league_overall),
    ]
    context_scores = [
        {
            "key": "role_security",
            "label": "Role Security",
            "score": round(float(getattr(scorecard, "role_security", 0.0) or 0.0), 1),
            "read": str(coach_conf.get("label") or "Role context"),
        },
        {
            "key": "consistency_score",
            "label": "Consistency",
            "score": round(float(getattr(scorecard, "consistency_score", 0.0) or 0.0), 1),
            "read": str(getattr(scorecard, "consistency_label", "") or ""),
        },
        {
            "key": "career_timing_score",
            "label": "Career Timing",
            "score": round(float(getattr(scorecard, "career_timing_score", 0.0) or 0.0), 1),
            "read": str(getattr(scorecard, "career_timing_label", "") or ""),
        },
        {
            "key": "top_tier_gap_score",
            "label": "Top-Tier Gap",
            "score": round(float(getattr(scorecard, "top_tier_gap_score", 0.0) or 0.0), 1),
            "read": "closer is stronger",
        },
    ]
    benchmark_metric = humanize_metric_name(
        str(getattr(features, "primary_metric", "") or data.get("position_main") or "current benchmark")
    )

    return {
        "minutes_trend": {
            "headline_fact": "Your role is moving up again." if str(coach_conf.get("direction") or "") == "up" else "Your role needs watching.",
            "season_minutes": season_minutes,
            "latest_vs_average_pct": round(_safe_float(coach_conf.get("latest_vs_average_pct")), 2),
            "regular_seasons": _safe_int(coach_conf.get("regular_seasons")),
            "role_security_level": "medium-high" if _safe_float(coach_conf.get("season_regular_share")) >= 0.6 else "medium",
        },
        "recent_form": {
            "headline_fact": "Your recent games give a useful checkpoint on your form.",
            "goal_contributions_trend_pct": round(_safe_float(comparison.get("goal_contributions_trend_pct")), 2),
            "minutes_trend_pct": round(_safe_float(comparison.get("minutes_trend_pct")), 2),
            "recent_metric_label": latest_metric_label,
            "recent_metric_delta_pct": round(latest_metric_delta_pct, 2),
        },
        "career_arc": {
            "headline_fact": "The bigger picture matters more than one short spell.",
            "career_phase": str(career_phase_data.get("career_phase") or ""),
            "momentum_score": _safe_int(career_phase_data.get("momentum_score")),
            "career_minutes": _safe_int(data.get("minutes_played")),
            "season_count": _history_season_count(data),
        },
        "career_trend": {
            "headline_fact": "The trend across seasons shows whether your level is really holding or shifting.",
            "career_phase": str(career_phase_data.get("career_phase") or ""),
            "momentum_score": _safe_int(career_phase_data.get("momentum_score")),
            "season_count": _history_season_count(data),
            "consistency_level": str(((career_signals or {}).get("consistency_score") or {}).get("level") or "MODERADA"),
            "primary_metric": str(getattr(features, "primary_metric", "") or "") if features is not None else "",
            "primary_metric_trend_pct": round(_safe_float(getattr(features, "primary_metric_trend_pct", 0.0)), 2) if features is not None else 0.0,
        },
        "career_phase_resolution": {
            "headline_fact": "Your current phase is being read from age, momentum, role trend, and supporting signals.",
            "career_phase": str(career_phase_data.get("career_phase") or ""),
            "momentum_score": _safe_int(career_phase_data.get("momentum_score")),
            "age": _safe_int(career_phase_data.get("age") or data.get("age")),
            "peak_range": list(career_phase_data.get("peak_range") or []),
            "transfer_window_quality": str(((career_signals or {}).get("transfer_window") or {}).get("quality") or ""),
            "consistency_level": str(((career_signals or {}).get("consistency_score") or {}).get("level") or "MODERADA"),
            "progression_resolution": dict(career_phase_data.get("progression_resolution") or {}),
        },
        "career_value_summary": {
            "headline_fact": "Your career weight comes from how much repeatable work is already there.",
            "season_count": _history_season_count(data),
            "career_minutes": _safe_int(data.get("minutes_played")),
            "career_goals": _safe_int(data.get("goals")),
            "career_assists": _safe_int(data.get("assists")),
            "consistency_level": str(((career_signals or {}).get("consistency_score") or {}).get("level") or "MODERADA"),
        },
        "percentile_profile": {
            "headline_fact": "Some parts of your game already help you more than others.",
            "top_strengths": [item["metric"] for item in profile_strengths[:3]],
            "top_limits": [item["metric"] for item in profile_limits[:3]],
            "main_limit": str(profile_limits[0]["metric"]) if profile_limits else "",
            "main_limit_percentile": _safe_int(profile_limits[0]["percentile"]) if profile_limits else 0,
            "main_lever": str(lever_facts[0]["focus_area"]) if lever_facts else "",
        },
        "projection_outlook": {
            "headline_fact": str(outlook_facts[0]["plain_fact"]) if outlook_facts else "",
            "career_phase": str(career_phase_data.get("career_phase") or ""),
            "momentum_score": _safe_int(career_phase_data.get("momentum_score")),
            "transfer_window_quality": str(((career_signals or {}).get("transfer_window") or {}).get("quality") or ""),
        },
        "team_positional_rank": {
            "headline_fact": "This shows where you sit against teammates in your role.",
            "dimension": _serialize_dimension(team_positional),
        },
        "team_global_rank": {
            "headline_fact": "This shows where you sit in the wider squad picture.",
            "dimension": _serialize_dimension(team_overall),
        },
        "league_positional_standing": {
            "headline_fact": "This shows your level against league peers in your role.",
            "dimension": _serialize_dimension(league_positional),
        },
        "league_global_standing": {
            "headline_fact": "This shows your level against the full league population.",
            "dimension": _serialize_dimension(league_overall),
        },
        "top_tier_gap": {
            "headline_fact": "This shows how far the profile still is from top-tier level.",
            "top_tier_gap_score": round(float(getattr(scorecard, "top_tier_gap_score", 0.0) or 0.0), 1),
        },
        "consistency_profile": {
            "headline_fact": "This shows whether your level is holding or still swinging.",
            "consistency_score": round(float(getattr(scorecard, "consistency_score", 0.0) or 0.0), 1),
            "consistency_label": str(getattr(scorecard, "consistency_label", "") or ""),
        },
        "team_context": {
            "headline_fact": "This read combines comparative standing with role security and consistency.",
            "team_context_score": round(float(getattr(scorecard, "team_context_score", 0.0) or 0.0), 1),
            "team_context_label": str(getattr(scorecard, "team_context_label", "") or ""),
            "role_security": round(float(getattr(scorecard, "role_security", 0.0) or 0.0), 1),
            "benchmark_metric": benchmark_metric,
            "comparison_rows": comparison_rows,
            "context_scores": context_scores,
        },
        "career_timing_context": {
            "headline_fact": "This shows where the current age and momentum sit in the career cycle.",
            "career_timing_score": round(float(getattr(scorecard, "career_timing_score", 0.0) or 0.0), 1),
            "career_timing_label": str(getattr(scorecard, "career_timing_label", "") or ""),
            "peak_range": list(career_phase_data.get("peak_range") or []),
            "age": _safe_int(career_phase_data.get("age") or data.get("age")),
        },
        "similarity_profiles": {
            "headline_fact": "The closest profiles show where you already fit and where you still need more weight.",
            "similar_players": (data.get("similar_players_meta") or {}).get("similar_players") or [],
        },
        "tactical_dna": {
            "headline_fact": "Your profile identity comes from the strongest parts of your game.",
            "cluster_label": str(data.get("cluster_label") or ""),
            "strength_traits": [item["metric"] for item in profile_strengths[:3]],
        },
    }


def build_career_intelligence_facts(
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    development_priorities: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Builds the shared deterministic career-facts contract for dashboard and evidence AI."""
    development_priorities = development_priorities or []
    percentiles_data = data.get("percentiles_data") or {}
    profile_strengths, profile_limits = _build_profile_groups(percentiles_data)
    role_facts = _build_role_facts(career_signals)
    pattern_facts = _build_pattern_facts(data, career_phase_data, career_signals)
    tension_facts = _build_tension_facts(career_phase_data, career_signals, development_priorities)
    lever_facts = _build_lever_facts(development_priorities, career_signals)
    outlook_facts = _build_outlook_facts(career_phase_data, career_signals)

    facts = {
        "player_context": {
            "player_name": str(data.get("player_name") or ""),
            "position_group": str(data.get("pos_group") or ""),
            "position_main": str(data.get("position_main") or ""),
            "team_name": str(data.get("team_name") or ""),
            "age": _safe_int(career_phase_data.get("age") or data.get("age")),
            "career_minutes": _safe_int(data.get("minutes_played")),
            "season_count": _history_season_count(data),
        },
        "career_summary": {
            "career_phase": str(career_phase_data.get("career_phase") or "unknown"),
            "recommended_phase": str(career_phase_data.get("recommended_phase") or "Find Consistency"),
            "momentum_score": _safe_int(career_phase_data.get("momentum_score")),
            "overall_direction": str(((career_signals or {}).get("coach_confidence") or {}).get("direction") or "stable"),
            "career_weight": "solid" if _safe_int(data.get("minutes_played")) >= 4000 else "building",
            "latest_season": _latest_season_label(data),
            "latest_minutes": _safe_int(((career_signals or {}).get("coach_confidence") or {}).get("latest_minutes")),
            "minutes_trend_pct": round(_safe_float(getattr(career_phase_data.get("progression_features"), "minutes_trend_pct", 0.0)), 2) if career_phase_data.get("progression_features") is not None else 0.0,
            "primary_metric": str(getattr(career_phase_data.get("progression_features"), "primary_metric", "") or "") if career_phase_data.get("progression_features") is not None else "",
            "primary_metric_trend_pct": round(_safe_float(getattr(career_phase_data.get("progression_features"), "primary_metric_trend_pct", 0.0)), 2) if career_phase_data.get("progression_features") is not None else 0.0,
            "consistency_level": str(((career_signals or {}).get("consistency_score") or {}).get("level") or "MODERADA"),
            "transfer_window_quality": str(((career_signals or {}).get("transfer_window") or {}).get("quality") or "MODERADA"),
            "top_tier_gap_score": round(float(getattr(career_phase_data.get("comparative_scorecard"), "top_tier_gap_score", 0.0) or 0.0), 1),
        },
        "role_facts": role_facts,
        "pattern_facts": pattern_facts,
        "profile_strengths": profile_strengths,
        "profile_limits": profile_limits,
        "tension_facts": tension_facts,
        "lever_facts": lever_facts,
        "outlook_facts": outlook_facts,
        "evidence_facts": _build_evidence_facts(
            data,
            career_phase_data,
            career_signals,
            profile_strengths,
            profile_limits,
            lever_facts,
            outlook_facts,
        ),
    }
    for evidence_key in list(facts["evidence_facts"].keys()):
        normalized = normalize_evidence_key(evidence_key)
        if normalized != evidence_key:
            facts["evidence_facts"][normalized] = facts["evidence_facts"].pop(evidence_key)
    return facts
