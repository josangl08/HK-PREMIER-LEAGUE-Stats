# ABOUTME: Smoke test script for the shared AI insight platform and career dashboard domain service.
# ABOUTME: Verifies deterministic payload generation, validation, and evidence routing without starting Dash.

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.ai_services.evidence_router import get_evidence_destination_meta
from utils.ai_services.validators import validate_insight_payload
from utils.career_intelligence import (
    build_career_dashboard_brief,
    get_career_phase_data,
    get_career_signals,
    get_development_priorities,
)


def main() -> int:
    history_df = pd.DataFrame(
        [
            {"Season": "2022/23", "Goals": 7, "Minutes played": 1240, "Key passes": 18, "Duels won": 44},
            {"Season": "2023/24", "Goals": 10, "Minutes played": 1680, "Key passes": 23, "Duels won": 51},
            {"Season": "2024/25", "Goals": 13, "Minutes played": 2115, "Key passes": 29, "Duels won": 58},
        ]
    )
    player = {
        "player_name": "Smoke Test Player",
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
    brief = build_career_dashboard_brief(
        player,
        phase_data,
        signals,
        development_priorities,
        ai_payload=None,
    )

    if not brief.signals:
        raise AssertionError("No signal payloads were generated.")
    if not brief.levers:
        raise AssertionError("No lever payloads were generated.")

    first_signal = brief.signals[0]
    payload_ok = validate_insight_payload(
        {
            "label": first_signal.title,
            "body": first_signal.body,
            "support": first_signal.support,
            "confidence": "high",
            "evidence_key": first_signal.evidence_key,
            "emphasis": first_signal.emphasis,
        }
    )
    if not payload_ok:
        raise AssertionError("First generated insight failed shared payload validation.")

    evidence_meta = get_evidence_destination_meta(first_signal.evidence_key)

    output = {
        "career_thesis": brief.career_thesis,
        "first_signal": {
            "title": first_signal.title,
            "body": first_signal.body,
            "support": first_signal.support,
            "evidence_key": first_signal.evidence_key,
            "evidence_title": evidence_meta["title"],
        },
        "lever_titles": [item.title for item in brief.levers],
        "outlook": brief.outlook,
        "status": "ok",
    }
    print(json.dumps(output, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"AI platform smoke test failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
