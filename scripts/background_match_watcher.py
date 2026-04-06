# ABOUTME: Background worker that intelligently polls Transfermarkt for recent match results.
# ABOUTME: Implements a retry schedule (10m, 30m, 1h...) to capture finished matches as soon as they appear.

import sys
import os
import logging
import time
import argparse
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_, or_

# Add root to path
sys.path.append(os.getcwd())

from models.db_models import Fixture, MatchHistory, Player, MatchUpdateQueue, Team, UserPlayerLink, agent_player_links
from utils.db_engine import SessionFactory
from data.transfermarkt_data_manager import TransfermarktDataManager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MatchWatcher")

# Retry intervals (in minutes)
RETRY_INTERVALS = [10, 30, 60, 120, 180, 240, 300, 360, 420, 480, 540, 600] # up to 10h, then hourly

class MatchWatcher:
    def __init__(self):
        self.tm_manager = TransfermarktDataManager(auto_load=False)

    def discover_finished_matches(self):
        """
        Looks for fixtures that finished in the last 48 hours but aren't in MatchHistory.
        Adds them to the update queue if not already there.
        """
        session = SessionFactory()
        try:
            now = datetime.now(timezone.utc)
            # Matches that started between 48h ago and 2h ago (assumed finished)
            lookback = now - timedelta(hours=48)
            min_finish = now - timedelta(minutes=115) 
            
            stmt = select(Fixture).where(
                and_(
                    Fixture.date_utc >= lookback,
                    Fixture.date_utc <= min_finish
                )
            )
            finished_fixtures = session.execute(stmt).scalars().all()
            
            new_entries = 0
            for fix in finished_fixtures:
                # Find ONLY players that are users or managed by agents in our app
                players_stmt = (
                    select(Player)
                    .outerjoin(UserPlayerLink)
                    .outerjoin(agent_player_links)
                    .where(
                        and_(
                            or_(Player.current_team_id == fix.home_team_id, Player.current_team_id == fix.away_team_id),
                            or_(UserPlayerLink.player_id.is_not(None), agent_player_links.c.player_id.is_not(None))
                        )
                    )
                    .distinct()
                )
                players = session.execute(players_stmt).scalars().all()
                
                for player in players:
                    if not player.tm_id: continue
                    
                    # Check if match already in history
                    fix_date_str = fix.date_utc.strftime("%Y-%m-%d")
                    history_exists = session.execute(
                        select(MatchHistory).where(
                            and_(
                                MatchHistory.player_id == player.id,
                                MatchHistory.date >= fix.date_utc - timedelta(hours=12),
                                MatchHistory.date <= fix.date_utc + timedelta(hours=12)
                            )
                        )
                    ).scalar_one_or_none()
                    
                    if history_exists: continue
                    
                    # Check if already in queue
                    in_queue = session.execute(
                        select(MatchUpdateQueue).where(
                            and_(
                                MatchUpdateQueue.fixture_id == fix.id,
                                MatchUpdateQueue.player_id == player.id,
                                MatchUpdateQueue.status == "PENDING"
                            )
                        )
                    ).scalar_one_or_none()
                    
                    if not in_queue:
                        # Add to queue
                        queue_item = MatchUpdateQueue(
                            fixture_id=fix.id,
                            player_id=player.id,
                            status="PENDING",
                            attempt_count=0,
                            next_attempt=fix.date_utc + timedelta(minutes=125) # First attempt: finish + 10m
                        )
                        session.add(queue_item)
                        new_entries += 1
            
            session.commit()
            if new_entries > 0:
                logger.info(f"Added {new_entries} player-match tasks to the update queue.")
        finally:
            session.close()

    def process_queue(self):
        """
        Finds pending tasks whose next_attempt time has passed and tries to update them.
        """
        session = SessionFactory()
        try:
            now = datetime.now(timezone.utc)
            stmt = select(MatchUpdateQueue).where(
                and_(
                    MatchUpdateQueue.status == "PENDING",
                    MatchUpdateQueue.next_attempt <= now
                )
            ).order_by(MatchUpdateQueue.next_attempt.asc()).limit(10) # Process in small batches
            
            tasks = session.execute(stmt).scalars().all()
            
            if not tasks:
                return
                
            logger.info(f"Processing {len(tasks)} pending update tasks...")
            
            # To avoid redundant scraping for players in the same match, group by player
            player_tasks = {}
            for t in tasks:
                if t.player_id not in player_tasks:
                    player_tasks[t.player_id] = []
                player_tasks[t.player_id].append(t)
            
            for p_id, p_tasks in player_tasks.items():
                logger.info(f"Refreshing Transfermarkt for player {p_id}...")
                success = self.tm_manager.refresh_player_data(p_id)
                
                # Update task statuses
                for t in p_tasks:
                    # Verify if the match specifically is now in history
                    # We re-check history because refresh_player_data upserts to DB
                    fix = session.get(Fixture, t.fixture_id)
                    history_exists = session.execute(
                        select(MatchHistory).where(
                            and_(
                                MatchHistory.player_id == t.player_id,
                                MatchHistory.date >= fix.date_utc - timedelta(hours=12),
                                MatchHistory.date <= fix.date_utc + timedelta(hours=12)
                            )
                        )
                    ).scalar_one_or_none()
                    
                    if history_exists:
                        t.status = "COMPLETED"
                        logger.info(f"✓ Task completed for {t.player_id} (Fixture {t.fixture_id})")
                    else:
                        t.attempt_count += 1
                        t.last_attempt = now
                        
                        if t.attempt_count >= len(RETRY_INTERVALS):
                            t.status = "FAILED"
                            logger.warning(f"❌ Task failed after max retries for {t.player_id}")
                        else:
                            # Schedule next retry
                            minutes_to_wait = RETRY_INTERVALS[t.attempt_count]
                            t.next_attempt = now + timedelta(minutes=minutes_to_wait)
                            logger.info(f"Match not found yet for {t.player_id}. Retry {t.attempt_count} scheduled at {t.next_attempt}")
                
                session.commit()
                # Sleep briefly between players to be polite to TM
                time.sleep(2)
                
        finally:
            session.close()

    def run_once(self):
        """Single pass of discovery and processing."""
        self.discover_finished_matches()
        self.process_queue()

def main():
    parser = argparse.ArgumentParser(description="Background watcher for recently finished matches.")
    parser.add_argument("--once", action="store_true", help="Run a single discovery/processing cycle and exit.")
    args = parser.parse_args()

    watcher = MatchWatcher()
    logger.info("Match Watcher Daemon started.")

    if args.once:
        watcher.run_once()
        logger.info("Match Watcher single cycle completed.")
        return

    # Simple loop: check every 5 minutes
    try:
        while True:
            watcher.run_once()
            logger.debug("Cycle complete. Sleeping 5 minutes...")
            time.sleep(300)
    except KeyboardInterrupt:
        logger.info("Match Watcher Daemon stopped by user.")

if __name__ == "__main__":
    main()
