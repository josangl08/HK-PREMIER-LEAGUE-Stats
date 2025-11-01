# ABOUTME: Skeleton screen components for better loading UX
# ABOUTME: Visual placeholders that mimic content structure during loading

"""
Skeleton Screen Components for HK Premier League Dashboard.

Provides skeleton loaders that match the structure of actual content,
creating a perception of faster loading times and better UX.
"""

from dash import html
import dash_bootstrap_components as dbc
from typing import Optional


def create_skeleton_pulse_css():
    """
    Create CSS for skeleton pulse animation.

    Returns:
        html.Style: CSS for pulse animation
    """
    css = """
    <style>
        @keyframes skeleton-pulse {
            0% { opacity: 1; }
            50% { opacity: 0.4; }
            100% { opacity: 1; }
        }

        .skeleton {
            animation: skeleton-pulse 1.5s ease-in-out infinite;
            background: linear-gradient(
                90deg,
                rgba(255, 255, 255, 0.05) 0%,
                rgba(255, 255, 255, 0.1) 50%,
                rgba(255, 255, 255, 0.05) 100%
            );
            border-radius: 4px;
        }

        .skeleton-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 1rem;
        }

        .skeleton-text {
            height: 16px;
            margin-bottom: 8px;
        }

        .skeleton-title {
            height: 24px;
            width: 60%;
            margin-bottom: 16px;
        }

        .skeleton-circle {
            border-radius: 50%;
        }

        .skeleton-chart {
            height: 300px;
            border-radius: 8px;
        }
    </style>
    """
    return html.Style(html.Div(dangerously_allow_html=True, children=css))


def create_skeleton_kpi_card():
    """
    Create a skeleton loader for KPI card.

    Returns:
        dbc.Col: Skeleton KPI card
    """
    return dbc.Col([
        dbc.Card([
            dbc.CardBody([
                # Icon placeholder
                html.Div(
                    className="skeleton skeleton-circle mb-2",
                    style={"width": "40px", "height": "40px"}
                ),
                # Value placeholder
                html.Div(
                    className="skeleton",
                    style={"width": "80px", "height": "32px", "marginBottom": "8px"}
                ),
                # Label placeholder
                html.Div(
                    className="skeleton",
                    style={"width": "120px", "height": "16px"}
                )
            ])
        ], className="skeleton-card metric-card")
    ], lg=3, md=6, sm=6, xs=12)


def create_skeleton_kpi_row(num_cards: int = 4):
    """
    Create a skeleton loader for KPI row.

    Args:
        num_cards: Number of KPI cards to show

    Returns:
        dbc.Row: Skeleton KPI row
    """
    cards = [create_skeleton_kpi_card() for _ in range(num_cards)]
    return dbc.Row(cards, className="mb-4")


def create_skeleton_chart(
    title: str = "Loading Chart...",
    height: int = 300,
    full_width: bool = False
):
    """
    Create a skeleton loader for chart.

    Args:
        title: Chart title
        height: Chart height in pixels
        full_width: Use full width (12 cols) or half width (6 cols)

    Returns:
        dbc.Col: Skeleton chart container
    """
    chart_md = 12 if full_width else 6

    return dbc.Col([
        dbc.Card([
            dbc.CardHeader(
                html.Div(
                    className="skeleton",
                    style={"width": "150px", "height": "20px"}
                )
            ),
            dbc.CardBody([
                html.Div(
                    className="skeleton skeleton-chart",
                    style={"height": f"{height}px"}
                )
            ])
        ], className="skeleton-card")
    ], md=chart_md, className="mb-4")


def create_skeleton_table(
    num_rows: int = 5,
    num_cols: int = 5
):
    """
    Create a skeleton loader for table.

    Args:
        num_rows: Number of skeleton rows
        num_cols: Number of columns

    Returns:
        html.Div: Skeleton table
    """
    # Header row
    header = html.Tr([
        html.Th(
            html.Div(
                className="skeleton",
                style={"width": "100%", "height": "16px"}
            )
        ) for _ in range(num_cols)
    ])

    # Data rows
    rows = []
    for _ in range(num_rows):
        row = html.Tr([
            html.Td(
                html.Div(
                    className="skeleton",
                    style={"width": "90%", "height": "14px"}
                )
            ) for _ in range(num_cols)
        ])
        rows.append(row)

    return dbc.Table([
        html.Thead(header),
        html.Tbody(rows)
    ], className="skeleton-card", bordered=True, dark=True, striped=True)


