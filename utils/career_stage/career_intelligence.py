# ABOUTME: Career-stage intelligence integration surface for artifact contracts, freshness policy, and deterministic context assembly.
# ABOUTME: Wraps existing career intelligence utilities in JSON-safe artifact payloads so multi-stage orchestration can reuse the season architecture.

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Mapping

import pandas as pd

from utils.career_intelligence import (
    build_career_dashboard_brief,
    classify_overlay_signals,
    get_career_phase_data,
    get_career_signals,
    get_development_priorities,
)
from utils.agents.stage_agents.career_agent import CareerStageAgent
from utils.intelligence.discovery_contracts import serialize_stage_analysis
from utils.intelligence.freshness_manager import FRESHNESS_COLD, FRESHNESS_WARM

CAREER_PHASE_CONTEXT_ARTIFACT = "career_phase_context"
CAREER_SIGNALS_CONTEXT_ARTIFACT = "career_signals_context"
CAREER_PRIORITIES_CONTEXT_ARTIFACT = "career_priorities_context"
CAREER_DASHBOARD_BRIEF_ARTIFACT = "career_dashboard_brief"
CAREER_OVERLAY_CANDIDATES_ARTIFACT = "career_overlay_candidates"

CAREER_ARTIFACT_TYPES = [
    CAREER_PHASE_CONTEXT_ARTIFACT,
    CAREER_SIGNALS_CONTEXT_ARTIFACT,
    CAREER_PRIORITIES_CONTEXT_ARTIFACT,
    CAREER_DASHBOARD_BRIEF_ARTIFACT,
    CAREER_OVERLAY_CANDIDATES_ARTIFACT,
]

CAREER_FRESHNESS_POLICY = {
    CAREER_PHASE_CONTEXT_ARTIFACT: {"regime": FRESHNESS_COLD, "ttl_hours": 72},
    CAREER_SIGNALS_CONTEXT_ARTIFACT: {"regime": FRESHNESS_COLD, "ttl_hours": 72},
    CAREER_PRIORITIES_CONTEXT_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 48},
    CAREER_DASHBOARD_BRIEF_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 48},
    CAREER_OVERLAY_CANDIDATES_ARTIFACT: {"regime": FRESHNESS_WARM, "ttl_hours": 48},
}


def _safe_scalar(value: Any) -> Any:
    """Convert pandas/numpy scalars into plain JSON-safe values."""
    if is_dataclass(value):
        return _safe_scalar(asdict(value))
    if isinstance(value, dict):
        return {
            str(key): _safe_scalar(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_safe_scalar(item) for item in value]
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _safe_mapping(mapping: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Normalize a mapping into JSON-safe scalar values."""
    if not mapping:
        return {}
    return {
        str(key): _safe_scalar(value)
        for key, value in mapping.items()
    }


def _safe_records(records: List[Mapping[str, Any]] | None) -> List[Dict[str, Any]]:
    """Normalize list items into JSON-safe shallow dicts."""
    return [_safe_mapping(record) for record in (records or [])]


def build_career_artifact_scope(player_id: str) -> Dict[str, str]:
    """Return the canonical career artifact scope."""
    return {
        "player_id": str(player_id or ""),
        "stage": "career",
    }


def build_career_phase_context_payload(player: Dict[str, Any], history_df: pd.DataFrame) -> Dict[str, Any]:
    """Build the durable career phase context payload."""
    phase_data = get_career_phase_data(player, history_df)
    return deepcopy(_safe_mapping(phase_data))


def build_career_signals_context_payload(
    player: Dict[str, Any],
    history_df: pd.DataFrame,
    career_phase_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the career signal-context payload."""
    signals = get_career_signals(player, history_df, career_phase_data)
    return deepcopy(_safe_mapping(signals))


def build_career_priorities_context_payload(percentiles_data: Dict[str, int] | None) -> Dict[str, Any]:
    """Build the development-priority payload."""
    priorities = get_development_priorities(percentiles_data or {})
    return {
        "priorities": deepcopy(_safe_records(priorities)),
        "priority_count": len(priorities),
    }


def build_career_dashboard_brief_payload(
    data: Dict[str, Any],
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    development_priorities: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the career dashboard brief artifact payload."""
    brief = build_career_dashboard_brief(
        data,
        career_phase_data,
        career_signals,
        development_priorities,
    )
    return {
        "player_name": str(
            (data.get("player") or {}).get("player_name")
            or data.get("player_name")
            or ""
        ),
        "career_thesis": deepcopy(_safe_mapping(getattr(brief, "career_thesis", {}) or {})),
        "signals": deepcopy(_safe_records([getattr(item, "__dict__", item) for item in getattr(brief, "signals", [])])),
        "levers": deepcopy(_safe_records([getattr(item, "__dict__", item) for item in getattr(brief, "levers", [])])),
        "outlook": deepcopy(_safe_mapping(getattr(brief, "outlook", {}) or {})),
    }


def build_career_overlay_candidates_payload(
    career_phase_data: Dict[str, Any],
    career_signals: Dict[str, Any],
    development_priorities: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the career overlay-candidate payload from existing overlay tiering."""
    overlay_signals = classify_overlay_signals(
        career_phase_data,
        career_signals,
        development_priorities,
    )
    normalized_signals = []
    for signal in overlay_signals:
        signal_dict = getattr(signal, "__dict__", signal)
        normalized_signals.append(_safe_mapping(signal_dict))
    return {
        "candidates": normalized_signals,
        "candidate_count": len(normalized_signals),
        "selected_candidate": deepcopy(normalized_signals[0]) if normalized_signals else None,
    }


def build_career_artifact_payloads(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build JSON-safe deterministic payloads for the career stage artifacts."""
    player = data.get("player") or {}
    history_df = data.get("history_df")
    if history_df is None:
        history_df = pd.DataFrame()
    percentiles_data = data.get("percentiles_data") or {}
    career_phase_data = get_career_phase_data(player, history_df)
    career_signals = get_career_signals(player, history_df, career_phase_data)
    development_priorities = get_development_priorities(percentiles_data)

    return {
        CAREER_PHASE_CONTEXT_ARTIFACT: build_career_phase_context_payload(player, history_df),
        CAREER_SIGNALS_CONTEXT_ARTIFACT: build_career_signals_context_payload(
            player,
            history_df,
            career_phase_data,
        ),
        CAREER_PRIORITIES_CONTEXT_ARTIFACT: build_career_priorities_context_payload(percentiles_data),
        CAREER_DASHBOARD_BRIEF_ARTIFACT: build_career_dashboard_brief_payload(
            data,
            career_phase_data,
            career_signals,
            development_priorities,
        ),
        CAREER_OVERLAY_CANDIDATES_ARTIFACT: build_career_overlay_candidates_payload(
            career_phase_data,
            career_signals,
            development_priorities,
        ),
    }


def build_career_stage_analysis_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Build the shared stage-analysis payload for career from deterministic artifacts."""
    player = data.get("player") or {}
    scope = build_career_artifact_scope(player.get("player_id") or player.get("id") or "")
    artifacts = {
        artifact_type: {"payload": payload}
        for artifact_type, payload in build_career_artifact_payloads(data).items()
    }
    analysis = CareerStageAgent().analyze(scope=scope, artifacts=artifacts, session_memory=None)
    return serialize_stage_analysis(analysis)
