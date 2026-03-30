from utils.app_context import get_hong_kong_data_manager
import logging
import os

# Mocking app context for script
from data.hong_kong_data_manager import HongKongDataManager
dm = HongKongDataManager(auto_load=True)

teams = dm.get_available_teams()
print(f"Available teams: {teams}")
players = dm.get_available_players()
print(f"Total players: {len(players)}")
