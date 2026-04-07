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


def _count_pending(job_types: set[str] | None = None) -> int:
    from datetime import datetime
    now = datetime.utcnow()
    with SessionFactory() as session:
        q = session.query(MatchUpdateQueue).filter(
            MatchUpdateQueue.status.in_(("PENDING", "DEFERRED")),
            MatchUpdateQueue.next_attempt <= now,
        )
        if job_types:
            q = q.filter(MatchUpdateQueue.job_type.in_(tuple(job_types)))
        return q.count()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run assisted Transfermarkt refresh flows.")
    parser.add_argument(
        "scope",
        choices=["priority", "users", "post-match", "all"],
        help="Which assisted queue preparation to run before processing",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=50,
        help="Max process_queue() cycles to run (default: 50)",
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

    cycles = 0
    idle_cycles = 0
    while cycles < args.max_cycles:
        pending = _count_pending()
        if pending == 0:
            print(f"Queue empty after {cycles} cycle(s).")
            break
        status = runtime.get_status()
        if status.mode == "BLOCKED":
            print(f"Transfermarkt BLOCKED after {cycles} cycle(s). Run again later or reset with: python scripts/tm_assisted_session.py reset-block")
            break
        pending_before = _count_pending()
        print(f"Cycle {cycles + 1}/{args.max_cycles} — {pending} jobs ready...")
        watcher.process_queue()
        cycles += 1
        pending_after = _count_pending()
        if pending_after >= pending_before:
            idle_cycles += 1
            if idle_cycles >= 3:
                print(f"No progress after {idle_cycles} cycles — all remaining jobs are deferred. Run again later.")
                break
        else:
            idle_cycles = 0
    else:
        print(f"Reached max-cycles limit ({args.max_cycles}). Run again to continue.")

    if args.scope == "priority":
        print(f"Assisted refresh completed for scope={args.scope}; requeued_failed={requeued}")
    else:
        print(f"Assisted refresh completed for scope={args.scope}")


if __name__ == "__main__":
    main()
