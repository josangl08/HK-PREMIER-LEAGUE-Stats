# ABOUTME: Shared season-stage agent that emits persisted stage discoveries from deterministic season artifacts.
# ABOUTME: Wraps the current season analysis and signal curation logic into the shared stage-analysis contract.

from __future__ import annotations

from typing import Any, Dict, Mapping

from utils.agents.season_agent import build_season_stage_analysis
from utils.agents.signal_agent import curate_signals
from utils.agents.stage_agents.base import StageAgent
from utils.domain_ai.season_agentic_discovery import synthesize_season_stage_analysis
from utils.intelligence.discovery_contracts import StageAnalysis, StageDiscovery
from utils.season_stage.season_intelligence import SEASON_SIGNALS_ARTIFACT


def _build_fallback_stage_analysis(
    *,
    scope: Dict[str, str],
    artifacts: Mapping[str, Mapping[str, Any]],
    session_memory: Mapping[str, Any] | None = None,
) -> StageAnalysis:
    """Build the deterministic fallback shared season analysis."""
    analysis_payload = build_season_stage_analysis(artifacts)
    signals_payload = ((artifacts.get(SEASON_SIGNALS_ARTIFACT) or {}).get("payload") or {})
    selected_signal = curate_signals(
        signals_payload.get("signals") or [],
        session_state=session_memory,
        session_memory=session_memory,
    )

    discoveries = []
    if selected_signal:
        discoveries.append(
            StageDiscovery(
                discovery_id=str(selected_signal.get("signal_id") or "season-worth-noticing"),
                stage="season",
                type="pattern",
                title=str(selected_signal.get("title") or "Worth Noticing"),
                body=str(selected_signal.get("body") or ""),
                priority=float(selected_signal.get("priority") or 0.0),
                confidence=float(selected_signal.get("confidence") or 0.0),
                evidence_keys=[str(selected_signal.get("signal_id") or "")],
                novelty_key=str(selected_signal.get("novelty_key") or selected_signal.get("signal_id") or ""),
                anchor=str(selected_signal.get("anchor") or ""),
                presentation_hint="prominent",
                cta_label="View insight",
                metadata=dict(selected_signal.get("evidence") or {}),
                supporting_artifacts=list(analysis_payload.get("supporting_artifacts") or []),
            )
        )

    if analysis_payload.get("available"):
        discoveries.append(
            StageDiscovery(
                discovery_id=f"season-summary:{scope.get('player_id', 'unknown')}:{scope.get('season', 'unknown')}",
                stage="season",
                type="summary",
                title="Season Intelligence",
                body=str(analysis_payload.get("summary") or ""),
                priority=0.58,
                confidence={"low": 0.35, "medium": 0.62, "high": 0.82}.get(
                    str(analysis_payload.get("confidence") or "medium"),
                    0.62,
                ),
                evidence_keys=[],
                novelty_key="season-summary",
                anchor="season_stage_analysis",
                presentation_hint="micro",
                cta_label="",
                metadata={
                    "key_points": list(analysis_payload.get("key_points") or []),
                    "tensions": list(analysis_payload.get("tensions") or []),
                    "caveats": list(analysis_payload.get("caveats") or []),
                },
                supporting_artifacts=list(analysis_payload.get("supporting_artifacts") or []),
            )
        )

    return StageAnalysis(
        stage="season",
        scope=scope,
        summary=str(analysis_payload.get("summary") or ""),
        confidence=str(analysis_payload.get("confidence") or "medium"),
        discoveries=discoveries,
        supporting_artifacts=list(analysis_payload.get("supporting_artifacts") or []),
        debug={
            "available": bool(analysis_payload.get("available")),
            "abstained": bool(analysis_payload.get("abstained")),
            "llm_generated": False,
            "analysis_source": "deterministic",
        },
    )


class SeasonStageAgent(StageAgent):
    stage_name = "season"

    def analyze(
        self,
        *,
        scope: Dict[str, str],
        artifacts: Mapping[str, Mapping[str, Any]],
        session_memory: Mapping[str, Any] | None = None,
    ) -> StageAnalysis:
        ai_analysis = synthesize_season_stage_analysis(
            scope=scope,
            artifacts=artifacts,
            session_memory=session_memory,
        )
        if ai_analysis is not None:
            return ai_analysis
        return _build_fallback_stage_analysis(
            scope=scope,
            artifacts=artifacts,
            session_memory=session_memory,
        )
