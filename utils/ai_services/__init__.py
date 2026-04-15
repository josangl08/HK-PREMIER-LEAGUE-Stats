# ABOUTME: Shared AI platform services for evidence routing, validation, Gemini access, and guarded orchestration.
# ABOUTME: Keeps dashboard/domain AI surfaces on deterministic-first contracts instead of inline model plumbing.

"""Shared AI platform services."""

from utils.ai_services.evidence_router import (
    EVIDENCE_DESTINATIONS,
    get_evidence_destination_meta,
    normalize_evidence_key,
)
from utils.ai_services.validators import (
    ALLOWED_CONFIDENCE_LEVELS,
    InsightPayload,
    build_fallback_insight_payload,
    normalize_confidence,
    validate_insight_payload,
)

__all__ = [
    "ALLOWED_CONFIDENCE_LEVELS",
    "EVIDENCE_DESTINATIONS",
    "InsightPayload",
    "build_fallback_insight_payload",
    "get_evidence_destination_meta",
    "normalize_confidence",
    "normalize_evidence_key",
    "validate_insight_payload",
]
