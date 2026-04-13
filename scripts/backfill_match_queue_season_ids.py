#!/usr/bin/env python
# ABOUTME: Backfills NULL season_id values in match_update_queue using fixture linkage and active-season heuristics.
# ABOUTME: Covers post_match_history, current_season_bootstrap, user_priority_refresh, and upcoming_opponent_refresh jobs.

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import datetime
from typing import Optional

from sqlalchemy import select

sys.path.append(os.getcwd())

from models.db_models import Fixture, MatchUpdateQueue
from utils.db_engine import SessionFactory, init_db


def resolve_active_season_id(session, reference_dt: Optional[datetime]) -> Optional[str]:
    reference_dt = reference_dt or datetime.utcnow()
    upcoming = session.execute(
        select(Fixture.season_id)
        .where(Fixture.date_utc >= reference_dt)
        .order_by(Fixture.date_utc.asc())
        .limit(1)
    ).scalar_one_or_none()
    if upcoming:
        return upcoming
    return session.execute(
        select(Fixture.season_id).order_by(Fixture.date_utc.desc()).limit(1)
    ).scalar_one_or_none()


def infer_season_id(session, row: MatchUpdateQueue) -> Optional[str]:
    if row.fixture_id:
        fixture = session.get(Fixture, row.fixture_id)
        if fixture and fixture.season_id:
            return fixture.season_id

    if row.job_type in {"current_season_bootstrap", "user_priority_refresh", "upcoming_opponent_refresh"}:
        return resolve_active_season_id(session, row.created_at or row.next_attempt)

    if row.job_type == "post_match_history":
        return resolve_active_season_id(session, row.created_at or row.next_attempt)

    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill NULL season_id values in match_update_queue.")
    parser.add_argument("--dry-run", action="store_true", help="Show proposed updates without writing.")
    args = parser.parse_args()

    init_db()
    with SessionFactory() as session:
        rows = session.execute(
            select(MatchUpdateQueue).where(MatchUpdateQueue.season_id.is_(None))
        ).scalars().all()
        if not rows:
            print("No NULL season_id rows found.")
            return

        updates = []
        unresolved = []
        for row in rows:
            season_id = infer_season_id(session, row)
            if season_id:
                updates.append((row, season_id))
            else:
                unresolved.append(row)

        print(f"Found {len(rows)} rows with NULL season_id.")
        print(f"Resolvable: {len(updates)}")
        print(f"Unresolved: {len(unresolved)}")
        print("Resolvable by season:", Counter(season for _, season in updates))
        print("Unresolved by job_type:", Counter(r.job_type for r in unresolved))

        for row, season_id in updates[:20]:
            print(f"id={row.id} job_type={row.job_type} fixture_id={row.fixture_id} -> season_id={season_id}")

        if args.dry_run:
            return

        for row, season_id in updates:
            row.season_id = season_id
        session.commit()
        print(f"Backfilled {len(updates)} rows.")


if __name__ == "__main__":
    main()
