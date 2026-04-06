# ABOUTME: Refreshes HKFA fixture metadata only for upcoming matches in a bounded window.
# ABOUTME: Intended for scheduled runs (for example twice weekly cron jobs) without a full ICS sync.

import os
import sys
import logging

sys.path.append(os.getcwd())

from data.managers.fixture_manager import get_fixture_manager


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    days_ahead = 15
    if len(sys.argv) > 1:
        days_ahead = int(sys.argv[1])

    logger.info(f"Starting upcoming fixture metadata refresh for next {days_ahead} days...")
    try:
        refreshed = get_fixture_manager().refresh_upcoming_fixture_metadata(days_ahead=days_ahead)
        logger.info(f"✓ Upcoming fixture metadata refresh completed. Refreshed: {refreshed}")
    except Exception as e:
        logger.error(f"❌ Error during upcoming fixture metadata refresh: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
