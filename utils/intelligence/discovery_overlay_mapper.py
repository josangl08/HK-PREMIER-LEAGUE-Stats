# ABOUTME: Shared mapper from persisted stage discoveries to overlay candidate payloads.
# ABOUTME: Keeps stage analyses UI-agnostic while preserving identity, evidence, and novelty for overlay consumption.

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from utils.intelligence.discovery_contracts import StageAnalysis, coerce_stage_analysis


def build_overlay_candidates_from_analysis(
    analysis: StageAnalysis | Mapping[str, Any] | None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Convert a shared stage analysis into overlay-candidate payloads."""
    normalized = coerce_stage_analysis(analysis)
    if normalized is None:
        return {"candidates": []}

    candidates: List[Dict[str, Any]] = []
    scope = dict(normalized.scope or {})
    for discovery in normalized.discoveries:
        candidates.append(
            {
                "signal_id": discovery.discovery_id,
                "title": discovery.title,
                "body": discovery.body,
                "anchor": discovery.anchor,
                "priority": discovery.priority,
                "confidence": discovery.confidence,
                "cta_label": discovery.cta_label,
                "evidence_key": discovery.evidence_keys[0] if discovery.evidence_keys else "",
                "type": discovery.type,
                "novelty_key": discovery.novelty_key,
                "presentation_hint": discovery.presentation_hint,
                "evidence": dict(discovery.metadata),
                "supporting_artifacts": list(discovery.supporting_artifacts),
                "stage": discovery.stage,
                "player_id": str(scope.get("player_id") or ""),
                "scope": scope,
            }
        )
    return {"candidates": candidates}
