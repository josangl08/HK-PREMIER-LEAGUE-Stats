# ABOUTME: One-time cleanup script for match_history records with wrong dates due to a
# ABOUTME: pandas dayfirst=True parsing bug that misinterpreted DD/MM/YYYY as MM/DD/YYYY.

"""
Root cause: _parse_date() in TransfermarktDataManager used pd.to_datetime(date_val, dayfirst=True),
which in pandas 2.2.x silently ignored dayfirst for ambiguous dates, storing e.g. "01/11/2020"
(1 Nov) as 2020-01-11 (11 Jan) instead of 2020-11-01 (1 Nov). This created duplicate records
alongside the correctly-migrated ones.

This script:
  1. Finds all match_history rows where raw_data['date'] exists but was mis-parsed.
  2. If the correctly-parsed date already exists in the DB (true duplicate) → deletes the bad row.
  3. If the correctly-parsed date does NOT exist → corrects the date in place.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, and_
from utils.db_engine import SessionFactory
from models.db_models import MatchHistory

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _correct_date(raw_date_str: str) -> datetime | None:
    """Parse a Transfermarkt DD/MM/YYYY date string unambiguously."""
    try:
        return datetime.strptime(raw_date_str.strip(), "%d/%m/%Y")
    except (ValueError, AttributeError):
        return None


def run():
    session = SessionFactory()
    deleted = 0
    corrected = 0
    skipped = 0

    try:
        records = session.execute(select(MatchHistory)).scalars().all()

        for record in records:
            raw = record.raw_data or {}
            raw_date_str = raw.get("date")
            if not raw_date_str:
                skipped += 1
                continue

            correct_dt = _correct_date(raw_date_str)
            if not correct_dt:
                skipped += 1
                continue

            # Normalise both to date-only for comparison (stored as midnight UTC)
            stored_date = record.date.date() if record.date else None
            correct_date = correct_dt.date()

            if stored_date == correct_date:
                # Already correct — nothing to do
                continue

            logger.warning(
                "Mismatch — player=%s id=%s raw='%s' stored=%s correct=%s",
                record.player_id, record.id, raw_date_str, stored_date, correct_date,
            )

            # Check whether a record with the correct date already exists for this player+opponent
            duplicate = session.execute(
                select(MatchHistory).where(
                    and_(
                        MatchHistory.player_id == record.player_id,
                        MatchHistory.date == correct_dt,
                        MatchHistory.opponent == record.opponent,
                    )
                )
            ).scalar_one_or_none()

            if duplicate:
                logger.info(
                    "  → True duplicate of id=%s — deleting bad record id=%s",
                    duplicate.id, record.id,
                )
                session.delete(record)
                deleted += 1
            else:
                logger.info(
                    "  → No duplicate found — correcting date on id=%s: %s → %s",
                    record.id, stored_date, correct_date,
                )
                record.date = correct_dt
                corrected += 1

        session.commit()

    except Exception as exc:
        session.rollback()
        logger.error("Error during cleanup: %s", exc)
        raise
    finally:
        session.close()

    logger.info(
        "Done. Deleted %d duplicate records, corrected %d records, skipped %d (no raw date).",
        deleted, corrected, skipped,
    )


if __name__ == "__main__":
    run()
