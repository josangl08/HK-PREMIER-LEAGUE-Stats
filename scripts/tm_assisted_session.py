#!/usr/bin/env python
# ABOUTME: Load, clear, and inspect assisted Transfermarkt cookie sessions.

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.append(os.getcwd())

from data.managers.transfermarkt_runtime_manager import TransfermarktRuntimeManager
from utils.db_engine import init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage assisted Transfermarkt session cookies.")
    sub = parser.add_subparsers(dest="command", required=True)

    load = sub.add_parser("load")
    load.add_argument("--from-file", required=True)
    load.add_argument("--created-by", default="manual")
    load.add_argument("--expires-hours", type=int, default=12)

    sub.add_parser("clear")
    sub.add_parser("status")

    args = parser.parse_args()
    init_db()
    runtime = TransfermarktRuntimeManager()

    if args.command == "load":
        payload = Path(args.from_file).read_text(encoding="utf-8")
        expires_at = datetime.now(timezone.utc) + timedelta(hours=args.expires_hours)
        runtime.store_cookie_payload(payload, created_by=args.created_by, expires_at=expires_at)
        runtime.activate_assisted_mode(expires_in_hours=args.expires_hours)
        print(f"Loaded Transfermarkt assisted cookies from {args.from_file}")
        print(f"Assisted mode active until {expires_at.isoformat()}")
        return

    if args.command == "clear":
        runtime.clear_cookie_payload()
        runtime.deactivate_assisted_mode()
        print("Cleared Transfermarkt assisted session.")
        return

    if args.command == "status":
        status = runtime.get_status()
        has_cookies = bool(runtime.get_cookie_payload())
        print(f"mode={status.mode}")
        print(f"status={status.status}")
        print(f"has_cookies={has_cookies}")
        print(f"assisted_session_loaded_at={status.assisted_session_loaded_at}")
        print(f"assisted_session_expires_at={status.assisted_session_expires_at}")


if __name__ == "__main__":
    main()
