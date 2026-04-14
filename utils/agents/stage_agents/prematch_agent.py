# ABOUTME: Initial prematch-stage agent that emits persisted fixture discoveries from deterministic prematch artifacts.
# ABOUTME: Packages matchup context and game-plan outputs into the shared stage-analysis contract for overlays and inbox recovery.

from __future__ import annotations

from typing import Any, Dict, Mapping

from utils.agents.stage_agents.base import StageAgent
from utils.domain_ai.prematch_agentic_discovery import synthesize_prematch_stage_analysis
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
        ai_analysis = synthesize_prematch_stage_analysis(
            scope=scope,
            artifacts=artifacts,
            session_memory=session_memory,
        )
        if ai_analysis is not None:
            return ai_analysis

        fixture_payload = ((artifacts.get("prematch_fixture_context") or {}).get("payload") or {})
        recent_form_payload = ((artifacts.get("prematch_recent_form_context") or {}).get("payload") or {})
        head_to_head_payload = ((artifacts.get("prematch_head_to_head_context") or {}).get("payload") or {})
        rival_profiles_payload = ((artifacts.get("prematch_rival_profiles_context") or {}).get("payload") or {})
        opponent_threat_payload = ((artifacts.get("prematch_opponent_threat_context") or {}).get("payload") or {})
        game_plan_payload = ((artifacts.get("prematch_game_plan_context") or {}).get("payload") or {})

        opponent = str(fixture_payload.get("opponent") or "opponent")
        confidence_label = str(game_plan_payload.get("confidence") or "limited").lower()
        confidence_score = {"high": 0.82, "medium": 0.68, "limited": 0.54}.get(confidence_label, 0.54)
        rivals = list(rival_profiles_payload.get("rivals") or [])
        primary_rival = dict(rivals[0] or {}) if rivals else {}
        top_scorer_name = str(opponent_threat_payload.get("top_scorer_name") or "")

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
                    "prematch_rival_profiles_context",
                    "prematch_opponent_threat_context",
                    "prematch_game_plan_context",
                ],
            )
        ]

        if primary_rival:
            rival_name = str(primary_rival.get("name") or "Likely rival")
            rival_weakness = str(primary_rival.get("weakness_text") or "").strip()
            if rival_weakness:
                discoveries.append(
                    StageDiscovery(
                        discovery_id=f"prematch-rival-window:{scope.get('fixture_id', opponent)}",
                        stage="prematch",
                        type="opportunity",
                        title=f"Go at {rival_name}",
                        body=f"{rival_name} looks most vulnerable when {rival_weakness.lower()}",
                        priority=0.63,
                        confidence=0.64,
                        evidence_keys=["prematch_rival_profiles_context"],
                        novelty_key=f"rival-window:{scope.get('fixture_id') or opponent}:{rival_name}",
                        anchor="prematch_rival_profiles_context",
                        presentation_hint="micro",
                        cta_label="",
                        metadata=dict(primary_rival),
                        supporting_artifacts=["prematch_rival_profiles_context"],
                    )
                )

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

        if top_scorer_name:
            discoveries.append(
                StageDiscovery(
                    discovery_id=f"prematch-threat:{scope.get('fixture_id', opponent)}",
                    stage="prematch",
                    type="warning",
                    title="Main threat to track",
                    body=f"{top_scorer_name} is their main scorer, so be ready for the first movement around the box.",
                    priority=0.56,
                    confidence=0.62,
                    evidence_keys=["prematch_opponent_threat_context"],
                    novelty_key=f"threat:{scope.get('fixture_id') or opponent}:{top_scorer_name}",
                    anchor="prematch_opponent_threat_context",
                    presentation_hint="micro",
                    cta_label="",
                    metadata=dict(opponent_threat_payload),
                    supporting_artifacts=["prematch_opponent_threat_context"],
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
                "prematch_rival_profiles_context",
                "prematch_opponent_threat_context",
                "prematch_game_plan_context",
            ],
            debug={
                "meeting_count": meeting_count,
                "recent_form_goals": recent_form_payload.get("goals_total"),
                "recent_form_assists": recent_form_payload.get("assists_total"),
                "rival_count": len(rivals),
                "top_scorer_name": top_scorer_name,
            },
        )
