# ABOUTME: Shared overlay-surface resolver for stage intelligence across season, career, prematch, and postmatch.
# ABOUTME: Normalizes stage-specific overlay candidates into one contract with presentation tiers, primary-surface enforcement, and inbox shaping.

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping

PRESENTATION_CRITICAL = "critical"
PRESENTATION_PROMINENT = "prominent"
PRESENTATION_CONTEXTUAL = "contextual"
PRESENTATION_MICRO = "micro"

PRIMARY_PRESENTATION_TIERS = (
    PRESENTATION_CRITICAL,
    PRESENTATION_PROMINENT,
    PRESENTATION_CONTEXTUAL,
)

_TIER_RANK = {
    PRESENTATION_CRITICAL: 3,
    PRESENTATION_PROMINENT: 2,
    PRESENTATION_CONTEXTUAL: 1,
    PRESENTATION_MICRO: 0,
}

_CRITICAL_PRIORITY_THRESHOLD = 0.9
_PROMINENT_PRIORITY_THRESHOLD = 0.75
_CONTEXTUAL_PRIORITY_THRESHOLD = 0.55


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _importance_score(value: Any, default: float = 0.0) -> float:
    """Normalize textual or numeric importance labels into 0..1 scores."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "high":
            return 0.82
        if normalized == "medium":
            return 0.68
        if normalized == "limited":
            return 0.54
        if normalized == "low":
            return 0.42
    return _safe_float(value, default)


def _candidate_title(candidate: Mapping[str, Any]) -> str:
    return str(
        candidate.get("title")
        or candidate.get("title_hint")
        or candidate.get("headline")
        or candidate.get("label")
        or "Stage Intelligence"
    )


def _candidate_body(candidate: Mapping[str, Any]) -> str:
    return str(candidate.get("body") or candidate.get("body_hint") or candidate.get("support") or "")


def _resolve_tier_from_importance(
    *,
    priority: float,
) -> str:
    """Resolve overlay tier from explicit surfacing urgency, not confidence."""
    if priority >= _CRITICAL_PRIORITY_THRESHOLD:
        return PRESENTATION_CRITICAL
    if priority >= _PROMINENT_PRIORITY_THRESHOLD:
        return PRESENTATION_PROMINENT
    if priority >= _CONTEXTUAL_PRIORITY_THRESHOLD:
        return PRESENTATION_CONTEXTUAL
    return PRESENTATION_MICRO


def _resolve_tier(
    candidate: Mapping[str, Any],
    *,
    priority: float,
) -> str:
    """Resolve presentation tier from explicit hint first, otherwise from importance."""
    hinted_tier = str(candidate.get("presentation_hint") or "").strip().lower()
    if hinted_tier in _TIER_RANK:
        return hinted_tier
    return _resolve_tier_from_importance(priority=priority)


def _normalize_season_candidate(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    confidence = _safe_float(candidate.get("confidence"), 0.8)
    priority = _safe_float(candidate.get("priority"))
    presentation_tier = _resolve_tier(candidate, priority=priority)
    return {
        "stage": "season",
        "signal_id": str(candidate.get("signal_id") or ""),
        "title": _candidate_title(candidate),
        "body": _candidate_body(candidate),
        "anchor": str(candidate.get("anchor") or ""),
        "priority": priority,
        "confidence": confidence,
        "presentation_tier": presentation_tier,
        "presentation_reason": "importance_resolved",
        "cta_label": "View insight",
        "dismissible": True,
        "evidence_key": str(candidate.get("signal_id") or ""),
        "type": str(candidate.get("type") or ""),
        "novelty_key": str(candidate.get("novelty_key") or ""),
        "evidence": deepcopy(dict(candidate.get("evidence") or {})),
        "source_tier": "",
        "raw_candidate": deepcopy(dict(candidate)),
    }


def _normalize_career_candidate(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    # Shared career stage analyses already emit normalized discovery candidates
    # with stable ids/novelty keys. Preserve that identity instead of remapping
    # them back onto legacy evidence keys.
    if candidate.get("signal_id") or candidate.get("novelty_key") or candidate.get("presentation_hint"):
        confidence = _safe_float(candidate.get("confidence"), 0.8)
        priority = _safe_float(candidate.get("priority"))
        presentation_tier = _resolve_tier(candidate, priority=priority)
        return {
            "stage": "career",
            "signal_id": str(candidate.get("signal_id") or candidate.get("evidence_key") or candidate.get("title") or ""),
            "title": _candidate_title(candidate),
            "body": _candidate_body(candidate),
            "anchor": str(candidate.get("anchor") or candidate.get("evidence_key") or "career_arc"),
            "priority": priority,
            "confidence": confidence,
            "presentation_tier": presentation_tier,
            "presentation_reason": "importance_resolved",
            "cta_label": str(candidate.get("cta_label") or "Ver análisis"),
            "dismissible": True,
            "evidence_key": str(candidate.get("evidence_key") or ""),
            "type": str(candidate.get("type") or "career_overlay"),
            "novelty_key": str(candidate.get("novelty_key") or candidate.get("signal_id") or candidate.get("evidence_key") or ""),
            "evidence": deepcopy(dict(candidate.get("evidence") or {})),
            "source_tier": str(candidate.get("source_tier") or ""),
            "raw_candidate": deepcopy(dict(candidate)),
        }

    source_tier = _safe_int(candidate.get("tier"), 2)
    raw_urgency = _safe_float(
        candidate.get("urgency"),
        _safe_float(candidate.get("priority"), _safe_float(candidate.get("confidence"))),
    )
    # Career still emits legacy T1/T2 urgency scores. Calibrate them into the
    # shared surface scale so contextual/prominent surfaces are not suppressed.
    if candidate.get("tier") is None:
        urgency = raw_urgency
    elif source_tier == 1:
        urgency = max(raw_urgency, 0.90)
    elif source_tier == 2:
        urgency = max(raw_urgency, 0.60)
    else:
        urgency = raw_urgency
    presentation_tier = _resolve_tier(candidate, priority=urgency)
    return {
        "stage": "career",
        "signal_id": str(candidate.get("evidence_key") or candidate.get("title") or ""),
        "title": _candidate_title(candidate),
        "body": _candidate_body(candidate),
        "anchor": str(candidate.get("evidence_key") or "career_arc"),
        "priority": urgency,
        "confidence": urgency,
        "presentation_tier": presentation_tier,
        "presentation_reason": "importance_resolved",
        "cta_label": str(candidate.get("cta_label") or "Ver análisis"),
        "dismissible": True,
        "evidence_key": str(candidate.get("evidence_key") or ""),
        "type": "career_overlay",
        "novelty_key": str(candidate.get("evidence_key") or candidate.get("title") or ""),
        "evidence": {},
        "source_tier": str(source_tier),
        "raw_candidate": deepcopy(dict(candidate)),
    }


def _normalize_postmatch_candidate(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    confidence = _importance_score(candidate.get("confidence"))
    priority = _importance_score(candidate.get("priority"))
    presentation_tier = _resolve_tier(candidate, priority=priority)
    return {
        "stage": "postmatch",
        "signal_id": str(candidate.get("evidence_key") or candidate.get("candidate_type") or ""),
        "title": _candidate_title(candidate),
        "body": _candidate_body(candidate),
        "anchor": str(candidate.get("evidence_key") or "postmatch_review"),
        "priority": priority,
        "confidence": confidence,
        "presentation_tier": presentation_tier,
        "presentation_reason": "importance_resolved",
        "cta_label": "Open review",
        "dismissible": True,
        "evidence_key": str(candidate.get("evidence_key") or ""),
        "type": str(candidate.get("emphasis") or "postmatch_reflection"),
        "novelty_key": str(candidate.get("evidence_key") or candidate.get("candidate_type") or ""),
        "evidence": {
            "match_result": candidate.get("match_result"),
            "minutes_played": candidate.get("minutes_played"),
        },
        "source_tier": "",
        "raw_candidate": deepcopy(dict(candidate)),
    }


def _normalize_prematch_candidate(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    confidence = _importance_score(candidate.get("confidence"), 0.72)
    priority = _importance_score(candidate.get("priority"))
    presentation_tier = _resolve_tier(candidate, priority=priority)
    return {
        "stage": "prematch",
        "signal_id": str(candidate.get("signal_id") or candidate.get("evidence_key") or ""),
        "title": _candidate_title(candidate),
        "body": _candidate_body(candidate),
        "anchor": str(candidate.get("anchor") or candidate.get("evidence_key") or "prematch_context"),
        "priority": priority,
        "confidence": confidence,
        "presentation_tier": presentation_tier,
        "presentation_reason": "importance_resolved",
        "cta_label": str(candidate.get("cta_label") or "Open preview"),
        "dismissible": True,
        "evidence_key": str(candidate.get("evidence_key") or ""),
        "type": str(candidate.get("type") or "prematch_context"),
        "novelty_key": str(candidate.get("novelty_key") or candidate.get("signal_id") or ""),
        "evidence": deepcopy(dict(candidate.get("evidence") or {})),
        "source_tier": "",
        "raw_candidate": deepcopy(dict(candidate)),
    }


def normalize_overlay_candidate(stage: str, candidate: Mapping[str, Any] | None) -> Dict[str, Any] | None:
    """Normalize a stage-specific candidate into the shared overlay contract."""
    if not candidate:
        return None

    stage_name = str(stage or "").strip().lower()
    if stage_name == "season":
        return _normalize_season_candidate(candidate)
    if stage_name == "career":
        return _normalize_career_candidate(candidate)
    if stage_name == "postmatch":
        return _normalize_postmatch_candidate(candidate)
    if stage_name == "prematch":
        return _normalize_prematch_candidate(candidate)

    confidence = _safe_float(candidate.get("confidence"))
    priority = _safe_float(candidate.get("priority"))
    return {
        "stage": stage_name or "unknown",
        "signal_id": str(candidate.get("signal_id") or ""),
        "title": _candidate_title(candidate),
        "body": _candidate_body(candidate),
        "anchor": str(candidate.get("anchor") or ""),
        "priority": priority,
        "confidence": confidence,
        "presentation_tier": PRESENTATION_MICRO,
        "presentation_reason": "importance_resolved",
        "cta_label": str(candidate.get("cta_label") or ""),
        "dismissible": True,
        "evidence_key": str(candidate.get("evidence_key") or ""),
        "type": str(candidate.get("type") or ""),
        "novelty_key": str(candidate.get("novelty_key") or candidate.get("signal_id") or ""),
        "evidence": deepcopy(dict(candidate.get("evidence") or {})),
        "source_tier": "",
        "raw_candidate": deepcopy(dict(candidate)),
    }


def build_overlay_inbox_entry(candidate: Mapping[str, Any], *, surfaced: bool = False) -> Dict[str, Any]:
    """Build a shared inbox entry from a normalized overlay candidate."""
    evidence = dict(candidate.get("evidence") or {})
    return {
        "stage": str(candidate.get("stage") or ""),
        "tier": str(candidate.get("presentation_tier") or PRESENTATION_MICRO),
        "title": str(candidate.get("title") or ""),
        "body": str(candidate.get("body") or ""),
        "timestamp": "",
        "anchor": str(candidate.get("anchor") or ""),
        "cta_context": {
            "stage": str(candidate.get("stage") or ""),
            "signal_id": str(candidate.get("signal_id") or ""),
            "evidence_key": str(candidate.get("evidence_key") or ""),
            "novelty_key": str(candidate.get("novelty_key") or ""),
            "anchor": str(candidate.get("anchor") or ""),
            "player_id": str(
                candidate.get("player_id")
                or evidence.get("player_id")
                or ((candidate.get("raw_candidate") or {}).get("player_id"))
                or ""
            ),
        },
        "surfaced": bool(surfaced),
    }


def choose_primary_overlay_candidate(
    candidates: List[Mapping[str, Any]] | None,
) -> Dict[str, Any] | None:
    """Choose the single visible primary overlay candidate."""
    primary_candidates = [
        dict(candidate)
        for candidate in (candidates or [])
        if str(candidate.get("presentation_tier") or "") in PRIMARY_PRESENTATION_TIERS
    ]
    if not primary_candidates:
        return None
    primary_candidates.sort(
        key=lambda candidate: (
            -_TIER_RANK.get(str(candidate.get("presentation_tier") or ""), -1),
            -_safe_float(candidate.get("priority")),
            -_safe_float(candidate.get("confidence")),
            str(candidate.get("signal_id") or ""),
        )
    )
    return primary_candidates[0]


def resolve_stage_overlay_surface(
    stage: str,
    overlay_payload: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Resolve stage overlay candidates into a shared rendering and inbox contract."""
    payload = overlay_payload or {}
    raw_candidates = list(payload.get("candidates") or [])
    normalized_candidates = [
        candidate
        for candidate in (
            normalize_overlay_candidate(stage, raw_candidate)
            for raw_candidate in raw_candidates
        )
        if candidate is not None
    ]
    primary_candidate = choose_primary_overlay_candidate(normalized_candidates)
    primary_signal_id = str((primary_candidate or {}).get("signal_id") or "")

    deferred_candidates: List[Dict[str, Any]] = []
    inbox_entries: List[Dict[str, Any]] = []
    for candidate in normalized_candidates:
        is_primary = primary_signal_id and str(candidate.get("signal_id") or "") == primary_signal_id
        if not is_primary:
            deferred_candidates.append(candidate)
        inbox_entries.append(build_overlay_inbox_entry(candidate, surfaced=is_primary))

    return {
        "stage": str(stage or "").strip().lower(),
        "candidates": normalized_candidates,
        "candidate_count": len(normalized_candidates),
        "primary_candidate": primary_candidate,
        "visible_primary": primary_candidate,
        "deferred_candidates": deferred_candidates,
        "inbox_entries": inbox_entries,
    }
