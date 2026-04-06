import sys
import os
from datetime import datetime, timezone, timedelta
sys.path.append(os.getcwd())

from scripts.background_match_watcher import MatchWatcher
from utils.db_engine import SessionFactory
from models.db_models import Fixture

def force_check():
    watcher = MatchWatcher()
    print("Running discovery pass...")
    watcher.discover_finished_matches()
    print("Discovery pass complete.")
    
    session = SessionFactory()
    from models.db_models import MatchUpdateQueue
    from sqlalchemy import select
    tasks = session.execute(select(MatchUpdateQueue)).scalars().all()
    print(f"Total tasks in queue: {len(tasks)}")
    for t in tasks:
        print(f"Task: Fixture {t.fixture_id}, Player {t.player_id}, Status {t.status}")
    session.close()

if __name__ == "__main__":
    force_check()
