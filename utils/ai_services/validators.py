# ABOUTME: Shared AI insight payload schema and validation helpers for deterministic-first dashboard rendering.
# ABOUTME: Enforces confidence normalization, evidence linkage, and fallback-safe payload validation across surfaces.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from utils.ai_services.evidence_router import normalize_evidence_key


ALLOWED_CONFIDENCE_LEVELS = ("low", "medium", "high")
ALLOWED_EMPHASIS_LEVELS = ("neutral", "positive", "warning")
ALLOWED_CAREER_PHASES = ("development", "building", "peak", "post-peak", "unknown")
ALLOWED_CAREER_DECISION_PHASES = ("Ambitious", "Keep Pushing", "Maintain Consistency", "Find Consistency")
ALLOWED_PHASE_ADJUSTMENTS = ("none", "lean_forward", "lean_backward")


@dataclass(frozen=True)
class InsightPayload:
    """UI-ready insight contract shared across deterministic and synthesized flows."""

    label: str
    body: str
    support: str
    confidence: str
    evidence_key: str
    emphasis: str = "neutral"
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class CareerProgressionAssessmentPayload:
    """Guardrailed AI assessment contract for limited progression adjustments."""

    recommended_phase: str
    phase_hypothesis: str
    phase_adjustment: str
    momentum_adjustment: int
    confidence: str
    context_patterns: tuple[str, ...]
    supporting_factors: tuple[str, ...]
    blockers: tuple[str, ...]
    risk_flags: tuple[str, ...]
    next_condition: str
    contradictions: tuple[str, ...]
    insight_flags: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class EvidenceExplanationPayload:
    """Structured evidence-modal explanation contract for deeper contextual reading."""

    evidence_key: str
    headline: str
    what_this_shows: str
    why_it_matters: str
    what_to_watch: str
    confidence: str
    llm_generated: bool = False
    source_model: str = ""


def normalize_confidence(value: Any, default: str = "medium") -> str:
    """Normalizes numeric or free-text confidence values to the platform enum."""
    if isinstance(value, (int, float)):
        score = float(value)
        if score >= 0.75:
            return "high"
        if score <= 0.35:
            return "low"
        return "medium"

    normalized = str(value or "").strip().lower()
    if normalized in ALLOWED_CONFIDENCE_LEVELS:
        return normalized
    if normalized in {"strong", "certain"}:
        return "high"
    if normalized in {"weak", "uncertain"}:
        return "low"
    return default


def normalize_emphasis(value: Any, default: str = "neutral") -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ALLOWED_EMPHASIS_LEVELS else default


def normalize_career_phase(value: Any, default: str = "unknown") -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ALLOWED_CAREER_PHASES else default


def normalize_career_decision_phase(value: Any, default: str = "Find Consistency") -> str:
    normalized = str(value or "").strip().lower()
    for allowed in ALLOWED_CAREER_DECISION_PHASES:
        if normalized == allowed.lower():
            return allowed
    legacy_map = {
        "push": "Ambitious",
        "build": "Keep Pushing",
        "consolidate": "Maintain Consistency",
        "reposition": "Find Consistency",
    }
    return legacy_map.get(normalized, default)


def normalize_phase_adjustment(value: Any, default: str = "none") -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ALLOWED_PHASE_ADJUSTMENTS else default


def coerce_career_progression_assessment(raw_payload: Any) -> Optional[CareerProgressionAssessmentPayload]:
    """Coerces a dict-like AI assessment into the progression contract."""
    if isinstance(raw_payload, CareerProgressionAssessmentPayload):
        return raw_payload
    if not isinstance(raw_payload, dict):
        return None
    try:
        momentum_adjustment = int(raw_payload.get("momentum_adjustment", 0))
    except (TypeError, ValueError):
        momentum_adjustment = 0
    momentum_adjustment = max(-1, min(1, momentum_adjustment))

    def _normalize_list(key: str) -> tuple[str, ...]:
        raw_items = raw_payload.get(key)
        if not isinstance(raw_items, (list, tuple)):
            return tuple()
        return tuple(str(item).strip() for item in raw_items if str(item).strip())

    payload = CareerProgressionAssessmentPayload(
        recommended_phase=normalize_career_decision_phase(
            raw_payload.get("recommended_phase") or raw_payload.get("label")
        ),
        phase_hypothesis=normalize_career_phase(raw_payload.get("phase_hypothesis")),
        phase_adjustment=normalize_phase_adjustment(raw_payload.get("phase_adjustment")),
        momentum_adjustment=momentum_adjustment,
        confidence=normalize_confidence(raw_payload.get("confidence", "medium")),
        context_patterns=_normalize_list("context_patterns"),
        supporting_factors=_normalize_list("supporting_factors"),
        blockers=_normalize_list("blockers"),
        risk_flags=_normalize_list("risk_flags"),
        next_condition=str(raw_payload.get("next_condition") or "").strip(),
        contradictions=_normalize_list("contradictions"),
        insight_flags=_normalize_list("insight_flags"),
        rationale=str(raw_payload.get("rationale") or "").strip(),
    )
    return payload


