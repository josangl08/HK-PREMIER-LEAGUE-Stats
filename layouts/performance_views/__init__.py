# ABOUTME: Performance views module exports
# ABOUTME: Clean imports for league, team, player view modules

"""
Performance Views Module.

This module contains modular view layouts for the performance dashboard.
Each view (league, team, player) has its own layout structure and chart IDs.

Exports:
    - league_view: League-level analysis layout
    - team_view: Team-level analysis layout
    - player_view: Player-level analysis layout
"""

from . import league_view
from . import team_view
from . import player_view

__all__ = [
    'league_view',
    'team_view',
    'player_view',
]
