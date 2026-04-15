# ABOUTME: Shared candidate-curation helpers for stage signal agents that rank and replace current insights conservatively.
# ABOUTME: Centralizes numeric coercion and replacement heuristics so season and career use the same continuity rules.

from __future__ import annotations

from typing import Any, Mapping


def safe_float(value: Any, default: float = 0.0) -> float:
    """Return a safe float conversion for mixed payload fields."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_materially_different(
    current_candidate: Mapping[str, Any] | None,
    next_candidate: Mapping[str, Any] | None,
    *,
    priority_delta_threshold: float = 0.08,
) -> bool:
    """Return whether a candidate differs enough from the current one to justify replacement."""
    if not next_candidate:
        return False
    if not current_candidate:
        return True

    current_novelty_key = str(current_candidate.get("novelty_key") or "")
    next_novelty_key = str(next_candidate.get("novelty_key") or "")
    if current_novelty_key and current_novelty_key == next_novelty_key:
        return False

    current_signal_id = str(current_candidate.get("signal_id") or "")
    next_signal_id = str(next_candidate.get("signal_id") or "")
    current_anchor = str(current_candidate.get("anchor") or "")
    next_anchor = str(next_candidate.get("anchor") or "")
    current_type = str(current_candidate.get("type") or "")
    next_type = str(next_candidate.get("type") or "")
    priority_delta = abs(
        safe_float(next_candidate.get("priority")) - safe_float(current_candidate.get("priority"))
    )

    if (
        current_signal_id
        and current_signal_id == next_signal_id
        and current_anchor == next_anchor
        and priority_delta < priority_delta_threshold
    ):
        return False

    if (
        current_anchor
        and current_anchor == next_anchor
        and current_type
        and current_type == next_type
        and priority_delta < (priority_delta_threshold + 0.04)
    ):
        return False

    return True


def is_clearly_stronger_candidate(
    current_candidate: Mapping[str, Any] | None,
    next_candidate: Mapping[str, Any] | None,
    *,
    base_priority_margin: float = 0.05,
    confidence_margin: float = 0.05,
    repeated_lane_priority_margin: float = 0.1,
    hybrid_margin_scale: float = 0.7,
) -> bool:
    """Return whether a replacement is clearly stronger than the currently visible candidate."""
    if not next_candidate:
        return False
    if not current_candidate:
        return True

    current_priority = safe_float(current_candidate.get("priority"))
    next_priority = safe_float(next_candidate.get("priority"))
    current_confidence = safe_float(current_candidate.get("confidence"))
    next_confidence = safe_float(next_candidate.get("confidence"))
    priority_gain = next_priority - current_priority
    confidence_gain = next_confidence - current_confidence
    current_anchor = str(current_candidate.get("anchor") or "")
    next_anchor = str(next_candidate.get("anchor") or "")
    current_type = str(current_candidate.get("type") or "")
    next_type = str(next_candidate.get("type") or "")

    same_reading_lane = (
        current_anchor
        and current_anchor == next_anchor
        and current_type
        and current_type == next_type
    )
    required_priority_gain = repeated_lane_priority_margin if same_reading_lane else base_priority_margin

    if priority_gain >= required_priority_gain:
        return True
    if confidence_gain >= confidence_margin and priority_gain >= 0.0:
        return True
    if (
        priority_gain >= (required_priority_gain * hybrid_margin_scale)
        and confidence_gain >= (confidence_margin * hybrid_margin_scale)
    ):
        return True
    return False
