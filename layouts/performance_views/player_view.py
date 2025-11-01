# ABOUTME: Player view layout module for performance dashboard
# ABOUTME: Defines responsive grid structure for 5 player-level charts

"""
Player View Layout Module.

This module creates the layout structure for player-level analysis.
Contains 5 chart containers organized in a responsive Bootstrap grid.

Chart Structure (FINAL_PLAN.md specification):
    1. Radar Chart: Player vs position average with percentile shading
    2. Horizontal Bar: Percentile rankings (top 6-8 metrics)
    3. Scatter Plot: Player efficiency (goals/xG vs assists/xA)
    4. Heatmap: Position-specific performance matrix
    5. Timeline: Performance evolution (multi-season if available)

Grid Design (UX-Optimized):
    Row 1: Chart 1 (6 cols) + Chart 2 (6 cols) - Radar + Percentiles
    Row 2: Chart 3 (6 cols) + Chart 4 (6 cols) - Efficiency + Matrix
    Row 3: Chart 5 (12 cols) - Evolution timeline full width

    Mobile (< 768px): All charts stack vertically (12 cols each)
    Tablet (768-991px): Maintains 6-6 grid for balanced display
    Desktop (>= 992px): Full 6-6 grid for symmetry

Dependencies:
    - dash.html
    - dash_bootstrap_components (for responsive grid)
"""

from dash import html
import dash_bootstrap_components as dbc


def create_player_view_layout():
    """
    Create player view layout with 5 chart containers in responsive grid.

    Returns:
        dbc.Container: Bootstrap container with responsive chart grid

    Chart IDs:
        - player-chart-1: Radar chart (player vs position avg)
        - player-chart-2: Horizontal bar (percentile rankings)
        - player-chart-3: Scatter plot (efficiency analysis)
        - player-chart-4: Heatmap (position-specific matrix)
        - player-chart-5: Timeline (performance evolution)

    Design Rationale:
        - Chart 1 (radar) shows player strengths vs peers
        - Chart 2 (percentiles) gives quick league-wide ranking
        - Chart 3 (scatter) reveals efficiency patterns
        - Chart 4 (heatmap) deep-dives position-specific metrics
        - Chart 5 (timeline) tracks improvement/decline over time
        - Symmetric 6-6 grid creates visual balance
    """
    return dbc.Container([
        # ===== ROW 1: RADAR + PERCENTILES =====
        dbc.Row([
            # Chart 1: Radar (Player vs Position Average)
            dbc.Col([
                html.Div(
                    id='player-chart-1',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando radar de jugador...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=6, md=6, sm=12),

            # Chart 2: Horizontal Bar (Percentile Rankings)
            dbc.Col([
                html.Div(
                    id='player-chart-2',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando percentiles...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=6, md=6, sm=12)
        ], className='mb-4'),

        # ===== ROW 2: EFFICIENCY SCATTER + HEATMAP =====
        dbc.Row([
            # Chart 3: Scatter Plot (Efficiency)
            dbc.Col([
                html.Div(
                    id='player-chart-3',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando analisis de eficiencia...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=6, md=6, sm=12),

            # Chart 4: Heatmap (Position-Specific Performance)
            dbc.Col([
                html.Div(
                    id='player-chart-4',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando matriz de rendimiento...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=6, md=6, sm=12)
        ], className='mb-4'),

        # ===== ROW 3: EVOLUTION TIMELINE (Full Width) =====
        dbc.Row([
            dbc.Col([
                html.Div(
                    id='player-chart-5',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando evolucion del jugador...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=12, md=12, sm=12)
        ], className='mb-4')

    ], fluid=True, className='player-view-container')


# ===== EXPORT FOR CLEAN IMPORTS =====
__all__ = ['create_player_view_layout']
