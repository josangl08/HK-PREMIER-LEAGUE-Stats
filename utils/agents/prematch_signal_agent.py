# ABOUTME: Curates one current prematch-stage overlay candidate from shared discovery candidates with continuity rules.
# ABOUTME: Mirrors the season and career signal-agent role so prematch keeps one coordinated tactical insight at a time.

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from utils.agents.signal_agent import is_materially_different


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_viable_prematch_candidate(candidate: Mapping[str, Any] | None) -> bool:
    """Return whether a prematch overlay candidate is usable for curation and continuity."""
    candidate = candidate or {}
    signal_id = str(candidate.get("signal_id") or "").strip()
    title = str(candidate.get("title") or "").strip()
    body = str(candidate.get("body") or "").strip()
    anchor = str(candidate.get("anchor") or "").strip()
    return bool(signal_id and anchor and (title or body))


def _is_clearly_stronger_prematch_candidate(
    current_candidate: Mapping[str, Any] | None,
    next_candidate: Mapping[str, Any] | None,
) -> bool:
    """Return whether a prematch replacement is clearly stronger than the current one."""
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
    same_anchor = str(current_candidate.get("anchor") or "") == str(next_candidate.get("anchor") or "")
    same_type = str(current_candidate.get("type") or "") == str(next_candidate.get("type") or "")
    required_priority_gain = 0.10 if same_anchor and same_type else 0.05

    if priority_gain >= required_priority_gain:
        return True
    if confidence_gain >= 0.05 and priority_gain >= 0.0:
        return True
    if priority_gain >= (required_priority_gain * 0.7) and confidence_gain >= 0.035:
        return True
    return False


def curate_prematch_signals(
    candidates: List[Mapping[str, Any]] | None,
    *,
    session_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Return the selected current prematch candidate and its source."""
    session_memory = session_memory or {}
    current_candidate = dict(session_memory.get("current_candidate") or {})
    if current_candidate and not is_viable_prematch_candidate(current_candidate):
        current_candidate = {}

    if not candidates:
        if current_candidate:
            return {"candidate": current_candidate, "source": "session_memory"}
        return {"candidate": None, "source": "fallback"}

    seen_novelty_keys = set(session_memory.get("seen_novelty_keys") or [])
    ranked_candidates = sorted(
        [dict(candidate) for candidate in candidates if is_viable_prematch_candidate(candidate)],
        key=lambda candidate: (
            -_safe_float(candidate.get("priority")),
            -_safe_float(candidate.get("confidence")),
            str(candidate.get("signal_id") or ""),
        ),
    )

    for candidate in ranked_candidates:
        novelty_key = str(candidate.get("novelty_key") or "")
        if novelty_key and novelty_key in seen_novelty_keys:
            continue
        if not is_materially_different(current_candidate, candidate, priority_delta_threshold=0.08):
            continue
        if current_candidate and not _is_clearly_stronger_prematch_candidate(current_candidate, candidate):
            continue
        return {"candidate": candidate, "source": "inline"}

    if current_candidate:
        return {"candidate": current_candidate, "source": "session_memory"}
    if ranked_candidates:
        return {"candidate": ranked_candidates[0], "source": "inline"}
    return {"candidate": None, "source": "fallback"}
