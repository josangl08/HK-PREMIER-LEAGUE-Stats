from dash import Input, Output, State, callback, html, dash_table, dcc
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import json
from dash.exceptions import PreventUpdate
from datetime import datetime

# Importar nuestro gestor de datos
from data import HongKongDataManager

# Inicializar el gestor de datos globalmente
data_manager = HongKongDataManager()

# Callback para manejar la habilitación de selectores
@callback(
    [Output('team-selector', 'disabled'),
     Output('player-selector', 'disabled'),
     Output('team-selector', 'options'),
     Output('player-selector', 'options'),
     Output('team-selector', 'value'),
     Output('player-selector', 'value')],
    [Input('analysis-level', 'value'),
     Input('team-selector', 'value')]
)
def update_selector_states(analysis_level, selected_team):
    """Actualiza el estado de los selectores según el nivel de análisis."""
    
    # Estados de los selectores
    team_disabled = analysis_level == 'league'
    player_disabled = analysis_level != 'player'
    
    # Opciones de equipos
    teams = data_manager.get_available_teams()
    team_options = [{"label": team, "value": team} for team in teams]
    
    # Opciones de jugadores (basado en el equipo seleccionado)
    if selected_team and analysis_level == 'player':
        players = data_manager.get_available_players(selected_team)
        player_options = [{"label": player, "value": player} for player in players]
    else:
        players = data_manager.get_available_players()
        player_options = [{"label": player, "value": player} for player in players]
    
    # Valores de los selectores
    team_value = None if team_disabled else selected_team
    player_value = None if player_disabled else None
    
    return (team_disabled, player_disabled, team_options, player_options, 
            team_value, player_value)

# Callback principal para cargar datos
@callback(
    [Output('performance-data-store', 'data'),
     Output('chart-data-store', 'data'),
     Output('current-filters-store', 'data'),
     Output('status-alerts', 'children')],
    [Input('analysis-level', 'value'),
     Input('team-selector', 'value'),
     Input('player-selector', 'value'),
     Input('position-filter', 'value'),
     Input('age-range', 'value'),
     Input('refresh-button', 'n_clicks')],
    prevent_initial_call=False
)
def load_performance_data(analysis_level, team, player, position_filter, age_range, n_clicks):
    """Carga los datos de performance según los filtros seleccionados."""
    
    try:
        # Guardar filtros actuales
        current_filters = {
            'analysis_level': analysis_level,
            'team': team,
            'player': player,
            'position_filter': position_filter,
            'age_range': age_range
        }
        
        # Obtener datos según el nivel
        if analysis_level == 'league':
            performance_data = data_manager.get_league_overview()
            chart_data = data_manager.get_chart_data('league')
        elif analysis_level == 'team' and team:
            performance_data = data_manager.get_team_overview(team)
            chart_data = data_manager.get_chart_data('team', team)
        elif analysis_level == 'player' and player:
            performance_data = data_manager.get_player_overview(player, team)
            chart_data = data_manager.get_chart_data('player', player)
        else:
            # Estado inicial o filtros incompletos
            performance_data = {"info": "Selecciona filtros para ver datos"}
            chart_data = {}
        
        # Alert de éxito
        status_alert = dbc.Alert(
            "✅ Datos cargados exitosamente",
            color="success",
            dismissable=True,
            duration=3000
        )
        
        return performance_data, chart_data, current_filters, status_alert
        
    except Exception as e:
        # Alert de error
        error_alert = dbc.Alert(
            f"❌ Error cargando datos: {str(e)}",
            color="danger",
            dismissable=True
        )
        return {}, {}, {}, error_alert

