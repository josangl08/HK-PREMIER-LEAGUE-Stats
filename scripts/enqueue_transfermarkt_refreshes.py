# ABOUTME: Enqueues prioritized Transfermarkt refresh jobs for current squads, upcoming opponents, and user-linked players.
# ABOUTME: Use force-all to enqueue every HK player with a tm_id regardless of squad/fixture filters.

import os
import sys
import argparse
import logging
from datetime import datetime

sys.path.append(os.getcwd())

from models.db_models import Player, MatchUpdateQueue
from utils.db_engine import SessionFactory, init_db
from scripts.background_match_watcher import MatchWatcher


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def force_enqueue_all_hk(watcher: MatchWatcher) -> int:
    """Enqueue current_season_bootstrap for every HK player with a tm_id, bypassing squad/fixture filters."""
    now = datetime.utcnow()
    added = 0
    with SessionFactory() as session:
        players = session.query(Player).filter(
            Player.id.like("hk_%"),
            Player.tm_id.isnot(None),
        ).all()
        for player in players:
            if watcher._enqueue_job(
                session,
                player_id=player.id,
                next_attempt=now,
                job_type="current_season_bootstrap",
                priority=60,
                source="force_all",
                reason="Manual full-roster refresh",
            ):
                added += 1
        session.commit()
    return added


def force_enqueue_season(watcher: MatchWatcher, season: str) -> int:
    """Enqueue current_season_bootstrap for ALL players with tm_id in a given season (no prefix filter)."""
    from sqlalchemy import select, and_
    from models.db_models import PlayerSeasonStat
    now = datetime.utcnow()
    added = 0
    with SessionFactory() as session:
        rows = session.execute(
            select(Player)
            .join(PlayerSeasonStat, and_(
                PlayerSeasonStat.player_id == Player.id,
                PlayerSeasonStat.season_id == season,
            ))
            .where(Player.tm_id.isnot(None))
            .distinct()
        ).scalars().all()
        for player in rows:
            if watcher._enqueue_job(
                session,
                player_id=player.id,
                next_attempt=now,
                job_type="current_season_bootstrap",
                priority=60,
                source="force_season",
                reason=f"Manual full-roster refresh season {season}",
            ):
                added += 1
        session.commit()
    return added


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

    subparsers.add_parser("force-all", help="Force-enqueue ALL HK players with tm_id, ignoring squad/fixture filters.")

    p_season = subparsers.add_parser("force-season", help="Force-enqueue ALL players with tm_id in a specific season (no prefix filter).")
    p_season.add_argument("season", nargs="?", default="2025-26", help="Season ID (default: 2025-26)")

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

    if args.command == "force-all":
        added = force_enqueue_all_hk(watcher)
        logger.info("✓ Force-enqueued %s HK players for current_season_bootstrap.", added)
        return

    if args.command == "force-season":
        added = force_enqueue_season(watcher, season=args.season)
        logger.info("✓ Force-enqueued %s players (season %s) for current_season_bootstrap.", added, args.season)
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
