# ABOUTME: Player view callbacks
# ABOUTME: All visualizations for player-level analysis

"""
Player view callbacks for performance dashboard.

This module contains all callbacks specific to player-level analysis,
including radar charts, percentiles, and player comparisons.
"""

from dash import Input, Output, callback, html, dcc
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .helpers import (
    validate_data,
    create_empty_state,
    create_error_alert
)


# CALLBACK 1: Main chart for player view (radar chart)
@callback(
    Output('main-chart-container', 'children', allow_duplicate=True),
    [Input('chart-data-store', 'data'),
     Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_player_main_chart(chart_data, filters):
    """
    Actualiza el gráfico principal para vista de jugador (radar chart).

    DESIGN NOTES:
    - Guard pattern for player view
    - Creates player vs position average radar
    - Normalizes metrics for visual balance
    """
    # GUARD: Only render for player view
    if not filters or filters.get('analysis_level') != 'player':
        return html.Div()

    # GUARD: Validate data
    if not validate_data(chart_data):
        return create_empty_state()

    try:
        if 'player_vs_position_radar' in chart_data:
            data = chart_data['player_vs_position_radar']
            player_name = filters.get('player', 'Jugador')

            # Extraer datos del radar
            metrics = data.get('metrics', [])
            player_values = data.get('player_values', [])
            position_avg = data.get('position_avg', [])

            # Verificar datos suficientes
            if not metrics or not player_values or not position_avg:
                return html.Div(
                    "No hay datos suficientes para el radar chart",
                    className="text-center p-4"
                )

            # NORMALIZACIÓN MEJORADA
            normalized_player = []
            normalized_position = []

            for i, metric in enumerate(metrics):
                if i < len(player_values) and i < len(position_avg):
                    # Obtener valores
                    p_val = player_values[i]
                    pos_val = position_avg[i]

                    # ARREGLO: Convertir None a 0
                    p_val = p_val if p_val is not None else 0
                    pos_val = pos_val if pos_val is not None else 0

                    # Si ambos valores son cercanos a cero
                    if abs(p_val) < 0.001 and abs(pos_val) < 0.001:
                        normalized_player.append(30)
                        normalized_position.append(25)
                        continue

                    # Calculamos el valor máximo para la normalización
                    max_val = max(p_val, pos_val) * 1.2

                    # Si la diferencia es muy pequeña, amplificamos
                    if abs(p_val - pos_val) < max_val * 0.1:
                        base = min(p_val, pos_val)
                        diff = abs(p_val - pos_val)
                        amplified_diff = max(diff, base * 0.2)

                        if p_val >= pos_val:
                            normalized_player.append(base + amplified_diff)
                            normalized_position.append(base)
                        else:
                            normalized_player.append(base)
                            normalized_position.append(base + amplified_diff)
                    else:
                        # Normalizar proporcional a 90
                        scale_factor = 90 / max_val
                        normalized_player.append(p_val * scale_factor)
                        normalized_position.append(pos_val * scale_factor)

            # Crear radar chart mejorado
            fig = go.Figure()

            # Añadir trace del jugador
            fig.add_trace(go.Scatterpolar(
                r=normalized_player,
                theta=metrics,
                fill='toself',
                name=player_name,
                line=dict(color='#2980b9', width=3)
            ))

            # Añadir trace de posición
            fig.add_trace(go.Scatterpolar(
                r=normalized_position,
                theta=metrics,
                fill='toself',
                name='Promedio Posición',
                line=dict(color='#e74c3c', width=2, dash='dot'),
                opacity=0.65
            ))

            # Configuración del layout
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100],
                        tickvals=[0, 20, 40, 60, 80, 90],
                        ticktext=["0", "20", "40", "60", "80", "90"],
                        showticklabels=True,
                        gridcolor='lightgrey'
                    ),
                    angularaxis=dict(
                        tickfont=dict(size=12, color='darkblue')
                    ),
                    bgcolor='#f9f9f9'
                ),
                title=dict(
                    text=f"Perfil de {player_name} vs Promedio de Posición",
                    font=dict(size=16)
                ),
                height=500,
                margin=dict(t=80, b=100, l=80, r=80),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.15,
                    xanchor="center",
                    x=0.5
                ),
                template="plotly_white"
            )

            # Añadir anotación explicativa
            fig.add_annotation(
                x=0.5, y=-0.15,
                xref="paper", yref="paper",
                text="Las métricas están normalizadas para mejor visualización",
                showarrow=False,
                font=dict(size=12, color="gray")
            )

            return dcc.Graph(figure=fig)
        else:
            return html.Div(
                "Gráfico no disponible", className="text-center p-4"
            )

    except Exception as e:
        return create_error_alert(str(e), "Error en Radar Chart")


