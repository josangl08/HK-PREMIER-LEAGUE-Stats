# ABOUTME: Initial career-stage agent that emits persisted discoveries from deterministic career intelligence artifacts.
# ABOUTME: Keeps the visible career dashboard deterministic-first while packaging background findings for overlays and inbox recovery.

from __future__ import annotations

from typing import Any, Dict, Mapping

from utils.agents.stage_agents.base import StageAgent
from utils.domain_ai.career_agentic_discovery import synthesize_career_stage_analysis
from utils.intelligence.discovery_contracts import StageAnalysis, StageDiscovery


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
        overlay_payload = ((artifacts.get("career_overlay_candidates") or {}).get("payload") or {})

        discoveries = []
        for idx, candidate in enumerate(list(overlay_payload.get("candidates") or [])[:3]):
            title = str(candidate.get("title") or f"Career signal {idx + 1}")
            body = str(candidate.get("body") or "")
            evidence_key = str(candidate.get("evidence_key") or "career_arc")
            urgency = float(candidate.get("urgency") or 0.0)
            discoveries.append(
                StageDiscovery(
                    discovery_id=f"career:{evidence_key}:{idx}",
                    stage="career",
                    type="warning" if urgency >= 0.85 else "opportunity" if urgency >= 0.6 else "pattern",
                    title=title,
                    body=body,
                    priority=urgency,
                    confidence=urgency,
                    evidence_keys=[evidence_key],
                    novelty_key=evidence_key or title,
                    anchor=evidence_key,
                    presentation_hint="critical" if urgency >= 0.9 else "contextual",
                    cta_label=str(candidate.get("cta_label") or "Ver análisis"),
                    metadata=dict(candidate),
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
                "career_overlay_candidates",
            ],
            debug={
                "career_phase": phase_payload.get("career_phase"),
                "recommended_phase": phase_payload.get("recommended_phase"),
                "priority_count": priorities_payload.get("priority_count", 0),
                "coach_confidence": (signals_payload.get("coach_confidence") or {}).get("label"),
            },
        )
