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
from utils.chart_helpers import HKFATheme

logger = logging.getLogger(__name__)


# ===== CHART 1: BAR CHART - TEAM GOALS =====
@callback(
    Output('league-chart-1', 'children'),
    [Input('chart-data-store', 'data'),
     Input('current-filters-store', 'data')],
    prevent_initial_call=False
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
                plot_bgcolor=HKFATheme.BG_PRIMARY,
                paper_bgcolor=HKFATheme.BG_PRIMARY,
                font=dict(color=HKFATheme.TEXT_PRIMARY)
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
    prevent_initial_call=False
)
def update_league_chart_2_position_radar(chart_data, filters):
    """
    Radar chart showing average metrics by position with percentiles.

    Chart Type: Radar (polar) chart
    Data Required: chart_data['position_analysis']
    Layout Position: Row 2, left column

    Design Notes:
        - Multi-series radar (one per position)
        - Normalized metrics 0-100 for visual balance
        - Toggle position visibility via legend
        - HKFA theme with position colors
    """
    logger.info("→ Rendering league-chart-2 (position radar)")

    if not validate_data(chart_data):
        return create_empty_state("Datos no disponibles")

    try:
        from utils.chart_helpers import (
            HKFATheme, create_radar_chart, normalize_metric
        )

        if 'position_analysis' in chart_data:
            position_data = chart_data['position_analysis']

            if not position_data:
                return create_empty_state(
                    "No hay datos de posiciones disponibles"
                )

            # Definir métricas para mostrar (consistente entre posiciones)
            metrics = [
                'Avg Goals/Player',
                'Avg Assists/Player',
                'Pass Accuracy %',
                'Dribble Success %',
                'Duels Won %'
            ]

            fig = go.Figure()

            # Agregar trace por cada posición
            position_colors = {
                'Goalkeeper': HKFATheme.ACCENT_BLUE,
                'Defender': HKFATheme.DATA_SERIES[4],  # Dark red
                'Midfielder': HKFATheme.ACCENT_GOLD,
                'Winger': HKFATheme.DATA_SERIES[6],   # Orange
                'Forward': HKFATheme.ACCENT_RED
            }

            for position, pos_metrics in position_data.items():
                # Extract values
                values = [
                    pos_metrics.get('avg_goals_per_player', 0),
                    pos_metrics.get('avg_assists_per_player', 0),
                    pos_metrics.get('avg_accurate_passes_pct', 0),
                    pos_metrics.get('avg_successful_dribbles_pct', 0),
                    pos_metrics.get('avg_duels_won_pct', 0)
                ]

                # Normalize metrics para balance visual (0-100)
                # Goals y assists ya son por player, solo escalar
                values_norm = [
                    min(values[0] * 10, 100),  # Goals × 10 (max ~10 goals)
                    min(values[1] * 20, 100),  # Assists × 20 (max ~5 assists)
                    values[2],                  # Already % (0-100)
                    values[3],                  # Already % (0-100)
                    values[4]                   # Already % (0-100)
                ]

                color = position_colors.get(position, HKFATheme.NEUTRAL)

                fig.add_trace(go.Scatterpolar(
                    r=values_norm,
                    theta=metrics,
                    fill='toself',
                    fillcolor=f'rgba({int(color[1:3], 16)}, '
                              f'{int(color[3:5], 16)}, '
                              f'{int(color[5:7], 16)}, 0.2)',
                    line=dict(color=color, width=2),
                    name=position,
                    hovertemplate=(
                        f'<b>{position}</b><br>'
                        '%{theta}<br>'
                        'Value: %{r:.1f}<br>'
                        f'Players: {pos_metrics.get("player_count", 0)}'
                        '<extra></extra>'
                    )
                ))

            # HKFA theme layout
            fig.update_layout(
                title="📊 Perfil de Métricas por Posición",
                height=500,
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100],
                        tickfont=dict(color=HKFATheme.TEXT_SECONDARY),
                        gridcolor=HKFATheme.BG_TERTIARY
                    ),
                    bgcolor=HKFATheme.BG_SECONDARY
                ),
                showlegend=True,
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=1.02
                ),
                plot_bgcolor=HKFATheme.BG_PRIMARY,
                paper_bgcolor=HKFATheme.BG_PRIMARY,
                font=dict(color=HKFATheme.TEXT_PRIMARY)
            )

            return dcc.Graph(
                figure=fig,
                config={'displayModeBar': False}
            )

        return create_empty_state("Datos de posiciones no disponibles")

    except Exception as e:
        logger.error(f"Error en league-chart-2: {e}")
        return create_error_alert(str(e), "Error en Position Radar Chart")