# CALLBACK 2: Secondary chart for player view (percentiles)
@callback(
    Output('secondary-chart-container', 'children', allow_duplicate=True),
    [Input('chart-data-store', 'data'),
     Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_player_secondary_chart(chart_data, filters):
    """
    Actualiza el gráfico secundario para jugador (percentiles).

    DESIGN NOTES:
    - Guard pattern for player view
    - Shows percentile bars
    """
    # GUARD: Only render for player view
    if not filters or filters.get('analysis_level') != 'player':
        return html.Div()

    # GUARD: Validate data
    if not validate_data(chart_data):
        return create_empty_state()

    try:
        if 'player_percentiles' in chart_data:
            data = chart_data['player_percentiles']
            fig = px.bar(
                x=data['percentiles'],
                y=data['metrics'],
                orientation='h',
                title="Percentiles vs Posición",
                labels={'x': 'Percentil', 'y': 'Métricas'},
                color=data['percentiles'],
                color_continuous_scale='RdYlGn'
            )
            fig.update_layout(height=400, showlegend=False)
            return dcc.Graph(figure=fig)
        else:
            return html.Div(
                "Gráfico secundario no disponible",
                className="text-center p-4"
            )

    except Exception as e:
        return create_error_alert(str(e), "Error en Gráfico de Percentiles")


# CALLBACK 3: Player profile card
@callback(
    Output('top-performers-container', 'children', allow_duplicate=True),
    [Input('performance-data-store', 'data'),
     Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_player_profile(performance_data, filters):
    """
    Actualiza el perfil del jugador.

    DESIGN NOTES:
    - Guard pattern for player view
    - Shows basic info and performance stats
    """
    # GUARD: Only render for player view
    if not filters or filters.get('analysis_level') != 'player':
        return html.Div()

    # GUARD: Validate data
    if not validate_data(performance_data):
        return create_empty_state()

    try:
        if 'basic_info' in performance_data:
            player_info = performance_data.get('basic_info', {})
            performance_stats = performance_data.get('performance_stats', {})

            player_name = player_info.get('name', 'Jugador')
            team = player_info.get('team', 'Equipo')
            position = player_info.get('position_group', 'N/A')

            # Tarjeta de perfil del jugador
            profile_card = dbc.Card([
                dbc.CardHeader(f"Perfil de {player_name}"),
                dbc.CardBody([
                    dbc.Row([
                        # Columna de información básica
                        dbc.Col([
                            html.H5(player_name, className="card-title"),
                            html.H6(
                                f"{team} | {position}",
                                className="card-subtitle text-muted mb-3"
                            ),
                            html.Div([
                                html.P([
                                    html.Strong("Edad: "),
                                    html.Span(
                                        f"{player_info.get('age', 'N/A')} años"
                                    )
                                ]),
                                html.P([
                                    html.Strong("Partidos: "),
                                    html.Span(
                                        player_info.get('matches_played', 'N/A')
                                    )
                                ]),
                                html.P([
                                    html.Strong("Minutos: "),
                                    html.Span(
                                        player_info.get('minutes_played', 'N/A')
                                    )
                                ])
                            ])
                        ], md=6),

                        # Columna de estadísticas
                        dbc.Col([
                            html.H5(
                                "Estadísticas Ofensivas",
                                className="card-title"
                            ),
                            html.Div([
                                html.P([
                                    html.Strong("Goles: "),
                                    html.Span(performance_stats.get('goals', 0))
                                ]),
                                html.P([
                                    html.Strong("Asistencias: "),
                                    html.Span(performance_stats.get('assists', 0))
                                ]),
                                html.P([
                                    html.Strong("Min. por partido: "),
                                    html.Span(
                                        f"{performance_stats.get('minutes_per_match', 0):.1f}"
                                    )
                                ])
                            ])
                        ], md=6)
                    ])
                ])
            ])

            return profile_card
        else:
            return html.Div(
                "Perfil de jugador no disponible",
                className="text-center p-4"
            )

    except Exception as e:
        return create_error_alert(str(e), "Error en Perfil de Jugador")


# CALLBACK 4: Player comparison chart
@callback(
    [Output('comparison-card', 'style', allow_duplicate=True),
     Output('comparison-chart-title', 'children', allow_duplicate=True),
     Output('comparison-chart-container', 'children', allow_duplicate=True)],
    [Input('current-filters-store', 'data'),
     Input('performance-data-store', 'data')],
    prevent_initial_call=True
)
def update_player_comparison(filters, performance_data):
    """
    Actualiza el gráfico de comparación para jugador.

    DESIGN NOTES:
    - Guard pattern for player view
    - Compares player vs position avg vs league avg
    - Uses subplots for multiple metrics
    """
    # GUARD: Only render for player view
    if not filters or filters.get('analysis_level') != 'player':
        return {"display": "none"}, "", html.Div()

    # Verificar disponibilidad de datos
    if not performance_data:
        return {"display": "block"}, "Comparación", html.Div(
            "No hay datos disponibles", className="text-center p-4"
        )

    try:
        player_name = filters.get('player', 'Jugador')

        # Si hay comparisons
        if 'comparisons' in performance_data:
            comparisons = performance_data['comparisons']

            # Extraer datos
            metrics = []
            player_values = []
            position_values = []
            league_values = []

            for metric, values in comparisons.items():
                if isinstance(values, dict):
                    player_val = values.get('player', 0)
                    position_val = values.get('position_avg', 0)
                    league_val = values.get('league_avg', 0)

                    # Formato más corto para métricas
                    display_metric = metric.replace("_", " ").title()
                    if len(display_metric) > 15:
                        display_metric = display_metric[:15] + "..."

                    metrics.append(display_metric)
                    player_values.append(player_val)
                    position_values.append(position_val)
                    league_values.append(league_val)

            if metrics:
                # Crear subplots
                fig = make_subplots(
                    rows=len(metrics),
                    cols=1,
                    subplot_titles=metrics,
                    vertical_spacing=0.05
                )

                # Colores
                colors = {
                    'player': '#3498db',
                    'position': '#e74c3c',
                    'league': '#2ecc71'
                }

                # Añadir barras para cada métrica
                for i, metric in enumerate(metrics):
                    p_val = player_values[i]
                    pos_val = position_values[i]
                    l_val = league_values[i]

                    fig.add_trace(
                        go.Bar(
                            x=[p_val],
                            y=[player_name],
                            orientation='h',
                            name=player_name if i == 0 else None,
                            marker_color=colors['player'],
                            showlegend=i == 0
                        ),
                        row=i+1, col=1
                    )

                    fig.add_trace(
                        go.Bar(
                            x=[pos_val],
                            y=["Posición"],
                            orientation='h',
                            name="Promedio Posición" if i == 0 else None,
                            marker_color=colors['position'],
                            showlegend=i == 0
                        ),
                        row=i+1, col=1
                    )

                    fig.add_trace(
                        go.Bar(
                            x=[l_val],
                            y=["Liga"],
                            orientation='h',
                            name="Promedio Liga" if i == 0 else None,
                            marker_color=colors['league'],
                            showlegend=i == 0
                        ),
                        row=i+1, col=1
                    )

                # Actualizar layout
                fig.update_layout(
                    height=100 + 150 * len(metrics),
                    title_text=f"Comparación de {player_name}",
                    margin=dict(t=80, l=120, r=50, b=50),
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="center",
                        x=0.5
                    ),
                    showlegend=True
                )

                return (
                    {"display": "block"},
                    f"Comparación - {player_name}",
                    dcc.Graph(figure=fig)
                )

        # Fallback
        return {"display": "block"}, f"Comparación - {player_name}", html.Div(
            "No hay datos suficientes", className="text-center p-4"
        )

    except Exception as e:
        return {"display": "block"}, "Error en Comparación", create_error_alert(
            str(e), "Error al generar comparación"
        )
