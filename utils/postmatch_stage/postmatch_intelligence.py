# ABOUTME: Postmatch-stage intelligence integration surface for recent-match artifact contracts and deterministic payload assembly.
# ABOUTME: Wraps existing postmatch helpers into JSON-safe artifacts so shared stage orchestration can reuse match-level intelligence without UI coupling.

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Mapping

from utils.agents.stage_agents.postmatch_agent import PostmatchStageAgent
from utils.domain_ai.postmatch_ai import get_postmatch_payloads
from utils.intelligence.discovery_contracts import serialize_stage_analysis
from utils.intelligence.freshness_manager import FRESHNESS_HOT, FRESHNESS_WARM

POSTMATCH_MATCH_CONTEXT_ARTIFACT = "postmatch_match_context"
POSTMATCH_PERFORMANCE_CONTEXT_ARTIFACT = "postmatch_performance_context"
POSTMATCH_REFLECTION_PAYLOADS_ARTIFACT = "postmatch_reflection_payloads"
POSTMATCH_OVERLAY_CANDIDATES_ARTIFACT = "postmatch_overlay_candidates"

POSTMATCH_ARTIFACT_TYPES = [
    POSTMATCH_MATCH_CONTEXT_ARTIFACT,
    POSTMATCH_PERFORMANCE_CONTEXT_ARTIFACT,
    POSTMATCH_REFLECTION_PAYLOADS_ARTIFACT,
    POSTMATCH_OVERLAY_CANDIDATES_ARTIFACT,
]

POSTMATCH_FRESHNESS_POLICY = {
    POSTMATCH_MATCH_CONTEXT_ARTIFACT: {"regime": FRESHNESS_HOT, "ttl_hours": 12},
    POSTMATCH_PERFORMANCE_CONTEXT_ARTIFACT: {"regime": FRESHNESS_HOT, "ttl_hours": 12},
    POSTMATCH_REFLECTION_PAYLOADS_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 24},
    POSTMATCH_OVERLAY_CANDIDATES_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 24},
}


def _safe_scalar(value: Any) -> Any:
    """Convert nested values into JSON-safe primitives."""
    if is_dataclass(value):
        return _safe_scalar(asdict(value))
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


def _safe_records(records: List[Any] | None) -> List[Dict[str, Any]]:
    """Normalize a list of records or dataclasses into JSON-safe shallow dicts."""
    normalized: List[Dict[str, Any]] = []
    for record in records or []:
        if is_dataclass(record):
            normalized.append(_safe_mapping(asdict(record)))
            continue
        if isinstance(record, dict):
            normalized.append(_safe_mapping(record))
            continue
        normalized.append({"value": _safe_scalar(record)})
    return normalized


def build_postmatch_artifact_scope(player_id: str, match_id: str) -> Dict[str, str]:
    """Return the canonical postmatch artifact scope."""
    return {
        "player_id": str(player_id or ""),
        "match_id": str(match_id or ""),
        "stage": "postmatch",
    }


def build_postmatch_match_context_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build the durable postmatch match-context payload from the stage payload."""
    keys = [
        "match_id",
        "fixture_id",
        "opponent",
        "home_team",
        "away_team",
        "competition",
        "kickoff_display",
        "date",
        "stadium",
        "result",
        "rating",
    ]
    return {
        str(key): _safe_scalar(payload.get(key))
        for key in keys
    }


def build_postmatch_performance_context_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build the player-performance context payload for postmatch refresh decisions."""
    player_stats = _safe_mapping(payload.get("player_stats") or {})
    performance_stats = _safe_mapping(player_stats.get("performance_stats") or {})
    match_stats = _safe_mapping(payload.get("match_stats") or {})
    recent_ratings = [_safe_scalar(item) for item in list(payload.get("recent_ratings") or [])[:5]]
    recent_contributions = [_safe_scalar(item) for item in list(payload.get("recent_contributions") or [])[:5]]

    keys = [
        "player_id",
        "position",
        "minutes_played",
        "goals",
        "assists",
        "yellow_cards",
        "red_cards",
        "started",
        "subbed_in",
        "subbed_out",
        "own_goals",
        "absence_reason",
    ]
    performance_payload = {
        str(key): _safe_scalar(payload.get(key))
        for key in keys
    }
    performance_payload["player_stats"] = player_stats
    performance_payload["performance_stats"] = performance_stats
    performance_payload["match_stats"] = match_stats
    performance_payload["recent_ratings"] = recent_ratings
    performance_payload["recent_contributions"] = recent_contributions
    return performance_payload


