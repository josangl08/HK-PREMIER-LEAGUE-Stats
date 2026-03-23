# ABOUTME: Skeleton screen components for better loading UX
# ABOUTME: Visual placeholders that mimic content structure during loading

"""
Skeleton Screen Components for HK Premier League Dashboard.

Provides skeleton loaders that match the structure of actual content,
creating a perception of faster loading times and better UX.
Classes are defined in assets/style.css.
"""

from dash import html
import dash_bootstrap_components as dbc


def create_skeleton_kpi_card():
    """
    Create a skeleton loader for KPI card.
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
    ], className="skeleton-card", bordered=True, striped=True)


def create_skeleton_timeline(num_items: int = 6):
    """
    Create a skeleton loader for the Player Portal Timeline.
    """
    items = []
    for _ in range(num_items):
        items.append(
            html.Div([
                html.Div(className="skeleton skeleton-circle me-3", 
                         style={"width": "24px", "height": "24px", "flexShrink": 0}),
                html.Div([
                    html.Div(className="skeleton", style={"width": "120px", "height": "16px", "marginBottom": "4px"}),
                    html.Div(className="skeleton", style={"width": "80px", "height": "12px"}),
                ], className="flex-grow-1")
            ], className="d-flex align-items-center mb-4 px-2")
        )
    return html.Div(items)


def create_skeleton_stage():
    """
    Create a skeleton loader for the Stage area.
    """
    return dbc.Card([
        dbc.CardBody([
            html.Div(className="skeleton skeleton-title mb-3", style={"width": "40%"}),
            html.Div(className="skeleton mb-2", style={"width": "100%", "height": "14px"}),
            html.Div(className="skeleton mb-2", style={"width": "95%", "height": "14px"}),
            html.Div(className="skeleton mb-4", style={"width": "80%", "height": "14px"}),
            dbc.Row([
                dbc.Col(html.Div(className="skeleton", style={"height": "200px"}), md=6),
                dbc.Col(html.Div(className="skeleton", style={"height": "200px"}), md=6),
            ])
        ])
    ], className="border-0 shadow-sm")


def get_skeleton_for_view(view_level: str):
    """
    Get appropriate skeleton loader based on view level.
    """
    if view_level == 'league':
        return html.Div([
            html.Div(className="skeleton skeleton-title mb-4", style={"width": "300px"}),
            create_skeleton_kpi_row(4),
            create_skeleton_chart(full_width=True),
            dbc.Row([create_skeleton_chart(), create_skeleton_chart()])
        ])
    elif view_level == 'team':
        return html.Div([
            html.Div(className="skeleton skeleton-title mb-4", style={"width": "400px"}),
            create_skeleton_kpi_row(4),
            dbc.Row([create_skeleton_chart(), create_skeleton_chart()])
        ])
    else:  # player
        return html.Div([
            html.Div(className="skeleton skeleton-title mb-4", style={"width": "350px"}),
            create_skeleton_kpi_row(4),
            dbc.Row([create_skeleton_chart(), create_skeleton_chart()]),
            create_skeleton_chart(full_width=True)
        ])


def create_loading_overlay(message: str = "Loading data..."):
    """
    Create a loading overlay.
    """
    return html.Div(
        html.Div([
            dbc.Spinner(size="lg", color="danger", spinner_style={"width": "3rem", "height": "3rem"}),
            html.H5(message, className="mt-3 text-secondary")
        ], className="text-center"),
        className="loading-overlay",
        style={
            'position': 'absolute', 'top': 0, 'left': 0, 'right': 0, 'bottom': 0,
            'backgroundColor': 'rgba(24, 24, 26, 0.95)', 'display': 'flex',
            'alignItems': 'center', 'justifyContent': 'center', 'zIndex': 1000,
            'borderRadius': '8px'
        }
    )
