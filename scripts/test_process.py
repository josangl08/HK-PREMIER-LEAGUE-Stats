import sys
import os
import logging
from datetime import datetime, timezone, timedelta
sys.path.append(os.getcwd())

from scripts.background_match_watcher import MatchWatcher
from utils.db_engine import SessionFactory
from data.transfermarkt_data_manager import TransfermarktDataManager

logging.basicConfig(level=logging.INFO)

def test_process():
    watcher = MatchWatcher()
    # Modify next_attempt to force processing now
    session = SessionFactory()
    from models.db_models import MatchUpdateQueue
    from sqlalchemy import update
    session.execute(update(MatchUpdateQueue).values(next_attempt=datetime.now(timezone.utc) - timedelta(minutes=1)))
    session.commit()
    session.close()

    print("Processing queue...")
    watcher.process_queue()
    print("Process complete.")

if __name__ == "__main__":
    test_process()
