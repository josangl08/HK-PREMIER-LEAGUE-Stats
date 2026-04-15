# ABOUTME: Career-stage tool catalog and local tool runners for the agentic discovery runtime.
# ABOUTME: Exposes career-scoped artifact views and session-memory context so the Career agent can inspect real stage data safely.

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Mapping

CAREER_PHASE_CONTEXT_ARTIFACT = "career_phase_context"
CAREER_SIGNALS_CONTEXT_ARTIFACT = "career_signals_context"
CAREER_PRIORITIES_CONTEXT_ARTIFACT = "career_priorities_context"
CAREER_DASHBOARD_BRIEF_ARTIFACT = "career_dashboard_brief"
@dataclass(frozen=True)
class CareerToolSpec:
    name: str
    description: str
    artifact_dependencies: tuple[str, ...]


_CAREER_TOOL_SPECS = (
    CareerToolSpec(
        name="phase_context",
        description="Career phase, recommendation, and durable progression context for this player.",
        artifact_dependencies=(CAREER_PHASE_CONTEXT_ARTIFACT,),
    ),
    CareerToolSpec(
        name="signals_context",
        description="Career signals describing trust, trend, role, and current progression pressure points.",
        artifact_dependencies=(CAREER_SIGNALS_CONTEXT_ARTIFACT,),
    ),
    CareerToolSpec(
        name="priorities_context",
        description="Development priorities derived from percentile gaps and growth levers.",
        artifact_dependencies=(CAREER_PRIORITIES_CONTEXT_ARTIFACT,),
    ),
    CareerToolSpec(
        name="dashboard_brief",
        description="Structured career thesis, key signals, levers, and outlook used by the dashboard.",
        artifact_dependencies=(CAREER_DASHBOARD_BRIEF_ARTIFACT,),
    ),
    CareerToolSpec(
        name="session_memory",
        description="Previously surfaced novelty keys and current surfaced candidate to avoid repetition across career refreshes.",
        artifact_dependencies=(),
    ),
)

_CAREER_CORE_TOOL_NAMES = (
    "phase_context",
    "dashboard_brief",
    "session_memory",
)


def get_career_tool_catalog() -> List[Dict[str, Any]]:
    """Return the public career tool catalog for prompt construction."""
    return [asdict(spec) for spec in _CAREER_TOOL_SPECS]


def get_career_core_tool_names() -> List[str]:
    """Return the always-included core tool names for career analysis."""
    return list(_CAREER_CORE_TOOL_NAMES)


def _artifact_payload(artifacts: Mapping[str, Mapping[str, Any]], artifact_name: str) -> Dict[str, Any]:
    return dict(((artifacts.get(artifact_name) or {}).get("payload") or {}))


def run_career_tool(
    tool_name: str,
    *,
    artifacts: Mapping[str, Mapping[str, Any]],
    session_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Execute one career tool against the current artifact set."""
    if tool_name == "phase_context":
        return _artifact_payload(artifacts, CAREER_PHASE_CONTEXT_ARTIFACT)
    if tool_name == "signals_context":
        return _artifact_payload(artifacts, CAREER_SIGNALS_CONTEXT_ARTIFACT)
    if tool_name == "priorities_context":
        return _artifact_payload(artifacts, CAREER_PRIORITIES_CONTEXT_ARTIFACT)
    if tool_name == "dashboard_brief":
        return _artifact_payload(artifacts, CAREER_DASHBOARD_BRIEF_ARTIFACT)
    if tool_name == "session_memory":
        return dict(session_memory or {})
    return {}


def run_career_tool_plan(
    selected_tools: List[str],
    *,
    artifacts: Mapping[str, Mapping[str, Any]],
    session_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Execute a validated list of career tools and return their outputs."""
    outputs: Dict[str, Dict[str, Any]] = {}
    valid_names = {spec.name for spec in _CAREER_TOOL_SPECS}
    for tool_name in selected_tools:
        normalized = str(tool_name or "").strip()
        if not normalized or normalized not in valid_names or normalized in outputs:
            continue
        outputs[normalized] = run_career_tool(
            normalized,
            artifacts=artifacts,
            session_memory=session_memory,
        )
    return outputs
