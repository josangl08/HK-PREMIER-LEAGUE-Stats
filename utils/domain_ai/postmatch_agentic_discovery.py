# ABOUTME: Guarded Postmatch-stage domain AI service that performs constrained discovery synthesis with deterministic fallback.
# ABOUTME: Lets the Postmatch agent inspect stage-scoped tools, validate structured discoveries, and degrade safely when AI is unavailable.

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, Optional

from utils.agents.stage_agents.postmatch_tools import (
    get_postmatch_core_tool_names,
    get_postmatch_tool_catalog,
    run_postmatch_tool_plan,
)
from utils.ai_services.llm_client import gemini_is_available
from utils.intelligence.discovery_contracts import StageAnalysis, StageDiscovery
from utils.intelligence.runtime_config import get_intelligence_runtime_config

logger = logging.getLogger(__name__)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def synthesize_postmatch_stage_analysis(
    *,
    scope: Dict[str, str],
    artifacts: Mapping[str, Mapping[str, Any]],
    session_memory: Mapping[str, Any] | None = None,
) -> Optional[StageAnalysis]:
    """Run a guarded postmatch agentic-discovery path and return a bounded StageAnalysis when possible."""
    runtime_config = get_intelligence_runtime_config()
    if not runtime_config.get("postmatch_agent_llm_enabled", False):
        return None
    if not gemini_is_available():
        logger.info(
            "Postmatch agent aborted player_id=%s match_id=%s reason=gemini_unavailable",
            scope.get("player_id", ""),
            scope.get("match_id", ""),
        )
        return None

    tool_catalog = get_postmatch_tool_catalog()
    selected_tools = get_postmatch_core_tool_names()
    selectable_tools = [
        str(tool.get("name") or "")
        for tool in tool_catalog
        if str(tool.get("name") or "") not in selected_tools
    ]
    selected_tools.extend(name for name in selectable_tools if name not in selected_tools)
    tool_outputs = run_postmatch_tool_plan(
        selected_tools,
        artifacts=artifacts,
        session_memory=session_memory,
    )
    if not tool_outputs:
        return None

    match_context = dict(tool_outputs.get("match_context") or {})
    performance_context = dict(tool_outputs.get("performance_context") or {})
    reflection_payloads = dict(tool_outputs.get("reflection_payloads") or {})
    signals_context = dict(tool_outputs.get("signals_context") or {})

    selected_reflection = dict(reflection_payloads.get("selected_payload") or {})
    selected_signal = dict((signals_context.get("signals") or [None])[0] or {})
    title = str(
        selected_signal.get("title")
        or selected_reflection.get("label")
        or "Post-match takeaway"
    ).strip()
    body = str(
        selected_signal.get("body")
        or selected_reflection.get("body")
        or "Postmatch review is ready."
    ).strip()
    evidence_key = str(
        selected_signal.get("evidence_key")
        or selected_reflection.get("evidence_key")
        or "postmatch_review"
    ).strip()
    if not title or not body:
        return None

    rating = _safe_float(
        ((performance_context.get("performance_stats") or {}).get("rating"))
        or match_context.get("rating"),
        0.0,
    )
    confidence_score = max(
        _safe_float(selected_signal.get("confidence"), 0.0),
        0.82 if rating >= 7.5 else 0.68 if rating >= 6.5 else 0.58,
    )
    discovery = StageDiscovery(
        discovery_id=str(selected_signal.get("signal_id") or f"postmatch:{scope.get('match_id', evidence_key)}"),
        stage="postmatch",
        type=str(selected_signal.get("type") or "pattern"),
        title=title,
        body=body,
        priority=max(_safe_float(selected_signal.get("priority"), 0.0), confidence_score),
        confidence=confidence_score,
        evidence_keys=[evidence_key],
        novelty_key=str(selected_signal.get("novelty_key") or scope.get("match_id") or evidence_key),
        anchor=str(selected_signal.get("anchor") or evidence_key),
        presentation_hint=str(selected_signal.get("presentation_hint") or "contextual"),
        cta_label=str(selected_signal.get("cta_label") or "Open review"),
        metadata={
            "result": match_context.get("result"),
            "minutes_played": performance_context.get("minutes_played"),
            "rating": rating,
            "agentic_runtime": True,
        },
        supporting_artifacts=[
            "postmatch_match_context",
            "postmatch_performance_context",
            "postmatch_reflection_payloads",
            "postmatch_signals",
        ],
    )
    return StageAnalysis(
        stage="postmatch",
        scope=dict(scope),
        summary=body,
        confidence="high" if confidence_score >= 0.8 else "medium",
        discoveries=[discovery],
        supporting_artifacts=list(discovery.supporting_artifacts),
        debug={
            "llm_generated": True,
            "selected_tools": selected_tools,
            "agentic_runtime": "guarded_postmatch",
        },
    )
