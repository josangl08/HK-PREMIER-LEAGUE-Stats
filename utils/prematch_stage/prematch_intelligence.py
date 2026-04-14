# ABOUTME: Prematch-stage intelligence integration surface for hot artifact contracts and deterministic context assembly.
# ABOUTME: Wraps existing prematch helpers into JSON-safe payloads so stage intelligence can extend beyond season without duplicating render logic.

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping

from utils.agents.stage_agents.prematch_agent import PrematchStageAgent
from utils.app_context import get_hong_kong_data_manager
from utils.intelligence.discovery_contracts import serialize_stage_analysis
from utils.intelligence.freshness_manager import FRESHNESS_HOT, FRESHNESS_WARM
from utils.stage_helpers import (
    _get_head_to_head_summary,
    _get_opponent_rivals,
    _get_recent_form_summary,
)

PREMATCH_FIXTURE_CONTEXT_ARTIFACT = "prematch_fixture_context"
PREMATCH_RECENT_FORM_CONTEXT_ARTIFACT = "prematch_recent_form_context"
PREMATCH_HEAD_TO_HEAD_CONTEXT_ARTIFACT = "prematch_head_to_head_context"
PREMATCH_RIVAL_PROFILES_CONTEXT_ARTIFACT = "prematch_rival_profiles_context"
PREMATCH_OPPONENT_THREAT_CONTEXT_ARTIFACT = "prematch_opponent_threat_context"
PREMATCH_GAME_PLAN_CONTEXT_ARTIFACT = "prematch_game_plan_context"

PREMATCH_ARTIFACT_TYPES = [
    PREMATCH_FIXTURE_CONTEXT_ARTIFACT,
    PREMATCH_RECENT_FORM_CONTEXT_ARTIFACT,
    PREMATCH_HEAD_TO_HEAD_CONTEXT_ARTIFACT,
    PREMATCH_RIVAL_PROFILES_CONTEXT_ARTIFACT,
    PREMATCH_OPPONENT_THREAT_CONTEXT_ARTIFACT,
    PREMATCH_GAME_PLAN_CONTEXT_ARTIFACT,
]

PREMATCH_FRESHNESS_POLICY = {
    PREMATCH_FIXTURE_CONTEXT_ARTIFACT: {"regime": FRESHNESS_HOT, "ttl_hours": 3},
    PREMATCH_RECENT_FORM_CONTEXT_ARTIFACT: {"regime": FRESHNESS_HOT, "ttl_hours": 3},
    PREMATCH_HEAD_TO_HEAD_CONTEXT_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 12},
    PREMATCH_RIVAL_PROFILES_CONTEXT_ARTIFACT: {"regime": FRESHNESS_HOT, "ttl_hours": 3},
    PREMATCH_OPPONENT_THREAT_CONTEXT_ARTIFACT: {"regime": FRESHNESS_HOT, "ttl_hours": 3},
    PREMATCH_GAME_PLAN_CONTEXT_ARTIFACT: {"regime": FRESHNESS_HOT, "ttl_hours": 3},
}


