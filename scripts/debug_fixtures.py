from data.managers.fixture_manager import get_fixture_manager
import logging

logging.basicConfig(level=logging.INFO)
fm = get_fixture_manager()
fixtures = fm.get_fixtures(season="2025-26")
print(f"Total fixtures for 2025-26: {len(fixtures)}")
if fixtures:
    print(f"First fixture keys: {list(fixtures[0].keys())}")
    print(f"First fixture home team: {fixtures[0]['home_team']}")