def create_skeleton_league_view():
    """
    Create skeleton loader for league view.

    Matches the structure of the actual league view with
    KPIs and 5 charts.

    Returns:
        html.Div: Skeleton league view
    """
    return html.Div([
        # Title skeleton
        html.Div(
            className="skeleton skeleton-title mb-4",
            style={"width": "300px"}
        ),

        # KPIs skeleton
        create_skeleton_kpi_row(4),

        # Charts skeleton (1 full width + 2x2 half width)
        dbc.Row([
            create_skeleton_chart(
                title="League Overview",
                height=350,
                full_width=True
            )
        ], className="mb-4"),

        dbc.Row([
            create_skeleton_chart(title="Position Analysis", height=300),
            create_skeleton_chart(title="Age Distribution", height=300)
        ], className="mb-4"),

        dbc.Row([
            create_skeleton_chart(title="Tactical Heatmap", height=300),
            create_skeleton_chart(title="Timeline", height=300)
        ], className="mb-4")
    ])


def create_skeleton_team_view():
    """
    Create skeleton loader for team view.

    Matches the structure of the team view.

    Returns:
        html.Div: Skeleton team view
    """
    return html.Div([
        # Title skeleton
        html.Div(
            className="skeleton skeleton-title mb-4",
            style={"width": "400px"}
        ),

        # KPIs skeleton
        create_skeleton_kpi_row(4),

        # Charts skeleton (asymmetric grid)
        dbc.Row([
            create_skeleton_chart(title="Team Radar", height=300),
            dbc.Col([
                create_skeleton_kpi_card(),
                html.Div(style={"height": "16px"}),  # Spacer
                create_skeleton_kpi_card()
            ], md=4)
        ], className="mb-4"),

        dbc.Row([
            create_skeleton_chart(title="Squad Depth", height=300),
            create_skeleton_chart(title="Player Minutes", height=300)
        ], className="mb-4"),

        dbc.Row([
            create_skeleton_chart(
                title="Tactical Fingerprint",
                height=300,
                full_width=True
            )
        ], className="mb-4")
    ])


def create_skeleton_player_view():
    """
    Create skeleton loader for player view.

    Matches the structure of the player view.

    Returns:
        html.Div: Skeleton player view
    """
    return html.Div([
        # Title skeleton
        html.Div(
            className="skeleton skeleton-title mb-4",
            style={"width": "350px"}
        ),

        # KPIs skeleton
        create_skeleton_kpi_row(4),

        # Charts skeleton (symmetric 6-6 grid)
        dbc.Row([
            create_skeleton_chart(title="Player Radar", height=300),
            create_skeleton_chart(title="Percentile Rankings", height=300)
        ], className="mb-4"),

        dbc.Row([
            create_skeleton_chart(title="Efficiency Scatter", height=300),
            create_skeleton_chart(title="Performance Heatmap", height=300)
        ], className="mb-4"),

        dbc.Row([
            create_skeleton_chart(
                title="Evolution Timeline",
                height=300,
                full_width=True
            )
        ], className="mb-4")
    ])


def get_skeleton_for_view(view_level: str):
    """
    Get appropriate skeleton loader based on view level.

    Args:
        view_level: 'league', 'team', or 'player'

    Returns:
        html.Div: Skeleton loader for the specified view
    """
    skeletons = {
        'league': create_skeleton_league_view,
        'team': create_skeleton_team_view,
        'player': create_skeleton_player_view
    }

    skeleton_func = skeletons.get(view_level, create_skeleton_league_view)
    return skeleton_func()


def create_loading_overlay(
    message: str = "Loading data...",
    show_spinner: bool = True
):
    """
    Create a loading overlay with optional spinner.

    Args:
        message: Loading message
        show_spinner: Show spinner animation

    Returns:
        html.Div: Loading overlay
    """
    children = []

    if show_spinner:
        children.append(
            dbc.Spinner(
                size="lg",
                color="danger",  # HKFA red
                spinner_style={"width": "3rem", "height": "3rem"}
            )
        )

    children.append(
        html.H5(message, className="mt-3 text-secondary")
    )

    return html.Div(
        html.Div(
            children,
            className="text-center"
        ),
        className="loading-overlay",
        style={
            'position': 'absolute',
            'top': 0,
            'left': 0,
            'right': 0,
            'bottom': 0,
            'backgroundColor': 'rgba(24, 24, 26, 0.95)',
            'display': 'flex',
            'alignItems': 'center',
            'justifyContent': 'center',
            'zIndex': 1000,
            'borderRadius': '8px'
        }
    )