def validate_career_progression_assessment(raw_payload: Any) -> bool:
    """Returns True when the AI progression assessment satisfies the contract."""
    payload = coerce_career_progression_assessment(raw_payload)
    if payload is None:
        return False
    if payload.phase_hypothesis not in ALLOWED_CAREER_PHASES:
        return False
    if payload.phase_adjustment not in ALLOWED_PHASE_ADJUSTMENTS:
        return False
    if payload.confidence not in ALLOWED_CONFIDENCE_LEVELS:
        return False
    if payload.momentum_adjustment not in (-1, 0, 1):
        return False
    if payload.recommended_phase not in ALLOWED_CAREER_DECISION_PHASES:
        return False
    return bool(payload.rationale and payload.next_condition)


def build_fallback_evidence_explanation_payload(
    *,
    evidence_key: str,
    headline: str,
    what_this_shows: str,
    why_it_matters: str,
    what_to_watch: str,
    confidence: Any = "medium",
    llm_generated: bool = False,
    source_model: str = "",
) -> EvidenceExplanationPayload:
    """Builds a normalized deterministic evidence explanation payload."""
    return EvidenceExplanationPayload(
        evidence_key=normalize_evidence_key(evidence_key),
        headline=str(headline or "").strip(),
        what_this_shows=str(what_this_shows or "").strip(),
        why_it_matters=str(why_it_matters or "").strip(),
        what_to_watch=str(what_to_watch or "").strip(),
        confidence=normalize_confidence(confidence),
        llm_generated=bool(llm_generated),
        source_model=str(source_model or "").strip(),
    )


def coerce_evidence_explanation_payload(raw_payload: Any) -> Optional[EvidenceExplanationPayload]:
    """Converts dict-like inputs into the structured evidence explanation contract."""
    if isinstance(raw_payload, EvidenceExplanationPayload):
        return raw_payload
    if not isinstance(raw_payload, dict):
        return None
    return build_fallback_evidence_explanation_payload(
        evidence_key=str(raw_payload.get("evidence_key") or ""),
        headline=str(raw_payload.get("headline") or "").strip(),
        what_this_shows=str(raw_payload.get("what_this_shows") or "").strip(),
        why_it_matters=str(raw_payload.get("why_it_matters") or "").strip(),
        what_to_watch=str(raw_payload.get("what_to_watch") or "").strip(),
        confidence=raw_payload.get("confidence", "medium"),
        llm_generated=raw_payload.get("llm_generated", False),
        source_model=str(raw_payload.get("source_model") or "").strip(),
    )


def validate_evidence_explanation_payload(raw_payload: Any) -> bool:
    """Returns True only when the evidence explanation satisfies the shared modal contract."""
    payload = coerce_evidence_explanation_payload(raw_payload)
    if payload is None:
        return False
    if payload.confidence not in ALLOWED_CONFIDENCE_LEVELS:
        return False
    if payload.evidence_key != normalize_evidence_key(payload.evidence_key):
        return False
    return all(
        [
            bool(payload.headline),
            bool(payload.what_this_shows),
            bool(payload.why_it_matters),
            bool(payload.what_to_watch),
        ]
    )


def build_fallback_insight_payload(
    *,
    label: str,
    body: str,
    support: str,
    evidence_key: str,
    confidence: Any = "medium",
    emphasis: Any = "neutral",
    metadata: Optional[Dict[str, Any]] = None,
) -> InsightPayload:
    """Builds a normalized deterministic payload for downstream rendering."""
    return InsightPayload(
        label=str(label or "").strip(),
        body=str(body or "").strip(),
        support=str(support or "").strip(),
        confidence=normalize_confidence(confidence),
        evidence_key=normalize_evidence_key(evidence_key),
        emphasis=normalize_emphasis(emphasis),
        metadata=metadata or {},
    )


def coerce_insight_payload(raw_payload: Any) -> Optional[InsightPayload]:
    """Converts dict-like inputs into the shared payload contract when possible."""
    if isinstance(raw_payload, InsightPayload):
        return raw_payload
    if not isinstance(raw_payload, dict):
        return None

    label = raw_payload.get("label") or raw_payload.get("title") or ""
    payload = build_fallback_insight_payload(
        label=str(label or "").strip(),
        body=str(raw_payload.get("body") or "").strip(),
        support=str(raw_payload.get("support") or "").strip(),
        confidence=raw_payload.get("confidence", "medium"),
        evidence_key=str(raw_payload.get("evidence_key") or ""),
        emphasis=raw_payload.get("emphasis", "neutral"),
        metadata=raw_payload.get("metadata") if isinstance(raw_payload.get("metadata"), dict) else {},
    )
    return payload


def validate_insight_payload(raw_payload: Any) -> bool:
    """Returns True only when the payload satisfies the shared render contract."""
    payload = coerce_insight_payload(raw_payload)
    if payload is None:
        return False
    if not payload.label or not payload.body or not payload.support:
        return False
    if payload.confidence not in ALLOWED_CONFIDENCE_LEVELS:
        return False
    if payload.evidence_key != normalize_evidence_key(payload.evidence_key):
        return False
    if payload.emphasis not in ALLOWED_EMPHASIS_LEVELS:
        return False
    return True
