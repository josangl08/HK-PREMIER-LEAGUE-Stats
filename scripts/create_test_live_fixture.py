# ABOUTME: Creates or updates a short-lived LIVE fixture in SQL for timeline/theme debugging.
# ABOUTME: Useful to validate Player Portal ordering and LIVE card styling without waiting for a real match window.

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.append(os.getcwd())

from sqlalchemy import select

from utils.db_engine import SessionFactory
from models.db_models import Fixture, Player, Team
from data.managers.fixture_manager import get_current_season


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _ensure_team(session, team_id: str) -> Team:
    team = session.get(Team, team_id)
    if team is None:
        raise ValueError(f"Team '{team_id}' does not exist.")
    return team


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_test_live_fixture.py <player_id> [opponent_team_id]")
        sys.exit(1)

    player_id = str(sys.argv[1]).strip()
    opponent_team_id = str(sys.argv[2]).strip() if len(sys.argv) > 2 else "kitchee"

    with SessionFactory() as session:
        player = session.get(Player, player_id)
        if player is None:
            raise ValueError(f"Player '{player_id}' not found.")
        if not player.current_team_id:
            raise ValueError(f"Player '{player_id}' has no current_team_id.")

        home_team = _ensure_team(session, player.current_team_id)
        away_team = _ensure_team(session, opponent_team_id)

        now_utc = datetime.now(timezone.utc)
        kickoff_utc = now_utc - timedelta(minutes=35)
        season_id = get_current_season()
        external_id = f"test-live:{player_id}:{season_id}"

        fixture = session.execute(
            select(Fixture).where(Fixture.external_id == external_id)
        ).scalar_one_or_none()

        payload = {
            "season_id": season_id,
            "date_utc": kickoff_utc.replace(tzinfo=None),
            "home_team_id": home_team.id,
            "away_team_id": away_team.id,
            "venue": home_team.stadium_name or "Test Venue",
            "competition_type": "HK Premier League",
            "stream_url": "https://example.com/live-test-stream",
            "home_team_logo": home_team.logo_url,
            "away_team_logo": away_team.logo_url,
            "metadata_json": {
                "source": "manual_test_fixture",
                "created_for": player_id,
                "status": "LIVE_TEST",
            },
        }

        if fixture is None:
            fixture = Fixture(external_id=external_id, **payload)
            session.add(fixture)
            action = "created"
        else:
            for key, value in payload.items():
                setattr(fixture, key, value)
            action = "updated"

        session.commit()
        logger.info(
            "Test LIVE fixture %s for player=%s team=%s vs %s kickoff_utc=%s external_id=%s",
            action,
            player_id,
            home_team.id,
            away_team.id,
            kickoff_utc.isoformat(),
            external_id,
        )


if __name__ == "__main__":
    main()