# Callback para actualizar KPIs principales
@callback(
    [Output('kpi-title', 'children'),
     Output('main-kpis', 'children')],
    [Input('performance-data-store', 'data'),
     Input('current-filters-store', 'data')]
)
def update_main_kpis(performance_data, filters):
    """Actualiza los KPIs principales según los datos."""
    
    if not performance_data or 'error' in performance_data:
        return "Sin datos disponibles", html.Div("Selecciona filtros válidos")
    
    analysis_level = filters.get('analysis_level', 'league')
    
    # KPIs para la liga
    if analysis_level == 'league' and 'overview' in performance_data:
        overview = performance_data['overview']
        title = f"Liga de Hong Kong - Temporada {overview.get('season', 'N/A')}"
        
        kpis = dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(overview.get('total_players', 0), className="text-primary"),
                        html.P("Jugadores", className="card-text")
                    ])
                ])
            ], md=2),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(overview.get('total_teams', 0), className="text-success"),
                        html.P("Equipos", className="card-text")
                    ])
                ])
            ], md=2),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(overview.get('total_goals', 0), className="text-warning"),
                        html.P("Goles Totales", className="card-text")
                    ])
                ])
            ], md=2),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(overview.get('total_assists', 0), className="text-info"),
                        html.P("Asistencias", className="card-text")
                    ])
                ])
            ], md=2),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(f"{overview.get('average_age', 0)}", className="text-secondary"),
                        html.P("Edad Promedio", className="card-text")
                    ])
                ])
            ], md=2),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(f"{overview.get('avg_goals_per_player', 0)}", className="text-primary"),
                        html.P("Goles/Jugador", className="card-text")
                    ])
                ])
            ], md=2)
        ])
        
        return title, kpis
    
    # KPIs para equipo
    elif analysis_level == 'team' and 'overview' in performance_data:
        overview = performance_data['overview']
        title = f"{overview.get('team_name', 'Equipo')} - Temporada {overview.get('season', 'N/A')}"
        
        kpis = dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(overview.get('total_players', 0), className="text-primary"),
                        html.P("Jugadores", className="card-text")
                    ])
                ])
            ], md=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(overview.get('total_goals', 0), className="text-warning"),
                        html.P("Goles Totales", className="card-text")
                    ])
                ])
            ], md=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(overview.get('total_assists', 0), className="text-info"),
                        html.P("Asistencias", className="card-text")
                    ])
                ])
            ], md=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(f"{overview.get('avg_age', 0)}", className="text-secondary"),
                        html.P("Edad Promedio", className="card-text")
                    ])
                ])
            ], md=3)
        ])
        
        return title, kpis
    
    # KPIs para jugador
    elif analysis_level == 'player' and 'basic_info' in performance_data:
        basic_info = performance_data['basic_info']
        performance_stats = performance_data.get('performance_stats', {})
        title = f"{basic_info.get('name', 'Jugador')} - {basic_info.get('team', 'N/A')}"
        
        kpis = dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(basic_info.get('age', 'N/A'), className="text-primary"),
                        html.P("Edad", className="card-text")
                    ])
                ])
            ], md=2),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(basic_info.get('matches_played', 0), className="text-success"),
                        html.P("Partidos", className="card-text")
                    ])
                ])
            ], md=2),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(performance_stats.get('goals', 0), className="text-warning"),
                        html.P("Goles", className="card-text")
                    ])
                ])
            ], md=2),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(performance_stats.get('assists', 0), className="text-info"),
                        html.P("Asistencias", className="card-text")
                    ])
                ])
            ], md=2),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(basic_info.get('position_group', 'N/A'), className="text-secondary"),
                        html.P("Posición", className="card-text")
                    ])
                ])
            ], md=2),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(f"{performance_stats.get('minutes_per_match', 0):.0f}", className="text-primary"),
                        html.P("Min/Partido", className="card-text")
                    ])
                ])
            ], md=2)
        ])
        
        return title, kpis
    
    return "Datos no disponibles", html.Div("Error procesando datos")

# Callback para gráfico principal
@callback(
    Output('main-chart-container', 'children'),
    [Input('chart-data-store', 'data'),
     Input('current-filters-store', 'data')]
)
def update_main_chart(chart_data, filters):
    """Actualiza el gráfico principal según los datos."""
    
    if not chart_data:
        return html.Div("No hay datos disponibles para mostrar", className="text-center p-4")
    
    analysis_level = filters.get('analysis_level', 'league')
    
    try:
        # Gráfico para liga - Goles por equipo
        if analysis_level == 'league' and 'team_goals' in chart_data:
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
        
        # Gráfico para equipo - Distribución de minutos
        elif analysis_level == 'team' and 'player_minutes' in chart_data:
            data = chart_data['player_minutes']
            fig = px.bar(
                x=data['players'],
                y=data['minutes'],
                title="Minutos Jugados por Jugador",
                labels={'x': 'Jugadores', 'y': 'Minutos'},
                color=data['minutes'],
                color_continuous_scale='Greens'
            )
            fig.update_layout(height=400, showlegend=False)
            fig.update_xaxes(tickangle=45)
            return dcc.Graph(figure=fig)
        
        # Gráfico para jugador - Radar chart
        elif analysis_level == 'player' and 'player_vs_position_radar' in chart_data:
            data = chart_data['player_vs_position_radar']
            
            fig = go.Figure()
            
            # Agregar línea del jugador
            fig.add_trace(go.Scatterpolar(
                r=data['player_values'],
                theta=data['metrics'],
                fill='toself',
                name='Jugador',
                line=dict(color='blue')
            ))
            
            # Agregar línea promedio de posición
            fig.add_trace(go.Scatterpolar(
                r=data['position_avg'],
                theta=data['metrics'],
                fill='toself',
                name='Promedio Posición',
                line=dict(color='red'),
                opacity=0.6
            ))
            
            fig.update_layout(
                title="Comparación vs Promedio de Posición",
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, max(max(data['player_values']), max(data['position_avg'])) * 1.1]
                    )
                ),
                height=400
            )
            return dcc.Graph(figure=fig)
        
        else:
            return html.Div("Gráfico no disponible para estos filtros", className="text-center p-4")
            
    except Exception as e:
        return html.Div(f"Error generando gráfico: {str(e)}", className="text-center p-4 text-danger")

