# ABOUTME: Test script for BeSoccer identity resolution.
# ABOUTME: Verifies if IdentityResolver can find BeSoccer IDs and ratings after the update.

import logging
import sys
import os

# Add root to path
sys.path.append(os.getcwd())

from utils.player_index import IdentityResolver
from utils.db_engine import SessionFactory
from models.db_models import Player
from data.extractors.besoccer_extractor import BeSoccerExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_resolution():
    resolver = IdentityResolver()
    extractor = BeSoccerExtractor()
    session = SessionFactory()
    
    try:
        # 1. Test resolution for Manuel Bleda (known slug from user)
        # We assume he might be in the DB with a slug or name
        bleda = session.query(Player).filter(Player.name.like("%Manuel Bleda%")).first()
        if bleda:
            logger.info(f"Testing resolution for: {bleda.name} (ID: {bleda.id})")
            results = resolver.resolve_external_ids(bleda.id, force=True)
            logger.info(f"Resolution results for {bleda.name}: {results}")
            
            if 'besoccer_id' in results:
                ratings = extractor.get_player_ratings(results['besoccer_id'])
                logger.info(f"Ratings found for {bleda.name}: {len(ratings)} matches")
                if ratings:
                    sample_date = list(ratings.keys())[0]
                    logger.info(f"Sample rating: {sample_date} -> {ratings[sample_date]}")

        # 2. Test for other random players
        players = session.query(Player).limit(3).all()
        for player in players:
            logger.info(f"Testing resolution for: {player.name} (ID: {player.id})")
            results = resolver.resolve_external_ids(player.id, force=True)
            logger.info(f"Results for {player.name}: {results}")
            
    finally:
        session.close()

if __name__ == "__main__":
    test_resolution()
