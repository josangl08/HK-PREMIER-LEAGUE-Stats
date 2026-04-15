# ABOUTME: Guarded Prematch-stage domain AI service that performs tool selection and discovery synthesis with deterministic fallback.
# ABOUTME: Lets the Prematch agent inspect stage-scoped tools, validate structured tactical discoveries, and degrade safely when AI is unavailable.

from __future__ import annotations

from difflib import SequenceMatcher
import logging
import re
import time
from typing import Any, Dict, Mapping, Optional

from utils.agents.stage_agents.prematch_tools import (
    get_prematch_core_tool_names,
    get_prematch_tool_catalog,
    run_prematch_tool_plan,
)
from utils.ai_services.llm_client import (
    GeminiCallResult,
    gemini_is_available,
    generate_gemini_content_with_status,
    get_stage_agent_model_candidates,
)
from utils.ai_services.orchestration import parse_structured_json
from utils.ai_services.prompt_builders import (
    build_prematch_discovery_synthesis_prompt,
    build_prematch_tool_selection_prompt,
)
from utils.ai_services.validators import (
    coerce_prematch_tool_plan,
    validate_prematch_tool_plan,
)
from utils.intelligence.discovery_contracts import StageAnalysis, coerce_stage_analysis
from utils.intelligence.runtime_config import get_intelligence_runtime_config

logger = logging.getLogger(__name__)

