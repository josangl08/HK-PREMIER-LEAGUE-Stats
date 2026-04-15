# ABOUTME: Selects eligible stage payloads from portal bootstrap data and dispatches non-blocking reevaluation across stages.
# ABOUTME: Keeps app-entry prewarm logic out of Dash callbacks while persisting stage intelligence before a stage is opened.

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Mapping

from utils.agents.career_intelligence_orchestrator import orchestrate_career_intelligence
from utils.agents.intelligence_orchestrator import orchestrate_season_intelligence
from utils.agents.postmatch_intelligence_orchestrator import orchestrate_postmatch_intelligence
from utils.agents.prematch_intelligence_orchestrator import orchestrate_prematch_intelligence
from utils.stage_helpers import _deserialize_dashboard_data


def _safe_date_key(value: Any) -> tuple[int, str]:
    text = str(value or "").strip()
    if not text:
        return (0, "")
    for candidate in (text, text[:10]):
        try:
            parsed = datetime.fromisoformat(candidate)
            return (1, parsed.isoformat())
        except ValueError:
            continue
    return (0, text)


def _derive_stage_scope_id(payload: Mapping[str, Any] | None, *, id_key: str) -> str:
    raw_payload = dict(payload or {})
    existing = str(raw_payload.get(id_key) or raw_payload.get("fixture_id") or raw_payload.get("match_id") or "").strip()
    if existing:
        return existing
    bits = [
        str(raw_payload.get("home_team") or "").strip().lower().replace(" ", "-"),
        "vs",
        str(raw_payload.get("away_team") or raw_payload.get("opponent") or "").strip().lower().replace(" ", "-"),
        str(raw_payload.get("date") or raw_payload.get("kickoff_display") or "").strip().lower().replace(" ", "-"),
    ]
    return "-".join([bit for bit in bits if bit]).strip("-")


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    return value


def _inject_stage_identity(
    payload: Mapping[str, Any] | None,
    *,
    player_id: str,
    player_name: str,
    id_key: str,
) -> Dict[str, Any]:
    enriched = _json_safe_value(dict(payload or {}))
    if player_id and not enriched.get("player_id"):
        enriched["player_id"] = player_id
    if player_name and not enriched.get("player_name"):
        enriched["player_name"] = player_name
    derived_id = _derive_stage_scope_id(enriched, id_key=id_key)
    if derived_id and not enriched.get(id_key):
        enriched[id_key] = derived_id
    return enriched


def _sorted_stage_milestones(milestones_data: List[Mapping[str, Any]] | None, *, stage_type: str) -> List[Dict[str, Any]]:
    normalized_stage = str(stage_type or "").strip().lower()
    matches = [
        dict(item)
        for item in list(milestones_data or [])
        if str(item.get("type") or "").strip().lower() == normalized_stage
    ]
    return sorted(
        matches,
        key=lambda item: _safe_date_key(item.get("date")),
        reverse=True,
    )


def build_background_stage_payloads(
    portal_data: Mapping[str, Any] | None,
    milestones_data: List[Mapping[str, Any]] | None,
) -> Dict[str, Any]:
    """Resolve the most relevant payload per mature stage for app-entry prewarm."""
    payloads: Dict[str, Any] = {
        "career": None,
        "season": None,
        "prematch": None,
        "postmatch": None,
    }

    if portal_data and portal_data.get("data"):
        career_data = _deserialize_dashboard_data(portal_data["data"])
        player_payload = dict(career_data.get("player") or {})
        if not player_payload.get("player_id"):
            player_payload["player_id"] = str(portal_data.get("player_id") or "")
        if not player_payload.get("player_name"):
            player_payload["player_name"] = str(portal_data.get("player_name") or "")
        career_data["player"] = player_payload
        career_data.setdefault("player_name", str(portal_data.get("player_name") or ""))
        payloads["career"] = career_data
    active_player_id = str((portal_data or {}).get("player_id") or "")
    active_player_name = str((portal_data or {}).get("player_name") or "")

    current_season = str(((portal_data or {}).get("career_phase") or {}).get("current_season") or "")
    season_milestones = _sorted_stage_milestones(milestones_data, stage_type="career")
    if season_milestones:
        preferred = next(
            (
                item
                for item in season_milestones
                if str((item.get("payload") or {}).get("season") or "") == current_season
            ),
            season_milestones[0],
        )
        payloads["season"] = dict(preferred.get("payload") or {})

    prematch_milestones = _sorted_stage_milestones(milestones_data, stage_type="pre-match")
    if prematch_milestones:
        payloads["prematch"] = _inject_stage_identity(
            prematch_milestones[0].get("payload") or {},
            player_id=active_player_id,
            player_name=active_player_name,
            id_key="fixture_id",
        )

    postmatch_milestones = _sorted_stage_milestones(milestones_data, stage_type="post-match")
    if postmatch_milestones:
        payloads["postmatch"] = _inject_stage_identity(
            postmatch_milestones[0].get("payload") or {},
            player_id=active_player_id,
            player_name=active_player_name,
            id_key="match_id",
        )

    return payloads


