#!/usr/bin/env python
# ABOUTME: Prints global Transfermarkt runtime state and queue summary.

import os
import sys

from sqlalchemy import func, select

sys.path.append(os.getcwd())

from data.managers.transfermarkt_runtime_manager import TransfermarktRuntimeManager
from models.db_models import MatchUpdateQueue
from utils.db_engine import SessionFactory, init_db


def main() -> None:
    init_db()
    runtime = TransfermarktRuntimeManager()
    status = runtime.get_status()
    print("TRANSFERMARKT RUNTIME")
    print(f"mode={status.mode}")
    print(f"status={status.status}")
    print(f"failure_count={status.failure_count}")
    print(f"last_success_at={status.last_success_at}")
    print(f"last_failure_at={status.last_failure_at}")
    print(f"blocked_at={status.blocked_at}")
    print(f"cooldown_until={status.cooldown_until}")
    print(f"assisted_session_loaded_at={status.assisted_session_loaded_at}")
    print(f"assisted_session_expires_at={status.assisted_session_expires_at}")
    print(f"block_reason={status.block_reason}")
    print()
    print("QUEUE")
    with SessionFactory() as session:
        rows = session.execute(
            select(MatchUpdateQueue.job_type, MatchUpdateQueue.status, func.count())
            .group_by(MatchUpdateQueue.job_type, MatchUpdateQueue.status)
            .order_by(MatchUpdateQueue.job_type, MatchUpdateQueue.status)
        ).all()
    for row in rows:
        print(f"{row[0]} {row[1]} {row[2]}")


if __name__ == "__main__":
    main()