_RETRYABLE_STATUSES = {"network_error", "empty_response"}
_PREMATCH_EVIDENCE_KEY_ALIASES = {
    "fixture_context": "prematch_fixture_context",
    "recent_form": "prematch_recent_form_context",
    "head_to_head": "prematch_head_to_head_context",
    "rival_profiles": "prematch_rival_profiles_context",
    "opponent_threat": "prematch_opponent_threat_context",
    "deterministic_baseline": "prematch_game_plan_context",
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _truncate_text(value: str, limit: int) -> str:
    text = _safe_text(value)
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(" ", 1)[0].strip()
    return (clipped or text[:limit]).rstrip(" ,.;:") + "..."


def _normalize_player_facing_copy(value: str) -> str:
    """Soften stiff tactical phrasing into cleaner player-facing language."""
    text = _safe_text(value)
    if not text:
        return text
    replacements = (
        (r"\bexploit\b", "attack"),
        (r"\btarget zones\b", "attack the space"),
        (r"\bprofile separation\b", "difference in profile"),
        (r"\bterminal actions\b", "final actions"),
        (r"\bprimary duel\b", "main duel"),
        (r"\bdirect rival\b", "likely rival"),
        (r"\bprimary rival\b", "likely rival"),
        (r"\bdictate the tempo\b", "settle on the ball"),
        (r"\bdisrupt(?:ing)? ([A-Z][a-z]+(?: [A-Z][a-z]+)*)'s rhythm\b", r"make \1 uncomfortable on the ball"),
    )
    normalized = text
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", normalized).strip()


def _normalize_confidence_label(value: Any) -> str:
    normalized = _safe_text(value).lower()
    if normalized in {"low", "medium", "high"}:
        return normalized
    if normalized in {"limited", "weak", "uncertain"}:
        return "low"
    if normalized in {"good", "strong"}:
        return "high"
    return "medium"


def _normalize_evidence_key(key: Any) -> str:
    normalized = _safe_text(key).lower()
    if not normalized:
        return ""
    for alias, canonical in _PREMATCH_EVIDENCE_KEY_ALIASES.items():
        if normalized == alias or normalized.startswith(f"{alias}_"):
            return canonical
    return _PREMATCH_EVIDENCE_KEY_ALIASES.get(normalized, normalized)


def _normalize_prematch_ai_payload(
    raw_payload: Dict[str, Any],
    *,
    scope: Dict[str, str],
    selected_tools: list[str],
) -> Dict[str, Any]:
    """Normalize relaxed flash-model output into the stricter shared prematch contract."""
    discoveries = []
    for item in list(raw_payload.get("discoveries") or [])[:2]:
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
        body = _safe_text(item.get("body"))
        title = _safe_text(item.get("title") or item.get("discovery_id") or item.get("signal_id"))
        if title and not body:
            body = _safe_text(raw_payload.get("summary"))
        normalized_item = {
            **item,
            "stage": "prematch",
            "title": title or "Prematch discovery",
            "body": body,
            "evidence_keys": evidence_keys,
            "anchor": anchor or (evidence_keys[0] if evidence_keys else ""),
            "presentation_hint": _safe_text(item.get("presentation_hint") or "contextual").lower() or "contextual",
            "cta_label": _safe_text(item.get("cta_label") or "Open preview"),
        }
        discoveries.append(normalized_item)
    return {
        "stage": "prematch",
        "scope": dict(scope),
        "summary": _safe_text(raw_payload.get("summary") or raw_payload.get("body")),
        "confidence": _normalize_confidence_label(raw_payload.get("confidence")),
        "discoveries": discoveries,
        "supporting_artifacts": list(selected_tools),
        "debug": dict(raw_payload.get("debug") or {}),
    }


def _is_viable_prematch_analysis(raw_payload: Dict[str, Any]) -> bool:
    """Accept normalized prematch analyses that carry usable discoveries, even if the raw model format is imperfect."""
    analysis = coerce_stage_analysis(raw_payload)
    if analysis is None or analysis.stage != "prematch":
        return False
    if analysis.confidence not in {"low", "medium", "high"}:
        return False
    if not analysis.discoveries or len(analysis.discoveries) > 3:
        return False
    return all(
        bool(item.title and item.body and (item.evidence_keys or item.anchor))
        for item in analysis.discoveries
    )


def _coerce_viable_prematch_analysis(raw_payload: Dict[str, Any]) -> Optional[StageAnalysis]:
    """Return a normalized prematch analysis when the parsed payload is materially usable."""
    analysis = coerce_stage_analysis(raw_payload)
    if analysis is None or analysis.stage != "prematch":
        return None
    if analysis.confidence not in {"low", "medium", "high"}:
        analysis = StageAnalysis(
            stage="prematch",
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
    ][:3]
    if not discoveries:
        return None
    return StageAnalysis(
        stage="prematch",
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


def _overlaps_materially(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    left_evidence = {str(item).strip() for item in list(left.get("evidence_keys") or []) if str(item).strip()}
    right_evidence = {str(item).strip() for item in list(right.get("evidence_keys") or []) if str(item).strip()}
    if left_evidence and right_evidence and left_evidence == right_evidence:
        return True
    if _discovery_similarity(left, right) >= 0.64:
        return True
    left_anchor = _safe_text(left.get("anchor"))
    right_anchor = _safe_text(right.get("anchor"))
    return bool(left_anchor and right_anchor and left_anchor == right_anchor)


def _compress_discovery(raw_discovery: Dict[str, Any], *, index: int) -> Dict[str, Any]:
    compressed = dict(raw_discovery)
    compressed["title"] = _truncate_text(_normalize_player_facing_copy(_safe_text(compressed.get("title"))), 42 if index == 0 else 48)
    compressed["body"] = _normalize_player_facing_copy(_safe_text(compressed.get("body")))
    if index == 0 and str(compressed.get("presentation_hint") or "").strip().lower() == "micro":
        compressed["presentation_hint"] = "contextual"
    return compressed


def _apply_matchup_confidence_guardrails(
    analysis: StageAnalysis,
    *,
    tool_outputs: Mapping[str, Any],
) -> StageAnalysis:
    rival_profiles = dict(tool_outputs.get("rival_profiles") or {})
    matchup_confidence = _safe_text(rival_profiles.get("matchup_confidence")).lower()
    if matchup_confidence not in {"low", "medium"}:
        return analysis

    guarded_discoveries = []
    for item in analysis.discoveries:
        evidence_keys = set(item.evidence_keys or [])
        uses_rival_profiles = "prematch_rival_profiles_context" in evidence_keys
        guarded_hint = item.presentation_hint
        guarded_body = item.body
        if uses_rival_profiles and matchup_confidence == "low" and guarded_hint == "critical":
            guarded_hint = "prominent"
        if uses_rival_profiles and matchup_confidence in {"low", "medium"}:
            normalized_body = _safe_text(guarded_body)
            if normalized_body and "likely rival" not in normalized_body.lower():
                guarded_body = re.sub(
                    r"^\s*(He|They)\b",
                    "Your likely rival",
                    normalized_body,
                    count=1,
                ) or guarded_body
        guarded_discoveries.append(
            item.__class__(
                discovery_id=item.discovery_id,
                stage=item.stage,
                type=item.type,
                title=item.title,
                body=guarded_body,
                priority=item.priority,
                confidence=item.confidence,
                evidence_keys=list(item.evidence_keys),
                novelty_key=item.novelty_key,
                anchor=item.anchor,
                presentation_hint=guarded_hint,
                cta_label=item.cta_label,
                metadata=dict(item.metadata),
                supporting_artifacts=list(item.supporting_artifacts),
                expires_at=item.expires_at,
            )
        )
    return StageAnalysis(
        stage=analysis.stage,
        scope=dict(analysis.scope),
        summary=analysis.summary,
        confidence=analysis.confidence,
        discoveries=guarded_discoveries,
        supporting_artifacts=list(analysis.supporting_artifacts),
        debug={**dict(analysis.debug), "matchup_confidence": matchup_confidence or "unknown"},
    )


def _curate_prematch_discoveries(analysis: StageAnalysis) -> StageAnalysis:
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
                "stage": "prematch",
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
        stage="prematch",
        scope=dict(analysis.scope),
        summary=_truncate_text(_normalize_player_facing_copy(analysis.summary), 320),
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
            "Prematch agent retrying model=%s attempt=%s status=%s",
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


def _select_prematch_tools(
    *,
    fixture_id: str,
    opponent: str,
    player_name: str,
    max_tools: int,
    model_profile: str,
    model_retries: int,
    retry_delay_seconds: float,
) -> Optional[Dict[str, Any]]:
    tool_catalog = get_prematch_tool_catalog()
    core_tools = get_prematch_core_tool_names()
    selectable_tool_catalog = [
        tool for tool in tool_catalog
        if str(tool.get("name") or "") not in set(core_tools)
    ]
    prompt = build_prematch_tool_selection_prompt(
        player_name=player_name,
        opponent=opponent,
        available_tools=selectable_tool_catalog,
        core_tools=core_tools,
        max_tools=max_tools,
    )
    logger.info(
        "Prematch agent tool-plan start player=%s opponent=%s fixture_id=%s profile=%s max_tools=%s",
        player_name,
        opponent,
        fixture_id,
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
        if validate_prematch_tool_plan(parsed, max_tools=max_tools):
            payload = coerce_prematch_tool_plan(parsed)
            if payload is None:
                continue
            selected_tools = []
            for tool_name in list(core_tools) + list(payload.selected_tools):
                normalized = str(tool_name or "").strip()
                if normalized and normalized not in selected_tools:
                    selected_tools.append(normalized)
            logger.info(
                "Prematch agent tool-plan selected player=%s opponent=%s model=%s tools=%s",
                player_name,
                opponent,
                result.model,
                selected_tools,
            )
            return {"selected_tools": selected_tools, "model": result.model}
        if result.ok:
            logger.info(
                "Prematch agent invalid tool-plan raw model=%s payload=%s",
                model_name,
                (result.text or "")[:1200],
            )
        logger.info(
            "Prematch agent tool-plan fallback model=%s status=%s valid_plan=%s",
            model_name,
            result.status,
            bool(validate_prematch_tool_plan(parsed, max_tools=max_tools)),
        )
    return None


def synthesize_prematch_stage_analysis(
    *,
    scope: Dict[str, str],
    artifacts: Mapping[str, Mapping[str, Any]],
    session_memory: Mapping[str, Any] | None = None,
) -> Optional[StageAnalysis]:
    """Run the guarded two-step prematch agentic discovery flow and return a validated StageAnalysis when possible."""
    runtime_config = get_intelligence_runtime_config()
    if not runtime_config.get("prematch_agent_llm_enabled", False):
        logger.info("Prematch agent skipped reason=llm_disabled")
        return None
    if not gemini_is_available():
        logger.info("Prematch agent skipped reason=gemini_unavailable")
        return None

    fixture_payload = ((artifacts.get("prematch_fixture_context") or {}).get("payload") or {})
    player_name = str(fixture_payload.get("player_name") or "Unknown player")
    opponent = str(fixture_payload.get("opponent") or "opponent")
    max_tools = int(runtime_config.get("prematch_agent_max_tools", 3))
    model_profile = str(runtime_config.get("prematch_agent_model_profile", "flash") or "flash")
    model_retries = int(runtime_config.get("prematch_agent_model_retries", 1))
    retry_delay_seconds = float(runtime_config.get("prematch_agent_retry_delay_seconds", 0.35))

    tool_plan = _select_prematch_tools(
        fixture_id=str(scope.get("fixture_id", "")),
        opponent=opponent,
        player_name=player_name,
        max_tools=max_tools,
        model_profile=model_profile,
        model_retries=model_retries,
        retry_delay_seconds=retry_delay_seconds,
    )
    if not tool_plan:
        logger.info(
            "Prematch agent aborted player=%s opponent=%s fixture_id=%s reason=no_valid_tool_plan",
            player_name,
            opponent,
            scope.get("fixture_id", ""),
        )
        return None

    selected_tools = list(tool_plan.get("selected_tools") or [])
    tool_outputs = run_prematch_tool_plan(
        selected_tools,
        artifacts=artifacts,
        session_memory=session_memory,
    )
    if not tool_outputs:
        logger.info(
            "Prematch agent aborted player=%s opponent=%s fixture_id=%s reason=empty_tool_outputs tools=%s",
            player_name,
            opponent,
            scope.get("fixture_id", ""),
            selected_tools,
        )
        return None

    prompt = build_prematch_discovery_synthesis_prompt(
        player_name=player_name,
        opponent=opponent,
        selected_tools=selected_tools,
        tool_outputs=tool_outputs,
        session_memory=dict(session_memory or {}),
        model_profile=model_profile,
    )
    logger.info(
        "Prematch agent discovery start player=%s opponent=%s fixture_id=%s profile=%s tools=%s",
        player_name,
        opponent,
        scope.get("fixture_id", ""),
        model_profile,
        selected_tools,
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
            parsed = _normalize_prematch_ai_payload(
                parsed,
                scope=scope,
                selected_tools=selected_tools,
            )
        analysis = _coerce_viable_prematch_analysis(parsed) if isinstance(parsed, dict) else None
        if analysis is None:
            if result.ok:
                logger.info(
                    "Prematch agent invalid analysis raw model=%s payload=%s",
                    model_name,
                    (result.text or "")[:2000],
                )
            logger.info(
                "Prematch agent discovery fallback model=%s status=%s valid_analysis=%s",
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
        debug.setdefault("data_gaps", [])
        curated_analysis = _curate_prematch_discoveries(
            StageAnalysis(
                stage="prematch",
                scope=dict(scope),
                summary=analysis.summary,
                confidence=analysis.confidence,
                discoveries=list(analysis.discoveries),
                supporting_artifacts=list(analysis.supporting_artifacts),
                debug=debug,
            )
        )
        curated_analysis = _apply_matchup_confidence_guardrails(
            curated_analysis,
            tool_outputs=tool_outputs,
        )
        logger.info(
            "Prematch agent discovery success player=%s opponent=%s fixture_id=%s tool_plan_model=%s discovery_model=%s discoveries=%s",
            player_name,
            opponent,
            scope.get("fixture_id", ""),
            tool_plan.get("model", ""),
            result.model,
            len(curated_analysis.discoveries),
        )
        return StageAnalysis(
            stage="prematch",
            scope=dict(curated_analysis.scope),
            summary=curated_analysis.summary,
            confidence=curated_analysis.confidence,
            discoveries=list(curated_analysis.discoveries),
            supporting_artifacts=list(curated_analysis.supporting_artifacts or selected_tools),
            debug=dict(curated_analysis.debug),
        )
    logger.info(
        "Prematch agent aborted player=%s opponent=%s fixture_id=%s reason=no_valid_analysis",
        player_name,
        opponent,
        scope.get("fixture_id", ""),
    )
    return None
