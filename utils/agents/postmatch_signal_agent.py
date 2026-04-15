# ABOUTME: Curates one current postmatch-stage overlay candidate from shared discovery candidates with continuity rules.
# ABOUTME: Mirrors season, career, and prematch signal curation so postmatch can reuse persisted runtime memory across revisits.

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from utils.agents.signal_agent import is_materially_different


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_viable_postmatch_candidate(candidate: Mapping[str, Any] | None) -> bool:
    """Return whether a postmatch overlay candidate is usable for curation and continuity."""
    candidate = candidate or {}
    signal_id = str(candidate.get("signal_id") or "").strip()
    title = str(candidate.get("title") or candidate.get("headline") or "").strip()
    body = str(candidate.get("body") or candidate.get("support") or "").strip()
    anchor = str(candidate.get("anchor") or candidate.get("evidence_key") or "").strip()
    return bool(signal_id and anchor and (title or body))


def curate_postmatch_signals(
    candidates: List[Mapping[str, Any]] | None,
    *,
    session_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Return the selected current postmatch candidate and its source."""
    session_memory = session_memory or {}
    current_candidate = dict(session_memory.get("current_candidate") or {})
    if current_candidate and not is_viable_postmatch_candidate(current_candidate):
        current_candidate = {}

    ranked_candidates = sorted(
        [dict(candidate) for candidate in candidates or [] if is_viable_postmatch_candidate(candidate)],
        key=lambda candidate: (
            -_safe_float(candidate.get("priority"), _safe_float(candidate.get("confidence"))),
            -_safe_float(candidate.get("confidence")),
            str(candidate.get("signal_id") or ""),
        ),
    )
    if not ranked_candidates:
        if current_candidate:
            return {"candidate": current_candidate, "source": "session_memory"}
        return {"candidate": None, "source": "fallback"}

    seen_novelty_keys = set(session_memory.get("seen_novelty_keys") or [])
    for candidate in ranked_candidates:
        novelty_key = str(candidate.get("novelty_key") or "")
        if novelty_key and novelty_key in seen_novelty_keys:
            continue
        if current_candidate and not is_materially_different(
            current_candidate,
            candidate,
            priority_delta_threshold=0.06,
        ):
            continue
        return {"candidate": candidate, "source": "inline"}

    if current_candidate:
        return {"candidate": current_candidate, "source": "session_memory"}
    return {"candidate": ranked_candidates[0], "source": "inline"}
