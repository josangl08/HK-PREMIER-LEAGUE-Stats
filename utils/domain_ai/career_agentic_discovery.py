# ABOUTME: Guarded Career-stage domain AI service that performs tool selection and discovery synthesis with deterministic fallback.
# ABOUTME: Lets the Career agent inspect stage-scoped tools, validate structured progression discoveries, and degrade safely when AI is unavailable.

from __future__ import annotations

from difflib import SequenceMatcher
import logging
import re
import time
from typing import Any, Dict, Mapping, Optional

from utils.agents.stage_agents.career_tools import (
    get_career_core_tool_names,
    get_career_tool_catalog,
    run_career_tool_plan,
)
from utils.ai_services.llm_client import (
    GeminiCallResult,
    gemini_is_available,
    generate_gemini_content_with_status,
    get_stage_agent_model_candidates,
)
from utils.ai_services.orchestration import parse_structured_json
from utils.ai_services.prompt_builders import (
    build_career_discovery_synthesis_prompt,
    build_career_tool_selection_prompt,
)
from utils.ai_services.validators import (
    coerce_career_tool_plan,
    validate_career_tool_plan,
)
from utils.intelligence.discovery_contracts import StageAnalysis, coerce_stage_analysis
from utils.intelligence.runtime_config import get_intelligence_runtime_config

logger = logging.getLogger(__name__)

_RETRYABLE_STATUSES = {"network_error", "empty_response"}
_CAREER_EVIDENCE_KEY_ALIASES = {
    "phase_context": "career_phase_context",
    "signals_context": "career_signals_context",
    "priorities_context": "career_priorities_context",
    "dashboard_brief": "career_dashboard_brief",
}
_CAREER_DISCOVERY_LIMIT = 4


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _truncate_text(value: str, limit: int) -> str:
    text = _safe_text(value)
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(" ", 1)[0].strip()
    return (clipped or text[:limit]).rstrip(" ,.;:") + "..."


def _normalize_player_facing_copy(value: str) -> str:
    text = _safe_text(value)
    if not text:
        return text
    replacements = (
        (r"\btrajectory\b", "direction"),
        (r"\bvolatility\b", "swings"),
        (r"\bprofile separation\b", "difference in profile"),
        (r"\bcompetitive value\b", "current level"),
        (r"\bcareer momentum\b", "current momentum"),
        (r"\bnext-step readiness\b", "readiness for the next step"),
    )
    normalized = text
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", normalized).strip()


def _normalize_evidence_key(key: Any) -> str:
    normalized = _safe_text(key).lower()
    if not normalized:
        return ""
    for alias, canonical in _CAREER_EVIDENCE_KEY_ALIASES.items():
        if normalized == alias or normalized.startswith(f"{alias}_"):
            return canonical
    return _CAREER_EVIDENCE_KEY_ALIASES.get(normalized, normalized)


def _normalize_confidence_label(value: Any) -> str:
    normalized = _safe_text(value).lower()
    if normalized in {"low", "medium", "high"}:
        return normalized
    if normalized in {"limited", "weak", "uncertain"}:
        return "low"
    if normalized in {"good", "strong", "certain"}:
        return "high"
    return "medium"


def _career_discovery_identity(item: Dict[str, Any]) -> tuple[str, str]:
    """Return stable signal_id and novelty_key for recurring career discovery families."""
    title = _safe_text(item.get("title")).lower()
    body = _safe_text(item.get("body")).lower()
    combined = f"{title} {body}".strip()
    evidence_keys = [
        _safe_text(key).lower()
        for key in list(item.get("evidence_keys") or [])
        if _safe_text(key)
    ]
    evidence_blob = " ".join(evidence_keys)

    role_stability_markers = (
        "minutes dropped",
        "playing time has dropped",
        "involvement has dropped",
        "career average",
        "starting role",
        "starting rhythm",
        "starting spot",
        "regular for",
    )
    technical_impact_markers = (
        "passing",
        "distribution",
        "ball retention",
        "interceptions",
        "bottom quartile",
        "bottom 25%",
        "technical impact",
        "on the ball",
    )

    if any(marker in combined for marker in role_stability_markers):
        return ("role_stability_alert", "career:role_stability:minutes_drop")
    if any(marker in combined for marker in technical_impact_markers):
        return ("technical_leverage_points", "career:technical_impact")
    if "career_phase_context" in evidence_blob:
        return ("career_phase_signal", "career:phase_signal")
    if "career_priorities_context" in evidence_blob:
        return ("priority_focus", "career:priority_focus")

    fallback_signal_id = _safe_text(item.get("discovery_id") or item.get("signal_id") or "career_discovery")
    fallback_novelty_key = _safe_text(
        item.get("novelty_key")
        or item.get("signal_id")
        or item.get("discovery_id")
        or fallback_signal_id
    )
    return (fallback_signal_id, fallback_novelty_key)