# Callback para gráfico secundario
@callback(
    Output('secondary-chart-container', 'children'),
    [Input('chart-data-store', 'data'),
     Input('current-filters-store', 'data')]
)
def update_secondary_chart(chart_data, filters):
    """Actualiza el gráfico secundario según los datos."""
    
    if not chart_data:
        return html.Div("No hay datos disponibles", className="text-center p-4")
    
    analysis_level = filters.get('analysis_level', 'league')
    
    try:
        # Gráfico para liga - Distribución por posición
        if analysis_level == 'league' and 'position_distribution' in chart_data:
            data = chart_data['position_distribution']
            fig = px.pie(
                values=data['counts'],
                names=data['positions'],
                title="Distribución por Posición"
            )
            fig.update_layout(height=400)
            return dcc.Graph(figure=fig)
        
        # Gráfico para equipo - Edad vs Goles
        elif analysis_level == 'team' and 'age_vs_goals' in chart_data:
            data = chart_data['age_vs_goals']
            fig = px.scatter(
                x=data['ages'],
                y=data['goals'],
                hover_name=data['players'],
                title="Edad vs Goles",
                labels={'x': 'Edad', 'y': 'Goles'}
            )
            fig.update_layout(height=400)
            return dcc.Graph(figure=fig)
        
        # Gráfico para jugador - Percentiles
        elif analysis_level == 'player' and 'player_percentiles' in chart_data:
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
            return html.Div("Gráfico secundario no disponible", className="text-center p-4")
            
    except Exception as e:
        return html.Div(f"Error generando gráfico: {str(e)}", className="text-center p-4 text-danger")

# Callback para top performers
@callback(
    Output('top-performers-container', 'children'),
    [Input('performance-data-store', 'data'),
     Input('current-filters-store', 'data')]
)
def update_top_performers(performance_data, filters):
    """Actualiza la sección de top performers."""
    
    if not performance_data:
        return html.Div("No hay datos disponibles", className="text-center p-4")
    
    analysis_level = filters.get('analysis_level', 'league')
    
    try:
        if analysis_level == 'league' and 'top_performers' in performance_data:
            performers = performance_data['top_performers']
            
            # Crear tabs para diferentes categorías
            tabs = []
            
            if 'top_scorers' in performers:
                tab_content = []
                for i, player in enumerate(performers['top_scorers'][:5], 1):
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
                for i, player in enumerate(performers['top_assisters'][:5], 1):
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
        
        elif analysis_level == 'team' and 'top_players' in performance_data:
            top_players = performance_data['top_players']
            
            content = []
            if 'top_scorer' in top_players:
                player = top_players['top_scorer']
                content.append(
                    dbc.ListGroupItem([
                        html.H6("🥅 Máximo Goleador", className="mb-1"),
                        html.P(f"{player['name']} - {player['goals']} goles", className="mb-1"),
                        html.Small(f"Posición: {player.get('position', 'N/A')}", className="text-muted")
                    ])
                )
            
            if 'top_assister' in top_players:
                player = top_players['top_assister']
                content.append(
                    dbc.ListGroupItem([
                        html.H6("🎯 Máximo Asistente", className="mb-1"),
                        html.P(f"{player['name']} - {player['assists']} asistencias", className="mb-1"),
                        html.Small(f"Posición: {player.get('position', 'N/A')}", className="text-muted")
                    ])
                )
            
            if 'most_played' in top_players:
                player = top_players['most_played']
                content.append(
                    dbc.ListGroupItem([
                        html.H6("⏱️ Más Minutos", className="mb-1"),
                        html.P(f"{player['name']} - {player['minutes']} min", className="mb-1"),
                        html.Small(f"Partidos: {player.get('matches', 'N/A')}", className="text-muted")
                    ])
                )
            
            return dbc.ListGroup(content, flush=True)
        
        else:
            return html.Div("Top performers no disponible para este nivel", className="text-center p-4")
            
    except Exception as e:
        return html.Div(f"Error: {str(e)}", className="text-center p-4 text-danger")

