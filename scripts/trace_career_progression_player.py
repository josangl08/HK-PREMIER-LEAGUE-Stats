# ABOUTME: Traces deterministic and AI-resolved career progression inputs for a real player from the dashboard pipeline.
# ABOUTME: Prints season history, progression features, resolved phase/momentum, and the final career thesis for debugging.

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.career_intelligence import (  # noqa: E402
    build_career_dashboard_brief,
    build_career_progression_features,
    get_career_phase_data,
    get_career_signals,
    get_development_priorities,
)
from utils.domain_ai.career_progression_assessor_ai import resolve_career_progression_cached  # noqa: E402
from utils.stage_helpers import _fetch_dashboard_data  # noqa: E402


def _serialize_features(features):
    payload = features.__dict__.copy()
    payload["peak_range"] = list(features.peak_range)
    return payload


def _serialize_resolution(resolution):
    return resolution.__dict__.copy()


def _serialize_brief(brief):
    return {
        "career_thesis": brief.career_thesis,
        "signals": [
            {
                "title": item.title,
                "body": item.body,
                "support": item.support,
                "evidence_key": item.evidence_key,
                "source_model": getattr(item, "source_model", ""),
                "llm_generated": getattr(item, "llm_generated", False),
            }
            for item in brief.signals
        ],
        "levers": [
            {
                "title": item.title,
                "body": item.body,
                "support": item.support,
                "evidence_key": item.evidence_key,
                "source_model": getattr(item, "source_model", ""),
                "llm_generated": getattr(item, "llm_generated", False),
            }
            for item in brief.levers
        ],
        "outlook": brief.outlook,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/trace_career_progression_player.py \"Player Name\" [player_id]")
        return 1

    player_name = sys.argv[1]
    player_id = sys.argv[2] if len(sys.argv) > 2 else ""
    data = _fetch_dashboard_data(player_name, player_id)
    history_df = data.get("history_df", pd.DataFrame())

    career_phase_data = get_career_phase_data(data, history_df)
    career_signals = get_career_signals(data, history_df, career_phase_data)
    progression_features = (
        career_phase_data.get("progression_features")
        if isinstance(career_phase_data, dict)
        else None
    ) or build_career_progression_features(data, history_df, career_signals)
    progression_resolution = resolve_career_progression_cached(
        player_identifier=str(data.get("player_id") or data.get("player_name") or "unknown"),
        player_name=str(data.get("player_name") or player_name),
        features=progression_features,
    )
    resolved_phase_data = {
        **(career_phase_data or {}),
        "progression_features": progression_features,
        "career_progression_resolution": progression_resolution,
        "career_phase": progression_resolution.resolved_phase,
        "momentum_score": progression_resolution.resolved_momentum,
        "base_career_phase": progression_resolution.base_phase,
        "base_momentum_score": progression_resolution.base_momentum,
        "progression_confidence": progression_resolution.confidence,
        "progression_adjustment_reason": progression_resolution.adjustment_reason,
        "progression_ai_used": progression_resolution.ai_used,
        "progression_ai_model": progression_resolution.ai_model,
    }
    resolved_signals = get_career_signals(data, history_df, resolved_phase_data)
    development_priorities = get_development_priorities(data.get("percentiles_data") or {})
    brief = build_career_dashboard_brief(
        data,
        resolved_phase_data,
        resolved_signals,
        development_priorities,
        ai_payload=data.get("career_dashboard_ai_brief"),
    )

    history_tail = []
    if isinstance(history_df, pd.DataFrame) and not history_df.empty:
        history_tail = history_df.tail(5).fillna("").to_dict("records")

    report = {
        "player_name": player_name,
        "player_id": data.get("player_id"),
        "identity": {
            "position_main": data.get("position_main"),
            "pos_group": data.get("pos_group"),
            "age": data.get("age"),
            "current_season": data.get("current_season"),
        },
        "history_tail": history_tail,
        "base_phase_data": career_phase_data,
        "base_signals": career_signals,
        "progression_features": _serialize_features(progression_features),
        "progression_resolution": _serialize_resolution(progression_resolution),
        "resolved_phase_data": resolved_phase_data,
        "resolved_signals": resolved_signals,
        "brief": _serialize_brief(brief),
    }
    print(json.dumps(report, indent=2, ensure_ascii=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