def _normalize_career_ai_payload(
    raw_payload: Dict[str, Any],
    *,
    scope: Dict[str, str],
    selected_tools: list[str],
) -> Dict[str, Any]:
    discoveries = []
    for item in list(raw_payload.get("discoveries") or [])[:_CAREER_DISCOVERY_LIMIT]:
        if not isinstance(item, dict):
            continue
        evidence_keys = []
        for key in list(item.get("evidence_keys") or []):
            normalized_key = _normalize_evidence_key(key)
            if normalized_key and normalized_key not in evidence_keys:
                evidence_keys.append(normalized_key)
        anchor = _normalize_evidence_key(item.get("anchor"))
        if anchor and anchor not in evidence_keys:
            evidence_keys.append(anchor)
        if not evidence_keys:
            for tool_name in selected_tools:
                fallback_key = _normalize_evidence_key(tool_name)
                if fallback_key and fallback_key != "session_memory":
                    evidence_keys.append(fallback_key)
                    break
        title = _safe_text(item.get("title") or item.get("discovery_id") or item.get("signal_id"))
        body = _safe_text(item.get("body"))
        if title and not body:
            body = _safe_text(raw_payload.get("summary"))
        signal_id, novelty_key = _career_discovery_identity(
            {
                **item,
                "evidence_keys": evidence_keys,
                "title": title,
                "body": body,
            }
        )
        normalized_item = {
            **item,
            "stage": "career",
            "discovery_id": signal_id,
            "signal_id": signal_id,
            "title": title or "Career discovery",
            "body": body,
            "evidence_keys": evidence_keys,
            "novelty_key": novelty_key,
            "anchor": anchor or (evidence_keys[0] if evidence_keys else ""),
            "presentation_hint": _safe_text(item.get("presentation_hint") or "contextual").lower() or "contextual",
            "cta_label": _safe_text(item.get("cta_label") or "See detail"),
        }
        discoveries.append(normalized_item)
    return {
        "stage": "career",
        "scope": dict(scope),
        "summary": _safe_text(raw_payload.get("summary") or raw_payload.get("body")),
        "confidence": _normalize_confidence_label(raw_payload.get("confidence")),
        "discoveries": discoveries,
        "supporting_artifacts": list(selected_tools),
        "debug": dict(raw_payload.get("debug") or {}),
    }


def _is_viable_career_analysis(raw_payload: Dict[str, Any]) -> bool:
    """Accept normalized career analyses that carry usable discoveries, even if the raw model format is imperfect."""
    analysis = coerce_stage_analysis(raw_payload)
    if analysis is None or analysis.stage != "career":
        return False
    if analysis.confidence not in {"low", "medium", "high"}:
        return False
    if not analysis.discoveries or len(analysis.discoveries) > _CAREER_DISCOVERY_LIMIT:
        return False
    return all(
        bool(item.title and item.body and (item.evidence_keys or item.anchor))
        for item in analysis.discoveries
    )


def _coerce_viable_career_analysis(raw_payload: Dict[str, Any]) -> Optional[StageAnalysis]:
    """Return a normalized career analysis when the parsed payload is materially usable."""
    analysis = coerce_stage_analysis(raw_payload)
    if analysis is None or analysis.stage != "career":
        return None
    if analysis.confidence not in {"low", "medium", "high"}:
        analysis = StageAnalysis(
            stage="career",
            scope=dict(analysis.scope),
            summary=analysis.summary,
            confidence="medium",
            discoveries=list(analysis.discoveries),
            supporting_artifacts=list(analysis.supporting_artifacts),
            debug=dict(analysis.debug),
        )
    discoveries = [
        item
        for item in analysis.discoveries
        if item.title and item.body and (item.evidence_keys or item.anchor)
    ][:_CAREER_DISCOVERY_LIMIT]
    if not discoveries:
        return None
    return StageAnalysis(
        stage="career",
        scope=dict(analysis.scope),
        summary=analysis.summary or discoveries[0].body,
        confidence=analysis.confidence,
        discoveries=discoveries,
        supporting_artifacts=list(analysis.supporting_artifacts),
        debug=dict(analysis.debug),
    )


