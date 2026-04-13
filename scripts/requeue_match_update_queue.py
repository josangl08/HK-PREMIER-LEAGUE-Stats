#!/usr/bin/env python
# ABOUTME: Requeues match_update_queue rows back to PENDING with filters for season, status, and job type.
# ABOUTME: Helps recover FAILED/DEFERRED Transfermarkt jobs and inspect affected rows before reprocessing.

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import select

sys.path.append(os.getcwd())

from models.db_models import MatchUpdateQueue
from utils.db_engine import SessionFactory, init_db


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Requeue match_update_queue rows back to PENDING.")
    parser.add_argument(
        "--status",
        action="append",
        dest="statuses",
        default=[],
        help="Queue status to requeue. Can be passed multiple times. Default: FAILED and DEFERRED.",
    )
    parser.add_argument("--season", help="Filter by season_id, e.g. 2025-26.")
    parser.add_argument("--job-type", action="append", dest="job_types", default=[], help="Filter by job_type.")
    parser.add_argument("--tm-status", action="append", dest="tm_statuses", default=[], help="Filter by tm_status.")
    parser.add_argument("--reason-contains", help="Filter rows whose reason contains this text.")
    parser.add_argument("--dry-run", action="store_true", help="Show matching rows without changing them.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    init_db()
    statuses = tuple(args.statuses or ["FAILED", "DEFERRED"])
    now = datetime.utcnow()

    with SessionFactory() as session:
        query = select(MatchUpdateQueue).where(MatchUpdateQueue.status.in_(statuses))
        if args.season:
            query = query.where(MatchUpdateQueue.season_id == args.season)
        if args.job_types:
            query = query.where(MatchUpdateQueue.job_type.in_(tuple(args.job_types)))
        if args.tm_statuses:
            query = query.where(MatchUpdateQueue.tm_status.in_(tuple(args.tm_statuses)))
        if args.reason_contains:
            query = query.where(MatchUpdateQueue.reason.ilike(f"%{args.reason_contains}%"))

        rows = session.execute(query).scalars().all()
        if not rows:
            print("No matching queue rows found.")
            return

        for row in rows:
            print(
                f"id={row.id} status={row.status} tm_status={row.tm_status} "
                f"season={row.season_id} job_type={row.job_type} attempts={row.attempt_count} "
                f"reason={row.reason!r}"
            )

        if args.dry_run:
            print(f"Dry run: {len(rows)} matching rows.")
            return

        for row in rows:
            row.status = "PENDING"
            row.tm_status = "READY"
            row.retry_after = None
            row.last_attempt = None
            row.next_attempt = now

        session.commit()
        print(f"Requeued {len(rows)} rows.")


if __name__ == "__main__":
    main()
