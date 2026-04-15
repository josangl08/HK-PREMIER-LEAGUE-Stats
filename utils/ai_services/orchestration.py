# ABOUTME: Guarded orchestration helpers for optional AI synthesis with deterministic fallback and schema validation.
# ABOUTME: Handles JSON parsing, validation rejection, and graceful degradation for shared dashboard AI services.

from __future__ import annotations

import json
from typing import Any, Callable, Iterable, List, Optional, Sequence, TypeVar

from utils.ai_services.validators import coerce_insight_payload, validate_insight_payload

T = TypeVar("T")


def parse_structured_json(raw_text: Any) -> Any:
    """Parses a JSON response string into Python data or returns None."""
    if not raw_text or not isinstance(raw_text, str):
        return None
    try:
        return json.loads(raw_text)
    except (TypeError, ValueError):
        return None


def resolve_with_deterministic_fallback(
    *,
    candidate: Optional[T],
    fallback: T,
    validator: Optional[Callable[[T], bool]] = None,
) -> T:
    """Returns the candidate when valid, otherwise the deterministic fallback."""
    if candidate is None:
        return fallback
    if validator and not validator(candidate):
        return fallback
    return candidate


def validate_payload_collection(raw_payloads: Any) -> bool:
    """Validates a list of insight payloads against the shared contract."""
    if not isinstance(raw_payloads, Sequence):
        return False
    normalized = [coerce_insight_payload(payload) for payload in raw_payloads]
    return bool(normalized) and all(validate_insight_payload(payload) for payload in normalized)


def resolve_payload_collection(
    raw_payloads: Any,
    fallback_payloads: Iterable[T],
) -> List[Any]:
    """Returns a validated synthesized payload collection or deterministic fallback payloads."""
    fallback_list = list(fallback_payloads)
    if not validate_payload_collection(raw_payloads):
        return fallback_list
    return [coerce_insight_payload(payload) for payload in raw_payloads]
