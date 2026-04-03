"""
Script to delete 'ghost' statistics from the database.
Ghost statistics are records with:
1. Very low minutes (< 15 min).
2. Missing or mostly NULL advanced metrics.
This helps clean up the dashboard and career history.
"""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, delete
from models.db_models import PlayerSeasonStat, Player
from utils.db_engine import SessionFactory

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def delete_noise():
    session = SessionFactory()
    try:
        # 1. Identify stats with 0 minutes or no advanced stats keys
        # We consider 'noise' any record where minutes < 15 and goals+assists == 0
        stmt = select(PlayerSeasonStat).where(
            PlayerSeasonStat.minutes_played < 15,
            PlayerSeasonStat.goals == 0,
            PlayerSeasonStat.assists == 0
        )
        noise_stats = session.execute(stmt).scalars().all()
        logger.info(f"Identified {len(noise_stats)} suspicious low-minute records.")
        
        count_deleted = 0
        for s in noise_stats:
            # Check if advanced stats is empty or contains mostly nulls
            is_empty = not s.advanced_stats or len(s.advanced_stats) < 5
            
            if is_empty:
                session.delete(s)
                count_deleted += 1
        
        session.commit()
        logger.info(f"Successfully deleted {count_deleted} noise/empty stat records.")
        
        # 2. Delete players that now have NO stats at all (abandoned identities)
        stmt_players = select(Player)
        all_players = session.execute(stmt_players).scalars().all()
        
        count_p_deleted = 0
        for p in all_players:
            stmt_check = select(PlayerSeasonStat).where(PlayerSeasonStat.player_id == p.id)
            has_stats = session.execute(stmt_check).first()
            
            if not has_stats:
                session.delete(p)
                count_p_deleted += 1
        
        session.commit()
        logger.info(f"Successfully deleted {count_p_deleted} abandoned player profiles.")

    except Exception as e:
        session.rollback()
        logger.error(f"Cleanup failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    delete_noise()
