# ABOUTME: Guardrailed AI assessor for career progression that proposes limited phase and momentum adjustments.
# ABOUTME: Keeps LLM-based progression analysis separate from deterministic feature engineering and dashboard rendering.

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from threading import Lock
from typing import Any, Dict, Optional

from utils.ai_services.llm_client import generate_gemini_content_with_status, get_dashboard_brief_model_candidates, gemini_is_available
from utils.ai_services.orchestration import parse_structured_json
from utils.ai_services.prompt_builders import build_career_progression_assessment_prompt
from utils.ai_services.validators import coerce_career_progression_assessment
from utils.career_intelligence import (
    CareerProgressionFeatures,
    CareerProgressionResolution,
    CareerComparativeScorecard,
    validate_career_decision_phase,
)

_PHASE_ORDER = ("development", "building", "peak", "post-peak")
_CAREER_PROGRESSION_AI_CACHE_VERSION = "v1"
_CAREER_PROGRESSION_AI_CACHE_TIMEOUT_SECONDS = 60 * 60 * 24 * 30
_CAREER_PROGRESSION_FALLBACK_CACHE_TIMEOUT_SECONDS = 60 * 60
_CAREER_PROGRESSION_CACHE_LOCK = Lock()


def _serialize_progression_features(features: CareerProgressionFeatures) -> Dict[str, Any]:
    payload = asdict(features)
    payload["peak_range"] = list(features.peak_range)
    return payload


def _serialize_scorecard(scorecard: CareerComparativeScorecard) -> Dict[str, Any]:
    return asdict(scorecard)


