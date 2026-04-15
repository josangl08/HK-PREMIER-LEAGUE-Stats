# ABOUTME: Initial career-stage agent that emits persisted discoveries from deterministic career intelligence artifacts.
# ABOUTME: Keeps the visible career dashboard deterministic-first while packaging background findings for overlays and inbox recovery.

from __future__ import annotations

from typing import Any, Dict, Mapping

from utils.agents.stage_agents.base import StageAgent
from utils.domain_ai.career_agentic_discovery import synthesize_career_stage_analysis
from utils.intelligence.discovery_contracts import StageAnalysis, StageDiscovery


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_brief_discovery(
    item: Mapping[str, Any],
    *,
    scope: Mapping[str, str],
    discovery_id: str,
    discovery_type: str,
    novelty_key: str,
    anchor_default: str,
    priority_default: float,
    confidence_default: float,
    presentation_hint: str,
) -> StageDiscovery | None:
    """Build a shared discovery from a normalized dashboard-brief item."""
    title = str(item.get("title") or "").strip()
    body = str(item.get("body") or "").strip()
    if not title or not body:
        return None
    evidence_key = str(item.get("evidence_key") or anchor_default).strip() or anchor_default
    return StageDiscovery(
        discovery_id=discovery_id,
        stage="career",
        type=discovery_type,
        title=title,
        body=body,
        priority=_safe_float(item.get("priority"), priority_default),
        confidence=_safe_float(item.get("confidence"), confidence_default),
        evidence_keys=[evidence_key],
        novelty_key=str(item.get("novelty_key") or novelty_key),
        anchor=evidence_key,
        presentation_hint=presentation_hint,
        cta_label=str(item.get("cta_label") or "See detail"),
        metadata=dict(item),
        supporting_artifacts=[
            "career_phase_context",
            "career_signals_context",
            "career_priorities_context",
            "career_dashboard_brief",
        ],
    )


class CareerStageAgent(StageAgent):
    stage_name = "career"

    def analyze(
        self,
        *,
        scope: Dict[str, str],
        artifacts: Mapping[str, Mapping[str, Any]],
        session_memory: Mapping[str, Any] | None = None,
    ) -> StageAnalysis:
        ai_analysis = synthesize_career_stage_analysis(
            scope=scope,
            artifacts=artifacts,
            session_memory=session_memory,
        )
        if ai_analysis is not None:
            return ai_analysis
        phase_payload = ((artifacts.get("career_phase_context") or {}).get("payload") or {})
        signals_payload = ((artifacts.get("career_signals_context") or {}).get("payload") or {})
        priorities_payload = ((artifacts.get("career_priorities_context") or {}).get("payload") or {})
        brief_payload = ((artifacts.get("career_dashboard_brief") or {}).get("payload") or {})

        discoveries = []

        signal_item = next(iter(list(brief_payload.get("signals") or [])), None)
        if signal_item:
            discovery = _build_brief_discovery(
                signal_item,
                scope=scope,
                discovery_id="career:brief_signal:0",
                discovery_type="warning",
                novelty_key="career:brief_signal",
                anchor_default="career_signals_context",
                priority_default=0.82,
                confidence_default=0.78,
                presentation_hint="prominent",
            )
            if discovery is not None:
                discoveries.append(discovery)

        lever_item = next(iter(list(brief_payload.get("levers") or [])), None)
        if lever_item:
            discovery = _build_brief_discovery(
                lever_item,
                scope=scope,
                discovery_id="career:brief_lever:1",
                discovery_type="opportunity",
                novelty_key="career:brief_lever",
                anchor_default="career_priorities_context",
                priority_default=0.66,
                confidence_default=0.7,
                presentation_hint="contextual",
            )
            if discovery is not None:
                discoveries.append(discovery)

        if not discoveries:
            summary_body = str(((brief_payload.get("career_thesis") or {}).get("body")) or "").strip()
            if summary_body:
                discoveries.append(
                    StageDiscovery(
                        discovery_id=f"career:summary:{scope.get('player_id', 'unknown')}",
                        stage="career",
                        type="summary",
                        title=str(((brief_payload.get("career_thesis") or {}).get("label")) or "Career summary"),
                        body=summary_body,
                        priority=0.52,
                        confidence=0.6,
                        evidence_keys=["career_dashboard_brief"],
                        novelty_key="career:summary",
                        anchor="career_dashboard_brief",
                        presentation_hint="micro",
                        cta_label="",
                        metadata=dict(brief_payload.get("career_thesis") or {}),
                        supporting_artifacts=[
                            "career_phase_context",
                            "career_signals_context",
                            "career_priorities_context",
                            "career_dashboard_brief",
                        ],
                    )
                )

        summary = str(((brief_payload.get("career_thesis") or {}).get("body")) or "")
        if not summary:
            summary = (
                f"Career phase is {phase_payload.get('career_phase') or 'unknown'} with "
                f"recommended phase {phase_payload.get('recommended_phase') or 'Find Consistency'}."
            )

        return StageAnalysis(
            stage="career",
            scope=scope,
            summary=summary,
            confidence="medium",
            discoveries=discoveries,
            supporting_artifacts=[
                "career_phase_context",
                "career_signals_context",
                "career_priorities_context",
                "career_dashboard_brief",
            ],
            debug={
                "career_phase": phase_payload.get("career_phase"),
                "recommended_phase": phase_payload.get("recommended_phase"),
                "priority_count": priorities_payload.get("priority_count", 0),
                "coach_confidence": (signals_payload.get("coach_confidence") or {}).get("label"),
                "fallback_source": "career_dashboard_brief",
            },
        )
