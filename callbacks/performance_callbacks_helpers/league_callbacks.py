# ABOUTME: League view callbacks
# ABOUTME: All visualizations for league-level analysis

"""
League view callbacks for performance dashboard.

This module contains all callbacks specific to league-level analysis,
including charts, tables, and position analysis.
"""

from dash import Input, Output, callback, html, dcc
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from utils.common import create_kpi_cards_row, safe_get_analysis_level, validate_filters
from utils.performance_helpers import (
    validate_performance_data,
    get_analysis_title,
    create_kpi_structure,
    handle_performance_error
)
from .helpers import (
    validate_data,
    create_empty_state,
    create_error_alert
)


# CALLBACK 1: Main KPIs for league view
@callback(
    [Output('kpi-title', 'children'),
     Output('main-kpis', 'children')],
    [Input('performance-data-store', 'data'),
     Input('current-filters-store', 'data')]
)
def update_main_kpis(performance_data, filters):
    """
    Actualiza los KPIs principales según los datos.

    DESIGN NOTES:
    - Handles all analysis levels (league/team/player)
    - Returns title and KPI cards
    - Uses helper functions for consistency
    """
    # Validar datos usando función auxiliar
    if not validate_performance_data(performance_data, "KPIs"):
        return "Sin datos disponibles", html.Div("Selecciona filtros válidos")

    try:
        # Obtener título usando función auxiliar
        title = get_analysis_title(filters, performance_data)

        # Validar filtros y obtener nivel de análisis
        filters = validate_filters(filters)
        analysis_level = safe_get_analysis_level(filters)

        # Crear estructura de KPIs usando función auxiliar
        kpi_data = create_kpi_structure(analysis_level, performance_data)

        if not kpi_data:
            return "Datos no disponibles", html.Div("Error procesando datos")

        # Crear fila de KPIs usando utilidad común
        kpis = create_kpi_cards_row(kpi_data)

        return title, kpis

    except Exception as e:
        error_info = handle_performance_error(e, "actualizando KPIs")
        return "Error", html.Div(
            str(error_info.get('error', 'Error desconocido'))
        )


