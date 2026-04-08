# ABOUTME: Shared AI insight payload schema and validation helpers for deterministic-first dashboard rendering.
# ABOUTME: Enforces confidence normalization, evidence linkage, and fallback-safe payload validation across surfaces.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from utils.ai_services.evidence_router import normalize_evidence_key


ALLOWED_CONFIDENCE_LEVELS = ("low", "medium", "high")
ALLOWED_EMPHASIS_LEVELS = ("neutral", "positive", "warning")
ALLOWED_CAREER_PHASES = ("development", "building", "peak", "post-peak", "unknown")
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

    phase_hypothesis: str
    phase_adjustment: str
    momentum_adjustment: int
    confidence: str
    supporting_factors: tuple[str, ...]
    contradictions: tuple[str, ...]
    insight_flags: tuple[str, ...]
    rationale: str


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
        phase_hypothesis=normalize_career_phase(raw_payload.get("phase_hypothesis")),
        phase_adjustment=normalize_phase_adjustment(raw_payload.get("phase_adjustment")),
        momentum_adjustment=momentum_adjustment,
        confidence=normalize_confidence(raw_payload.get("confidence", "medium")),
        supporting_factors=_normalize_list("supporting_factors"),
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
    return bool(payload.rationale)


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
