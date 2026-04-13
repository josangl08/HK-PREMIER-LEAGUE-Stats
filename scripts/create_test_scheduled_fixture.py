# ABOUTME: Creates or updates a scheduled test fixture in the DB for UI/integration debugging.
# ABOUTME: Inserts Tai Po vs Kitchee on 2026-04-18 18:00 HKT at Mong Kok Stadium without touching ICS.

import logging
import os
import sys
from datetime import datetime, timezone

sys.path.append(os.getcwd())

from sqlalchemy import select

from utils.db_engine import SessionFactory
from models.db_models import Fixture, Team


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

HOME_TEAM_ID = "tai_po"
AWAY_TEAM_ID = "kitchee"
KICKOFF_UTC = datetime(2026, 4, 18, 10, 0, 0)  # 18:00 HKT = 10:00 UTC
VENUE = "Mong Kok Stadium"
COMPETITION = "HK Premier League"
SEASON_ID = "2025-26"
EXTERNAL_ID = "test-scheduled:tai_po-vs-kitchee:2026-04-18"


def _ensure_team(session, team_id: str) -> Team:
    team = session.get(Team, team_id)
    if team is None:
        raise ValueError(f"Team '{team_id}' does not exist in the database.")
    return team


def main() -> None:
    with SessionFactory() as session:
        home_team = _ensure_team(session, HOME_TEAM_ID)
        away_team = _ensure_team(session, AWAY_TEAM_ID)

        fixture = session.execute(
            select(Fixture).where(Fixture.external_id == EXTERNAL_ID)
        ).scalar_one_or_none()

        payload = {
            "season_id": SEASON_ID,
            "date_utc": KICKOFF_UTC,
            "home_team_id": home_team.id,
            "away_team_id": away_team.id,
            "venue": VENUE,
            "competition_type": COMPETITION,
            "stream_url": None,
            "home_team_logo": home_team.logo_url,
            "away_team_logo": away_team.logo_url,
            "metadata_json": {
                "source": "manual_test_fixture",
                "status": "SCHEDULED_TEST",
            },
        }

        if fixture is None:
            fixture = Fixture(external_id=EXTERNAL_ID, **payload)
            session.add(fixture)
            action = "created"
        else:
            for key, value in payload.items():
                setattr(fixture, key, value)
            action = "updated"

        session.commit()
        logger.info(
            "Test scheduled fixture %s: %s vs %s | %s | %s HKT | venue=%s | external_id=%s",
            action,
            home_team.id,
            away_team.id,
            SEASON_ID,
            KICKOFF_UTC.strftime("%Y-%m-%d 18:00"),
            VENUE,
            EXTERNAL_ID,
        )


if __name__ == "__main__":
    main()
