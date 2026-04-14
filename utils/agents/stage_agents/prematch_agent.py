# ABOUTME: Initial prematch-stage agent that emits persisted fixture discoveries from deterministic prematch artifacts.
# ABOUTME: Packages matchup context and game-plan outputs into the shared stage-analysis contract for overlays and inbox recovery.

from __future__ import annotations

from typing import Any, Dict, Mapping

from utils.agents.stage_agents.base import StageAgent
from utils.intelligence.discovery_contracts import StageAnalysis, StageDiscovery


class PrematchStageAgent(StageAgent):
    stage_name = "prematch"

    def analyze(
        self,
        *,
        scope: Dict[str, str],
        artifacts: Mapping[str, Mapping[str, Any]],
        session_memory: Mapping[str, Any] | None = None,
    ) -> StageAnalysis:
        del session_memory
        fixture_payload = ((artifacts.get("prematch_fixture_context") or {}).get("payload") or {})
        recent_form_payload = ((artifacts.get("prematch_recent_form_context") or {}).get("payload") or {})
        head_to_head_payload = ((artifacts.get("prematch_head_to_head_context") or {}).get("payload") or {})
        game_plan_payload = ((artifacts.get("prematch_game_plan_context") or {}).get("payload") or {})

        opponent = str(fixture_payload.get("opponent") or "opponent")
        confidence_label = str(game_plan_payload.get("confidence") or "limited").lower()
        confidence_score = {"high": 0.82, "medium": 0.68, "limited": 0.54}.get(confidence_label, 0.54)

        discoveries = [
            StageDiscovery(
                discovery_id=f"prematch-plan:{scope.get('fixture_id', opponent)}",
                stage="prematch",
                type="tactical_plan",
                title=f"Pre-match focus vs {opponent}",
                body=str(game_plan_payload.get("plan_headline") or ""),
                priority=confidence_score,
                confidence=confidence_score,
                evidence_keys=["prematch_game_plan"],
                novelty_key=str(scope.get("fixture_id") or opponent),
                anchor="prematch_game_plan_context",
                presentation_hint="contextual",
                cta_label="Open preview",
                metadata=dict(game_plan_payload),
                supporting_artifacts=[
                    "prematch_fixture_context",
                    "prematch_recent_form_context",
                    "prematch_head_to_head_context",
                    "prematch_game_plan_context",
                ],
            )
        ]

        meeting_count = int(head_to_head_payload.get("meeting_count", 0) or 0)
        if meeting_count > 0:
            discoveries.append(
                StageDiscovery(
                    discovery_id=f"prematch-h2h:{scope.get('fixture_id', opponent)}",
                    stage="prematch",
                    type="pattern",
                    title="Head-to-head context",
                    body=f"You have {meeting_count} recorded meetings against {opponent} in the current dataset.",
                    priority=0.5,
                    confidence=0.58,
                    evidence_keys=["prematch_head_to_head_context"],
                    novelty_key=f"h2h:{opponent}",
                    anchor="prematch_head_to_head_context",
                    presentation_hint="micro",
                    cta_label="",
                    metadata={"meeting_count": meeting_count},
                    supporting_artifacts=["prematch_head_to_head_context"],
                )
            )

        summary = str(game_plan_payload.get("plan_headline") or f"Prematch context ready for {opponent}.")
        return StageAnalysis(
            stage="prematch",
            scope=scope,
            summary=summary,
            confidence=confidence_label or "medium",
            discoveries=discoveries,
            supporting_artifacts=[
                "prematch_fixture_context",
                "prematch_recent_form_context",
                "prematch_head_to_head_context",
                "prematch_game_plan_context",
            ],
            debug={
                "meeting_count": meeting_count,
                "recent_form_goals": recent_form_payload.get("goals_total"),
                "recent_form_assists": recent_form_payload.get("assists_total"),
            },
        )
