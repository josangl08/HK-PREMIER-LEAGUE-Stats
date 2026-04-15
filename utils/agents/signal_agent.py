# ABOUTME: Constrained signal curation agent that selects one season-stage Worth Noticing candidate from deterministic signals.
# ABOUTME: Applies session-memory and low-evidence rules so curated highlights remain selective and non-repetitive.

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping

from utils.agents.candidate_curation import (
    is_clearly_stronger_candidate,
    is_materially_different,
    safe_float,
)

logger = logging.getLogger(__name__)


def _build_curated_candidate(signal: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the UI-facing curated payload from a deterministic signal."""
    return {
        "kind": "worth_noticing",
        "signal_id": str(signal.get("signal_id") or ""),
        "title": str(signal.get("title_hint") or "Worth Noticing"),
        "body": str(signal.get("body_hint") or ""),
        "anchor": str(signal.get("anchor") or ""),
        "novelty_key": str(signal.get("novelty_key") or ""),
        "priority": safe_float(signal.get("priority")),
        "confidence": safe_float(signal.get("confidence")),
        "type": str(signal.get("type") or "curiosity"),
        "evidence": dict(signal.get("evidence") or {}),
    }


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
    minimum_priority = safe_float(session_state.get("minimum_priority"), 0.65)
    minimum_confidence = safe_float(session_state.get("minimum_confidence"), 0.7)
    priority_delta_threshold = safe_float(
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
        "priority": safe_float(
            session_state.get("current_priority")
            or session_memory.get("current_priority"),
        ),
        "confidence": safe_float(
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
            -safe_float(signal.get("priority")),
            -safe_float(signal.get("confidence")),
            str(signal.get("signal_id") or ""),
        ),
    )

    for signal in ranked_signals:
        priority = safe_float(signal.get("priority"))
        confidence = safe_float(signal.get("confidence"))
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

        if current_candidate and not is_clearly_stronger_candidate(
            current_candidate,
            curated,
            repeated_lane_priority_margin=0.1,
        ):
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
