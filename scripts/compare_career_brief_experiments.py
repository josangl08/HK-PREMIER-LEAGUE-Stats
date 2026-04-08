# ABOUTME: Compares official Gemini model candidates and prompt variants for the career dashboard brief.
# ABOUTME: Helps choose a production hierarchy by testing robustness and response quality with the real brief payload.

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.ai_services.llm_client import generate_gemini_content_with_status  # noqa: E402
from utils.ai_services.orchestration import parse_structured_json, validate_payload_collection  # noqa: E402
from utils.ai_services.prompt_builders import build_career_dashboard_synthesis_prompt  # noqa: E402
from utils.career_intelligence import (  # noqa: E402
    build_fallback_career_dashboard_brief,
    get_career_phase_data,
    get_career_signals,
    get_development_priorities,
)


EXPERIMENTS = [
    {"label": "2.5-pro-strict", "model": "gemini-2.5-pro", "prompt_variant": "strict"},
    {"label": "2.5-pro-lean", "model": "gemini-2.5-pro", "prompt_variant": "lean"},
    {"label": "2.5-flash-strict", "model": "gemini-2.5-flash", "prompt_variant": "strict"},
    {"label": "3.1-flash-lite-preview-strict", "model": "gemini-3.1-flash-lite-preview", "prompt_variant": "strict"},
    {"label": "3.1-pro-preview-strict", "model": "gemini-3.1-pro-preview", "prompt_variant": "strict"},
    {"label": "3-flash-preview-strict", "model": "gemini-3-flash-preview", "prompt_variant": "strict"},
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
    fallback = build_fallback_career_dashboard_brief(
        player,
        phase_data,
        signals,
        development_priorities,
    )
    return player, phase_data, signals, fallback


def _item_to_payload(item: Any) -> Dict[str, Any]:
    return {
        "label": item.title,
        "body": item.body,
        "support": item.support,
        "confidence": "medium",
        "evidence_key": item.evidence_key,
        "emphasis": item.emphasis,
    }


def _build_strict_prompt(
    player: Dict[str, Any],
    phase_data: Dict[str, Any],
    signals: Dict[str, Any],
    fallback: Any,
) -> str:
    return build_career_dashboard_synthesis_prompt(
        player_name=player["player_name"],
        career_thesis=fallback.career_thesis,
        signals=[_item_to_payload(item) for item in fallback.signals],
        levers=[_item_to_payload(item) for item in fallback.levers],
        outlook=fallback.outlook,
        context={
            "career_phase": phase_data.get("career_phase"),
            "momentum_score": phase_data.get("momentum_score"),
            "coach_confidence": (signals.get("coach_confidence") or {}).get("label"),
            "transfer_window": (signals.get("transfer_window") or {}).get("quality"),
            "consistency": (signals.get("consistency_score") or {}).get("level"),
        },
    )


def _build_lean_prompt(
    player: Dict[str, Any],
    phase_data: Dict[str, Any],
    signals: Dict[str, Any],
    fallback: Any,
) -> str:
    payload = {
        "player_name": player["player_name"],
        "career_phase": phase_data.get("career_phase"),
        "momentum_score": phase_data.get("momentum_score"),
        "career_thesis": fallback.career_thesis,
        "signals": [_item_to_payload(item) for item in fallback.signals],
        "outlook": fallback.outlook,
    }
    return (
        "Rewrite this football career dashboard payload for player-facing UI.\n"
        "Return JSON only with top-level keys career_thesis, signals, and outlook.\n"
        "For every signal keep fields label, body, support, confidence, evidence_key, emphasis.\n"
        "Do not invent facts or evidence keys.\n"
        f"Payload JSON: {json.dumps(payload, ensure_ascii=True)}"
    )


def _build_prompt(variant: str, player: Dict[str, Any], phase_data: Dict[str, Any], signals: Dict[str, Any], fallback: Any) -> str:
    if variant == "lean":
        return _build_lean_prompt(player, phase_data, signals, fallback)
    return _build_strict_prompt(player, phase_data, signals, fallback)


def _score_response(parsed: Any) -> Dict[str, Any]:
    if not isinstance(parsed, dict):
        return {"parsed_json": False, "valid_signals": False, "valid_levers": False, "has_outlook": False}
    return {
        "parsed_json": True,
        "valid_signals": validate_payload_collection(parsed.get("signals")) if isinstance(parsed.get("signals"), list) else False,
        "valid_levers": validate_payload_collection(parsed.get("levers")) if isinstance(parsed.get("levers"), list) else False,
        "has_outlook": isinstance(parsed.get("outlook"), dict),
        "has_career_thesis": isinstance(parsed.get("career_thesis"), dict),
    }


def main() -> int:
    player, phase_data, signals, fallback = _build_fixture()
    results: List[Dict[str, Any]] = []

    for experiment in EXPERIMENTS:
        prompt = _build_prompt(experiment["prompt_variant"], player, phase_data, signals, fallback)
        result = generate_gemini_content_with_status(
            prompt,
            model_name=experiment["model"],
            response_mime_type="application/json",
            max_output_tokens=1400,
            temperature=0.35,
        )
        parsed = parse_structured_json(result.text) if result.text else None
        results.append(
            {
                "label": experiment["label"],
                "model": experiment["model"],
                "prompt_variant": experiment["prompt_variant"],
                "prompt_length": len(prompt),
                "ok": result.ok,
                "status": result.status,
                "error_type": result.error_type,
                "error_message": result.error_message,
                "quality": _score_response(parsed),
                "text_preview": (result.text or "")[:800],
            }
        )

    print(json.dumps({"experiments": results}, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
