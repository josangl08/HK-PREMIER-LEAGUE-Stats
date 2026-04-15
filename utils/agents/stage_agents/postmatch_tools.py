# ABOUTME: Postmatch-stage tool catalog and local tool runners for the agentic discovery runtime.
# ABOUTME: Exposes postmatch-scoped artifact views and session-memory context so the Postmatch agent can inspect real stage data safely.

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Mapping

POSTMATCH_MATCH_CONTEXT_ARTIFACT = "postmatch_match_context"
POSTMATCH_PERFORMANCE_CONTEXT_ARTIFACT = "postmatch_performance_context"
POSTMATCH_REFLECTION_PAYLOADS_ARTIFACT = "postmatch_reflection_payloads"
POSTMATCH_SIGNALS_ARTIFACT = "postmatch_signals"


@dataclass(frozen=True)
class PostmatchToolSpec:
    name: str
    description: str
    artifact_dependencies: tuple[str, ...]


_POSTMATCH_TOOL_SPECS = (
    PostmatchToolSpec(
        name="match_context",
        description="Final match wrapper including fixture identity, teams, competition, result, and rating envelope.",
        artifact_dependencies=(POSTMATCH_MATCH_CONTEXT_ARTIFACT,),
    ),
    PostmatchToolSpec(
        name="performance_context",
        description="Player postmatch performance context including minutes, goals, assists, cards, recent ratings, and raw match stats.",
        artifact_dependencies=(POSTMATCH_PERFORMANCE_CONTEXT_ARTIFACT,),
    ),
    PostmatchToolSpec(
        name="reflection_payloads",
        description="Deterministic reflective payload candidates built from postmatch evidence and summary text.",
        artifact_dependencies=(POSTMATCH_REFLECTION_PAYLOADS_ARTIFACT,),
    ),
    PostmatchToolSpec(
        name="signals_context",
        description="Normalized overlay candidates already derived from the shared postmatch stage-analysis contract.",
        artifact_dependencies=(POSTMATCH_SIGNALS_ARTIFACT,),
    ),
    PostmatchToolSpec(
        name="session_memory",
        description="Previously surfaced novelty keys and current surfaced candidate to avoid repetition across match revisits.",
        artifact_dependencies=(),
    ),
)

_POSTMATCH_CORE_TOOL_NAMES = (
    "match_context",
    "performance_context",
    "session_memory",
)


def get_postmatch_tool_catalog() -> List[Dict[str, Any]]:
    """Return the public postmatch tool catalog for prompt construction."""
    return [asdict(spec) for spec in _POSTMATCH_TOOL_SPECS]


def get_postmatch_core_tool_names() -> List[str]:
    """Return the always-included core tool names for postmatch analysis."""
    return list(_POSTMATCH_CORE_TOOL_NAMES)


def _artifact_payload(artifacts: Mapping[str, Mapping[str, Any]], artifact_name: str) -> Dict[str, Any]:
    return dict(((artifacts.get(artifact_name) or {}).get("payload") or {}))


def run_postmatch_tool(
    tool_name: str,
    *,
    artifacts: Mapping[str, Mapping[str, Any]],
    session_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Execute one postmatch tool against the current artifact set."""
    if tool_name == "match_context":
        return _artifact_payload(artifacts, POSTMATCH_MATCH_CONTEXT_ARTIFACT)
    if tool_name == "performance_context":
        return _artifact_payload(artifacts, POSTMATCH_PERFORMANCE_CONTEXT_ARTIFACT)
    if tool_name == "reflection_payloads":
        return _artifact_payload(artifacts, POSTMATCH_REFLECTION_PAYLOADS_ARTIFACT)
    if tool_name == "signals_context":
        return _artifact_payload(artifacts, POSTMATCH_SIGNALS_ARTIFACT)
    if tool_name == "session_memory":
        return dict(session_memory or {})
    return {}


def run_postmatch_tool_plan(
    selected_tools: List[str],
    *,
    artifacts: Mapping[str, Mapping[str, Any]],
    session_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Execute a validated list of postmatch tools and return their outputs."""
    outputs: Dict[str, Dict[str, Any]] = {}
    valid_names = {spec.name for spec in _POSTMATCH_TOOL_SPECS}
    for tool_name in selected_tools:
        normalized = str(tool_name or "").strip()
        if not normalized or normalized not in valid_names or normalized in outputs:
            continue
        outputs[normalized] = run_postmatch_tool(
            normalized,
            artifacts=artifacts,
            session_memory=session_memory,
        )
    return outputs
