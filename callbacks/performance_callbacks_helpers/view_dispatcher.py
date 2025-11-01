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
import logging

# Import view layouts
from layouts.performance_views import league_view, team_view, player_view

logger = logging.getLogger(__name__)


@callback(
    [
        # Visibility controls (display: block/none)
        Output('league-view-container', 'style'),
        Output('team-view-container', 'style'),
        Output('player-view-container', 'style'),

        # Content rendering
        Output('league-view-container', 'children'),
        Output('team-view-container', 'children'),
        Output('player-view-container', 'children'),
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
            - analysis_level: 'league' | 'team' | 'player'
            - season, team, player, position_filter, age_range

    Returns:
        tuple: (
            league_style, team_style, player_style,
            league_content, team_content, player_content
        )

    Design Notes:
        - Inactive views get [] (empty) to save rendering time
        - Only one view has display: block, others display: none
        - No duplicate outputs (each container controlled once)
        - analysis_level determines which view to show

    Performance:
        - Only active view re-renders on filter changes
        - Inactive views callbacks don't execute (prevent_initial_call)
        - Minimal DOM manipulation (visibility toggle only)
    """
    # Extract analysis level from filters
    analysis_level = filters.get('analysis_level') if filters else None

    logger.info(f"View dispatcher triggered - analysis_level: {analysis_level}")

    # === VISIBILITY STYLES ===
    # Only one view visible at a time
    league_style = (
        {'display': 'block'}
        if analysis_level == 'league'
        else {'display': 'none'}
    )
    team_style = (
        {'display': 'block'}
        if analysis_level == 'team'
        else {'display': 'none'}
    )
    player_style = (
        {'display': 'block'}
        if analysis_level == 'player'
        else {'display': 'none'}
    )

    # === CONTENT RENDERING ===
    # Only render active view, leave others empty

    if analysis_level == 'league':
        # LEAGUE VIEW ACTIVE
        logger.info("-> Rendering league view layout")
        league_content = league_view.create_league_view_layout()
        team_content = []  # Empty (not visible)
        player_content = []  # Empty (not visible)

    elif analysis_level == 'team':
        # TEAM VIEW ACTIVE
        logger.info("-> Rendering team view layout")
        league_content = []
        team_content = team_view.create_team_view_layout()
        player_content = []

    elif analysis_level == 'player':
        # PLAYER VIEW ACTIVE
        logger.info("-> Rendering player view layout")
        league_content = []
        team_content = []
        player_content = player_view.create_player_view_layout()

    else:
        # NO LEVEL SELECTED (Initial state)
        logger.info("-> No analysis level selected (initial state)")
        league_content = html.Div([
            html.H4(
                "Selecciona filtros para comenzar",
                className='text-center text-muted p-5'
            )
        ])
        team_content = []
        player_content = []

    return (
        league_style,
        team_style,
        player_style,
        league_content,
        team_content,
        player_content
    )


# ===== EXPORT FOR CLEAN IMPORTS =====
__all__ = ['dispatch_view_rendering']