# Callback para análisis por posición
@callback(
    Output('position-analysis-container', 'children'),
    [Input('performance-data-store', 'data'),
     Input('current-filters-store', 'data')]
)
def update_position_analysis(performance_data, filters):
    """Actualiza el análisis por posición."""
    
    if not performance_data:
        return html.Div("No hay datos disponibles", className="text-center p-4")
    
    analysis_level = filters.get('analysis_level', 'league')
    
    try:
        if analysis_level == 'league' and 'position_analysis' in performance_data:
            positions = performance_data['position_analysis']
            
            cards = []
            for position, stats in positions.items():
                card = dbc.Card([
                    dbc.CardBody([
                        html.H6(position, className="card-title"),
                        html.P(f"Jugadores: {stats['player_count']}", className="card-text"),
                        html.P(f"Goles: {stats['total_goals']}", className="card-text"),
                        html.P(f"Edad promedio: {stats['avg_age']}", className="card-text"),
                        html.Small(f"Min. promedio: {stats['avg_minutes']}", className="text-muted")
                    ])
                ], className="h-100")
                
                cards.append(dbc.Col(card, md=6, lg=4, className="mb-3"))
            
            return dbc.Row(cards)
        
        elif analysis_level == 'team' and 'position_breakdown' in performance_data:
            breakdown = performance_data['position_breakdown']
            
            cards = []
            for position, stats in breakdown.items():
                card = dbc.Card([
                    dbc.CardBody([
                        html.H6(position, className="card-title"),
                        html.P(f"Jugadores: {stats['count']}", className="card-text"),
                        html.P(f"Goles: {stats['total_goals']}", className="card-text"),
                        html.P(f"Asistencias: {stats['total_assists']}", className="card-text"),
                        html.Small(f"Edad promedio: {stats['avg_age']}", className="text-muted")
                    ])
                ], className="h-100")
                
                cards.append(dbc.Col(card, md=6, lg=4, className="mb-3"))
            
            return dbc.Row(cards)
        
        else:
            return html.Div("Análisis por posición no disponible", className="text-center p-4")
            
    except Exception as e:
        return html.Div(f"Error: {str(e)}", className="text-center p-4 text-danger")

# Callback para controlar visibilidad del gráfico de comparación
@callback(
    [Output('comparison-card', 'style'),
     Output('comparison-chart-title', 'children')],
    [Input('current-filters-store', 'data')]
)
def toggle_comparison_chart(filters):
    """Controla la visibilidad del gráfico de comparación."""
    
    analysis_level = filters.get('analysis_level', 'league')
    
    if analysis_level in ['team', 'player']:
        return {"display": "block"}, f"Comparación - {analysis_level.title()}"
    else:
        return {"display": "none"}, ""

# Callback para exportar PDF
@callback(
    Output('download-performance-pdf', 'data'),
    [Input('export-pdf-button', 'n_clicks')],
    [State('performance-data-store', 'data'),
     State('current-filters-store', 'data')],
    prevent_initial_call=True
)
def export_performance_pdf(n_clicks, performance_data, filters):
    """Exporta el reporte de performance a PDF."""
    
    if n_clicks is None:
        raise PreventUpdate
    
    try:
        # Aquí implementaremos la generación de PDF
        # Por ahora retornamos un mensaje placeholder
        
        analysis_level = filters.get('analysis_level', 'league')
        
        # Generar nombre de archivo
        if analysis_level == 'team':
            filename = f"performance_report_{filters.get('team', 'team')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        elif analysis_level == 'player':
            filename = f"performance_report_{filters.get('player', 'player')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        else:
            filename = f"performance_report_league_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        # TODO: Implementar generación real de PDF
        # Por ahora, simulamos devolviendo un archivo de texto
        content = f"Reporte de Performance - {analysis_level}\n"
        content += f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += json.dumps(performance_data, indent=2)
        
        return {
            'content': content,
            'filename': filename,
            'type': 'text/plain'
        }
        
    except Exception as e:
        raise PreventUpdate