# CALLBACK 2: Main chart for league view
@callback(
    Output('main-chart-container', 'children', allow_duplicate=True),
    [Input('chart-data-store', 'data'),
     Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_league_main_chart(chart_data, filters):
    """
    Actualiza el gráfico principal para vista de liga.

    DESIGN NOTES:
    - Uses guard pattern to only render for league view
    - Returns empty div for other analysis levels
    - Creates bar chart of team goals
    """
    # GUARD: Only render for league view
    if not filters or filters.get('analysis_level') != 'league':
        return html.Div()

    # GUARD: Validate data
    if not validate_data(chart_data):
        return create_empty_state()

    try:
        # NIVEL LIGA: Gráfico de goles por equipo
        if 'team_goals' in chart_data:
            data = chart_data['team_goals']
            fig = px.bar(
                x=data['teams'],
                y=data['goals'],
                title="Goles por Equipo",
                labels={'x': 'Equipos', 'y': 'Goles'},
                color=data['goals'],
                color_continuous_scale='Blues'
            )
            fig.update_layout(height=400, showlegend=False)
            return dcc.Graph(figure=fig)
        else:
            return html.Div(
                "Gráfico no disponible para estos filtros",
                className="text-center p-4"
            )

    except Exception as e:
        return create_error_alert(str(e), "Error en el Gráfico Principal")


# CALLBACK 3: Secondary chart for league view
@callback(
    Output('secondary-chart-container', 'children', allow_duplicate=True),
    [Input('chart-data-store', 'data'),
     Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_league_secondary_chart(chart_data, filters):
    """
    Actualiza el gráfico secundario para liga.

    DESIGN NOTES:
    - Guard pattern for league view only
    - Creates age vs performance scatter plot
    - Includes trend line
    """
    # GUARD: Only render for league view
    if not filters or filters.get('analysis_level') != 'league':
        return html.Div()

    # GUARD: Validate data
    if not validate_data(chart_data):
        return create_empty_state()

    try:
        # NUEVO: Gráfico de Dispersión de Edad vs. Rendimiento
        if 'age_performance' in chart_data:
            data = chart_data.get('age_performance', {})

            if data and 'ages' in data and 'goals' in data:
                # Crear un DataFrame para facilitar el manejo
                df = pd.DataFrame({
                    'Edad': data['ages'],
                    'Goles': data['goals'],
                    'Jugadores': data['players'],
                    'Posición': data.get(
                        'positions', ['Unknown'] * len(data['ages'])
                    ),
                    'Equipo': data.get('teams', ['Unknown'] * len(data['ages']))
                })

                # Calcular promedio de goles por edad
                age_avg = df.groupby('Edad')['Goles'].mean().reset_index()

                # Crear scatter plot con línea de tendencia
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
                    text=df['Jugadores'] + '<br>Equipo: ' +
                    df['Equipo'] + '<br>Posición: ' + df['Posición'],
                    hoverinfo='text',
                    name='Jugadores'
                ))

                # Línea de tendencia
                fig.add_trace(go.Scatter(
                    x=age_avg['Edad'],
                    y=age_avg['Goles'],
                    mode='lines',
                    line=dict(color='red', width=2, dash='dash'),
                    name='Promedio por Edad'
                ))

                # Actualizar layout
                fig.update_layout(
                    title="Relación Edad-Rendimiento",
                    xaxis_title="Edad",
                    yaxis_title="Goles",
                    height=400,
                    hovermode='closest',
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1
                    )
                )

                return dcc.Graph(figure=fig)

        # Fallback: Distribución por posición
        elif 'position_distribution' in chart_data:
            data = chart_data['position_distribution']
            fig = px.pie(
                values=data['counts'],
                names=data['positions'],
                title="Distribución por Posición"
            )
            fig.update_layout(height=400)
            return dcc.Graph(figure=fig)
        else:
            return html.Div(
                "Gráfico secundario no disponible",
                className="text-center p-4"
            )

    except Exception as e:
        return create_error_alert(str(e), "Error en Gráfico Secundario")


# CALLBACK 4: Top performers for league view
@callback(
    Output('top-performers-container', 'children', allow_duplicate=True),
    [Input('performance-data-store', 'data'),
     Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_league_performers(performance_data, filters):
    """
    Actualiza top performers para liga.

    DESIGN NOTES:
    - Guard pattern for league view
    - Creates tabs with top scorers and assisters
    - Shows top 10 in each category
    """
    # GUARD: Only render for league view
    if not filters or filters.get('analysis_level') != 'league':
        return html.Div()

    # GUARD: Validate data
    if not validate_data(performance_data):
        return create_empty_state()

    try:
        # NIVEL LIGA: Tabs con top performers
        if 'top_performers' in performance_data:
            performers = performance_data['top_performers']

            # Crear tabs para diferentes categorías
            tabs = []

            if 'top_scorers' in performers:
                tab_content = []
                for i, player in enumerate(performers['top_scorers'][:10], 1):
                    tab_content.append(
                        html.Tr([
                            html.Td(f"{i}°"),
                            html.Td(player['Player']),
                            html.Td(player['Team']),
                            html.Td(f"{player['Goals']} goles"),
                            html.Td(player.get('Position_Group', 'N/A'))
                        ])
                    )

                tabs.append(
                    dbc.Tab(
                        html.Table([
                            html.Thead([
                                html.Tr([
                                    html.Th("Pos"),
                                    html.Th("Jugador"),
                                    html.Th("Equipo"),
                                    html.Th("Goles"),
                                    html.Th("Posición")
                                ])
                            ]),
                            html.Tbody(tab_content)
                        ], className="table table-striped"),
                        label="Top Goleadores",
                        tab_id="scorers"
                    )
                )

            if 'top_assisters' in performers:
                tab_content = []
                for i, player in enumerate(performers['top_assisters'][:10], 1):
                    tab_content.append(
                        html.Tr([
                            html.Td(f"{i}°"),
                            html.Td(player['Player']),
                            html.Td(player['Team']),
                            html.Td(f"{player['Assists']} asist."),
                            html.Td(player.get('Position_Group', 'N/A'))
                        ])
                    )

                tabs.append(
                    dbc.Tab(
                        html.Table([
                            html.Thead([
                                html.Tr([
                                    html.Th("Pos"),
                                    html.Th("Jugador"),
                                    html.Th("Equipo"),
                                    html.Th("Asistencias"),
                                    html.Th("Posición")
                                ])
                            ]),
                            html.Tbody(tab_content)
                        ], className="table table-striped"),
                        label="Top Asistentes",
                        tab_id="assisters"
                    )
                )

            return dbc.Tabs(tabs, active_tab="scorers")
        else:
            return html.Div(
                "Top performers no disponible",
                className="text-center p-4"
            )

    except Exception as e:
        return create_error_alert(str(e), "Error en Top Performers")


# CALLBACK 5: Position analysis for league view
@callback(
    Output('position-analysis-container', 'children', allow_duplicate=True),
    [Input('performance-data-store', 'data'),
     Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_league_position_analysis(performance_data, filters):
    """
    Actualiza análisis por posición para liga.

    DESIGN NOTES:
    - Guard pattern for league view
    - Creates position cards with stats
    - Shows player count, goals, assists, age
    """
    # GUARD: Only render for league view
    if not filters or filters.get('analysis_level') != 'league':
        return html.Div()

    # GUARD: Validate data
    if not validate_data(performance_data):
        return create_empty_state()

    try:
        if 'position_analysis' in performance_data:
            positions = performance_data['position_analysis']

            cards = []
            for position, stats in positions.items():
                card = dbc.Card([
                    dbc.CardBody([
                        html.H6(position, className="card-title"),
                        html.P(
                            f"Players: {stats['player_count']}",
                            className="card-text"
                        ),
                        html.P([
                            html.Span(
                                f"Goals: {stats['total_goals']}",
                                className="card-text"
                            ),
                            html.Span(" | ", className="text-muted mx-1"),
                            html.Span(
                                f"Assists: {stats['total_assists']}",
                                className="card-text"
                            )
                        ]),
                        html.P(
                            f"Avg. Age: {stats['avg_age']}",
                            className="card-text"
                        ),
                        html.Small(
                            f"Avg. Minutes: {stats['avg_minutes']}",
                            className="text-muted"
                        )
                    ])
                ], className="h-100")

                cards.append(dbc.Col(card, md=6, lg=4, className="mb-3"))

            return dbc.Row(cards)
        else:
            return html.Div(
                "Análisis por posición no disponible",
                className="text-center p-4"
            )

    except Exception as e:
        return create_error_alert(str(e), "Error en Análisis de Posición")
