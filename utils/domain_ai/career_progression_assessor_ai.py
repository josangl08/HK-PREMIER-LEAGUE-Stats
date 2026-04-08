# ABOUTME: Guardrailed AI assessor for career progression that proposes limited phase and momentum adjustments.
# ABOUTME: Keeps LLM-based progression analysis separate from deterministic feature engineering and dashboard rendering.

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any, Dict, Optional

from utils.ai_services.llm_client import generate_gemini_content_with_status, get_dashboard_brief_model_candidates, gemini_is_available
from utils.ai_services.orchestration import parse_structured_json
from utils.ai_services.prompt_builders import build_career_progression_assessment_prompt
from utils.ai_services.validators import coerce_career_progression_assessment
from utils.career_intelligence import CareerProgressionFeatures, CareerProgressionResolution

_PHASE_ORDER = ("development", "building", "peak", "post-peak")
_CAREER_PROGRESSION_AI_CACHE_VERSION = "v1"
_CAREER_PROGRESSION_AI_CACHE_TIMEOUT_SECONDS = 60 * 60 * 24 * 30
_CAREER_PROGRESSION_FALLBACK_CACHE_TIMEOUT_SECONDS = 60 * 60


def _serialize_progression_features(features: CareerProgressionFeatures) -> Dict[str, Any]:
    payload = asdict(features)
    payload["peak_range"] = list(features.peak_range)
    return payload


