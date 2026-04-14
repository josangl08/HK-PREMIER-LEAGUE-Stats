# ABOUTME: Initial postmatch-stage agent that emits persisted discoveries from deterministic reflection artifacts.
# ABOUTME: Packages recent-match takeaways into the shared stage-analysis contract so overlays and inbox can consume one runtime path.

from __future__ import annotations

from typing import Any, Dict, Mapping

from utils.agents.stage_agents.base import StageAgent
from utils.intelligence.discovery_contracts import StageAnalysis, StageDiscovery


class PostmatchStageAgent(StageAgent):
    stage_name = "postmatch"

    def analyze(
        self,
        *,
        scope: Dict[str, str],
        artifacts: Mapping[str, Mapping[str, Any]],
        session_memory: Mapping[str, Any] | None = None,
    ) -> StageAnalysis:
        del session_memory
        match_payload = ((artifacts.get("postmatch_match_context") or {}).get("payload") or {})
        performance_payload = ((artifacts.get("postmatch_performance_context") or {}).get("payload") or {})
        reflection_payloads = ((artifacts.get("postmatch_reflection_payloads") or {}).get("payload") or {})
        overlay_payload = ((artifacts.get("postmatch_overlay_candidates") or {}).get("payload") or {})

        selected_reflection = dict((reflection_payloads.get("selected_payload") or {}))
        selected_candidate = dict((overlay_payload.get("selected_candidate") or {}))
        confidence_label = str(selected_reflection.get("confidence") or "limited").lower()
        confidence_score = {"high": 0.82, "medium": 0.68, "limited": 0.54}.get(confidence_label, 0.54)
        evidence_key = str(
            selected_candidate.get("evidence_key")
            or selected_reflection.get("evidence_key")
            or "postmatch_review"
        )
        title = str(selected_candidate.get("headline") or selected_reflection.get("label") or "Post-match takeaway")
        body = str(
            selected_candidate.get("body")
            or selected_candidate.get("support")
            or selected_reflection.get("body")
            or "Recent match review is ready."
        )

        discoveries = []
        if title or body:
            discoveries.append(
                StageDiscovery(
                    discovery_id=f"postmatch:{scope.get('match_id', evidence_key)}",
                    stage="postmatch",
                    type="pattern",
                    title=title,
                    body=body,
                    priority=confidence_score,
                    confidence=confidence_score,
                    evidence_keys=[evidence_key],
                    novelty_key=str(scope.get("match_id") or evidence_key),
                    anchor=evidence_key,
                    presentation_hint="contextual" if confidence_score < 0.75 else "prominent",
                    cta_label="Open review",
                    metadata={
                        "result": match_payload.get("result"),
                        "minutes_played": performance_payload.get("minutes_played"),
                        "emphasis": selected_candidate.get("emphasis") or selected_reflection.get("emphasis"),
                    },
                    supporting_artifacts=[
                        "postmatch_match_context",
                        "postmatch_performance_context",
                        "postmatch_reflection_payloads",
                        "postmatch_overlay_candidates",
                    ],
                )
            )

        return StageAnalysis(
            stage="postmatch",
            scope=scope,
            summary=body or "Postmatch reflection is ready.",
            confidence=confidence_label or "medium",
            discoveries=discoveries,
            supporting_artifacts=[
                "postmatch_match_context",
                "postmatch_performance_context",
                "postmatch_reflection_payloads",
                "postmatch_overlay_candidates",
            ],
            debug={
                "result": match_payload.get("result"),
                "minutes_played": performance_payload.get("minutes_played"),
            },
        )
