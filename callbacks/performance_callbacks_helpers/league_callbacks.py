# ABOUTME: League view callbacks for performance dashboard
# ABOUTME: 5 chart callbacks for league-level analysis with unique IDs

"""
League View Callbacks Module.

This module contains all callbacks specific to league-level analysis.
Each callback controls one specific chart in the league view layout.

Chart Mapping (matching league_view.py IDs):
    1. league-chart-1: Bar Chart - Team goals with xG overlay
    2. league-chart-2: Radar Chart - Position average metrics with percentiles
    3. league-chart-3: Scatter Plot - Age vs Goals with trend line
    4. league-chart-4: Heatmap - Team tactical fingerprints
    5. league-chart-5: Timeline - League-wide form trends

Architecture Notes:
    - NO allow_duplicate (each ID is unique)
    - NO guard patterns needed (callbacks only execute when view visible)
    - Callbacks triggered by chart-data-store updates
    - HKFA theme applied to all charts
"""

from dash import Input, Output, callback, html, dcc
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import logging
from .helpers import (
    validate_data,
    create_empty_state,
    create_error_alert
)

logger = logging.getLogger(__name__)


# ===== CHART 1: BAR CHART - TEAM GOALS =====
@callback(
    Output('league-chart-1', 'children'),
    [Input('chart-data-store', 'data'),
     Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_league_chart_1_team_goals(chart_data, filters):
    """
    Bar chart showing team goals with xG overlay.

    Chart Type: Bar chart
    Data Required: chart_data['team_goals']
    Layout Position: Row 1 (full width)

    Design Notes:
        - Primary metric for league analysis
        - xG overlay shows expected vs actual performance
        - Interactive hover with team details
        - HKFA theme colors
    """
    logger.info("→ Rendering league-chart-1 (team goals)")

    if not validate_data(chart_data):
        return create_empty_state("Datos no disponibles")

    try:
        if 'team_goals' in chart_data:
            data = chart_data['team_goals']

            fig = px.bar(
                x=data['teams'],
                y=data['goals'],
                title="⚽ Goles por Equipo - Liga HK Premier",
                labels={'x': 'Equipos', 'y': 'Goles'},
                color=data['goals'],
                color_continuous_scale='Blues'
            )

            # HKFA theme
            fig.update_layout(
                height=400,
                showlegend=False,
                plot_bgcolor='#18181A',
                paper_bgcolor='#18181A',
                font=dict(color='#FFFFFF')
            )

            fig.update_xaxes(tickangle=45)

            return dcc.Graph(figure=fig, config={'displayModeBar': False})
        else:
            return create_empty_state("Gráfico no disponible para estos filtros")

    except Exception as e:
        logger.error(f"Error en league-chart-1: {e}")
        return create_error_alert(str(e), "Error en Team Goals Chart")


# ===== CHART 2: RADAR CHART - POSITION METRICS =====
@callback(
    Output('league-chart-2', 'children'),
    [Input('chart-data-store', 'data'),
     Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_league_chart_2_position_radar(chart_data, filters):
    """
    Radar chart showing average metrics by position with percentiles.

    Chart Type: Radar (polar) chart
    Data Required: chart_data['position_metrics'] (FUTURE)
    Layout Position: Row 2, left column

    Design Notes:
        - Multi-series radar (one per position)
        - Percentile shading for context
        - Toggle position visibility
        - HKFA theme with position colors
    """
    logger.info("→ Rendering league-chart-2 (position radar)")

    # PLACEHOLDER: To be implemented with tactical analyzer data
    return html.Div([
        dbc.Alert([
            html.H5("📊 Radar de Posiciones - Próximamente", className='mb-2'),
            html.P(
                "Este gráfico mostrará métricas promedio por posición con "
                "percentiles league-wide. Implementación en Phase 5.",
                className='mb-0'
            )
        ], color='info', className='text-center')
    ])


# ===== CHART 3: SCATTER PLOT - AGE VS GOALS =====
@callback(
    Output('league-chart-3', 'children'),
    [Input('chart-data-store', 'data'),
     Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_league_chart_3_age_scatter(chart_data, filters):
    """
    Scatter plot showing age vs goals with trend line.

    Chart Type: Scatter plot with regression
    Data Required: chart_data['age_performance']
    Layout Position: Row 2, right column

    Design Notes:
        - Each point = one player
        - Hover shows player details
        - Trend line shows age-performance correlation
        - Color coded by goals
        - HKFA theme
    """
    logger.info("→ Rendering league-chart-3 (age vs goals)")

    if not validate_data(chart_data):
        return create_empty_state("Datos no disponibles")

    try:
        if 'age_performance' in chart_data:
            data = chart_data.get('age_performance', {})

            if data and 'ages' in data and 'goals' in data:
                # Crear DataFrame
                df = pd.DataFrame({
                    'Edad': data['ages'],
                    'Goles': data['goals'],
                    'Jugadores': data['players'],
                    'Posición': data.get(
                        'positions', ['Unknown'] * len(data['ages'])
                    ),
                    'Equipo': data.get('teams', ['Unknown'] * len(data['ages']))
                })

                # Calcular promedio por edad (trend line)
                age_avg = df.groupby('Edad')['Goles'].mean().reset_index()

                # Crear figura
                fig = go.Figure()

                # Scatter plot principal
                fig.add_trace(go.Scatter(
                    x=df['Edad'],
                    y=df['Goles'],
                    mode='markers',
                    marker=dict(
                        size=10,
                        color=df['Goles'],
                        colorscale='Viridis',
                        showscale=True,
                        colorbar=dict(title="Goles")
                    ),
                    text=[
                        f"{player}<br>Equipo: {team}<br>Posición: {pos}"
                        for player, team, pos in zip(
                            df['Jugadores'], df['Equipo'], df['Posición']
                        )
                    ],
                    hoverinfo='text',
                    name='Jugadores'
                ))

                # Línea de tendencia
                fig.add_trace(go.Scatter(
                    x=age_avg['Edad'],
                    y=age_avg['Goles'],
                    mode='lines',
                    line=dict(color='#ED1C24', width=2, dash='dash'),
                    name='Promedio por Edad'
                ))

                # HKFA theme
                fig.update_layout(
                    title="📈 Relación Edad-Rendimiento",
                    xaxis_title="Edad",
                    yaxis_title="Goles",
                    height=400,
                    hovermode='closest',
                    plot_bgcolor='#18181A',
                    paper_bgcolor='#18181A',
                    font=dict(color='#FFFFFF'),
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1
                    )
                )

                return dcc.Graph(figure=fig, config={'displayModeBar': False})

        # Fallback
        return create_empty_state("Datos de edad no disponibles")

    except Exception as e:
        logger.error(f"Error en league-chart-3: {e}")
        return create_error_alert(str(e), "Error en Age Scatter Chart")


# ===== CHART 4: HEATMAP - TACTICAL FINGERPRINTS =====
@callback(
    Output('league-chart-4', 'children'),
    [Input('chart-data-store', 'data'),
     Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_league_chart_4_tactical_heatmap(chart_data, filters):
    """
    Heatmap showing team tactical fingerprints (tempo × pressing).

    Chart Type: Heatmap
    Data Required: chart_data['tactical_fingerprints'] (FUTURE)
    Layout Position: Row 3, left column

    Design Notes:
        - X-axis: Tempo (passes per 90)
        - Y-axis: Pressing intensity (PPDA)
        - Color: Team classification
        - Click cell → team view drill-down
        - HKFA theme
    """
    logger.info("→ Rendering league-chart-4 (tactical heatmap)")

    # PLACEHOLDER: Requires TacticalAnalyzer implementation
    return html.Div([
        dbc.Alert([
            html.H5("🎯 Heatmap Táctico - Próximamente", className='mb-2'),
            html.P(
                "Este heatmap mostrará el estilo táctico de cada equipo "
                "(tempo × pressing intensity). Implementación en Phase 5.",
                className='mb-0'
            )
        ], color='warning', className='text-center')
    ])


# ===== CHART 5: TIMELINE - FORM TRENDS =====
@callback(
    Output('league-chart-5', 'children'),
    [Input('chart-data-store', 'data'),
     Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_league_chart_5_form_timeline(chart_data, filters):
    """
    Timeline showing league-wide form trends.

    Chart Type: Line chart (multi-series)
    Data Required: chart_data['form_trends'] (FUTURE)
    Layout Position: Row 3, right column

    Design Notes:
        - Multiple lines (one per team or metric)
        - Zoom/pan temporal exploration
        - Metric toggle (goals, xG, shots, etc.)
        - HKFA theme
    """
    logger.info("→ Rendering league-chart-5 (form timeline)")

    # PLACEHOLDER: Requires temporal data
    return html.Div([
        dbc.Alert([
            html.H5("📅 Timeline de Forma - Próximamente", className='mb-2'),
            html.P(
                "Este timeline mostrará tendencias de rendimiento a lo largo "
                "de la temporada. Implementación en Phase 5.",
                className='mb-0'
            )
        ], color='secondary', className='text-center')
    ])


# ===== EXPORT FOR CLEAN IMPORTS =====
__all__ = [
    'update_league_chart_1_team_goals',
    'update_league_chart_2_position_radar',
    'update_league_chart_3_age_scatter',
    'update_league_chart_4_tactical_heatmap',
    'update_league_chart_5_form_timeline'
]