def _discovery_similarity(left: Dict[str, Any], right: Dict[str, Any]) -> float:
    combined_left = f"{_safe_text(left.get('title')).lower()} {_safe_text(left.get('body')).lower()}".strip()
    combined_right = f"{_safe_text(right.get('title')).lower()} {_safe_text(right.get('body')).lower()}".strip()
    if not combined_left or not combined_right:
        return 0.0
    return SequenceMatcher(None, combined_left, combined_right).ratio()


def _curate_career_discoveries(analysis: StageAnalysis) -> StageAnalysis:
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
        if any(_discovery_similarity(item, kept) >= 0.64 for kept in curated):
            continue
        item["title"] = _truncate_text(_normalize_player_facing_copy(item.get("title")), 44 if not curated else 48)
        item["body"] = _normalize_player_facing_copy(item.get("body"))
        curated.append(item)

    compressed_discoveries = [
        coerce_stage_analysis(
            {
                "stage": "career",
                "scope": dict(analysis.scope),
                "summary": analysis.summary,
                "confidence": analysis.confidence,
                "discoveries": [item],
                "supporting_artifacts": list(analysis.supporting_artifacts),
                "debug": dict(analysis.debug),
            }
        ).discoveries[0]
        for item in curated[:_CAREER_DISCOVERY_LIMIT]
    ]
    return StageAnalysis(
        stage="career",
        scope=dict(analysis.scope),
        summary=_truncate_text(_normalize_player_facing_copy(analysis.summary), 300),
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
            "Career agent retrying model=%s attempt=%s status=%s",
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


def _select_career_tools(
    *,
    player_name: str,
    max_tools: int,
    model_profile: str,
    model_retries: int,
    retry_delay_seconds: float,
) -> Optional[Dict[str, Any]]:
    tool_catalog = get_career_tool_catalog()
    core_tools = get_career_core_tool_names()
    selectable_tool_catalog = [
        tool for tool in tool_catalog
        if str(tool.get("name") or "") not in set(core_tools)
    ]
    prompt = build_career_tool_selection_prompt(
        player_name=player_name,
        available_tools=selectable_tool_catalog,
        core_tools=core_tools,
        max_tools=max_tools,
    )
    logger.info(
        "Career agent tool-plan start player=%s profile=%s max_tools=%s",
        player_name,
        model_profile,
        max_tools,
    )
    for model_name in get_stage_agent_model_candidates(model_profile):
        result = _call_model_with_retries(
            prompt,
            model_name=model_name,
            temperature=0.2,
            max_output_tokens=700,
            response_mime_type="application/json",
            retries=model_retries,
            retry_delay_seconds=retry_delay_seconds,
        )
        parsed = parse_structured_json(result.text) if result.ok else None
        if validate_career_tool_plan(parsed, max_tools=max_tools):
            payload = coerce_career_tool_plan(parsed)
            if payload is None:
                continue
            selected_tools = []
            for tool_name in list(core_tools) + list(payload.selected_tools):
                normalized = str(tool_name or "").strip()
                if normalized and normalized not in selected_tools:
                    selected_tools.append(normalized)
            logger.info(
                "Career agent tool-plan selected player=%s model=%s tools=%s",
                player_name,
                result.model,
                selected_tools,
            )
            return {"selected_tools": selected_tools, "model": result.model}
        logger.info(
            "Career agent tool-plan fallback model=%s status=%s valid_plan=%s",
            model_name,
            result.status,
            bool(validate_career_tool_plan(parsed, max_tools=max_tools)),
        )
    return None


def synthesize_career_stage_analysis(
    *,
    scope: Dict[str, str],
    artifacts: Mapping[str, Mapping[str, Any]],
    session_memory: Mapping[str, Any] | None = None,
) -> Optional[StageAnalysis]:
    """Run the guarded two-step career agentic discovery flow and return a validated StageAnalysis when possible."""
    runtime_config = get_intelligence_runtime_config()
    if not runtime_config.get("career_agent_llm_enabled", False):
        logger.info("Career agent skipped reason=llm_disabled")
        return None
    if not gemini_is_available():
        logger.info("Career agent skipped reason=gemini_unavailable")
        return None

    brief_payload = ((artifacts.get("career_dashboard_brief") or {}).get("payload") or {})
    player_name = (
        _safe_text(brief_payload.get("player_name"))
        or _safe_text(((brief_payload.get("career_thesis") or {}).get("player_name")))
        or "Unknown player"
    )
    max_tools = int(runtime_config.get("career_agent_max_tools", 3))
    model_profile = str(runtime_config.get("career_agent_model_profile", "flash") or "flash")
    model_retries = int(runtime_config.get("career_agent_model_retries", 1))
    retry_delay_seconds = float(runtime_config.get("career_agent_retry_delay_seconds", 0.35))

    tool_plan = _select_career_tools(
        player_name=player_name,
        max_tools=max_tools,
        model_profile=model_profile,
        model_retries=model_retries,
        retry_delay_seconds=retry_delay_seconds,
    )
    if not tool_plan:
        return None

    selected_tools = list(tool_plan.get("selected_tools") or [])
    tool_outputs = run_career_tool_plan(
        selected_tools,
        artifacts=artifacts,
        session_memory=session_memory,
    )
    if not tool_outputs:
        logger.info(
            "Career agent aborted player=%s reason=empty_tool_outputs tools=%s",
            player_name,
            selected_tools,
        )
        return None

    try:
        prompt = build_career_discovery_synthesis_prompt(
            player_name=player_name,
            selected_tools=selected_tools,
            tool_outputs=tool_outputs,
            session_memory=dict(session_memory or {}),
            model_profile=model_profile,
        )
    except Exception as exc:
        logger.info(
            "Career agent aborted player=%s reason=prompt_build_error error=%s",
            player_name,
            exc,
        )
        return None
    logger.info(
        "Career agent discovery start player=%s profile=%s tools=%s tool_output_keys=%s",
        player_name,
        model_profile,
        selected_tools,
        sorted(tool_outputs.keys()),
    )
    for model_name in get_stage_agent_model_candidates(model_profile):
        result = _call_model_with_retries(
            prompt,
            model_name=model_name,
            temperature=0.25,
            max_output_tokens=1500,
            response_mime_type="application/json",
            retries=model_retries,
            retry_delay_seconds=retry_delay_seconds,
        )
        parsed = parse_structured_json(result.text) if result.ok else None
        if isinstance(parsed, dict):
            parsed = _normalize_career_ai_payload(
                parsed,
                scope=scope,
                selected_tools=selected_tools,
            )
        analysis = _coerce_viable_career_analysis(parsed) if isinstance(parsed, dict) else None
        if analysis is None:
            if result.ok:
                logger.info(
                    "Career agent invalid analysis raw model=%s payload=%s",
                    model_name,
                    (result.text or "")[:1800],
                )
            logger.info(
                "Career agent discovery fallback model=%s status=%s valid_analysis=%s",
                model_name,
                result.status,
                bool(analysis),
            )
            continue
        debug = dict(analysis.debug or {})
        debug["llm_generated"] = True
        debug["used_tools"] = selected_tools
        debug["model_profile"] = model_profile
        debug["tool_plan_model"] = tool_plan.get("model", "")
        debug["discovery_model"] = result.model
        curated_analysis = _curate_career_discoveries(
            StageAnalysis(
                stage="career",
                scope=dict(scope),
                summary=analysis.summary,
                confidence=analysis.confidence,
                discoveries=list(analysis.discoveries),
                supporting_artifacts=list(analysis.supporting_artifacts),
                debug=debug,
            )
        )
        logger.info(
            "Career agent discovery success player=%s tool_plan_model=%s discovery_model=%s discoveries=%s",
            player_name,
            tool_plan.get("model", ""),
            result.model,
            len(curated_analysis.discoveries),
        )
        return curated_analysis
    logger.info("Career agent aborted player=%s reason=no_valid_analysis", player_name)
    return None
