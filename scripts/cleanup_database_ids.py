"""
Database cleanup script to unify player IDs and remove name-based slugs.
Strategy:
1. Load PlayerIndex.
2. Identify players in DB whose ID is NOT in the index OR doesn't match the index canonical ID for that name.
3. For each 'bad' player entry:
   a. Find the 'good' ID from index.
   b. If the 'good' ID exists in DB, move stats from 'bad' to 'good'.
   c. If the 'good' ID doesn't exist, rename the 'bad' ID to 'good'.
   d. Delete the 'bad' player entry if redundant.
"""

import logging
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update, delete, and_
from models.db_models import Player, PlayerSeasonStat, Team
from utils.db_engine import SessionFactory
from utils.player_index import get_player_index

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def cleanup():
    player_index = get_player_index()
    player_index.build(force=True) # Ensure it is fresh
    
    session = SessionFactory()
    try:
        # 1. Get all players in DB
        stmt = select(Player)
        db_players = session.execute(stmt).scalars().all()
        logger.info(f"Total players in DB before cleanup: {len(db_players)}")
        
        count_deleted = 0
        count_merged = 0
        
        for p in db_players:
            # Get the ID that SHOULD be used for this name according to the index
            canonical_id = player_index.get_player_id(p.name)
            
            if not canonical_id:
                # If name not in index, they have 0 minutes or are noise
                logger.info(f"Removing player with no index entry (noise): {p.name} ({p.id})")
                # Delete stats first
                session.execute(delete(PlayerSeasonStat).where(PlayerSeasonStat.player_id == p.id))
                session.delete(p)
                count_deleted += 1
                session.flush()
                continue
                
            if p.id != canonical_id:
                logger.info(f"Found mismatched ID: {p.name} (Current: {p.id}, Target: {canonical_id})")
                
                # Check if the target canonical ID already exists in DB
                target_p = session.get(Player, canonical_id)
                
                if not target_p:
                    # CREATE TARGET PLAYER FIRST
                    logger.info(f"  Target ID {canonical_id} not in DB. Creating skeleton...")
                    target_p = Player(
                        id=canonical_id,
                        name=p.name,
                        current_team_id=p.current_team_id,
                        position_main=p.position_main,
                        age=p.age
                    )
                    session.add(target_p)
                    session.flush()

                # MERGE/MOVE STATS
                logger.info(f"  Migrating stats from {p.id} to {canonical_id}...")
                
                # Get all stats from bad ID
                stmt_stats = select(PlayerSeasonStat).where(PlayerSeasonStat.player_id == p.id)
                bad_stats = session.execute(stmt_stats).scalars().all()
                
                for bs in bad_stats:
                    # Check if target ID already has stats for THIS season
                    stmt_exists = select(PlayerSeasonStat).where(
                        and_(
                            PlayerSeasonStat.player_id == canonical_id,
                            PlayerSeasonStat.season_id == bs.season_id
                        )
                    )
                    existing_stats = session.execute(stmt_exists).scalars().all()
                    
                    if existing_stats:
                        # If multiple exist (unexpected but possible), find the best one
                        existing_stat = max(existing_stats, key=lambda s: s.minutes_played or 0)
                        
                        # Delete all others except the best one
                        for s in existing_stats:
                            if s != existing_stat:
                                session.delete(s)

                        # If bad stat is better than the best existing one, update it
                        if (bs.minutes_played or 0) > (existing_stat.minutes_played or 0):
                            logger.info(f"    Updating season {bs.season_id} with better stats from {p.id}")
                            existing_stat.matches_played = bs.matches_played
                            existing_stat.minutes_played = bs.minutes_played
                            existing_stat.goals = bs.goals
                            existing_stat.assists = bs.assists
                            existing_stat.yellow_cards = bs.yellow_cards
                            existing_stat.red_cards = bs.red_cards
                            existing_stat.advanced_stats = bs.advanced_stats
                    else:
                        # Create a NEW stat object for the canonical ID
                        new_stat = PlayerSeasonStat(
                            player_id=canonical_id,
                            season_id=bs.season_id,
                            matches_played=bs.matches_played,
                            minutes_played=bs.minutes_played,
                            goals=bs.goals,
                            assists=bs.assists,
                            yellow_cards=bs.yellow_cards,
                            red_cards=bs.red_cards,
                            advanced_stats=bs.advanced_stats
                        )
                        session.add(new_stat)
                    
                    # Delete the 'bad' season record
                    session.delete(bs)
                
                # Now it's safe to delete the old player record
                session.delete(p)
                count_merged += 1
                session.flush() 
        
        session.commit()
        logger.info("Cleanup complete.")
        logger.info(f"Players deleted (noise): {count_deleted}")
        logger.info(f"Players merged/renamed: {count_merged}")
        
        # Verify final count
        final_count = session.execute(select(Player)).scalars().all()
        logger.info(f"Total players in DB after cleanup: {len(final_count)}")

    except Exception as e:
        session.rollback()
        logger.error(f"Cleanup failed: {e}")
        import traceback; traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    cleanup()
