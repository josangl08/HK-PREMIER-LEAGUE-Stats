# ABOUTME: Test script for BeSoccer extraction with direct ID.
# ABOUTME: Verifies if BeSoccerExtractor can fetch ratings when the ID is known.

import logging
import sys
import os

# Add root to path
sys.path.append(os.getcwd())

from data.extractors.besoccer_extractor import BeSoccerExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_extraction():
    extractor = BeSoccerExtractor()
    
    # Use the direct ID provided by the user
    besoccer_id = "manuel-bleda-268319"
    logger.info(f"Testing extraction for: {besoccer_id}")
    
    ratings = extractor.get_player_ratings(besoccer_id)
    logger.info(f"Ratings found: {len(ratings)} matches")
    
    for date, rating in list(ratings.items())[:5]:
        logger.info(f"  {date} -> {rating}")

if __name__ == "__main__":
    test_extraction()
