# ABOUTME: Compares multiple Gemini models against the real career dashboard brief prompt.
# ABOUTME: Helps choose the primary and fallback models for the career dashboard AI synthesis path.

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.ai_services.llm_client import generate_gemini_content_with_status  # noqa: E402
from utils.ai_services.prompt_builders import build_career_dashboard_synthesis_prompt  # noqa: E402
from utils.career_intelligence import (  # noqa: E402
    build_fallback_career_dashboard_brief,
    get_career_phase_data,
    get_career_signals,
    get_development_priorities,
)


MODEL_CANDIDATES = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
]


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


def _build_prompt() -> str:
    player, phase_data, signals, development_priorities = _build_fixture()
    fallback = build_fallback_career_dashboard_brief(
        player,
        phase_data,
        signals,
        development_priorities,
    )

    def item_to_payload(item):
        return {
            "label": item.title,
            "body": item.body,
            "support": item.support,
            "confidence": "medium",
            "evidence_key": item.evidence_key,
            "emphasis": item.emphasis,
        }

    return build_career_dashboard_synthesis_prompt(
        player_name=player["player_name"],
        career_thesis=fallback.career_thesis,
        signals=[item_to_payload(item) for item in fallback.signals],
        levers=[item_to_payload(item) for item in fallback.levers],
        outlook=fallback.outlook,
        context={
            "career_phase": phase_data.get("career_phase"),
            "momentum_score": phase_data.get("momentum_score"),
            "coach_confidence": (signals.get("coach_confidence") or {}).get("label"),
            "transfer_window": (signals.get("transfer_window") or {}).get("quality"),
            "consistency": (signals.get("consistency_score") or {}).get("level"),
        },
    )


def main() -> int:
    prompt = _build_prompt()
    results = []
    for model in MODEL_CANDIDATES:
        result = generate_gemini_content_with_status(
            prompt,
            model_name=model,
            response_mime_type="application/json",
            max_output_tokens=1400,
            temperature=0.35,
        )
        results.append(
            {
                "model": model,
                "ok": result.ok,
                "status": result.status,
                "error_type": result.error_type,
                "error_message": result.error_message,
                "text_preview": (result.text or "")[:700],
            }
        )

    report = {
        "prompt_length": len(prompt),
        "models": results,
    }
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
