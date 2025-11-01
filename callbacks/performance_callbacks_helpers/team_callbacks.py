# ABOUTME: Team view callbacks for performance dashboard
# ABOUTME: 5 chart callbacks for team-level analysis with unique IDs

"""
Team View Callbacks Module.

5 callbacks for team-level analysis charts.
Fully implemented in Phase 5.
"""

from dash import Input, Output, callback, html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import logging
from .helpers import validate_data, create_empty_state, create_error_alert
from utils.chart_helpers import (
    create_radar_chart,
    create_heatmap,
    HKFATheme,
    apply_hkfa_theme
)

logger = logging.getLogger(__name__)


@callback(
    Output('team-chart-1', 'children'),
    [Input('chart-data-store', 'data'), Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_team_chart_1(chart_data, filters):
    """Chart 1: Team vs League Radar (6-8 key metrics)."""
    logger.info("-> Rendering team-chart-1 (team vs league radar)")

    if not chart_data or 'team_vs_league_radar' not in chart_data:
        return create_empty_state("No hay datos de radar disponibles")

    radar_data = chart_data['team_vs_league_radar']

    try:
        # Create radar chart with team vs league comparison
        fig = create_radar_chart(
            values=radar_data['team_values'],
            metrics=radar_data['metrics'],
            title="Equipo vs Promedio de Liga",
            name='Equipo',
            reference_values=radar_data['league_values'],
            reference_name='Promedio Liga'
        )

        return dcc.Graph(figure=fig, config={'displayModeBar': False})

    except Exception as e:
        logger.error(f"Error creating team radar chart: {e}")
        return create_error_alert(f"Error al crear el gráfico: {str(e)}")


@callback(
    Output('team-chart-2', 'children'),
    [Input('chart-data-store', 'data'), Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_team_chart_2(chart_data, filters):
    """Chart 2: Squad Depth Stacked Bar by Position."""
    logger.info("-> Rendering team-chart-2 (squad depth)")

    if not chart_data or 'squad_depth' not in chart_data:
        return create_empty_state("No hay datos de plantilla disponibles")

    squad_data = chart_data['squad_depth']

    try:
        # Create stacked bar chart for squad depth
        fig = go.Figure()

        # Add player count trace
        fig.add_trace(go.Bar(
            name='Número de Jugadores',
            x=squad_data['positions'],
            y=squad_data['player_counts'],
            marker_color=HKFATheme.ACCENT_RED,
            text=squad_data['player_counts'],
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>' +
                         'Jugadores: %{y}<br>' +
                         'Edad promedio: %{customdata[0]:.1f}<br>' +
                         'Minutos totales: %{customdata[1]:,.0f}<br>' +
                         '<extra></extra>',
            customdata=list(zip(squad_data['avg_ages'], squad_data['total_minutes']))
        ))

        fig.update_layout(
            title="Profundidad de Plantilla por Posición",
            xaxis_title="Posición",
            yaxis_title="Número de Jugadores",
            showlegend=False,
            height=350
        )

        apply_hkfa_theme(fig)

        return dcc.Graph(figure=fig, config={'displayModeBar': False})

    except Exception as e:
        logger.error(f"Error creating squad depth chart: {e}")
        return create_error_alert(f"Error al crear el gráfico: {str(e)}")


@callback(
    Output('team-chart-3', 'children'),
    [Input('chart-data-store', 'data'), Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_team_chart_3(chart_data, filters):
    """Chart 3: Player Minutes Treemap."""
    logger.info("-> Rendering team-chart-3 (player minutes treemap)")

    if not chart_data or 'player_minutes' not in chart_data:
        return create_empty_state("No hay datos de minutos disponibles")

    minutes_data = chart_data['player_minutes']

    try:
        # Create treemap for player minutes distribution
        total_minutes = sum(minutes_data['minutes'])

        fig = go.Figure(go.Treemap(
            labels=minutes_data['players'],
            parents=[''] * len(minutes_data['players']),
            values=minutes_data['minutes'],
            text=[f"{m:,.0f} min<br>({m/total_minutes*100:.1f}%)"
                  for m in minutes_data['minutes']],
            textposition='middle center',
            marker=dict(
                colors=minutes_data['minutes'],
                colorscale='Reds',
                cmid=sum(minutes_data['minutes']) / len(minutes_data['minutes'])
            ),
            hovertemplate='<b>%{label}</b><br>' +
                         'Minutos: %{value:,.0f}<br>' +
                         'Porcentaje: %{percentParent}<br>' +
                         '<extra></extra>'
        ))

        fig.update_layout(
            title="Distribución de Minutos por Jugador",
            height=400
        )

        apply_hkfa_theme(fig)

        return dcc.Graph(figure=fig, config={'displayModeBar': False})

    except Exception as e:
        logger.error(f"Error creating treemap: {e}")
        return create_error_alert(f"Error al crear el gráfico: {str(e)}")


@callback(
    Output('team-chart-4', 'children'),
    [Input('chart-data-store', 'data'), Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_team_chart_4(chart_data, filters):
    """Chart 4: Tactical Fingerprint Heatmap."""
    logger.info("-> Rendering team-chart-4 (tactical fingerprint)")

    if not chart_data or 'tactical_fingerprint' not in chart_data:
        return create_empty_state(
            "No hay datos tácticos disponibles para este equipo"
        )

    tactical_data = chart_data['tactical_fingerprint']

    try:
        # Create horizontal bar chart for tactical metrics
        fig = go.Figure(go.Bar(
            x=tactical_data['values'],
            y=tactical_data['metrics'],
            orientation='h',
            marker=dict(
                color=tactical_data['values'],
                colorscale='RdYlBu_r',
                showscale=True,
                colorbar=dict(title="Intensidad")
            ),
            text=[f"{v:.2f}" for v in tactical_data['values']],
            textposition='auto',
            hovertemplate='<b>%{y}</b><br>' +
                         'Valor: %{x:.2f}<br>' +
                         '<extra></extra>'
        ))

        fig.update_layout(
            title=f"Huella Táctica - {tactical_data['team_name']}",
            xaxis_title="Valor",
            yaxis_title="Métrica",
            height=400,
            showlegend=False
        )

        apply_hkfa_theme(fig)

        return dcc.Graph(figure=fig, config={'displayModeBar': False})

    except Exception as e:
        logger.error(f"Error creating tactical fingerprint: {e}")
        return create_error_alert(f"Error al crear el gráfico: {str(e)}")


@callback(
    Output('team-chart-5', 'children'),
    [Input('chart-data-store', 'data'), Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_team_chart_5(chart_data, filters):
    """Chart 5: Form Timeline Placeholder."""
    logger.info("-> Rendering team-chart-5 (form timeline placeholder)")

    # Educational placeholder for temporal data
    return html.Div([
        dbc.Alert([
            html.I(className='bi bi-graph-up-arrow', style={'fontSize': '48px', 'color': HKFATheme.ACCENT_RED}),
            html.H5("Evolución de Forma del Equipo", className='mt-3 mb-2'),
            html.P([
                "Este gráfico mostrará la evolución del rendimiento del equipo a lo largo de la temporada. ",
                "Para visualizar esta información, se requieren datos partido por partido (match-by-match)."
            ], className='mb-2'),
            html.P([
                html.Strong("Datos necesarios: "),
                "Métricas agregadas por jornada o partido individual."
            ], className='mb-0 text-muted')
        ], color='info', className='text-center')
    ])
