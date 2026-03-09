# ABOUTME: Callback for the Pre-match Card — resolves the logged-in player's next fixture.
# ABOUTME: Reads player team from user profile, delegates to FixtureManager, renders card.

import logging
from dash import Input, Output, callback, no_update
from flask_login import current_user

from utils.app_context import get_hong_kong_data_manager

logger = logging.getLogger(__name__)


@callback(
    Output('prematch-card-container', 'children'),
    Input('url', 'pathname'),
    prevent_initial_call=False,
)
def render_prematch_card(pathname):
    """
    Resolves the logged-in player's team and renders the Pre-match Card.
    Runs on every page navigation; renders only if user is authenticated as a player.
    """
    from layouts.prematch_card import create_prematch_card

    if not current_user or not current_user.is_authenticated:
        return create_prematch_card(None)

    if current_user.role != 'player':
        return create_prematch_card(None)

    player_profile = getattr(current_user, 'player_profile', None) or {}
    # player_profile is stored on the User object but loaded from users.json at login
    # Fall back to reading from the auth repository if not available on user object
    if not player_profile:
        try:
            from utils.auth import AuthRepository
            user_data = AuthRepository._load_all_users().get(current_user.username, {})
            player_profile = user_data.get('player_profile', {})
        except Exception:
            pass

    team = (player_profile or {}).get('team')
    profile_season = (player_profile or {}).get('season')

    if not team:
        logger.debug(f"No team found for player '{current_user.username}' — skipping fixture lookup.")
        return create_prematch_card(None)

    try:
        dm = get_hong_kong_data_manager()
        
        # CRITICAL: Verify the player is active in the CURRENT league season
        # A player shouldn't see fixtures if their profile association is for an old season
        if profile_season != dm.current_season:
            logger.info(
                f"Player '{current_user.username}' associated with {team} in {profile_season}, "
                f"but system is in {dm.current_season}. Skipping fixture card."
            )
            return create_prematch_card(None)

        fixture = dm.get_next_fixture(team)
    except Exception as e:
        logger.warning(f"Fixture lookup failed for team '{team}': {e}")
        fixture = None

    return create_prematch_card(fixture)
