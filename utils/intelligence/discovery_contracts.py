# ABOUTME: Shared typed contracts for stage intelligence discoveries and persisted analyses.
# ABOUTME: Normalizes stage-agent output so orchestration, overlays, and persistence share one schema.

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Dict, List, Literal, Mapping, Optional


DiscoveryType = Literal[
    "pattern",
    "milestone",
    "curiosity",
    "warning",
    "opportunity",
    "tactical_plan",
    "comparative_edge",
    "comparative_gap",
    "summary",
]
PresentationHint = Literal["critical", "prominent", "contextual", "micro"]
StageName = Literal["season", "career", "prematch", "postmatch"]


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class StageDiscovery:
    discovery_id: str
    stage: StageName
    type: DiscoveryType
    title: str
    body: str
    priority: float
    confidence: float
    evidence_keys: List[str] = field(default_factory=list)
    novelty_key: str = ""
    anchor: str = ""
    presentation_hint: PresentationHint = "contextual"
    cta_label: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    supporting_artifacts: List[str] = field(default_factory=list)
    expires_at: str = ""


@dataclass(frozen=True)
class StageAnalysis:
    stage: StageName
    scope: Dict[str, str]
    summary: str
    confidence: str
    discoveries: List[StageDiscovery] = field(default_factory=list)
    supporting_artifacts: List[str] = field(default_factory=list)
    debug: Dict[str, Any] = field(default_factory=dict)


def coerce_stage_discovery(
    raw_discovery: Any,
    *,
    default_stage: str = "season",
) -> Optional[StageDiscovery]:
    """Coerce dict-like input into a normalized stage-discovery contract."""
    if isinstance(raw_discovery, StageDiscovery):
        return raw_discovery
    if not isinstance(raw_discovery, Mapping):
        return None

    title = _safe_str(raw_discovery.get("title"))
    body = _safe_str(raw_discovery.get("body"))
    discovery_id = _safe_str(raw_discovery.get("discovery_id") or raw_discovery.get("signal_id") or title)
    if not discovery_id or (not title and not body):
        return None

    evidence_keys = []
    for item in raw_discovery.get("evidence_keys") or []:
        value = _safe_str(item)
        if value:
            evidence_keys.append(value)
    if not evidence_keys:
        evidence_value = _safe_str(raw_discovery.get("evidence_key"))
        if evidence_value:
            evidence_keys.append(evidence_value)

    supporting_artifacts = []
    for item in raw_discovery.get("supporting_artifacts") or []:
        value = _safe_str(item)
        if value:
            supporting_artifacts.append(value)

    presentation_hint = _safe_str(raw_discovery.get("presentation_hint") or "contextual").lower()
    if presentation_hint not in {"critical", "prominent", "contextual", "micro"}:
        presentation_hint = "contextual"

    discovery_type = _safe_str(raw_discovery.get("type") or "pattern").lower()
    if discovery_type not in {
        "pattern",
        "milestone",
        "curiosity",
        "warning",
        "opportunity",
        "tactical_plan",
        "comparative_edge",
        "comparative_gap",
        "summary",
    }:
        discovery_type = "pattern"

    stage_name = _safe_str(raw_discovery.get("stage") or default_stage).lower()
    if stage_name not in {"season", "career", "prematch", "postmatch"}:
        stage_name = default_stage

    return StageDiscovery(
        discovery_id=discovery_id,
        stage=stage_name,  # type: ignore[arg-type]
        type=discovery_type,  # type: ignore[arg-type]
        title=title or "Stage discovery",
        body=body,
        priority=max(0.0, min(1.0, _safe_float(raw_discovery.get("priority"), 0.0))),
        confidence=max(0.0, min(1.0, _safe_float(raw_discovery.get("confidence"), 0.0))),
        evidence_keys=evidence_keys,
        novelty_key=_safe_str(raw_discovery.get("novelty_key") or discovery_id),
        anchor=_safe_str(raw_discovery.get("anchor")),
        presentation_hint=presentation_hint,  # type: ignore[arg-type]
        cta_label=_safe_str(raw_discovery.get("cta_label")),
        metadata=dict(raw_discovery.get("metadata") or raw_discovery.get("evidence") or {}),
        supporting_artifacts=supporting_artifacts,
        expires_at=_safe_str(raw_discovery.get("expires_at")),
    )


def serialize_stage_discovery(discovery: StageDiscovery | Mapping[str, Any]) -> Dict[str, Any]:
    """Return a JSON-safe serialized discovery payload."""
    if isinstance(discovery, StageDiscovery):
        return asdict(discovery)
    coerced = coerce_stage_discovery(discovery)
    return asdict(coerced) if coerced is not None else {}


def coerce_stage_analysis(raw_analysis: Any) -> Optional[StageAnalysis]:
    """Coerce dict-like input into the shared stage-analysis contract."""
    if isinstance(raw_analysis, StageAnalysis):
        return raw_analysis
    if not isinstance(raw_analysis, Mapping):
        return None

    stage_name = _safe_str(raw_analysis.get("stage") or "season").lower()
    if stage_name not in {"season", "career", "prematch", "postmatch"}:
        return None

    discoveries = []
    for raw_discovery in raw_analysis.get("discoveries") or []:
        discovery = coerce_stage_discovery(raw_discovery, default_stage=stage_name)
        if discovery is not None:
            discoveries.append(discovery)

    return StageAnalysis(
        stage=stage_name,  # type: ignore[arg-type]
        scope={str(key): _safe_str(value) for key, value in dict(raw_analysis.get("scope") or {}).items()},
        summary=_safe_str(raw_analysis.get("summary")),
        confidence=_safe_str(raw_analysis.get("confidence") or "medium").lower() or "medium",
        discoveries=discoveries,
        supporting_artifacts=[_safe_str(item) for item in list(raw_analysis.get("supporting_artifacts") or []) if _safe_str(item)],
        debug=dict(raw_analysis.get("debug") or {}),
    )


def serialize_stage_analysis(analysis: StageAnalysis | Mapping[str, Any]) -> Dict[str, Any]:
    """Return a JSON-safe serialized stage-analysis payload."""
    if isinstance(analysis, StageAnalysis):
        return {
            "stage": analysis.stage,
            "scope": dict(analysis.scope),
            "summary": analysis.summary,
            "confidence": analysis.confidence,
            "discoveries": [serialize_stage_discovery(item) for item in analysis.discoveries],
            "supporting_artifacts": list(analysis.supporting_artifacts),
            "debug": dict(analysis.debug),
        }
    coerced = coerce_stage_analysis(analysis)
    return serialize_stage_analysis(coerced) if coerced is not None else {}