def _should_dispatch(result: Mapping[str, Any] | None) -> bool:
    reevaluation = dict((result or {}).get("reevaluation") or {})
    refresh_plan = list((result or {}).get("refresh_plan") or [])
    return bool(refresh_plan or reevaluation.get("should_reevaluate"))


def _dispatch_stage(stage_name: str, payload: Any) -> Dict[str, Any]:
    if stage_name == "career":
        initial = orchestrate_career_intelligence(payload)
    elif stage_name == "season":
        initial = orchestrate_season_intelligence(payload)
    elif stage_name == "prematch":
        initial = orchestrate_prematch_intelligence(payload)
    elif stage_name == "postmatch":
        initial = orchestrate_postmatch_intelligence(payload)
    else:
        initial = {}

    dispatched = _should_dispatch(initial)
    final_result = initial
    debug = dict((final_result or {}).get("debug") or {})
    return {
        "eligible": True,
        "dispatched": dispatched,
        "refresh_plan": list((initial or {}).get("refresh_plan") or []),
        "reevaluation": dict((initial or {}).get("reevaluation") or {}),
        "served_from": dict(debug.get("served_from") or {}),
        "scope": dict(debug.get("scope") or {}),
        "background_refresh_required": bool((initial or {}).get("background_refresh_required")),
    }


def dispatch_background_stage_reevaluations(
    portal_data: Mapping[str, Any] | None,
    milestones_data: List[Mapping[str, Any]] | None,
) -> Dict[str, Any]:
    """Evaluate all eligible mature stages from app entry and refresh only the ones that need it."""
    payloads = build_background_stage_payloads(portal_data, milestones_data)
    summary: Dict[str, Any] = {
        "career": {"eligible": False, "dispatched": False},
        "season": {"eligible": False, "dispatched": False},
        "prematch": {"eligible": False, "dispatched": False},
        "postmatch": {"eligible": False, "dispatched": False},
    }

    # Career already has a first-party async build path on portal entry via
    # `career-stage-analysis-store`, so dispatching it again here just doubles
    # the same LLM work during startup when persistence is disabled.
    career_payload = payloads.get("career")
    if career_payload and ((career_payload.get("player") or {}).get("player_id") or ""):
        summary["career"] = {
            "eligible": True,
            "dispatched": False,
            "refresh_plan": [],
            "reevaluation": {"should_reevaluate": False, "reason": "handled_by_primary_stage_callback"},
            "served_from": {},
            "scope": {},
            "background_refresh_required": False,
        }

    season_payload = payloads.get("season")
    if season_payload and season_payload.get("season") and season_payload.get("player_id"):
        summary["season"] = _dispatch_stage("season", season_payload)

    prematch_payload = payloads.get("prematch")
    if prematch_payload and prematch_payload.get("player_id") and prematch_payload.get("fixture_id"):
        summary["prematch"] = _dispatch_stage("prematch", prematch_payload)

    postmatch_payload = payloads.get("postmatch")
    postmatch_match_id = str((postmatch_payload or {}).get("match_id") or (postmatch_payload or {}).get("fixture_id") or "")
    if postmatch_payload and postmatch_payload.get("player_id") and postmatch_match_id:
        summary["postmatch"] = _dispatch_stage("postmatch", postmatch_payload)

    return summary
