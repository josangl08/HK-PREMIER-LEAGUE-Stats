# ABOUTME: Console trace script for the career dashboard AI platform path and fallback behavior.
# ABOUTME: Shows whether the career domain service resolves deterministic fallback or structured AI payloads.

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.ai_services.llm_client import (  # noqa: E402
    gemini_is_available,
    get_dashboard_brief_model_candidates,
    generate_gemini_content_with_status,
    get_default_gemini_model,
)
from utils.ai_services.orchestration import parse_structured_json  # noqa: E402
from utils.ai_services.prompt_builders import build_career_dashboard_synthesis_prompt  # noqa: E402
from utils.ai_services.prompt_builders import build_career_narrative_prompt  # noqa: E402
from utils.career_intelligence import (  # noqa: E402
    build_career_dashboard_brief,
    build_fallback_career_dashboard_brief,
    get_career_phase_data,
    get_career_signals,
    get_development_priorities,
)
from utils.stage_helpers import _generate_career_insight  # noqa: E402


def _build_fixture():
    history_df = pd.DataFrame(
        [
            {"Season": "2022/23", "Goals": 7, "Minutes played": 1240, "Key passes": 18, "Duels won": 44},
            {"Season": "2023/24", "Goals": 10, "Minutes played": 1680, "Key passes": 23, "Duels won": 51},
            {"Season": "2024/25", "Goals": 13, "Minutes played": 2115, "Key passes": 29, "Duels won": 58},
        ]
    )
    player = {
        "player_name": "Trace Player",
        "position_main": "Forward",
        "birth_date": date.today() - timedelta(days=25 * 365),
        "history_df": history_df,
        "minutes_played": 2115,
        "goals": 13,
        "assists": 5,
        "percentiles_data": {
            "Goals": 42,
            "Key passes": 39,
            "Duels won": 71,
        },
    }
    phase_data = get_career_phase_data(player, history_df)
    phase_data["transferability"] = {"score": 0.68, "label": "Strong fit"}
    signals = get_career_signals(player, history_df, phase_data)
    development_priorities = get_development_priorities(player["percentiles_data"])
    return player, phase_data, signals, development_priorities


def _serialize_brief(brief):
    return {
        "career_thesis": brief.career_thesis,
        "signals": [
            {
                "title": item.title,
                "body": item.body,
                "support": item.support,
                "evidence_key": item.evidence_key,
                "emphasis": item.emphasis,
            }
            for item in brief.signals
        ],
        "levers": [
            {
                "title": item.title,
                "body": item.body,
                "support": item.support,
                "evidence_key": item.evidence_key,
                "emphasis": item.emphasis,
            }
            for item in brief.levers
        ],
        "outlook": brief.outlook,
    }


def main() -> int:
    player, phase_data, signals, development_priorities = _build_fixture()
    history_df = player["history_df"]

    fallback_brief = build_fallback_career_dashboard_brief(
        player,
        phase_data,
        signals,
        development_priorities,
    )
    resolved_without_ai = build_career_dashboard_brief(
        player,
        phase_data,
        signals,
        development_priorities,
        ai_payload=None,
    )
    resolved_with_ai = build_career_dashboard_brief(
        player,
        phase_data,
        signals,
        development_priorities,
        ai_payload={
            "career_thesis": {
                "label": "AI Thesis",
                "body": "AI payload accepted for the career dashboard.",
                "support": "Structured AI payload supplied.",
            },
            "signals": [
                {
                    "label": "AI Role Evolution",
                    "body": "AI payload replaced the deterministic signal.",
                    "support": "Structured AI signal support.",
                    "confidence": "high",
                    "evidence_key": "minutes_trend",
                    "emphasis": "positive",
                }
            ],
            "levers": [],
            "outlook": {
                "label": "AI Outlook",
                "body": "AI payload replaced the deterministic outlook.",
                "support": "Structured AI outlook support.",
                "evidence_key": "projection_outlook",
            },
        },
    )

    brief_stats = ", ".join(
        f"{row['Season']}: {float(row['Goals']):.1f}"
        for _, row in history_df.tail(3).iterrows()
    )
    llm_prompt = build_career_narrative_prompt(
        player_name=player["player_name"],
        position_group=player["position_main"],
        primary_metric="Goals",
        brief_stats=brief_stats,
        form_trend={"trend": "up", "slope": 0.125},
        transferability=phase_data.get("transferability"),
    )
    llm_narrative = _generate_career_insight(
        history_df=history_df,
        primary_metric="Goals",
        player_name=player["player_name"],
        pos_group=player["position_main"],
        form_trend={"trend": "up", "slope": 0.125},
        transferability=phase_data.get("transferability"),
    )
    brief_prompt = build_career_dashboard_synthesis_prompt(
        player_name=player["player_name"],
        career_thesis=fallback_brief.career_thesis,
        signals=[
            {
                "label": item.title,
                "body": item.body,
                "support": item.support,
                "confidence": "medium",
                "evidence_key": item.evidence_key,
                "emphasis": item.emphasis,
            }
            for item in fallback_brief.signals
        ],
        levers=[
            {
                "label": item.title,
                "body": item.body,
                "support": item.support,
                "confidence": "medium",
                "evidence_key": item.evidence_key,
                "emphasis": item.emphasis,
            }
            for item in fallback_brief.levers
        ],
        outlook=fallback_brief.outlook,
        context={
            "career_phase": phase_data.get("career_phase"),
            "momentum_score": phase_data.get("momentum_score"),
            "coach_confidence": (signals.get("coach_confidence") or {}).get("label"),
            "transfer_window": (signals.get("transfer_window") or {}).get("quality"),
            "consistency": (signals.get("consistency_score") or {}).get("level"),
        },
    )
    brief_llm_result = generate_gemini_content_with_status(
        brief_prompt,
        temperature=0.35,
        max_output_tokens=1400,
        response_mime_type="application/json",
    )

    report = {
        "fallback_mode": {
            "used": _serialize_brief(resolved_without_ai) == _serialize_brief(fallback_brief),
            "reason": "No ai_payload provided",
            "brief": _serialize_brief(resolved_without_ai),
        },
        "structured_ai_mode": {
            "used": resolved_with_ai.career_thesis["label"] == "AI Thesis",
            "reason": "Valid ai_payload provided",
            "brief": _serialize_brief(resolved_with_ai),
        },
        "llm_mode": {
            "gemini_available": gemini_is_available(),
            "dashboard_brief_model": get_default_gemini_model(),
            "dashboard_brief_candidates": get_dashboard_brief_model_candidates(),
            "prompt_preview": llm_prompt[:240],
            "narrative_result": llm_narrative,
            "used_shared_client": bool(gemini_is_available() and llm_narrative),
            "fallback_detected": (
                isinstance(llm_narrative, str)
                and (
                    "Best-ever season" in llm_narrative
                    or "upward trajectory" in llm_narrative
                    or "fewer goals" in llm_narrative
                    or "Consistent output" in llm_narrative
                )
            ),
            "parsed_as_structured_json": isinstance(parse_structured_json(llm_narrative), dict),
            "brief_call": {
                "ok": brief_llm_result.ok,
                "status": brief_llm_result.status,
                "model": brief_llm_result.model,
                "error_type": brief_llm_result.error_type,
                "error_message": brief_llm_result.error_message,
                "text_preview": (brief_llm_result.text or "")[:400],
            },
        },
    }

    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
