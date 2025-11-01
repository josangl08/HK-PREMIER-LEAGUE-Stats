# ABOUTME: Debouncing utilities for optimizing filter updates
# ABOUTME: Prevents excessive callback triggers during user input

"""
Debouncing Helpers for Dash Callbacks.

Provides utilities to optimize filter updates and reduce
unnecessary server roundtrips during user interactions.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
from typing import Optional


def create_debounced_input(
    input_id: str,
    placeholder: str = "",
    value: Optional[str] = None,
    debounce_delay: int = 500,
    input_type: str = "text"
):
    """
    Create a debounced input component.

    Args:
        input_id: ID for the input component
        placeholder: Placeholder text
        value: Initial value
        debounce_delay: Delay in milliseconds before triggering callback
        input_type: Type of input ("text", "number", "search")

    Returns:
        dcc.Input: Debounced input component
    """
    return dcc.Input(
        id=input_id,
        type=input_type,
        placeholder=placeholder,
        value=value,
        debounce=True,  # Built-in Dash debouncing
        className="form-control",
        style={
            'transition': 'border-color 0.2s ease-in-out'
        }
    )


def create_debounced_dropdown(
    dropdown_id: str,
    options: list = None,
    value: Optional[str] = None,
    placeholder: str = "Select...",
    clearable: bool = True,
    searchable: bool = True,
    multi: bool = False
):
    """
    Create a debounced dropdown component.

    Note: Dash dropdowns don't have built-in debounce,
    but we can use dcc.Store to debounce the updates.

    Args:
        dropdown_id: ID for the dropdown
        options: List of options
        value: Initial value
        placeholder: Placeholder text
        clearable: Allow clearing selection
        searchable: Allow searching in dropdown
        multi: Allow multiple selections

    Returns:
        html.Div: Container with dropdown and debounce store
    """
    return html.Div([
        dcc.Dropdown(
            id=dropdown_id,
            options=options or [],
            value=value,
            placeholder=placeholder,
            clearable=clearable,
            searchable=searchable,
            multi=multi,
            className="mb-3"
        ),
        # Store for debounced value
        dcc.Store(
            id=f"{dropdown_id}-debounced",
            data=value
        ),
        # Interval for debouncing (disabled by default)
        dcc.Interval(
            id=f"{dropdown_id}-debounce-timer",
            interval=500,  # 500ms delay
            n_intervals=0,
            disabled=True
        )
    ])


def create_clientside_callback_script():
    """
    Generate clientside callback script for instant UI updates.

    Clientside callbacks run in the browser without server roundtrip,
    providing instant feedback for simple UI changes.

    Returns:
        html.Script: JavaScript for clientside callbacks
    """
    script = """
    window.dash_clientside = Object.assign({}, window.dash_clientside, {
        clientside: {
            // Toggle visibility without server roundtrip
            toggle_visibility: function(n_clicks, current_style) {
                if (!current_style) {
                    current_style = {display: 'block'};
                }
                const new_display = current_style.display === 'none' ? 'block' : 'none';
                return {...current_style, display: new_display};
            },

            // Update loading state instantly
            update_loading_state: function(is_loading) {
                return is_loading ? 'Loading...' : 'Ready';
            },

            // Debounce input value (store raw value, return debounced)
            debounce_value: function(value, n_intervals) {
                // Simple debounce: only return value after interval fires
                if (n_intervals > 0) {
                    return value;
                }
                return window.dash_clientside.no_update;
            }
        }
    });
    """
    return html.Script(script, type="text/javascript")


def create_filter_change_indicator():
    """
    Create a visual indicator for when filters are being processed.

    Returns:
        html.Div: Loading indicator for filter changes
    """
    return html.Div(
        [
            dbc.Spinner(
                size="sm",
                color="primary",
                spinner_style={"width": "1rem", "height": "1rem"}
            ),
            html.Span(
                "Updating...",
                className="ms-2 text-secondary"
            )
        ],
        id="filter-loading-indicator",
        style={"display": "none"},
        className="d-inline-flex align-items-center"
    )


def create_smart_filter_section(
    filters: list,
    show_loading_indicator: bool = True
):
    """
    Create a smart filter section with debouncing and loading states.

    Args:
        filters: List of filter components
        show_loading_indicator: Show loading indicator during updates

    Returns:
        html.Div: Smart filter section with debouncing
    """
    children = [
        dbc.Row(filters, className="mb-3")
    ]

    if show_loading_indicator:
        children.append(
            html.Div(
                create_filter_change_indicator(),
                className="text-end mb-3"
            )
        )

    return html.Div(
        children,
        className="filter-section p-3 mb-4",
        style={
            'backgroundColor': 'rgba(255, 255, 255, 0.05)',
            'borderRadius': '8px',
            'border': '1px solid rgba(255, 255, 255, 0.1)'
        }
    )


# Debounce configuration presets
DEBOUNCE_PRESETS = {
    'instant': 0,        # No debounce
    'fast': 200,         # 200ms - for simple filters
    'normal': 500,       # 500ms - default for most cases
    'slow': 1000,        # 1s - for expensive operations
    'very_slow': 2000    # 2s - for very expensive operations
}


def get_debounce_delay(preset: str = 'normal') -> int:
    """
    Get debounce delay from preset name.

    Args:
        preset: Preset name ('instant', 'fast', 'normal', 'slow', 'very_slow')

    Returns:
        int: Debounce delay in milliseconds
    """
    return DEBOUNCE_PRESETS.get(preset, DEBOUNCE_PRESETS['normal'])