def build_postmatch_reflection_payloads_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build reflective postmatch payloads from the deterministic-first domain AI entrypoint."""
    context = {
        "match_context": build_postmatch_match_context_payload(payload),
        "performance_context": build_postmatch_performance_context_payload(payload),
    }
    reflections = get_postmatch_payloads(context, allow_llm_synthesis=False)
    normalized_reflections = _safe_records(reflections)
    return {
        "payloads": deepcopy(normalized_reflections),
        "payload_count": len(normalized_reflections),
        "selected_payload": deepcopy(normalized_reflections[0]) if normalized_reflections else None,
    }


def build_postmatch_overlay_candidates_payload(
    match_context_payload: Dict[str, Any],
    performance_context_payload: Dict[str, Any],
    reflection_payloads_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Build lightweight postmatch overlay candidates from reflective payloads."""
    selected_payload = deepcopy(reflection_payloads_payload.get("selected_payload"))
    candidates: List[Dict[str, Any]] = []
    if selected_payload:
        candidates.append(
            {
                "candidate_type": "postmatch_reflection",
                "headline": selected_payload.get("label"),
                "body": selected_payload.get("body"),
                "support": selected_payload.get("support"),
                "confidence": selected_payload.get("confidence"),
                "evidence_key": selected_payload.get("evidence_key"),
                "emphasis": selected_payload.get("emphasis"),
                "match_result": match_context_payload.get("result"),
                "minutes_played": performance_context_payload.get("minutes_played"),
            }
        )
    return {
        "candidates": candidates,
        "candidate_count": len(candidates),
        "selected_candidate": deepcopy(candidates[0]) if candidates else None,
    }


def build_postmatch_artifact_payloads(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build JSON-safe deterministic payloads for the postmatch stage artifacts."""
    match_context_payload = build_postmatch_match_context_payload(payload)
    performance_context_payload = build_postmatch_performance_context_payload(payload)
    reflection_payloads_payload = build_postmatch_reflection_payloads_payload(payload)
    overlay_candidates_payload = build_postmatch_overlay_candidates_payload(
        match_context_payload,
        performance_context_payload,
        reflection_payloads_payload,
    )
    return {
        POSTMATCH_MATCH_CONTEXT_ARTIFACT: match_context_payload,
        POSTMATCH_PERFORMANCE_CONTEXT_ARTIFACT: performance_context_payload,
        POSTMATCH_REFLECTION_PAYLOADS_ARTIFACT: reflection_payloads_payload,
        POSTMATCH_OVERLAY_CANDIDATES_ARTIFACT: overlay_candidates_payload,
    }


def build_postmatch_stage_analysis_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build the shared stage-analysis payload for postmatch from deterministic artifacts."""
    scope = build_postmatch_artifact_scope(
        str(payload.get("player_id") or ""),
        str(payload.get("match_id") or payload.get("fixture_id") or ""),
    )
    artifacts = {
        artifact_type: {"payload": artifact_payload}
        for artifact_type, artifact_payload in build_postmatch_artifact_payloads(payload).items()
    }
    analysis = PostmatchStageAgent().analyze(scope=scope, artifacts=artifacts, session_memory=None)
    return serialize_stage_analysis(analysis)
