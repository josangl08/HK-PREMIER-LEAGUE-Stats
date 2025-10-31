# ABOUTME: Shared utilities for performance callbacks
# ABOUTME: Validation, formatting, and error handling functions

"""Helper functions for performance callback modules."""

import logging
from dash import html
import dash_bootstrap_components as dbc

logger = logging.getLogger(__name__)


def validate_data(data, context=""):
    """
    Validate that data dict is not empty and has expected structure.

    Args:
        data (dict): Data to validate
        context (str): Where validation is happening (for logging)

    Returns:
        bool: True if data is valid, False otherwise
    """
    if not data or not isinstance(data, dict):
        if context:
            logger.warning(f"Invalid data in {context}: {type(data)}")
        return False
    return True


def format_chart_title(analysis_level, entity_name=""):
    """
    Create consistent chart titles based on analysis level.

    Args:
        analysis_level (str): 'league', 'team', or 'player'
        entity_name (str): Team or player name if applicable

    Returns:
        str: Formatted title
    """
    titles = {
        'league': f"League Analysis - {entity_name}".strip(),
        'team': f"Team Analysis: {entity_name}",
        'player': f"Player Profile: {entity_name}"
    }
    return titles.get(analysis_level, "Analysis")


def create_empty_state(message="No data available"):
    """
    Create consistent empty state component.

    Args:
        message (str): Message to display

    Returns:
        html.Div: Empty state container
    """
    return html.Div(
        [
            html.H5(message, className="text-center text-muted mt-4"),
            html.P(
                "Select filters or view different data",
                className="text-center text-muted small"
            )
        ],
        className="p-5"
    )


def create_error_alert(error_message, title="Error"):
    """
    Create consistent error alert component.

    Args:
        error_message (str): Error message to display
        title (str): Alert title

    Returns:
        dbc.Alert: Error alert component
    """
    return dbc.Alert(
        [
            html.H4(title, className="alert-heading"),
            html.P(str(error_message)),
        ],
        color="danger",
        className="mt-3"
    )


def create_loading_skeleton(height=400):
    """
    Create skeleton screen for loading states.

    Args:
        height (int): Height of skeleton

    Returns:
        html.Div: Skeleton loader component
    """
    return html.Div(
        [
            html.Div(
                className="placeholder-glow",
                children=[
                    html.Div(
                        className="placeholder col-12",
                        style={"height": f"{height}px"}
                    )
                ]
            )
        ],
        className="p-3"
    )
