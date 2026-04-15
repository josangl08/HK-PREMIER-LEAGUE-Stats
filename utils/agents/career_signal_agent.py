# ABOUTME: Curates one current career-stage overlay candidate from shared discovery candidates with continuity rules.
# ABOUTME: Mirrors the season signal-agent role so career keeps one coordinated current insight instead of replacing it too eagerly.

from __future__ import annotations

from typing import Dict, List, Mapping

from utils.agents.candidate_curation import (
    is_clearly_stronger_candidate,
    is_materially_different,
    safe_float,
)


def is_viable_career_candidate(candidate: Mapping[str, Any] | None) -> bool:
    """Return whether a career overlay candidate is usable for curation and continuity."""
    candidate = candidate or {}
    signal_id = str(candidate.get("signal_id") or "").strip()
    title = str(candidate.get("title") or "").strip()
    body = str(candidate.get("body") or "").strip()
    return bool(signal_id and (title or body))


def curate_career_signals(
    candidates: List[Mapping[str, Any]] | None,
    *,
    session_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Return the selected current career candidate and its source."""
    session_memory = session_memory or {}
    current_candidate = dict(session_memory.get("current_candidate") or {})
    if current_candidate and not is_viable_career_candidate(current_candidate):
        current_candidate = {}

    if not candidates:
        if current_candidate:
            return {"candidate": current_candidate, "source": "session_memory"}
        return {"candidate": None, "source": "fallback"}

    seen_novelty_keys = set(session_memory.get("seen_novelty_keys") or [])
    ranked_candidates = sorted(
        [dict(candidate) for candidate in candidates if is_viable_career_candidate(candidate)],
        key=lambda candidate: (
            -safe_float(candidate.get("priority")),
            -safe_float(candidate.get("confidence")),
            str(candidate.get("signal_id") or ""),
        ),
    )

    for candidate in ranked_candidates:
        novelty_key = str(candidate.get("novelty_key") or "")
        if novelty_key and novelty_key in seen_novelty_keys:
            continue
        if not is_materially_different(current_candidate, candidate, priority_delta_threshold=0.08):
            continue
        if current_candidate and not is_clearly_stronger_candidate(
            current_candidate,
            candidate,
            repeated_lane_priority_margin=0.1,
            confidence_margin=0.05,
            hybrid_margin_scale=0.7,
        ):
            continue
        return {"candidate": candidate, "source": "inline"}

    if current_candidate:
        return {"candidate": current_candidate, "source": "session_memory"}
    if ranked_candidates:
        return {"candidate": ranked_candidates[0], "source": "inline"}
    return {"candidate": None, "source": "fallback"}
