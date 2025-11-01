# ABOUTME: Team view layout module for performance dashboard
# ABOUTME: Defines responsive grid structure for 5 team-level charts

"""
Team View Layout Module.

This module creates the layout structure for team-level analysis.
Contains 5 chart containers organized in a responsive Bootstrap grid.

Chart Structure (FINAL_PLAN.md specification):
    1. Radar Chart: Team vs league average (featured)
    2. Stacked Bar: Squad depth by position
    3. Treemap: Player minutes distribution
    4. Heatmap: Tactical fingerprint matrix
    5. Line Chart: Form trends over time

Grid Design (UX-Optimized):
    Row 1: Chart 1 (8 cols) + Chart 2 (4 cols) - Radar featured
    Row 2: Chart 3 (7 cols) + Chart 4 (5 cols) - Minutes + Tactical
    Row 3: Chart 5 (12 cols) - Form timeline full width

    Mobile (< 768px): All charts stack vertically (12 cols each)
    Tablet (768-991px): Adjusted proportions for better fit
    Desktop (>= 992px): Full asymmetric grid for visual hierarchy

Dependencies:
    - dash.html
    - dash_bootstrap_components (for responsive grid)
"""

from dash import html
import dash_bootstrap_components as dbc


def create_team_view_layout():
    """
    Create team view layout with 5 chart containers in responsive grid.

    Returns:
        dbc.Container: Bootstrap container with responsive chart grid

    Chart IDs:
        - team-chart-1: Radar chart (team vs league)
        - team-chart-2: Stacked bar (squad depth)
        - team-chart-3: Treemap (player minutes)
        - team-chart-4: Heatmap (tactical fingerprint)
        - team-chart-5: Line chart (form trends)

    Design Rationale:
        - Chart 1 (radar) gets 8 cols - primary team comparison
        - Chart 2 (squad depth) gets 4 cols - compact overview
        - Chart 3 (treemap) gets 7 cols - needs space for player names
        - Chart 4 (heatmap) gets 5 cols - tactical metrics
        - Chart 5 (form) gets full width - temporal data needs space
    """
    return dbc.Container([
        # ===== ROW 1: RADAR (Featured) + SQUAD DEPTH =====
        dbc.Row([
            # Chart 1: Radar (Team vs League) - Featured
            dbc.Col([
                html.Div(
                    id='team-chart-1',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando radar de equipo...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=8, md=8, sm=12),

            # Chart 2: Stacked Bar (Squad Depth)
            dbc.Col([
                html.Div(
                    id='team-chart-2',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando profundidad de plantilla...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=4, md=4, sm=12)
        ], className='mb-4'),

        # ===== ROW 2: TREEMAP + HEATMAP =====
        dbc.Row([
            # Chart 3: Treemap (Player Minutes)
            dbc.Col([
                html.Div(
                    id='team-chart-3',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando distribucion de minutos...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=7, md=7, sm=12),

            # Chart 4: Heatmap (Tactical Fingerprint)
            dbc.Col([
                html.Div(
                    id='team-chart-4',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando huella tactica...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=5, md=5, sm=12)
        ], className='mb-4'),

        # ===== ROW 3: FORM TIMELINE (Full Width) =====
        dbc.Row([
            dbc.Col([
                html.Div(
                    id='team-chart-5',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando tendencias de forma...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=12, md=12, sm=12)
        ], className='mb-4')

    ], fluid=True, className='team-view-container')


# ===== EXPORT FOR CLEAN IMPORTS =====
__all__ = ['create_team_view_layout']
