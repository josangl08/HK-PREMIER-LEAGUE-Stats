# ABOUTME: Script to scrape and store player profile photos from Transfermarkt as blobs in the DB.
# ABOUTME: Handles both players with known tm_id and players that need name-based TM search first.

import sys
import time
import logging
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from models.db_models import Player, PlayerPhoto
from utils.db_engine import SessionFactory, init_db
from data.extractors.transfermarkt_extractor import TransfermarktExtractor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RATE_LIMIT_SECONDS = 2


def _has_primary_photo_blob(session, player_id: str) -> bool:
    """Returns True if the player already has a primary photo with blob data in the DB."""
    stmt = select(PlayerPhoto).where(
        PlayerPhoto.player_id == player_id,
        PlayerPhoto.is_primary == True,
        PlayerPhoto.photo_data.is_not(None),
    )
    return session.execute(stmt).scalars().first() is not None


def run(dry_run: bool = False) -> None:
    """
    Ensures every player has a photo blob in the DB.

    Group A — has tm_id, no photo yet:
        Fetch photo directly from TM profile URL.

    Group B — no tm_id, no photo:
        Search TM by name + available bio hints (nationality, birth_year, position),
        persist the resolved tm_id, then fetch the photo.

    Use --dry-run to log what would happen without writing anything.
    """
    init_db()
    extractor = TransfermarktExtractor()
    session = SessionFactory()
    prefix = "[DRY-RUN] " if dry_run else ""

    try:
        all_players = session.execute(select(Player)).scalars().all()
        needs_photo = [p for p in all_players if not _has_primary_photo_blob(session, p.id)]

        group_a = [p for p in needs_photo if p.tm_id]
        group_b = [p for p in needs_photo if not p.tm_id]

        logger.info(
            f"Players needing a photo: {len(needs_photo)} total "
            f"({len(group_a)} with tm_id, {len(group_b)} without tm_id)"
        )

        stats = {"a_ok": 0, "a_fail": 0, "b_resolved": 0, "b_not_found": 0, "b_ok": 0, "b_fail": 0}

        # ── Group A: tm_id known ─────────────────────────────────────────────
        for player in group_a:
            tm_id_str = str(player.tm_id)
            logger.info(f"{prefix}[A] {player.name} (tm_id={tm_id_str})")
            if not dry_run:
                ok = extractor.fetch_and_store_player_photo(player.id, tm_id_str, session)
                if ok:
                    stats["a_ok"] += 1
                else:
                    logger.warning(f"    No photo retrieved for {player.name}")
                    stats["a_fail"] += 1
                time.sleep(RATE_LIMIT_SECONDS)

        # ── Group B: no tm_id — search first ────────────────────────────────
        for player in group_b:
            # Build bio hints from whatever the DB has
            birth_year = None
            if player.birth_date:
                birth_year = player.birth_date.year
            elif player.age:
                from datetime import datetime
                birth_year = datetime.now().year - player.age

            team_hint = player.current_team.name if player.current_team else ""
            nat_hint  = player.nationality or player.birth_country or ""
            pos_hint  = player.position_main or ""

            logger.info(
                f"{prefix}[B] {player.name} | team='{team_hint}' nat='{nat_hint}' "
                f"by={birth_year} pos='{pos_hint}'"
            )

            if dry_run:
                continue

            found_tm_id = extractor.search_player_by_name(
                player.name,
                team=team_hint,
                nationality=nat_hint,
                birth_year=birth_year,
                position=pos_hint,
            )

            if not found_tm_id:
                logger.warning(f"    Could not resolve tm_id for {player.name!r} — skipping photo.")
                stats["b_not_found"] += 1
                time.sleep(RATE_LIMIT_SECONDS)
                continue

            stats["b_resolved"] += 1
            player.tm_id = found_tm_id
            session.commit()
            logger.info(f"    Resolved tm_id={found_tm_id}")

            ok = extractor.fetch_and_store_player_photo(player.id, str(found_tm_id), session)
            if ok:
                stats["b_ok"] += 1
            else:
                logger.warning(f"    No photo retrieved for {player.name}")
                stats["b_fail"] += 1

            time.sleep(RATE_LIMIT_SECONDS)

        logger.info(
            f"\nDone. "
            f"GroupA: ok={stats['a_ok']} fail={stats['a_fail']} | "
            f"GroupB: resolved={stats['b_resolved']} not_found={stats['b_not_found']} "
            f"ok={stats['b_ok']} fail={stats['b_fail']}"
        )

    except Exception as e:
        logger.error(f"Script error: {e}", exc_info=True)
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh player photos from Transfermarkt.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Log what would happen without writing to the DB.")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
