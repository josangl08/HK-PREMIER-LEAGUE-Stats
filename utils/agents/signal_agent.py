# ABOUTME: Constrained signal curation agent that selects one season-stage Worth Noticing candidate from deterministic signals.
# ABOUTME: Applies session-memory and low-evidence rules so curated highlights remain selective and non-repetitive.

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping

logger = logging.getLogger(__name__)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_curated_candidate(signal: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the UI-facing curated payload from a deterministic signal."""
    return {
        "kind": "worth_noticing",
        "signal_id": str(signal.get("signal_id") or ""),
        "title": str(signal.get("title_hint") or "Worth Noticing"),
        "body": str(signal.get("body_hint") or ""),
        "anchor": str(signal.get("anchor") or ""),
        "novelty_key": str(signal.get("novelty_key") or ""),
        "priority": _safe_float(signal.get("priority")),
        "confidence": _safe_float(signal.get("confidence")),
        "type": str(signal.get("type") or "curiosity"),
        "evidence": dict(signal.get("evidence") or {}),
    }


def is_materially_different(
    current_candidate: Mapping[str, Any] | None,
    next_candidate: Mapping[str, Any] | None,
    *,
    priority_delta_threshold: float = 0.08,
) -> bool:
    """Return whether a new candidate is meaningfully different enough to replace the current one."""
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
        _safe_float(next_candidate.get("priority")) - _safe_float(current_candidate.get("priority"))
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


def _is_clearly_stronger(
    current_candidate: Mapping[str, Any] | None,
    next_candidate: Mapping[str, Any] | None,
    *,
    base_priority_margin: float = 0.05,
    confidence_margin: float = 0.05,
    repeated_type_priority_margin: float = 0.1,
) -> bool:
    """Return whether a replacement is clearly stronger than the currently shown insight."""
    if not next_candidate:
        return False
    if not current_candidate:
        return True

    current_priority = _safe_float(current_candidate.get("priority"))
    next_priority = _safe_float(next_candidate.get("priority"))
    current_confidence = _safe_float(current_candidate.get("confidence"))
    next_confidence = _safe_float(next_candidate.get("confidence"))
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
    required_priority_gain = repeated_type_priority_margin if same_reading_lane else base_priority_margin

    if priority_gain >= required_priority_gain:
        return True
    if confidence_gain >= confidence_margin and priority_gain >= 0.0:
        return True
    if priority_gain >= (required_priority_gain * 0.7) and confidence_gain >= (confidence_margin * 0.7):
        return True
    return False


def curate_signals(
    signals: List[Mapping[str, Any]] | None,
    session_state: Mapping[str, Any] | None = None,
    session_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Any] | None:
    """Return one curated Worth Noticing candidate or abstain when evidence is weak."""
    if not signals:
        logger.info("Signal agent abstained: no signals available.")
        return None

    session_state = session_state or {}
    session_memory = session_memory or session_state.get("session_memory") or {}
    seen_novelty_keys = set(session_state.get("seen_novelty_keys") or [])
    seen_novelty_keys.update(session_memory.get("seen_novelty_keys") or [])
    current_anchor = str(
        session_state.get("current_anchor")
        or session_memory.get("current_anchor")
        or ""
    )
    minimum_priority = _safe_float(session_state.get("minimum_priority"), 0.65)
    minimum_confidence = _safe_float(session_state.get("minimum_confidence"), 0.7)
    priority_delta_threshold = _safe_float(
        session_state.get("priority_delta_threshold"),
        0.08,
    )
    current_candidate = {
        "signal_id": str(
            session_state.get("current_signal_id")
            or session_memory.get("last_curated_signal_id")
            or ""
        ),
        "novelty_key": str(
            session_state.get("current_novelty_key")
            or session_memory.get("current_novelty_key")
            or ""
        ),
        "anchor": current_anchor,
        "priority": _safe_float(
            session_state.get("current_priority")
            or session_memory.get("current_priority"),
        ),
        "confidence": _safe_float(
            session_state.get("current_confidence")
            or session_memory.get("current_confidence"),
        ),
        "type": str(
            session_state.get("current_type")
            or session_memory.get("current_type")
            or ""
        ),
    }
    if not any(current_candidate.values()):
        current_candidate = {}

    ranked_signals = sorted(
        signals,
        key=lambda signal: (
            signal.get("anchor") != current_anchor if current_anchor else False,
            -_safe_float(signal.get("priority")),
            -_safe_float(signal.get("confidence")),
            str(signal.get("signal_id") or ""),
        ),
    )

    for signal in ranked_signals:
        priority = _safe_float(signal.get("priority"))
        confidence = _safe_float(signal.get("confidence"))
        novelty_key = str(signal.get("novelty_key") or "")
        if priority < minimum_priority or confidence < minimum_confidence:
            continue
        if novelty_key and novelty_key in seen_novelty_keys:
            logger.info(
                "Signal agent skipped repeated novelty_key=%s signal_id=%s",
                novelty_key,
                str(signal.get("signal_id") or ""),
            )
            continue

        curated = _build_curated_candidate(signal)
        if not is_materially_different(
            current_candidate,
            curated,
            priority_delta_threshold=priority_delta_threshold,
        ):
            logger.info(
                "Signal agent suppressed replacement signal_id=%s novelty_key=%s current_signal_id=%s",
                curated["signal_id"],
                curated["novelty_key"],
                current_candidate.get("signal_id") or "",
            )
            continue

        if current_candidate and not _is_clearly_stronger(current_candidate, curated):
            logger.info(
                "Signal agent held current insight signal_id=%s candidate_signal_id=%s current_type=%s candidate_type=%s",
                current_candidate.get("signal_id") or "",
                curated["signal_id"],
                current_candidate.get("type") or "",
                curated["type"],
            )
            continue

        logger.info(
            "Signal agent selected signal_id=%s novelty_key=%s priority=%.2f confidence=%.2f",
            curated["signal_id"],
            curated["novelty_key"],
            curated["priority"],
            curated["confidence"],
        )
        logger.debug("Signal agent curated payload=%s", curated)
        return curated

    logger.info(
        "Signal agent abstained: no signal cleared thresholds min_priority=%.2f min_confidence=%.2f seen=%s",
        minimum_priority,
        minimum_confidence,
        sorted(seen_novelty_keys),
    )
    return None