def _build_progression_cache_key(player_identifier: str, features: CareerProgressionFeatures) -> str:
    payload = {
        "version": _CAREER_PROGRESSION_AI_CACHE_VERSION,
        "models": get_dashboard_brief_model_candidates(),
        "player_identifier": player_identifier,
        "features": _serialize_progression_features(features),
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"career-progression-resolution:{player_identifier}:{digest}"


def _serialize_resolution(resolution: CareerProgressionResolution) -> Dict[str, Any]:
    return asdict(resolution)


def _deserialize_resolution(payload: Dict[str, Any]) -> CareerProgressionResolution:
    return CareerProgressionResolution(
        base_phase=str(payload.get("base_phase") or "unknown"),
        resolved_phase=str(payload.get("resolved_phase") or "unknown"),
        base_momentum=int(payload.get("base_momentum") or 3),
        resolved_momentum=int(payload.get("resolved_momentum") or 3),
        ai_used=bool(payload.get("ai_used", False)),
        ai_model=str(payload.get("ai_model") or ""),
        adjustment_applied=bool(payload.get("adjustment_applied", False)),
        adjustment_reason=str(payload.get("adjustment_reason") or ""),
        confidence=str(payload.get("confidence") or "medium"),
        supporting_factors=list(payload.get("supporting_factors") or []),
        contradictions=list(payload.get("contradictions") or []),
    )


def _get_cached_resolution(cache_key: str) -> Optional[CareerProgressionResolution]:
    try:
        from utils.cache import cache

        cached = cache.get(cache_key)
        if isinstance(cached, dict):
            return _deserialize_resolution(cached)
    except Exception:
        return None
    return None


def _set_cached_resolution(cache_key: str, resolution: CareerProgressionResolution) -> None:
    try:
        from utils.cache import cache

        cache.set(
            cache_key,
            _serialize_resolution(resolution),
            timeout=(
                _CAREER_PROGRESSION_AI_CACHE_TIMEOUT_SECONDS
                if resolution.ai_used
                else _CAREER_PROGRESSION_FALLBACK_CACHE_TIMEOUT_SECONDS
            ),
        )
    except Exception:
        return


def assess_career_progression_with_ai(
    player_name: str,
    features: CareerProgressionFeatures,
) -> tuple[Optional[Any], str]:
    """Runs the guarded AI assessment and returns a validated payload plus model name."""
    if not gemini_is_available():
        return None, ""

    prompt = build_career_progression_assessment_prompt(
        player_name=player_name,
        features=_serialize_progression_features(features),
    )
    for model_name in get_dashboard_brief_model_candidates():
        result = generate_gemini_content_with_status(
            prompt,
            model_name=model_name,
            temperature=0.15,
            max_output_tokens=800,
            response_mime_type="application/json",
        )
        parsed = parse_structured_json(result.text) if result.ok else None
        assessment = coerce_career_progression_assessment(parsed)
        if assessment is not None:
            return assessment, result.model
    return None, ""


def _shift_phase(base_phase: str, adjustment: str) -> str:
    if base_phase not in _PHASE_ORDER:
        return base_phase
    idx = _PHASE_ORDER.index(base_phase)
    if adjustment == "lean_forward":
        return _PHASE_ORDER[min(len(_PHASE_ORDER) - 1, idx + 1)]
    if adjustment == "lean_backward":
        return _PHASE_ORDER[max(0, idx - 1)]
    return base_phase


def resolve_career_progression(
    features: CareerProgressionFeatures,
    assessment: Optional[Any] = None,
    *,
    model_name: str = "",
) -> CareerProgressionResolution:
    """Resolves deterministic progression plus optional guarded AI adjustments."""
    base_phase = features.base_phase
    base_momentum = max(0, min(5, int(features.base_momentum)))
    if assessment is None:
        return CareerProgressionResolution(
            base_phase=base_phase,
            resolved_phase=base_phase,
            base_momentum=base_momentum,
            resolved_momentum=base_momentum,
            ai_used=False,
            ai_model="",
            adjustment_applied=False,
            adjustment_reason="Deterministic baseline only.",
            confidence="medium",
            supporting_factors=[],
            contradictions=[],
        )

    confidence = str(assessment.confidence or "medium")
    contradictions = list(assessment.contradictions)
    adjustment_allowed = confidence in {"medium", "high"} and len(contradictions) <= 2 and base_phase != "unknown"
    if not adjustment_allowed:
        return CareerProgressionResolution(
            base_phase=base_phase,
            resolved_phase=base_phase,
            base_momentum=base_momentum,
            resolved_momentum=base_momentum,
            ai_used=True,
            ai_model=model_name,
            adjustment_applied=False,
            adjustment_reason=str(assessment.rationale or "AI assessment did not clear guardrails."),
            confidence=confidence,
            supporting_factors=list(assessment.supporting_factors),
            contradictions=contradictions,
        )

    normalized_phase_adjustment = assessment.phase_adjustment
    if features.late_peak_candidate and base_phase == "post-peak" and normalized_phase_adjustment == "none":
        if assessment.phase_hypothesis == "peak" and confidence == "high":
            normalized_phase_adjustment = "lean_backward"

    resolved_phase = _shift_phase(base_phase, normalized_phase_adjustment)
    if assessment.phase_hypothesis in _PHASE_ORDER and assessment.phase_hypothesis != resolved_phase:
        # Keep the deterministic neighborhood but prefer a compatible AI hypothesis.
        candidate_phase = _shift_phase(base_phase, normalized_phase_adjustment)
        if candidate_phase == assessment.phase_hypothesis:
            resolved_phase = candidate_phase
    resolved_momentum = max(0, min(5, base_momentum + int(assessment.momentum_adjustment)))
    adjustment_applied = resolved_phase != base_phase or resolved_momentum != base_momentum

    return CareerProgressionResolution(
        base_phase=base_phase,
        resolved_phase=resolved_phase,
        base_momentum=base_momentum,
        resolved_momentum=resolved_momentum,
        ai_used=True,
        ai_model=model_name,
        adjustment_applied=adjustment_applied,
        adjustment_reason=str(assessment.rationale or "AI assessment accepted."),
        confidence=confidence,
        supporting_factors=list(assessment.supporting_factors),
        contradictions=contradictions,
    )


def resolve_career_progression_cached(
    *,
    player_identifier: str,
    player_name: str,
    features: CareerProgressionFeatures,
) -> CareerProgressionResolution:
    """Returns a cached progression resolution, computing AI assessment only when data changed."""
    cache_key = _build_progression_cache_key(player_identifier or "unknown", features)
    cached = _get_cached_resolution(cache_key)
    if cached is not None:
        return cached

    if features.age <= 0 or features.season_count < 2:
        resolution = resolve_career_progression(features, None, model_name="")
        _set_cached_resolution(cache_key, resolution)
        return resolution

    assessment, model_name = assess_career_progression_with_ai(player_name, features)
    resolution = resolve_career_progression(features, assessment, model_name=model_name)
    _set_cached_resolution(cache_key, resolution)
    return resolution
