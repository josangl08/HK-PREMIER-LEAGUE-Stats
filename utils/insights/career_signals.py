# ABOUTME: Deterministic career-stage signal builder for role, trajectory, and development insights derived from career artifacts.
# ABOUTME: Produces ranked signal contracts for career curation without requiring LLM calls.

from __future__ import annotations

from typing import Any, Dict, List, Mapping


CAREER_STAGE_NAME = "career"
CAREER_SIGNAL_TYPES = {
    "warning",
    "opportunity",
    "pattern",
    "summary",
    "comparison",
    "trend",
    "risk",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_career_signal_contract(
    *,
    signal_id: str,
    signal_type: str,
    priority: float,
    confidence: float,
    title_hint: str,
    body_hint: str | None,
    anchor: str,
    novelty_key: str,
    evidence: Dict[str, Any],
    presentation_hint: str,
    cta_label: str = "See detail",
) -> Dict[str, Any]:
    """Build the canonical deterministic career signal contract."""
    normalized_type = signal_type if signal_type in CAREER_SIGNAL_TYPES else "pattern"
    return {
        "signal_id": signal_id,
        "stage": CAREER_STAGE_NAME,
        "type": normalized_type,
        "priority": round(float(priority), 3),
        "confidence": round(float(confidence), 3),
        "title_hint": str(title_hint or ""),
        "body_hint": str(body_hint) if body_hint is not None else None,
        "anchor": str(anchor or ""),
        "novelty_key": str(novelty_key or signal_id),
        "evidence": evidence or {},
        "presentation_hint": str(presentation_hint or "contextual"),
        "cta_label": str(cta_label or "See detail"),
    }


def _signal_from_brief_item(
    item: Mapping[str, Any],
    *,
    signal_id: str,
    signal_type: str,
    novelty_key: str,
    anchor_default: str,
    priority_default: float,
    confidence_default: float,
    presentation_hint: str,
) -> Dict[str, Any] | None:
    title = str(item.get("title") or "").strip()
    body = str(item.get("body") or "").strip()
    if not title or not body:
        return None
    anchor = str(item.get("evidence_key") or anchor_default).strip() or anchor_default
    return build_career_signal_contract(
        signal_id=signal_id,
        signal_type=signal_type,
        priority=_safe_float(item.get("priority"), priority_default),
        confidence=_safe_float(item.get("confidence"), confidence_default),
        title_hint=title,
        body_hint=body,
        anchor=anchor,
        novelty_key=str(item.get("novelty_key") or novelty_key),
        evidence=dict(item),
        presentation_hint=presentation_hint,
        cta_label=str(item.get("cta_label") or "See detail"),
    )


def build_career_signals(artifacts: Mapping[str, Mapping[str, Any]] | None) -> List[Dict[str, Any]]:
    """Build deterministic career signals from the stage artifacts."""
    if not artifacts:
        return []

    phase_payload = ((artifacts.get("career_phase_context") or {}).get("payload") or {})
    signals_payload = ((artifacts.get("career_signals_context") or {}).get("payload") or {})
    priorities_payload = ((artifacts.get("career_priorities_context") or {}).get("payload") or {})
    brief_payload = ((artifacts.get("career_dashboard_brief") or {}).get("payload") or {})

    built_signals: List[Dict[str, Any]] = []

    signal_item = next(iter(list(brief_payload.get("signals") or [])), None)
    if signal_item:
        signal = _signal_from_brief_item(
            signal_item,
            signal_id="career_brief_signal",
            signal_type="warning",
            novelty_key="career:brief_signal",
            anchor_default="career_signals_context",
            priority_default=0.82,
            confidence_default=0.78,
            presentation_hint="prominent",
        )
        if signal:
            built_signals.append(signal)

    lever_item = next(iter(list(brief_payload.get("levers") or [])), None)
    if lever_item:
        signal = _signal_from_brief_item(
            lever_item,
            signal_id="career_brief_lever",
            signal_type="opportunity",
            novelty_key="career:brief_lever",
            anchor_default="career_priorities_context",
            priority_default=0.66,
            confidence_default=0.7,
            presentation_hint="contextual",
        )
        if signal:
            built_signals.append(signal)

    thesis_body = str(((brief_payload.get("career_thesis") or {}).get("body")) or "").strip()
    if thesis_body:
        built_signals.append(
            build_career_signal_contract(
                signal_id="career_summary",
                signal_type="summary",
                priority=0.52,
                confidence=0.6,
                title_hint=str(((brief_payload.get("career_thesis") or {}).get("label")) or "Career summary"),
                body_hint=thesis_body,
                anchor="career_dashboard_brief",
                novelty_key="career:summary",
                evidence=dict(brief_payload.get("career_thesis") or {}),
                presentation_hint="micro",
                cta_label="",
            )
        )

    if not built_signals and phase_payload:
        built_signals.append(
            build_career_signal_contract(
                signal_id="career_phase_snapshot",
                signal_type="pattern",
                priority=0.5,
                confidence=0.58,
                title_hint="Career phase snapshot",
                body_hint=(
                    f"Career phase is {phase_payload.get('career_phase') or 'unknown'} with "
                    f"recommended phase {phase_payload.get('recommended_phase') or 'Find Consistency'}."
                ),
                anchor="career_phase_context",
                novelty_key="career:phase_snapshot",
                evidence=dict(phase_payload),
                presentation_hint="micro",
                cta_label="",
            )
        )

    built_signals.sort(
        key=lambda item: (
            -_safe_float(item.get("priority")),
            -_safe_float(item.get("confidence")),
            str(item.get("signal_id") or ""),
        )
    )
    return built_signals


def build_career_signals_payload(signals: List[Mapping[str, Any]] | None) -> Dict[str, Any]:
    """Build the runtime career-signals payload from deterministic signal contracts."""
    return {
        "signals": [dict(signal) for signal in (signals or [])],
        "signal_count": len(list(signals or [])),
    }
