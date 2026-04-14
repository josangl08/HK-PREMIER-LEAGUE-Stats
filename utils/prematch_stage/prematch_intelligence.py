# ABOUTME: Prematch-stage intelligence integration surface for hot artifact contracts and deterministic context assembly.
# ABOUTME: Wraps existing prematch helpers into JSON-safe payloads so stage intelligence can extend beyond season without duplicating render logic.

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping

from utils.agents.stage_agents.prematch_agent import PrematchStageAgent
from utils.intelligence.discovery_contracts import serialize_stage_analysis
from utils.intelligence.freshness_manager import FRESHNESS_HOT, FRESHNESS_WARM
from utils.stage_helpers import (
    _get_head_to_head_summary,
    _get_recent_form_summary,
)

PREMATCH_FIXTURE_CONTEXT_ARTIFACT = "prematch_fixture_context"
PREMATCH_RECENT_FORM_CONTEXT_ARTIFACT = "prematch_recent_form_context"
PREMATCH_HEAD_TO_HEAD_CONTEXT_ARTIFACT = "prematch_head_to_head_context"
PREMATCH_GAME_PLAN_CONTEXT_ARTIFACT = "prematch_game_plan_context"

PREMATCH_ARTIFACT_TYPES = [
    PREMATCH_FIXTURE_CONTEXT_ARTIFACT,
    PREMATCH_RECENT_FORM_CONTEXT_ARTIFACT,
    PREMATCH_HEAD_TO_HEAD_CONTEXT_ARTIFACT,
    PREMATCH_GAME_PLAN_CONTEXT_ARTIFACT,
]

PREMATCH_FRESHNESS_POLICY = {
    PREMATCH_FIXTURE_CONTEXT_ARTIFACT: {"regime": FRESHNESS_HOT, "ttl_hours": 3},
    PREMATCH_RECENT_FORM_CONTEXT_ARTIFACT: {"regime": FRESHNESS_HOT, "ttl_hours": 3},
    PREMATCH_HEAD_TO_HEAD_CONTEXT_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 12},
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


def build_prematch_game_plan_context_payload(
    fixture_payload: Dict[str, Any],
    recent_form_payload: Dict[str, Any],
    head_to_head_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a lightweight deterministic prematch game-plan summary artifact."""
    opponent = str(fixture_payload.get("opponent") or "")
    goals_total = int(recent_form_payload.get("goals_total", 0) or 0)
    assists_total = int(recent_form_payload.get("assists_total", 0) or 0)
    meeting_count = int(head_to_head_payload.get("meeting_count", 0) or 0)
    assist_bias = assists_total > goals_total
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
    }


def build_prematch_artifact_payloads(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build JSON-safe deterministic payloads for the prematch stage artifacts."""
    player_id = str(payload.get("player_id") or "")
    opponent = str(payload.get("opponent") or "")
    fixture_payload = build_prematch_fixture_context_payload(payload)
    recent_form_payload = build_prematch_recent_form_context_payload(player_id)
    head_to_head_payload = build_prematch_head_to_head_context_payload(player_id, opponent)

    return {
        PREMATCH_FIXTURE_CONTEXT_ARTIFACT: fixture_payload,
        PREMATCH_RECENT_FORM_CONTEXT_ARTIFACT: recent_form_payload,
        PREMATCH_HEAD_TO_HEAD_CONTEXT_ARTIFACT: head_to_head_payload,
        PREMATCH_GAME_PLAN_CONTEXT_ARTIFACT: build_prematch_game_plan_context_payload(
            fixture_payload,
            recent_form_payload,
            head_to_head_payload,
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
