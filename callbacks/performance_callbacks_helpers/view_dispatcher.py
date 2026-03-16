# ABOUTME: View dispatcher callback - master controller for view switching
# ABOUTME: Controls visibility and rendering of league/team/player views

"""
View Dispatcher Module.

This module contains the master callback that controls:
1. Visibility of view containers (league/team/player)
2. Dynamic rendering of view-specific layouts
3. Efficient rendering (only active view is populated)

Architecture:
    - Single callback controls all 3 views
    - Only one view visible at a time (display: block/none)
    - Only active view is rendered (others remain empty [])
    - No race conditions (single source of truth)

Design Pattern:
    - Input: current-filters-store (contains analysis_level)
    - Outputs: 6 outputs (3 styles + 3 children for each container)
    - Logic: Switch based on analysis_level
    - Optimization: Empty arrays for inactive views (saves CPU)
"""

from dash import Input, Output, callback, html
from flask_login import current_user
import logging

# Import view layouts
from layouts.performance_views import league_view, team_view, player_view
from layouts.performance_views import agent_view

logger = logging.getLogger(__name__)


@callback(
    [
        # Visibility controls (display: block/none)
        Output('league-view-container', 'style'),
        Output('team-view-container', 'style'),
        Output('player-view-container', 'style'),
        Output('agent-view-container', 'style'),

        # Content rendering
        Output('league-view-container', 'children'),
        Output('team-view-container', 'children'),
        Output('player-view-container', 'children'),
        Output('agent-view-container', 'children'),
    ],
    [
        Input('current-filters-store', 'data'),
    ],
    prevent_initial_call=False
)
def dispatch_view_rendering(filters):
    """
    Master callback for view switching and rendering.

    Controls which view is visible and populates it with the appropriate
    layout. Only the active view is rendered to optimize performance.

    Args:
        filters (dict): Current filter state from store
            - analysis_level: 'league' | 'team' | 'player' | 'agent'
            - season, team, player, position_filter, age_range

    Returns:
        tuple: (
            league_style, team_style, player_style, agent_style,
            league_content, team_content, player_content, agent_content
        )
    """
    # Extract analysis level from filters
    analysis_level = filters.get('analysis_level') if filters else None

    # Auto-detect agent role: show agent portal when user is an agent
    # and no specific analysis level has been chosen
    if analysis_level is None and current_user and current_user.is_authenticated:
        if getattr(current_user, 'role', None) == 'agent':
            analysis_level = 'agent'

    logger.info(f"View dispatcher triggered - analysis_level: {analysis_level}")

    _show = {'display': 'block'}
    _hide = {'display': 'none'}

    league_style = _show if analysis_level == 'league' else _hide
    team_style = _show if analysis_level == 'team' else _hide
    player_style = _show if analysis_level == 'player' else _hide
    agent_style = _show if analysis_level == 'agent' else _hide

    # === CONTENT RENDERING — only active view is populated ===

    if analysis_level == 'league':
        logger.info("-> Rendering league view layout")
        league_content = league_view.create_league_view_layout()
        team_content = player_content = agent_content = []

    elif analysis_level == 'team':
        logger.info("-> Rendering team view layout")
        team_content = team_view.create_team_view_layout()
        league_content = player_content = agent_content = []

    elif analysis_level == 'player':
        logger.info("-> Rendering player view layout")
        player_content = player_view.create_player_view_layout()
        league_content = team_content = agent_content = []

    elif analysis_level == 'agent':
        logger.info("-> Rendering agent portal layout")
        agent_content = agent_view.create_agent_view_layout()
        league_content = team_content = player_content = []

    else:
        # NO LEVEL SELECTED (Initial state)
        logger.info("-> No analysis level selected (initial state)")
        league_content = html.Div([
            html.H4(
                "Selecciona filtros para comenzar",
                className='text-center text-muted p-5'
            )
        ])
        team_content = player_content = agent_content = []

    return (
        league_style, team_style, player_style, agent_style,
        league_content, team_content, player_content, agent_content,
    )


# ===== EXPORT FOR CLEAN IMPORTS =====
__all__ = ['dispatch_view_rendering']
