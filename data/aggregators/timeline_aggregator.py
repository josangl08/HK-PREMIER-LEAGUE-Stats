# ABOUTME: Aggregator for player timeline milestones.
# ABOUTME: Combines historical season data, fixtures, and Transfermarkt match history per season.

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from data.hong_kong_data_manager import HongKongDataManager

from data.managers.fixture_manager import get_fixture_manager
from utils.player_index import get_player_index

logger = logging.getLogger(__name__)

class TimelineAggregator:
    def __init__(self, data_manager: Optional['HongKongDataManager'] = None):
        if data_manager is None:
            from data.hong_kong_data_manager import HongKongDataManager
            self.data_manager = HongKongDataManager()
        else:
            self.data_manager = data_manager
        
        self.fixture_manager = get_fixture_manager()
        self.player_index = get_player_index()

    def get_player_timeline(self, player_id: str) -> List[Dict[str, Any]]:
        """
        Returns a chronological list of milestones for a player.
        Milestones include:
        - Upcoming fixtures (pre-match)
        - Recent matches (post-match)
        - Career summaries (career)
        """
        timeline = []
        
        # 1. Resolve player info
        player_info = self.player_index.get_player_info(player_id)
        if not player_info:
            logger.warning(f"Player ID {player_id} not found in index.")
            return []

        player_name = player_info.get("canonical_name")
        
        # 2. Find player's current team
        current_team = None
        player_stats = self.data_manager.get_player_overview(player_name)
        if player_stats and 'error' not in player_stats:
            current_team = player_stats.get('basic_info', {}).get('team')
        
        now_utc = datetime.now(timezone.utc)

        # 3. Add Next Fixture (pre-match)
        if current_team:
            next_fix = self.fixture_manager.get_next_fixture(current_team)
            if next_fix:
                opponent = next_fix.get("away_team") if next_fix.get("home_team") == current_team else next_fix.get("home_team")
                timeline.append({
                    "type": "pre-match",
                    "label": f"Próximo: vs {opponent}",
                    "icon": "calendar-plus",
                    "date": next_fix.get("kickoff_utc"),
                    "payload": {
                        "opponent": opponent,
                        "date": next_fix.get("kickoff_utc"),
                        "kickoff_display": next_fix.get("kickoff_display"),
                        "stadium": next_fix.get("stadium"),
                        "home_team": next_fix.get("home_team"),
                        "away_team": next_fix.get("away_team"),
                        "home_logo": next_fix.get("home_logo_url"),
                        "away_logo": next_fix.get("away_logo_url"),
                        "streaming_url": next_fix.get("streaming_url"),
                        "competition": next_fix.get("competition")
                    }
                })

        # 4. Add Past Matches (post-match)
        if current_team:
            all_fixtures = self.fixture_manager.get_fixtures()
            past_team_matches = [
                f for f in all_fixtures
                if (f.get("home_team") == current_team or f.get("away_team") == current_team)
                and f.get("kickoff_utc") < now_utc
            ]
            # Sort by date descending
            past_team_matches.sort(key=lambda x: x.get("kickoff_utc"), reverse=True)
            
            for match in past_team_matches[:5]: # Limit to last 5
                opponent = match.get("away_team") if match.get("home_team") == current_team else match.get("home_team")
                timeline.append({
                    "type": "post-match",
                    "label": f"Resultado: vs {opponent}",
                    "icon": "chart-bar",
                    "date": match.get("kickoff_utc"),
                    "payload": {
                        "opponent": opponent,
                        "date": match.get("kickoff_utc"),
                        "kickoff_display": match.get("kickoff_display"),
                        "home_team": match.get("home_team"),
                        "away_team": match.get("away_team"),
                        "player_stats": player_stats,
                        "match_id": match.get("uid")
                    }
                })

        # 5. Add Career Milestones (career) with historical match sub-milestones
        seasons = player_info.get("seasons", [])
        for season in seasons:
            try:
                # "2024-25" → May 2025
                year_end = int(season.split('-')[0]) + 1
                season_date = datetime(year_end, 5, 30, tzinfo=timezone.utc)
            except Exception:
                season_date = now_utc - timedelta(days=365)

            # Derive Transfermarkt saison_id (start year) and fetch match history
            matches: List[Dict[str, Any]] = []
            try:
                season_start_year = season.split('-')[0]
                from data.extractors.transfermarkt_extractor import TransfermarktExtractor
                extractor = TransfermarktExtractor()
                matches = extractor.get_match_history(player_id, season_start_year)
            except Exception as match_exc:
                logger.debug(f"Match history unavailable for {player_id}/{season}: {match_exc}")

            timeline.append({
                "type": "career",
                "label": f"Temporada {season}",
                "icon": "trophy",
                "date": season_date,
                "payload": {
                    "season": season,
                    "player_id": player_id,
                    "player_name": player_name,
                    "matches": matches,
                }
            })

        # Final sort: most recent first
        timeline.sort(key=lambda x: x["date"], reverse=True)
        
        return timeline