# ===== CHART 3: SCATTER PLOT - AGE VS GOALS =====
@callback(
    Output('league-chart-3', 'children'),
    [Input('chart-data-store', 'data'),
     Input('current-filters-store', 'data')],
    prevent_initial_call=False
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
                    plot_bgcolor=HKFATheme.BG_PRIMARY,
                    paper_bgcolor=HKFATheme.BG_PRIMARY,
                    font=dict(color=HKFATheme.TEXT_PRIMARY),
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
    prevent_initial_call=False
)
def update_league_chart_4_tactical_heatmap(chart_data, filters):
    """
    Heatmap showing team tactical fingerprints.

    Chart Type: Heatmap
    Data Required: chart_data['tactical_fingerprints']
    Layout Position: Row 3, left column

    Design Notes:
        - X-axis: Tactical metrics (tempo, pressing, transitions, formation)
        - Y-axis: Teams
        - Color: Normalized values (blue=low, red=high)
        - Hover shows exact values and percentile
        - HKFA theme
    """
    logger.info("→ Rendering league-chart-4 (tactical heatmap)")

    if not validate_data(chart_data):
        return create_empty_state("Datos no disponibles")

    try:
        from utils.chart_helpers import (
            HKFATheme, create_heatmap, normalize_metric
        )
        import numpy as np

        if 'tactical_fingerprints' in chart_data:
            tactical_data = chart_data['tactical_fingerprints']

            if not tactical_data:
                return create_empty_state(
                    "Datos tácticos no disponibles"
                )

            # Prepare data for heatmap
            teams = list(tactical_data.keys())
            metrics = [
                'Tempo\n(Passes/90)',
                'Pressing\n(PPDA)',
                'Press Intensity\n(Def Actions)',
                'Recovery\nTime',
                'Wide Play\nRatio'
            ]

            # Extract values into matrix
            matrix = []
            for team in teams:
                team_data = tactical_data[team]
                row = [
                    team_data.get('tempo_passes_per_90', 0),
                    team_data.get('pressing_ppda', 0),
                    team_data.get('pressing_defensive_actions_att_third', 0),
                    team_data.get('transition_recovery_time', 0),
                    team_data.get('formation_wide_play_ratio', 0)
                ]
                matrix.append(row)

            # Convert to numpy array for normalization
            matrix_np = np.array(matrix)

            # Normalize each metric column to 0-100 scale
            normalized_matrix = []
            for i in range(matrix_np.shape[1]):
                col = matrix_np[:, i]
                if col.max() == col.min():
                    normalized_col = np.full_like(col, 50.0)
                else:
                    normalized_col = (
                        (col - col.min()) / (col.max() - col.min()) * 100
                    )
                normalized_matrix.append(normalized_col)

            normalized_matrix = np.array(normalized_matrix).T

            # Create figure
            fig = go.Figure(data=go.Heatmap(
                z=normalized_matrix,
                x=metrics,
                y=teams,
                colorscale='RdYlBu_r',  # Red=high, Blue=low
                text=[
                    [f'{val:.0f}' for val in row]
                    for row in normalized_matrix
                ],
                texttemplate='%{text}',
                textfont=dict(color=HKFATheme.TEXT_PRIMARY, size=11),
                colorbar=dict(
                    title="Intensidad<br>(0-100)",
                    tickfont=dict(color=HKFATheme.TEXT_PRIMARY),
                    thickness=20
                ),
                hovertemplate=(
                    '<b>%{y}</b><br>'
                    '%{x}<br>'
                    'Value: %{z:.0f}/100<br>'
                    '<extra></extra>'
                )
            ))

            # HKFA theme layout
            fig.update_layout(
                title="🎯 Fingerprint Táctico por Equipo",
                xaxis_title="",
                yaxis_title="",
                height=500,
                xaxis=dict(
                    tickfont=dict(size=10, color=HKFATheme.TEXT_PRIMARY),
                    side='top'
                ),
                yaxis=dict(tickfont=dict(size=11)),
                plot_bgcolor=HKFATheme.BG_PRIMARY,
                paper_bgcolor=HKFATheme.BG_PRIMARY,
                font=dict(color=HKFATheme.TEXT_PRIMARY)
            )

            return dcc.Graph(
                figure=fig,
                config={'displayModeBar': False}
            )

        return create_empty_state("Datos tácticos no disponibles")

    except Exception as e:
        logger.error(f"Error en league-chart-4: {e}")
        return create_error_alert(str(e), "Error en Tactical Heatmap")