def _build_progression_cache_key(
    player_identifier: str,
    features: CareerProgressionFeatures,
    scorecard: CareerComparativeScorecard,
) -> str:
    payload = {
        "version": _CAREER_PROGRESSION_AI_CACHE_VERSION,
        "models": get_dashboard_brief_model_candidates(),
        "player_identifier": player_identifier,
        "features": _serialize_progression_features(features),
        "scorecard": _serialize_scorecard(scorecard),
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
        recommended_phase=str(payload.get("recommended_phase") or "Find Consistency"),
        ai_used=bool(payload.get("ai_used", False)),
        ai_model=str(payload.get("ai_model") or ""),
        adjustment_applied=bool(payload.get("adjustment_applied", False)),
        adjustment_reason=str(payload.get("adjustment_reason") or ""),
        validation_status=str(payload.get("validation_status") or "reject"),
        alignment_score=float(payload.get("alignment_score") or 0.55),
        blocking_rules=list(payload.get("blocking_rules") or []),
        context_patterns=list(payload.get("context_patterns") or []),
        confidence=str(payload.get("confidence") or "medium"),
        supporting_factors=list(payload.get("supporting_factors") or []),
        blockers=list(payload.get("blockers") or []),
        risk_flags=list(payload.get("risk_flags") or []),
        next_condition=str(payload.get("next_condition") or ""),
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
    scorecard: CareerComparativeScorecard,
    assessment: Optional[Any] = None,
    *,
    model_name: str = "",
) -> CareerProgressionResolution:
    """Resolves deterministic progression plus optional guarded AI adjustments."""
    base_phase = features.base_phase
    base_momentum = max(0, min(5, int(features.base_momentum)))
    if assessment is None:
        audit = validate_career_decision_phase(scorecard, None)
        return CareerProgressionResolution(
            base_phase=base_phase,
            resolved_phase=base_phase,
            base_momentum=base_momentum,
            resolved_momentum=base_momentum,
            recommended_phase=audit.final_phase,
            ai_used=False,
            ai_model="",
            adjustment_applied=False,
            adjustment_reason="Deterministic baseline only.",
            validation_status=audit.validation_status,
            alignment_score=audit.alignment_score,
            blocking_rules=audit.blocking_rules,
            context_patterns=[],
            confidence="medium",
            supporting_factors=audit.main_drivers,
            blockers=audit.blockers,
            risk_flags=audit.risk_flags,
            next_condition=audit.next_condition,
            contradictions=[],
        )

    confidence = str(assessment.confidence or "medium")
    contradictions = list(assessment.contradictions)
    adjustment_allowed = confidence in {"medium", "high"} and len(contradictions) <= 2 and base_phase != "unknown"
    audit = validate_career_decision_phase(scorecard, assessment)
    if not adjustment_allowed:
        return CareerProgressionResolution(
            base_phase=base_phase,
            resolved_phase=base_phase,
            base_momentum=base_momentum,
            resolved_momentum=base_momentum,
            recommended_phase=audit.final_phase,
            ai_used=True,
            ai_model=model_name,
            adjustment_applied=False,
            adjustment_reason=str(assessment.rationale or "AI assessment did not clear guardrails."),
            validation_status=audit.validation_status,
            alignment_score=audit.alignment_score,
            blocking_rules=audit.blocking_rules,
            context_patterns=list(getattr(assessment, "context_patterns", ()) or ()),
            confidence=confidence,
            supporting_factors=list(assessment.supporting_factors),
            blockers=list(getattr(assessment, "blockers", ()) or ()),
            risk_flags=list(getattr(assessment, "risk_flags", ()) or ()),
            next_condition=str(getattr(assessment, "next_condition", "") or audit.next_condition),
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
    if (
        base_phase == "post-peak"
        and resolved_phase == "peak"
        and (
            features.coach_confidence_direction == "down"
            or features.minutes_trend_pct <= -10
            or features.recent_minutes_delta_pct <= -10
            or features.recent_metric_delta_pct <= -10
        )
    ):
        resolved_phase = "post-peak"
    resolved_momentum = max(0, min(5, base_momentum + int(assessment.momentum_adjustment)))
    adjustment_applied = resolved_phase != base_phase or resolved_momentum != base_momentum

    return CareerProgressionResolution(
        base_phase=base_phase,
        resolved_phase=resolved_phase,
        base_momentum=base_momentum,
        resolved_momentum=resolved_momentum,
        recommended_phase=audit.final_phase,
        ai_used=True,
        ai_model=model_name,
        adjustment_applied=adjustment_applied,
        adjustment_reason=str(assessment.rationale or "AI assessment accepted."),
        validation_status=audit.validation_status,
        alignment_score=audit.alignment_score,
        blocking_rules=audit.blocking_rules,
        context_patterns=list(getattr(assessment, "context_patterns", ()) or ()),
        confidence=confidence,
        supporting_factors=list(assessment.supporting_factors),
        blockers=list(getattr(assessment, "blockers", ()) or ()),
        risk_flags=list(getattr(assessment, "risk_flags", ()) or ()),
        next_condition=str(getattr(assessment, "next_condition", "") or audit.next_condition),
        contradictions=contradictions,
    )


def resolve_career_progression_cached(
    *,
    player_identifier: str,
    player_name: str,
    features: CareerProgressionFeatures,
    scorecard: CareerComparativeScorecard,
) -> CareerProgressionResolution:
    """Returns a cached progression resolution, computing AI assessment only when data changed."""
    cache_key = _build_progression_cache_key(player_identifier or "unknown", features, scorecard)
    cached = _get_cached_resolution(cache_key)
    if cached is not None:
        return cached

    with _CAREER_PROGRESSION_CACHE_LOCK:
        cached = _get_cached_resolution(cache_key)
        if cached is not None:
            return cached

        if features.age <= 0 or features.season_count < 2:
            resolution = resolve_career_progression(features, scorecard, None, model_name="")
            _set_cached_resolution(cache_key, resolution)
            return resolution

        assessment, model_name = assess_career_progression_with_ai(player_name, features)
        resolution = resolve_career_progression(features, scorecard, assessment, model_name=model_name)
        _set_cached_resolution(cache_key, resolution)
        return resolution
