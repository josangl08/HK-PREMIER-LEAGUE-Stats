# ABOUTME: Guarded Season-stage domain AI service that performs tool selection and discovery synthesis with deterministic fallback.
# ABOUTME: Lets the Season agent inspect stage-scoped tools, validate structured discoveries, and degrade safely when AI is unavailable.

from __future__ import annotations

from difflib import SequenceMatcher
import logging
import re
import time
from typing import Any, Dict, Mapping, Optional

from utils.agents.stage_agents.season_tools import (
    get_season_core_tool_names,
    get_season_tool_catalog,
    run_season_tool_plan,
)
from utils.ai_services.llm_client import (
    GeminiCallResult,
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

_RETRYABLE_STATUSES = {"network_error", "empty_response"}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _truncate_text(value: str, limit: int) -> str:
    text = _safe_text(value)
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(" ", 1)[0].strip()
    return (clipped or text[:limit]).rstrip(" ,.;:") + "..."


def _normalize_player_facing_copy(value: str) -> str:
    """Soften cold statistical phrasing into more natural player-facing language."""
    text = _safe_text(value)
    if not text:
        return text
    replacements = (
        (r"\b100% decline from (?:his|the) previous five-game block\b", "after contributing in the previous five games"),
        (r"\b100% decline\b", "a clear drop-off"),
        (r"\bzero goal contributions\b", "no goal contributions"),
        (r"\bterminal point for attacks\b", "more of the end point of attacks"),
        (r"\btotal absence of creative passing\b", "very little creative passing"),
        (r"\bhas recorded\b", "has had"),
        (r"\bpost(?:ing)? an elite\b", "showing an elite"),
    )
    normalized = text
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _discovery_similarity(left: Dict[str, Any], right: Dict[str, Any]) -> float:
    left_title = _safe_text(left.get("title")).lower()
    left_body = _safe_text(left.get("body")).lower()
    right_title = _safe_text(right.get("title")).lower()
    right_body = _safe_text(right.get("body")).lower()
    combined_left = f"{left_title} {left_body}".strip()
    combined_right = f"{right_title} {right_body}".strip()
    if not combined_left or not combined_right:
        return 0.0
    return SequenceMatcher(None, combined_left, combined_right).ratio()


def _overlaps_materially(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    left_evidence = {str(item).strip() for item in list(left.get("evidence_keys") or []) if str(item).strip()}
    right_evidence = {str(item).strip() for item in list(right.get("evidence_keys") or []) if str(item).strip()}
    if left_evidence and right_evidence and left_evidence == right_evidence:
        return True
    if _discovery_similarity(left, right) >= 0.62:
        return True
    left_anchor = _safe_text(left.get("anchor"))
    right_anchor = _safe_text(right.get("anchor"))
    return bool(left_anchor and right_anchor and left_anchor == right_anchor)


def _compress_discovery(raw_discovery: Dict[str, Any], *, index: int) -> Dict[str, Any]:
    """Shorten overlay-facing discovery copy while preserving the analysis angle."""
    compressed = dict(raw_discovery)
    title = _normalize_player_facing_copy(_safe_text(compressed.get("title")))
    body = _normalize_player_facing_copy(_safe_text(compressed.get("body")))
    compressed["title"] = _truncate_text(title, 44 if index == 0 else 52) or title
    compressed["body"] = _truncate_text(body, 220 if index == 0 else 170) or body
    if index == 0 and str(compressed.get("presentation_hint") or "").strip().lower() == "micro":
        compressed["presentation_hint"] = "contextual"
    return compressed


def _curate_season_discoveries(analysis: StageAnalysis) -> StageAnalysis:
    """Reduce overlap and tighten copy before the analysis is persisted and surfaced."""
    curated: list[Dict[str, Any]] = []
    raw_discoveries = [
        {
            "discovery_id": item.discovery_id,
            "stage": item.stage,
            "type": item.type,
            "title": item.title,
            "body": item.body,
            "priority": item.priority,
            "confidence": item.confidence,
            "evidence_keys": list(item.evidence_keys),
            "novelty_key": item.novelty_key,
            "anchor": item.anchor,
            "presentation_hint": item.presentation_hint,
            "cta_label": item.cta_label,
            "metadata": dict(item.metadata),
            "supporting_artifacts": list(item.supporting_artifacts),
            "expires_at": item.expires_at,
        }
        for item in analysis.discoveries
    ]
    raw_discoveries.sort(
        key=lambda item: (
            -float(item.get("priority") or 0.0),
            -float(item.get("confidence") or 0.0),
            _safe_text(item.get("title")),
        )
    )
    for item in raw_discoveries:
        if any(_overlaps_materially(item, kept) for kept in curated):
            continue
        curated.append(item)
    compressed_discoveries = [
        coerce_stage_analysis(
            {
                "stage": "season",
                "scope": dict(analysis.scope),
                "summary": analysis.summary,
                "confidence": analysis.confidence,
                "discoveries": [_compress_discovery(item, index=idx)],
                "supporting_artifacts": list(analysis.supporting_artifacts),
                "debug": dict(analysis.debug),
            }
        ).discoveries[0]
        for idx, item in enumerate(curated[:2])
    ]
    return StageAnalysis(
        stage=analysis.stage,
        scope=dict(analysis.scope),
        summary=_truncate_text(_normalize_player_facing_copy(analysis.summary), 220),
        confidence=analysis.confidence,
        discoveries=compressed_discoveries,
        supporting_artifacts=list(analysis.supporting_artifacts),
        debug={**dict(analysis.debug), "post_curated": True},
    )


def _call_model_with_retries(
    prompt: str,
    *,
    model_name: str,
    temperature: float,
    max_output_tokens: int,
    response_mime_type: str,
    retries: int,
    retry_delay_seconds: float,
) -> GeminiCallResult:
    """Call Gemini with short retries for transient stage-agent failures."""
    attempts = max(1, int(retries) + 1)
    last_result: GeminiCallResult | None = None
    for attempt in range(1, attempts + 1):
        result = generate_gemini_content_with_status(
            prompt,
            model_name=model_name,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type=response_mime_type,
        )
        last_result = result
        if result.ok:
            return result
        if result.status not in _RETRYABLE_STATUSES or attempt >= attempts:
            return result
        logger.info(
            "Season agent retrying model=%s attempt=%s status=%s",
            model_name,
            attempt,
            result.status,
        )
        time.sleep(retry_delay_seconds)
    return last_result or GeminiCallResult(
        ok=False,
        status="unknown_error",
        model=model_name,
        error_type="unknown_error",
        error_message="No Gemini result returned.",
    )


def _select_season_tools(
    *,
    scope: Dict[str, str],
    player_name: str,
    max_tools: int,
    model_profile: str,
    model_retries: int,
    retry_delay_seconds: float,
) -> Optional[Dict[str, Any]]:
    """Run the tool-selection step for the season agent."""
    tool_catalog = get_season_tool_catalog()
    core_tools = get_season_core_tool_names()
    selectable_tool_catalog = [
        tool for tool in tool_catalog
        if str(tool.get("name") or "") not in set(core_tools)
    ]
    prompt = build_season_tool_selection_prompt(
        player_name=player_name,
        season=scope.get("season", ""),
        available_tools=selectable_tool_catalog,
        core_tools=core_tools,
        max_tools=max_tools,
    )
    logger.info(
        "Season agent tool-plan start player=%s season=%s profile=%s max_tools=%s",
        player_name,
        scope.get("season", ""),
        model_profile,
        max_tools,
    )
    for model_name in get_stage_agent_model_candidates(model_profile):
        result = _call_model_with_retries(
            prompt,
            model_name=model_name,
            temperature=0.2,
            max_output_tokens=900,
            response_mime_type="application/json",
            retries=model_retries,
            retry_delay_seconds=retry_delay_seconds,
        )
        parsed = parse_structured_json(result.text) if result.ok else None
        if validate_season_tool_plan(parsed, max_tools=max_tools):
            payload = coerce_season_tool_plan(parsed)
            if payload is None:
                continue
            selected_tools = []
            for tool_name in list(core_tools) + list(payload.selected_tools):
                normalized = str(tool_name or "").strip()
                if normalized and normalized not in selected_tools:
                    selected_tools.append(normalized)
            logger.info(
                "Season agent tool-plan selected player=%s season=%s model=%s tools=%s",
                player_name,
                scope.get("season", ""),
                result.model,
                selected_tools,
            )
            return {
                "selected_tools": selected_tools,
                "model": result.model,
            }
        if result.ok:
            logger.info(
                "Season agent invalid tool-plan raw model=%s payload=%s",
                model_name,
                (result.text or "")[:1200],
            )
        logger.info(
            "Season agent tool-plan fallback model=%s status=%s valid_plan=%s",
            model_name,
            result.status,
            bool(validate_season_tool_plan(parsed, max_tools=max_tools)),
        )
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
    max_tools = int(runtime_config.get("season_agent_max_tools", 3))
    model_profile = str(runtime_config.get("season_agent_model_profile", "flash") or "flash")
    model_retries = int(runtime_config.get("season_agent_model_retries", 1))
    retry_delay_seconds = float(runtime_config.get("season_agent_retry_delay_seconds", 0.35))
    tool_plan = _select_season_tools(
        scope=scope,
        player_name=player_name,
        max_tools=max_tools,
        model_profile=model_profile,
        model_retries=model_retries,
        retry_delay_seconds=retry_delay_seconds,
    )
    if not tool_plan:
        logger.info(
            "Season agent aborted player=%s season=%s reason=no_valid_tool_plan",
            player_name,
            scope.get("season", ""),
        )
        return None

    selected_tools = list(tool_plan.get("selected_tools") or [])
    tool_outputs = run_season_tool_plan(
        selected_tools,
        artifacts=artifacts,
        session_memory=session_memory,
    )
    if not tool_outputs:
        logger.info(
            "Season agent aborted player=%s season=%s reason=empty_tool_outputs tools=%s",
            player_name,
            scope.get("season", ""),
            selected_tools,
        )
        return None

    prompt = build_season_discovery_synthesis_prompt(
        player_name=player_name,
        season=scope.get("season", ""),
        selected_tools=selected_tools,
        tool_outputs=tool_outputs,
        session_memory=dict(session_memory or {}),
        model_profile=model_profile,
    )
    logger.info(
        "Season agent discovery start player=%s season=%s profile=%s tools=%s",
        player_name,
        scope.get("season", ""),
        model_profile,
        selected_tools,
    )

    for model_name in get_stage_agent_model_candidates(model_profile):
        result = _call_model_with_retries(
            prompt,
            model_name=model_name,
            temperature=0.25,
            max_output_tokens=1800,
            response_mime_type="application/json",
            retries=model_retries,
            retry_delay_seconds=retry_delay_seconds,
        )
        parsed = parse_structured_json(result.text) if result.ok else None
        if isinstance(parsed, dict) and "stage" not in parsed:
            parsed = {
                "stage": "season",
                "scope": dict(scope),
                "supporting_artifacts": selected_tools,
                "debug": {},
                **parsed,
            }
        if not validate_season_stage_analysis_payload(parsed):
            if result.ok:
                logger.info(
                    "Season agent invalid analysis raw model=%s payload=%s",
                    model_name,
                    (result.text or "")[:2000],
                )
            logger.info(
                "Season agent discovery fallback model=%s status=%s valid_analysis=%s",
                model_name,
                result.status,
                bool(validate_season_stage_analysis_payload(parsed)),
            )
            continue

        analysis = coerce_stage_analysis(parsed)
        if analysis is None:
            continue

        debug = dict(analysis.debug or {})
        debug["analysis_source"] = "agentic"
        debug["llm_generated"] = True
        debug["used_tools"] = selected_tools
        debug["model_profile"] = model_profile
        debug["tool_plan_model"] = tool_plan.get("model", "")
        debug["discovery_model"] = result.model
        debug.setdefault("data_gaps", [])
        curated_analysis = _curate_season_discoveries(
            StageAnalysis(
                stage="season",
                scope=dict(scope),
                summary=analysis.summary,
                confidence=analysis.confidence,
                discoveries=list(analysis.discoveries),
                supporting_artifacts=list(analysis.supporting_artifacts),
                debug=debug,
            )
        )
        logger.info(
            "Season agent discovery success player=%s season=%s tool_plan_model=%s discovery_model=%s discoveries=%s",
            player_name,
            scope.get("season", ""),
            tool_plan.get("model", ""),
            result.model,
            len(curated_analysis.discoveries),
        )
        return StageAnalysis(
            stage="season",
            scope=dict(curated_analysis.scope),
            summary=curated_analysis.summary,
            confidence=curated_analysis.confidence,
            discoveries=list(curated_analysis.discoveries),
            supporting_artifacts=list(curated_analysis.supporting_artifacts),
            debug=dict(curated_analysis.debug),
        )
    logger.info(
        "Season agent aborted player=%s season=%s reason=no_valid_analysis",
        player_name,
        scope.get("season", ""),
    )
    return None
