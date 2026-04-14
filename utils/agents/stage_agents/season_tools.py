# ABOUTME: Season-stage tool catalog and local tool runners for the agentic discovery runtime.
# ABOUTME: Exposes season-scoped artifact views and session-memory context so the Season agent can inspect real stage data safely.

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Mapping

from utils.agents.season_agent import build_season_stage_analysis
from utils.season_stage.season_intelligence import (
    COMPETITION_SPLIT_CONTEXT_ARTIFACT,
    PREVIOUS_SEASON_CONTEXT_ARTIFACT,
    RECENT_FORM_CONTEXT_ARTIFACT,
    SEASON_PERFORMANCE_CONTEXT_ARTIFACT,
    SEASON_PROFILE_CONTEXT_ARTIFACT,
    SEASON_SIGNALS_ARTIFACT,
)


@dataclass(frozen=True)
class SeasonToolSpec:
    name: str
    description: str
    artifact_dependencies: tuple[str, ...]


_SEASON_TOOL_SPECS = (
    SeasonToolSpec(
        name="season_profile",
        description="Role profile, archetype, top strengths, top gaps, and nearest profile context for the current season.",
        artifact_dependencies=(SEASON_PROFILE_CONTEXT_ARTIFACT,),
    ),
    SeasonToolSpec(
        name="season_performance",
        description="Season snapshot, matches played, minutes, output totals, and compact performance metrics.",
        artifact_dependencies=(SEASON_PERFORMANCE_CONTEXT_ARTIFACT,),
    ),
    SeasonToolSpec(
        name="competition_split",
        description="Competition-by-competition split to detect uneven output or load concentration across tournaments.",
        artifact_dependencies=(COMPETITION_SPLIT_CONTEXT_ARTIFACT,),
    ),
    SeasonToolSpec(
        name="previous_season",
        description="Previous-season comparison for continuity, improvement, regression, or role stability checks.",
        artifact_dependencies=(PREVIOUS_SEASON_CONTEXT_ARTIFACT,),
    ),
    SeasonToolSpec(
        name="recent_form",
        description="Last-5 and previous-5 recent-form windows for momentum, cooling, and short-term tension checks.",
        artifact_dependencies=(RECENT_FORM_CONTEXT_ARTIFACT,),
    ),
    SeasonToolSpec(
        name="season_signals",
        description="Deterministic season signal candidates already extracted from the current stage context.",
        artifact_dependencies=(SEASON_SIGNALS_ARTIFACT,),
    ),
    SeasonToolSpec(
        name="session_memory",
        description="Previously surfaced novelty keys and current surfaced candidate to avoid repetition.",
        artifact_dependencies=(),
    ),
    SeasonToolSpec(
        name="deterministic_baseline",
        description="The current deterministic season analysis summary with key points, tensions, and caveats.",
        artifact_dependencies=(
            SEASON_PROFILE_CONTEXT_ARTIFACT,
            SEASON_PERFORMANCE_CONTEXT_ARTIFACT,
            COMPETITION_SPLIT_CONTEXT_ARTIFACT,
            PREVIOUS_SEASON_CONTEXT_ARTIFACT,
            RECENT_FORM_CONTEXT_ARTIFACT,
        ),
    ),
)


def get_season_tool_catalog() -> List[Dict[str, Any]]:
    """Return the public season tool catalog for prompt construction."""
    return [asdict(spec) for spec in _SEASON_TOOL_SPECS]


def _artifact_payload(artifacts: Mapping[str, Mapping[str, Any]], artifact_name: str) -> Dict[str, Any]:
    return dict(((artifacts.get(artifact_name) or {}).get("payload") or {}))


def run_season_tool(
    tool_name: str,
    *,
    artifacts: Mapping[str, Mapping[str, Any]],
    session_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Execute one season tool against the current artifact set."""
    if tool_name == "season_profile":
        return _artifact_payload(artifacts, SEASON_PROFILE_CONTEXT_ARTIFACT)
    if tool_name == "season_performance":
        return _artifact_payload(artifacts, SEASON_PERFORMANCE_CONTEXT_ARTIFACT)
    if tool_name == "competition_split":
        return _artifact_payload(artifacts, COMPETITION_SPLIT_CONTEXT_ARTIFACT)
    if tool_name == "previous_season":
        return _artifact_payload(artifacts, PREVIOUS_SEASON_CONTEXT_ARTIFACT)
    if tool_name == "recent_form":
        return _artifact_payload(artifacts, RECENT_FORM_CONTEXT_ARTIFACT)
    if tool_name == "season_signals":
        return _artifact_payload(artifacts, SEASON_SIGNALS_ARTIFACT)
    if tool_name == "session_memory":
        return dict(session_memory or {})
    if tool_name == "deterministic_baseline":
        return build_season_stage_analysis(artifacts)
    return {}


def run_season_tool_plan(
    selected_tools: List[str],
    *,
    artifacts: Mapping[str, Mapping[str, Any]],
    session_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Execute a validated list of season tools and return their outputs."""
    outputs: Dict[str, Dict[str, Any]] = {}
    valid_names = {spec.name for spec in _SEASON_TOOL_SPECS}
    for tool_name in selected_tools:
        normalized = str(tool_name or "").strip()
        if not normalized or normalized not in valid_names or normalized in outputs:
            continue
        outputs[normalized] = run_season_tool(
            normalized,
            artifacts=artifacts,
            session_memory=session_memory,
        )
    return outputs
