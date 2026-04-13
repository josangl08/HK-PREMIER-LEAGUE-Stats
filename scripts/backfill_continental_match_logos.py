#!/usr/bin/env python
# ABOUTME: Marks AFC/ACL MatchHistory rows for crest resolution and clears obsolete tm_* mini-logo references.
# ABOUTME: Targets only players linked to platform users or agent rosters, across historical continental matches.

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.append(os.getcwd())

from models.db_models import MatchHistory, UserPlayerLink, agent_player_links
from utils.db_engine import SessionFactory, init_db


def is_national_team_competition(name: str | None) -> bool:
    text = str(name or "").lower()
    national_tokens = [
        "asian cup",
        "world cup",
        "qualification",
        "qualifier",
        "nations cup",
        "friendly international",
        "u17",
        "u20",
        "u23",
        "u-17",
        "u-20",
        "u-23",
    ]
    return any(token in text for token in national_tokens)


def is_club_continental_competition(name: str | None) -> bool:
    text = str(name or "").lower()
    club_tokens = [
        "afc champions league",
        "champions league two",
        "afc cup",
        "copa de la afc",
        "acl",
    ]
    return any(token in text for token in club_tokens) and not is_national_team_competition(text)


def is_obsolete_tm_logo(path: str | None) -> bool:
    if not path:
        return False
    filename = Path(path).name.lower()
    return filename.startswith("tm_")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill continental MatchHistory rows for future crest resolution.")
    parser.add_argument("--dry-run", action="store_true", help="Show affected rows without writing.")
    args = parser.parse_args()

    init_db()
    with SessionFactory() as session:
        player_ids = {row[0] for row in session.execute(select(UserPlayerLink.player_id)).all()}
        player_ids.update(row[0] for row in session.execute(select(agent_player_links.c.player_id)).all())
        if not player_ids:
            print("No user/agent-linked players found.")
            return

        rows = session.execute(
            select(MatchHistory).where(MatchHistory.player_id.in_(tuple(player_ids)))
        ).scalars().all()

        affected = []
        for match in rows:
            if not is_club_continental_competition(match.competition_name):
                continue
            raw = dict(match.raw_data or {})
            existing_status = raw.get("logo_resolution_status")
            home_logo = raw.get("home_logo")
            away_logo = raw.get("away_logo")
            changed = False

            if is_obsolete_tm_logo(home_logo):
                raw["home_logo"] = None
                changed = True
            if is_obsolete_tm_logo(away_logo):
                raw["away_logo"] = None
                changed = True

            if not raw.get("logo_resolution_source"):
                raw["logo_resolution_source"] = "transfermarkt_match_report"
                changed = True

            if existing_status not in {"resolved", "pending"}:
                raw["logo_resolution_status"] = "pending"
                changed = True
            elif existing_status == "pending":
                changed = changed or False

            if changed:
                affected.append((match, raw))

        print(f"Continental user-linked rows to mark: {len(affected)}")
        for match, raw in affected[:20]:
            print(
                f"id={match.id} player_id={match.player_id} date={match.date.date()} "
                f"competition={match.competition_name!r} opponent={match.opponent!r} "
                f"status={raw.get('logo_resolution_status')}"
            )

        if args.dry_run:
            return

        for match, raw in affected:
            match.raw_data = raw
        session.commit()
        print(f"Updated {len(affected)} MatchHistory rows.")


if __name__ == "__main__":
    main()
