#!/usr/bin/env python
# ABOUTME: Runs a controlled assisted Transfermarkt refresh cycle using the unified queue.

from __future__ import annotations

import argparse
import os
import sys

sys.path.append(os.getcwd())

from data.managers.transfermarkt_runtime_manager import TransfermarktRuntimeManager
from models.db_models import MatchUpdateQueue
from scripts.background_match_watcher import MatchWatcher
from utils.db_engine import SessionFactory, init_db


def _requeue_failed_tm_jobs_by_type(job_types: set[str]) -> int:
    with SessionFactory() as session:
        failed_jobs = session.query(MatchUpdateQueue).filter(
            MatchUpdateQueue.status == "FAILED",
            MatchUpdateQueue.job_type.in_(tuple(job_types)),
        ).all()
        now = watcher_now()
        count = 0
        for job in failed_jobs:
            job.status = "PENDING"
            job.tm_status = "READY"
            job.retry_after = None
            job.last_attempt = None
            job.next_attempt = now
            count += 1
        session.commit()
        return count


def watcher_now():
    from datetime import datetime
    return datetime.utcnow()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run assisted Transfermarkt refresh flows.")
    parser.add_argument(
        "scope",
        choices=["priority", "users", "post-match", "all"],
        help="Which assisted queue preparation to run before processing",
    )
    args = parser.parse_args()

    init_db()
    runtime = TransfermarktRuntimeManager()
    if not runtime.get_cookie_payload():
        raise SystemExit("No assisted Transfermarkt cookies loaded. Use scripts/tm_assisted_session.py load first.")

    runtime.activate_assisted_mode()
    watcher = MatchWatcher()
    requeued = 0

    if args.scope in {"priority", "all"}:
        requeued = _requeue_failed_tm_jobs_by_type({"post_match_history", "user_priority_refresh"})
        watcher.discover_finished_matches()
        watcher.enqueue_user_priority_refresh()
    if args.scope in {"users", "all"}:
        watcher.enqueue_user_priority_refresh()
    if args.scope in {"post-match", "all"}:
        watcher.discover_finished_matches()
    if args.scope == "all":
        watcher.enqueue_upcoming_opponents()
    if args.scope == "all":
        watcher.enqueue_current_season_bootstrap()

    watcher.process_queue()
    if args.scope == "priority":
        print(f"Assisted refresh completed for scope={args.scope}; requeued_failed={requeued}")
    else:
        print(f"Assisted refresh completed for scope={args.scope}")


if __name__ == "__main__":
    main()