def _safe_scalar(value: Any) -> Any:
    """Convert nested values into JSON-safe primitives."""
    if isinstance(value, dict):
        return {str(key): _safe_scalar(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_scalar(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _safe_mapping(mapping: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Normalize a mapping into JSON-safe values."""
    if not mapping:
        return {}
    return {str(key): _safe_scalar(value) for key, value in mapping.items()}


def _safe_records(records: List[Mapping[str, Any]] | None) -> List[Dict[str, Any]]:
    """Normalize a list of records into JSON-safe shallow dicts."""
    return [_safe_mapping(record) for record in (records or [])]


def build_prematch_artifact_scope(player_id: str, fixture_id: str) -> Dict[str, str]:
    """Return the canonical prematch artifact scope."""
    return {
        "player_id": str(player_id or ""),
        "fixture_id": str(fixture_id or ""),
        "stage": "prematch",
    }


def build_prematch_fixture_context_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build the fixture-context payload from the prematch stage payload."""
    keys = [
        "fixture_id",
        "opponent",
        "home_team",
        "away_team",
        "competition",
        "kickoff_display",
        "stadium",
        "broadcast_type",
        "streaming_url",
        "has_var",
        "is_tv",
        "player_name",
        "player_pos_group",
        "player_position_main",
        "player_current_role",
    ]
    return {
        str(key): _safe_scalar(payload.get(key))
        for key in keys
    }


def build_prematch_recent_form_context_payload(player_id: str) -> Dict[str, Any]:
    """Build the recent-form payload from the existing prematch helper."""
    return deepcopy(_safe_mapping(_get_recent_form_summary(player_id)))


def build_prematch_head_to_head_context_payload(player_id: str, opponent_team: str) -> Dict[str, Any]:
    """Build the head-to-head payload from the existing prematch helper."""
    matches = _get_head_to_head_summary(player_id, opponent_team)
    return {
        "matches": deepcopy(_safe_records(matches)),
        "meeting_count": len(matches),
    }


def build_prematch_rival_profiles_context_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build direct-rival scouting cards for the active prematch scope."""
    opponent_team = str(payload.get("opponent") or "")
    player_pos_group = str(payload.get("player_pos_group") or "Midfielder")
    player_position_main = str(payload.get("player_current_role") or payload.get("player_position_main") or "")
    try:
        data_manager = get_hong_kong_data_manager()
        rivals = _get_opponent_rivals(
            opponent_team,
            player_pos_group,
            player_position_main,
            data_manager,
        )
    except Exception:
        rivals = []
    primary_rival = dict(rivals[0] or {}) if rivals else {}
    secondary_rivals = deepcopy(_safe_records(rivals[1:])) if len(rivals) > 1 else []
    primary_score = float(primary_rival.get("rival_score", 0.0) or 0.0)
    secondary_score = float((secondary_rivals[0] or {}).get("rival_score", 0.0) or 0.0) if secondary_rivals else 0.0
    score_gap = max(0.0, primary_score - secondary_score)
    matchup_confidence = "high" if primary_score >= 18.0 and score_gap >= 4.0 else "medium" if primary_score >= 10.0 else "low"
    matchup_confidence_score = 0.82 if matchup_confidence == "high" else 0.66 if matchup_confidence == "medium" else 0.48
    return {
        "opponent": opponent_team,
        "player_pos_group": player_pos_group,
        "player_position_main": player_position_main,
        "primary_rival": deepcopy(_safe_mapping(primary_rival)),
        "secondary_rivals": secondary_rivals,
        "matchup_confidence": matchup_confidence,
        "matchup_confidence_score": matchup_confidence_score,
        "selection_reason": str(primary_rival.get("selection_reason") or ""),
        "primary_vs_secondary_gap": score_gap,
        "rivals": deepcopy(_safe_records(rivals)),
        "rival_count": len(rivals),
    }


def build_prematch_opponent_threat_context_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build a lightweight opponent-threat payload from existing team statistics."""
    opponent_team = str(payload.get("opponent") or "")
    top_scorer_name = ""
    top_scorer_goals = 0
    top_assister_name = ""
    top_assister_assists = 0
    most_played_name = ""
    most_played_minutes = 0
    most_valuable_name = ""
    most_valuable_value = 0
    try:
        data_manager = get_hong_kong_data_manager()
        team_stats = data_manager.get_team_statistics(opponent_team) if data_manager and opponent_team else {}
        top_players = (team_stats.get("top_players", {}) or {})
        top_scorers = top_players.get("top_scorers", []) or []
        if top_scorers:
            top_scorer_name = str(top_scorers[0].get("name") or "")
            top_scorer_goals = int(top_scorers[0].get("goals", 0) or 0)
        top_assister = dict(top_players.get("top_assister") or {})
        if top_assister:
            top_assister_name = str(top_assister.get("name") or "")
            top_assister_assists = int(top_assister.get("assists", 0) or 0)
        most_played = dict(top_players.get("most_played") or {})
        if most_played:
            most_played_name = str(most_played.get("name") or "")
            most_played_minutes = int(most_played.get("minutes", 0) or 0)
        most_valuable = dict(top_players.get("most_valuable") or {})
        if most_valuable:
            most_valuable_name = str(most_valuable.get("name") or "")
            most_valuable_value = int(most_valuable.get("value", 0) or 0)
    except Exception:
        top_scorer_name = ""
        top_scorer_goals = 0
        top_assister_name = ""
        top_assister_assists = 0
        most_played_name = ""
        most_played_minutes = 0
        most_valuable_name = ""
        most_valuable_value = 0
    return {
        "opponent": opponent_team,
        "top_scorer": {
            "name": top_scorer_name,
            "goals": top_scorer_goals,
        },
        "top_scorer_name": top_scorer_name,
        "top_scorer_goals": top_scorer_goals,
        "top_assister": {
            "name": top_assister_name,
            "assists": top_assister_assists,
        },
        "top_assister_name": top_assister_name,
        "top_assister_assists": top_assister_assists,
        "most_played": {
            "name": most_played_name,
            "minutes": most_played_minutes,
        },
        "most_played_name": most_played_name,
        "most_played_minutes": most_played_minutes,
        "most_valuable": {
            "name": most_valuable_name,
            "value": most_valuable_value,
        },
        "most_valuable_name": most_valuable_name,
        "most_valuable_value": most_valuable_value,
        "named_threats": [
            threat
            for threat in [
                {"type": "scorer", "name": top_scorer_name, "value": top_scorer_goals},
                {"type": "creator", "name": top_assister_name, "value": top_assister_assists},
                {"type": "ever_present", "name": most_played_name, "value": most_played_minutes},
            ]
            if threat["name"]
        ],
        "has_named_threat": bool(top_scorer_name),
    }


def build_prematch_game_plan_context_payload(
    fixture_payload: Dict[str, Any],
    recent_form_payload: Dict[str, Any],
    head_to_head_payload: Dict[str, Any],
    rival_profiles_payload: Dict[str, Any],
    opponent_threat_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a lightweight deterministic prematch game-plan summary artifact."""
    opponent = str(fixture_payload.get("opponent") or "")
    goals_total = int(recent_form_payload.get("goals_total", 0) or 0)
    assists_total = int(recent_form_payload.get("assists_total", 0) or 0)
    meeting_count = int(head_to_head_payload.get("meeting_count", 0) or 0)
    rivals = list(rival_profiles_payload.get("rivals") or [])
    main_rival = dict(rivals[0] or {}) if rivals else {}
    rival_name = str(main_rival.get("name") or "")
    rival_weakness = str(main_rival.get("weakness_text") or "").strip()
    rival_strength = str(main_rival.get("strength_text") or "").strip()
    matchup_confidence = str(rival_profiles_payload.get("matchup_confidence") or "low")
    top_scorer_name = str(opponent_threat_payload.get("top_scorer_name") or "")
    top_scorer_goals = int(opponent_threat_payload.get("top_scorer_goals", 0) or 0)
    top_assister_name = str(opponent_threat_payload.get("top_assister_name") or "")
    assist_bias = assists_total > goals_total
    if rival_name and rival_weakness:
        plan_headline = f"Target {rival_name} early and force the duel into the phase where they {rival_weakness.lower()}."
    elif top_scorer_name:
        plan_headline = f"Control the first action around {top_scorer_name} and attack quickly once their front line is broken."
    else:
        plan_headline = (
            f"Attack {opponent} through quick release combinations."
            if assist_bias else
            f"Attack the box early against {opponent} once the first line is broken."
        )
    return {
        "opponent": opponent,
        "confidence": "high" if meeting_count >= 3 else "medium" if meeting_count >= 1 else "limited",
        "plan_headline": plan_headline,
        "recent_form_goals": goals_total,
        "recent_form_assists": assists_total,
        "meeting_count": meeting_count,
        "main_rival_name": rival_name,
        "matchup_confidence": matchup_confidence,
        "main_rival_strength": rival_strength,
        "main_rival_weakness": rival_weakness,
        "top_scorer_name": top_scorer_name,
        "top_scorer_goals": top_scorer_goals,
        "top_assister_name": top_assister_name,
        "assist_bias": assist_bias,
    }


def build_prematch_artifact_payloads(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build JSON-safe deterministic payloads for the prematch stage artifacts."""
    player_id = str(payload.get("player_id") or "")
    opponent = str(payload.get("opponent") or "")
    fixture_payload = build_prematch_fixture_context_payload(payload)
    recent_form_payload = build_prematch_recent_form_context_payload(player_id)
    head_to_head_payload = build_prematch_head_to_head_context_payload(player_id, opponent)
    rival_profiles_payload = build_prematch_rival_profiles_context_payload(payload)
    opponent_threat_payload = build_prematch_opponent_threat_context_payload(payload)

    return {
        PREMATCH_FIXTURE_CONTEXT_ARTIFACT: fixture_payload,
        PREMATCH_RECENT_FORM_CONTEXT_ARTIFACT: recent_form_payload,
        PREMATCH_HEAD_TO_HEAD_CONTEXT_ARTIFACT: head_to_head_payload,
        PREMATCH_RIVAL_PROFILES_CONTEXT_ARTIFACT: rival_profiles_payload,
        PREMATCH_OPPONENT_THREAT_CONTEXT_ARTIFACT: opponent_threat_payload,
        PREMATCH_GAME_PLAN_CONTEXT_ARTIFACT: build_prematch_game_plan_context_payload(
            fixture_payload,
            recent_form_payload,
            head_to_head_payload,
            rival_profiles_payload,
            opponent_threat_payload,
        ),
    }


def build_prematch_stage_analysis_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build the shared stage-analysis payload for prematch from deterministic artifacts."""
    scope = build_prematch_artifact_scope(
        str(payload.get("player_id") or ""),
        str(payload.get("fixture_id") or ""),
    )
    artifacts = {
        artifact_type: {"payload": artifact_payload}
        for artifact_type, artifact_payload in build_prematch_artifact_payloads(payload).items()
    }
    analysis = PrematchStageAgent().analyze(scope=scope, artifacts=artifacts, session_memory=None)
    return serialize_stage_analysis(analysis)
