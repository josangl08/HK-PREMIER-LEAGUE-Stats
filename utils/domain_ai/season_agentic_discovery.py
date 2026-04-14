# ABOUTME: Guarded Season-stage domain AI service that performs tool selection and discovery synthesis with deterministic fallback.
# ABOUTME: Lets the Season agent inspect stage-scoped tools, validate structured discoveries, and degrade safely when AI is unavailable.

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, Optional

from utils.agents.season_agent import build_season_stage_analysis
from utils.agents.stage_agents.season_tools import get_season_tool_catalog, run_season_tool_plan
from utils.ai_services.llm_client import (
    gemini_is_available,
    generate_gemini_content_with_status,
    get_stage_agent_model_candidates,
)
from utils.ai_services.orchestration import parse_structured_json
from utils.ai_services.prompt_builders import (
    build_season_discovery_synthesis_prompt,
    build_season_tool_selection_prompt,
)
from utils.ai_services.validators import (
    coerce_season_tool_plan,
    validate_season_stage_analysis_payload,
    validate_season_tool_plan,
)
from utils.intelligence.discovery_contracts import StageAnalysis, coerce_stage_analysis
from utils.intelligence.runtime_config import get_intelligence_runtime_config

logger = logging.getLogger(__name__)


def _deterministic_fallback_analysis(
    *,
    scope: Dict[str, str],
    artifacts: Mapping[str, Mapping[str, Any]],
) -> StageAnalysis:
    """Build the deterministic season analysis fallback as a shared contract."""
    from utils.agents.stage_agents.season_agent import _build_fallback_stage_analysis

    return _build_fallback_stage_analysis(scope=scope, artifacts=artifacts, session_memory=None)


def _select_season_tools(
    *,
    scope: Dict[str, str],
    player_name: str,
    max_tools: int,
) -> Optional[Dict[str, Any]]:
    """Run the tool-selection step for the season agent."""
    tool_catalog = get_season_tool_catalog()
    prompt = build_season_tool_selection_prompt(
        player_name=player_name,
        season=scope.get("season", ""),
        available_tools=tool_catalog,
        max_tools=max_tools,
    )
    for model_name in get_stage_agent_model_candidates():
        result = generate_gemini_content_with_status(
            prompt,
            model_name=model_name,
            temperature=0.2,
            max_output_tokens=900,
            response_mime_type="application/json",
        )
        parsed = parse_structured_json(result.text) if result.ok else None
        if validate_season_tool_plan(parsed, max_tools=max_tools):
            payload = coerce_season_tool_plan(parsed)
            if payload is None:
                continue
            return {
                "selected_tools": list(payload.selected_tools),
                "selection_rationale": list(payload.selection_rationale),
                "data_gaps": list(payload.data_gaps),
                "model": result.model,
            }
    return None


def synthesize_season_stage_analysis(
    *,
    scope: Dict[str, str],
    artifacts: Mapping[str, Mapping[str, Any]],
    session_memory: Mapping[str, Any] | None = None,
) -> Optional[StageAnalysis]:
    """Run the guarded two-step season agentic discovery flow and return a validated StageAnalysis when possible."""
    runtime_config = get_intelligence_runtime_config()
    if not runtime_config.get("season_agent_llm_enabled", False):
        return None
    if not gemini_is_available():
        return None

    performance_payload = ((artifacts.get("season_performance_context") or {}).get("payload") or {})
    player_name = str(performance_payload.get("player_name") or "Unknown player")
    max_tools = int(runtime_config.get("season_agent_max_tools", 4))
    tool_plan = _select_season_tools(
        scope=scope,
        player_name=player_name,
        max_tools=max_tools,
    )
    if not tool_plan:
        return None

    selected_tools = list(tool_plan.get("selected_tools") or [])
    tool_outputs = run_season_tool_plan(
        selected_tools,
        artifacts=artifacts,
        session_memory=session_memory,
    )
    if not tool_outputs:
        return None

    prompt = build_season_discovery_synthesis_prompt(
        player_name=player_name,
        season=scope.get("season", ""),
        selected_tools=selected_tools,
        tool_outputs=tool_outputs,
        session_memory=dict(session_memory or {}),
    )

    for model_name in get_stage_agent_model_candidates():
        result = generate_gemini_content_with_status(
            prompt,
            model_name=model_name,
            temperature=0.25,
            max_output_tokens=1800,
            response_mime_type="application/json",
        )
        parsed = parse_structured_json(result.text) if result.ok else None
        if not validate_season_stage_analysis_payload(parsed):
            continue

        analysis = coerce_stage_analysis(parsed)
        if analysis is None:
            continue

        debug = dict(analysis.debug or {})
        debug["llm_generated"] = True
        debug["used_tools"] = selected_tools
        debug["tool_plan_model"] = tool_plan.get("model", "")
        debug["discovery_model"] = result.model
        debug.setdefault("data_gaps", list(tool_plan.get("data_gaps") or []))
        return StageAnalysis(
            stage="season",
            scope=dict(scope),
            summary=analysis.summary,
            confidence=analysis.confidence,
            discoveries=list(analysis.discoveries),
            supporting_artifacts=list(analysis.supporting_artifacts),
            debug=debug,
        )
    return None