# ===== CHART 5: TIMELINE - FORM TRENDS =====
@callback(
    Output('league-chart-5', 'children'),
    [Input('chart-data-store', 'data'),
     Input('current-filters-store', 'data')],
    prevent_initial_call=False
)
def update_league_chart_5_form_timeline(chart_data, filters):
    """
    Timeline showing league-wide form trends.

    Chart Type: Informational placeholder
    Data Required: Temporal match-by-match data (NOT AVAILABLE)
    Layout Position: Row 3, right column

    Design Notes:
        - Current dataset: Static season aggregates
        - Timeline requires: Match-by-match performance data
        - Future enhancement: Integrate with match data source
        - For now: Educational placeholder with data requirements
    """
    logger.info("→ Rendering league-chart-5 (form timeline - placeholder)")

    # Informational placeholder for future enhancement
    return html.Div([
        dbc.Card([
            dbc.CardBody([
                html.H5([
                    html.I(className="bi bi-graph-up-arrow me-2"),
                    "Timeline de Forma - Próximamente"
                ], className='mb-3 text-center'),
                html.Hr(),
                html.P([
                    html.Strong("Visualización planificada:"),
                    " Timeline interactivo mostrando tendencias de rendimiento "
                    "de equipos a lo largo de la temporada."
                ], className='mb-2'),
                html.P([
                    html.Strong("Requisitos de datos:"),
                ], className='mb-1'),
                html.Ul([
                    html.Li("Datos match-by-match (por jornada)"),
                    html.Li("Métricas temporales (goles, xG, forma reciente)"),
                    html.Li("Rolling averages (últimas 5 jornadas)"),
                    html.Li("Win/draw/loss sequences")
                ], className='mb-2'),
                html.P([
                    html.Strong("Estado actual:"),
                    " Dataset contiene datos agregados de temporada completa. "
                    "La funcionalidad timeline se implementará cuando se "
                    "integren datos temporales."
                ], className='mb-0 text-muted'),
                html.Hr(),
                html.Div([
                    html.Small([
                        html.I(className="bi bi-info-circle me-1"),
                        "Para activar esta visualización, considera integrar "
                        "datos de jornadas individuales desde la fuente de datos."
                    ], className='text-info')
                ])
            ])
        ], color="dark", outline=True, className='shadow-sm')
    ], className='p-3')


# ===== EXPORT FOR CLEAN IMPORTS =====
__all__ = [
    'update_league_chart_1_team_goals',
    'update_league_chart_2_position_radar',
    'update_league_chart_3_age_scatter',
    'update_league_chart_4_tactical_heatmap',
    'update_league_chart_5_form_timeline'
]
