# ABOUTME: Prematch-stage tool catalog and local tool runners for the agentic discovery runtime.
# ABOUTME: Exposes prematch-scoped artifact views and session-memory context so the Prematch agent can inspect real stage data safely.

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Mapping

PREMATCH_FIXTURE_CONTEXT_ARTIFACT = "prematch_fixture_context"
PREMATCH_RECENT_FORM_CONTEXT_ARTIFACT = "prematch_recent_form_context"
PREMATCH_HEAD_TO_HEAD_CONTEXT_ARTIFACT = "prematch_head_to_head_context"
PREMATCH_RIVAL_PROFILES_CONTEXT_ARTIFACT = "prematch_rival_profiles_context"
PREMATCH_OPPONENT_THREAT_CONTEXT_ARTIFACT = "prematch_opponent_threat_context"
PREMATCH_GAME_PLAN_CONTEXT_ARTIFACT = "prematch_game_plan_context"


@dataclass(frozen=True)
class PrematchToolSpec:
    name: str
    description: str
    artifact_dependencies: tuple[str, ...]


_PREMATCH_TOOL_SPECS = (
    PrematchToolSpec(
        name="fixture_context",
        description="Active fixture context including opponent, competition, kickoff, and the player's role envelope for this match.",
        artifact_dependencies=(PREMATCH_FIXTURE_CONTEXT_ARTIFACT,),
    ),
    PrematchToolSpec(
        name="recent_form",
        description="Latest player attacking and minutes trend before the fixture, including goals, assists, xG, and xA.",
        artifact_dependencies=(PREMATCH_RECENT_FORM_CONTEXT_ARTIFACT,),
    ),
    PrematchToolSpec(
        name="head_to_head",
        description="Recorded meetings against the current opponent for historical context and previous match patterns.",
        artifact_dependencies=(PREMATCH_HEAD_TO_HEAD_CONTEXT_ARTIFACT,),
    ),
    PrematchToolSpec(
        name="rival_profiles",
        description="Direct rival scouting cards for likely matchups, including a primary rival, secondary rivals, matchup confidence, strengths, weaknesses, and recent form indicators.",
        artifact_dependencies=(PREMATCH_RIVAL_PROFILES_CONTEXT_ARTIFACT,),
    ),
    PrematchToolSpec(
        name="opponent_threat",
        description="Opponent threat summary including scorer, creator, most-used player, and compact named-threat cues for the fixture.",
        artifact_dependencies=(PREMATCH_OPPONENT_THREAT_CONTEXT_ARTIFACT,),
    ),
    PrematchToolSpec(
        name="deterministic_baseline",
        description="The current deterministic prematch game-plan baseline built from fixture, rival, recent form, and head-to-head context.",
        artifact_dependencies=(PREMATCH_GAME_PLAN_CONTEXT_ARTIFACT,),
    ),
    PrematchToolSpec(
        name="session_memory",
        description="Previously surfaced novelty keys and current surfaced candidate to avoid repetition across the fixture lifecycle.",
        artifact_dependencies=(),
    ),
)

_PREMATCH_CORE_TOOL_NAMES = (
    "fixture_context",
    "recent_form",
    "session_memory",
)


def get_prematch_tool_catalog() -> List[Dict[str, Any]]:
    """Return the public prematch tool catalog for prompt construction."""
    return [asdict(spec) for spec in _PREMATCH_TOOL_SPECS]


def get_prematch_core_tool_names() -> List[str]:
    """Return the always-included core tool names for prematch analysis."""
    return list(_PREMATCH_CORE_TOOL_NAMES)


def _artifact_payload(artifacts: Mapping[str, Mapping[str, Any]], artifact_name: str) -> Dict[str, Any]:
    return dict(((artifacts.get(artifact_name) or {}).get("payload") or {}))


def run_prematch_tool(
    tool_name: str,
    *,
    artifacts: Mapping[str, Mapping[str, Any]],
    session_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Execute one prematch tool against the current artifact set."""
    if tool_name == "fixture_context":
        return _artifact_payload(artifacts, PREMATCH_FIXTURE_CONTEXT_ARTIFACT)
    if tool_name == "recent_form":
        return _artifact_payload(artifacts, PREMATCH_RECENT_FORM_CONTEXT_ARTIFACT)
    if tool_name == "head_to_head":
        return _artifact_payload(artifacts, PREMATCH_HEAD_TO_HEAD_CONTEXT_ARTIFACT)
    if tool_name == "rival_profiles":
        return _artifact_payload(artifacts, PREMATCH_RIVAL_PROFILES_CONTEXT_ARTIFACT)
    if tool_name == "opponent_threat":
        return _artifact_payload(artifacts, PREMATCH_OPPONENT_THREAT_CONTEXT_ARTIFACT)
    if tool_name == "deterministic_baseline":
        return _artifact_payload(artifacts, PREMATCH_GAME_PLAN_CONTEXT_ARTIFACT)
    if tool_name == "session_memory":
        return dict(session_memory or {})
    return {}


def run_prematch_tool_plan(
    selected_tools: List[str],
    *,
    artifacts: Mapping[str, Mapping[str, Any]],
    session_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Execute a validated list of prematch tools and return their outputs."""
    outputs: Dict[str, Dict[str, Any]] = {}
    valid_names = {spec.name for spec in _PREMATCH_TOOL_SPECS}
    for tool_name in selected_tools:
        normalized = str(tool_name or "").strip()
        if not normalized or normalized not in valid_names or normalized in outputs:
            continue
        outputs[normalized] = run_prematch_tool(
            normalized,
            artifacts=artifacts,
            session_memory=session_memory,
        )
    return outputs
