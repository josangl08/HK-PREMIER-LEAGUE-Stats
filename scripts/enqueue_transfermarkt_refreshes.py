# ABOUTME: Enqueues prioritized Transfermarkt refresh jobs for current squads, upcoming opponents, and user-linked players.

import os
import sys
import argparse
import logging

sys.path.append(os.getcwd())

from utils.db_engine import init_db
from scripts.background_match_watcher import MatchWatcher


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Enqueue Transfermarkt refresh jobs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_bootstrap = subparsers.add_parser("current-season", help="Queue current-season squad coverage jobs.")
    p_bootstrap.add_argument("days_ahead", nargs="?", type=int, default=7)

    p_upcoming = subparsers.add_parser("upcoming-opponents", help="Queue scouting refresh for teams with upcoming fixtures.")
    p_upcoming.add_argument("days_ahead", nargs="?", type=int, default=10)

    subparsers.add_parser("user-priority", help="Queue refreshes for user/agent-linked players.")

    p_all = subparsers.add_parser("all", help="Queue all supported TM refresh job classes.")
    p_all.add_argument("days_ahead", nargs="?", type=int, default=10)

    args = parser.parse_args()

    init_db()
    watcher = MatchWatcher()

    if args.command == "current-season":
        added = watcher.enqueue_current_season_bootstrap(days_ahead=args.days_ahead)
        logger.info(f"✓ Enqueued current-season jobs: {added}")
        return

    if args.command == "upcoming-opponents":
        added = watcher.enqueue_upcoming_opponents(days_ahead=args.days_ahead)
        logger.info(f"✓ Enqueued upcoming-opponent jobs: {added}")
        return

    if args.command == "user-priority":
        added = watcher.enqueue_user_priority_refresh()
        logger.info(f"✓ Enqueued user-priority jobs: {added}")
        return

    added_bootstrap = watcher.enqueue_current_season_bootstrap(days_ahead=args.days_ahead)
    added_upcoming = watcher.enqueue_upcoming_opponents(days_ahead=args.days_ahead)
    added_users = watcher.enqueue_user_priority_refresh()
    logger.info(
        "✓ Enqueued TM jobs | current-season=%s upcoming=%s user-priority=%s total=%s",
        added_bootstrap,
        added_upcoming,
        added_users,
        added_bootstrap + added_upcoming + added_users,
    )


if __name__ == "__main__":
    main()
