# ABOUTME: League view layout module for performance dashboard
# ABOUTME: Defines responsive grid structure for 5 league-level charts

"""
League View Layout Module.

This module creates the layout structure for league-level analysis.
Contains 5 chart containers organized in a responsive Bootstrap grid.

Chart Structure (FINAL_PLAN.md specification):
    1. Bar Chart: Team goals with xG overlay (featured)
    2. Radar Chart: Average metrics by position with percentiles
    3. Scatter Plot: Age vs Goals with trend line
    4. Heatmap: Team tactical fingerprints (tempo vs pressing)
    5. Timeline: League-wide form trends

Grid Design (UX-Optimized):
    Row 1: Chart 1 (12 cols) - Feature chart, needs full width
    Row 2: Chart 2 (6 cols) + Chart 3 (6 cols) - Comparative analysis
    Row 3: Chart 4 (6 cols) + Chart 5 (6 cols) - Advanced insights

    Mobile (< 768px): All charts stack vertically (12 cols each)
    Tablet (768-991px): Maintains 6-6 grid for better use of space
    Desktop (>= 992px): Full 6-6 grid with optimal spacing

Dependencies:
    - dash.html
    - dash_bootstrap_components (for responsive grid)
"""

from dash import html
import dash_bootstrap_components as dbc


def create_league_view_layout():
    """
    Create league view layout with 5 chart containers in responsive grid.

    Returns:
        dbc.Container: Bootstrap container with responsive chart grid

    Chart IDs:
        - league-chart-1: Bar chart (team goals)
        - league-chart-2: Radar chart (position metrics)
        - league-chart-3: Scatter plot (age vs goals)
        - league-chart-4: Heatmap (tactical fingerprints)
        - league-chart-5: Timeline (form trends)

    Design Rationale:
        - Chart 1 gets full width (12 cols) because it's the primary metric
        - Charts 2-3 are side-by-side (6-6) for comparative analysis
        - Charts 4-5 are side-by-side (6-6) for advanced insights
        - All charts have loading states managed by individual callbacks
    """
    return dbc.Container([
        # ===== ROW 1: FEATURE CHART (Full Width) =====
        dbc.Row([
            dbc.Col([
                html.Div(
                    id='league-chart-1',
                    className='chart-container',
                    children=[
                        # Placeholder - populated by callback
                        html.Div(
                            "Cargando grafico principal...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=12, md=12, sm=12)
        ], className='mb-4'),  # Margin bottom for spacing

        # ===== ROW 2: COMPARATIVE ANALYSIS (Side by Side) =====
        dbc.Row([
            # Chart 2: Radar (Position Metrics)
            dbc.Col([
                html.Div(
                    id='league-chart-2',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando radar de posiciones...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=6, md=6, sm=12),

            # Chart 3: Scatter (Age vs Goals)
            dbc.Col([
                html.Div(
                    id='league-chart-3',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando analisis de edad...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=6, md=6, sm=12)
        ], className='mb-4'),

        # ===== ROW 3: ADVANCED INSIGHTS (Side by Side) =====
        dbc.Row([
            # Chart 4: Heatmap (Tactical Fingerprints)
            dbc.Col([
                html.Div(
                    id='league-chart-4',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando analisis tactico...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=6, md=6, sm=12),

            # Chart 5: Timeline (Form Trends)
            dbc.Col([
                html.Div(
                    id='league-chart-5',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando tendencias...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=6, md=6, sm=12)
        ], className='mb-4')

    ], fluid=True, className='league-view-container')


# ===== EXPORT FOR CLEAN IMPORTS =====
__all__ = ['create_league_view_layout']
