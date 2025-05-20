from dash import Input, Output, State, callback, html, dash_table, dcc, no_update
import dash
import dash_bootstrap_components as dbc
from dash.dcc.express import send_bytes, send_string
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
data_manager = HongKongDataManager(auto_load=True, background_preload=True)

# Agregar esta función helper al inicio del archivo (después de los imports):
def format_season_short(season):
    """Convierte '2024-25' a '24/25'"""
    if not season or '-' not in season:
        return season
    
    try:
        year1, year2 = season.split('-')
        short_year1 = year1[-2:]  # Últimos 2 dígitos
        short_year2 = year2[-2:]  # Últimos 2 dígitos
        return f"{short_year1}/{short_year2}"
    except:
        return season
    

# Callback para actualizar opciones de selectores basado en temporada
@callback(
    [Output('team-selector', 'options'),
    Output('player-selector', 'options')],
    [Input('season-selector', 'value'),
    Input('team-selector', 'value')],
    prevent_initial_call=False
)
def update_selector_options(season, selected_team):
    """Actualiza las opciones de equipos y jugadores según la temporada y equipo seleccionado."""
    
    # Actualizar temporada si es necesaria
    if season != data_manager.current_season:
        data_manager.refresh_data(season)
    
    # Opciones de equipos (siempre disponibles)
    teams = data_manager.get_available_teams()
    team_options = [{"label": f"🏆 {team}", "value": team} for team in teams]
    
    # Opciones de jugadores (basado en el equipo seleccionado)
    if selected_team:
        # Jugadores del equipo seleccionado
        players = data_manager.get_available_players(selected_team)
        player_options = [{"label": f"👤 {player}", "value": player} for player in players]
    else:
        # Todos los jugadores ordenados alfabéticamente
        players = data_manager.get_available_players()
        player_options = [{"label": f"👤 {player}", "value": player} for player in players]
    
    return team_options, player_options

# Callback principal para cargar datos con filtros aplicados
@callback(
    [Output('performance-data-store', 'data'),
    Output('chart-data-store', 'data'),
    Output('current-filters-store', 'data'),
    Output('status-alerts', 'children'),
    Output('season-selector', 'options')], 
    [Input('season-selector', 'value'),
    Input('team-selector', 'value'),
    Input('player-selector', 'value'),
    Input('position-filter', 'value'),
    Input('age-range', 'value')],
    prevent_initial_call=False
)
def load_performance_data(season, team, player, position_filter, age_range):
    """Carga los datos de performance según los filtros seleccionados."""
    
    try:
        # Generar opciones de temporadas dinámicamente
        available_seasons = data_manager.get_available_seasons()
        season_options = [
            {"label": format_season_short(s), "value": s} 
            for s in available_seasons
        ]

        # Si season es None, usar la temporada actual
        if not season:
            season = data_manager.current_season

        # Cambiar temporada si es necesario
        if season != data_manager.current_season:
            data_manager.refresh_data(season)
        
        # Guardar filtros actuales
        current_filters = {
            'season': season,
            'team': team,
            'player': player,
            'position_filter': position_filter,
            'age_range': age_range
        }
        
        # Determinar nivel de análisis basado en filtros
        if player:
            # Análisis de jugador específico
            analysis_level = 'player'
            performance_data = data_manager.get_player_overview(player, team)
            chart_data = data_manager.get_chart_data('player', player)
        elif team:
            # Análisis de equipo específico (con filtros aplicados)
            analysis_level = 'team'
            # Obtener datos del agregador directamente para aplicar filtros
            if data_manager.aggregator:
                performance_data = data_manager.aggregator.get_team_statistics(
                    team, position_filter, age_range
                )
                chart_data = data_manager.get_chart_data('team', team)
            else:
                performance_data = {"error": "Aggregator not initialized"}
                chart_data = {}
        else:
            # Análisis de toda la liga (con filtros aplicados)
            analysis_level = 'league'
            # Obtener datos del agregador directamente para aplicar filtros
            if data_manager.aggregator:
                performance_data = data_manager.aggregator.get_league_statistics(
                    position_filter, age_range
                )
                chart_data = data_manager.get_chart_data('league')
            else:
                performance_data = {"error": "Aggregator not initialized"}
                chart_data = {}
        
        # Agregar nivel de análisis a filtros
        current_filters['analysis_level'] = analysis_level
        
        # Alert de éxito mejorado
        if analysis_level == 'league':
                status_alert = dbc.Alert(
                    f"✅ Datos cargados exitosamente - Liga ({format_season_short(season)})",
                    color="success",
                    dismissable=True,
                    duration=3000
                )
        elif analysis_level == 'team':
            status_alert = dbc.Alert(
                f"✅ Datos cargados exitosamente - Equipo: {team} ({format_season_short(season)})",
                color="success",
                dismissable=True,
                duration=3000
            )
        elif analysis_level == 'player':
            player_message = f"✅ Datos cargados exitosamente - Jugador: {player}"
            if team:
                player_message += f" ({team})"
            status_alert = dbc.Alert(
                player_message,
                color="success",
                dismissable=True,
                duration=3000
            )
        
        return performance_data, chart_data, current_filters, status_alert, season_options
        
    except Exception as e:
        # Alert de error
        error_alert = dbc.Alert(
            f"❌ Error cargando datos: {str(e)}",
            color="danger",
            dismissable=True
        )
        
        # Opciones por defecto en caso de error
        default_seasons = [
            {"label": "24/25", "value": "2024-25"},
            {"label": "23/24", "value": "2023-24"},
            {"label": "22/23", "value": "2022-23"}
        ]
        
        return {}, {}, {}, error_alert, default_seasons

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
    
    # VALIDAR QUE FILTERS NO SEA None
    if filters is None or not isinstance(filters, dict):
        filters = {'analysis_level': 'league', 'season': 'N/A'}
    
    analysis_level = filters.get('analysis_level', 'league')
    season = filters.get('season', 'N/A')
    
    # Aplicar filtros en el título
    filter_info = []
    if filters.get('position_filter') and filters.get('position_filter') != 'all':
        filter_info.append(f"Pos: {filters['position_filter']}")
    if filters.get('age_range') and filters['age_range'] != [15, 45]:
        filter_info.append(f"Edad: {filters['age_range'][0]}-{filters['age_range'][1]}")
    
    filter_suffix = f" ({', '.join(filter_info)})" if filter_info else ""
    
    # KPIs para la liga
    if analysis_level == 'league' and 'overview' in performance_data:
        overview = performance_data['overview']
        title = f"Liga de Hong Kong - {season}{filter_suffix}"
        
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
        title = f"{overview.get('team_name', 'Equipo')} - {season}{filter_suffix}"
        
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
    
    # VALIDAR QUE FILTERS NO SEA None
    if filters is None or not isinstance(filters, dict):
        filters = {'analysis_level': 'league'}
    
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
    
    # VALIDAR QUE FILTERS NO SEA None
    if filters is None or not isinstance(filters, dict):
        filters = {'analysis_level': 'league'}
    
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
    """Actualiza la sección de top performers - TOP 10."""
    
    if not performance_data:
        return html.Div("No hay datos disponibles", className="text-center p-4")
    
    # VALIDAR QUE FILTERS NO SEA None
    if filters is None or not isinstance(filters, dict):
        filters = {'analysis_level': 'league'}
    
    analysis_level = filters.get('analysis_level', 'league')
    
    try:
        if analysis_level in ['league', 'team'] and 'top_performers' in performance_data:
            performers = performance_data['top_performers']
            
            # Crear tabs para diferentes categorías
            tabs = []
            
            if 'top_scorers' in performers:
                tab_content = []
                for i, player in enumerate(performers['top_scorers'][:10], 1):  # TOP 10
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
                for i, player in enumerate(performers['top_assisters'][:10], 1):  # TOP 10
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
    
    # VALIDAR QUE FILTERS NO SEA None
    if filters is None or not isinstance(filters, dict):
        filters = {'analysis_level': 'league'}
    
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
    [Input('current-filters-store', 'data')],
    prevent_initial_call=True  # AGREGAR ESTO PARA EVITAR EJECUCIÓN CON DATOS VACÍOS
)
def toggle_comparison_chart(filters):
    """Controla la visibilidad del gráfico de comparación."""
    
    # VALIDAR QUE FILTERS NO SEA None
    if filters is None or not isinstance(filters, dict):
        return {"display": "none"}, ""
    
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
    
    # Variables para debugging
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    try:
        # Verificar datos básicos
        if not performance_data:
            raise ValueError("No hay datos de performance disponibles")
        
        if not filters:
            filters = {"analysis_level": "league"}  # Valor por defecto
        
        # Importar generador
        from utils.pdf_generator import SportsPDFGenerator
        
        # Determinar análisis level y filename
        analysis_level = filters.get('analysis_level', 'league')
        season = filters.get('season', 'unknown')
        
        if analysis_level == 'team':
            filename = f"reporte_performance_{filters.get('team', 'equipo')}_{season}_{timestamp}.pdf"
        elif analysis_level == 'player':
            filename = f"reporte_performance_{filters.get('player', 'jugador')}_{season}_{timestamp}.pdf"
        else:
            filename = f"reporte_performance_liga_{season}_{timestamp}.pdf"
        
        # Generar PDF
        pdf_generator = SportsPDFGenerator()
        pdf_buffer = pdf_generator.create_performance_report(performance_data, filters)
        
        # Usar send_bytes para manejar automáticamente los bytes
        return send_bytes(pdf_buffer.getvalue(), filename)
        
    except Exception as e:
        # En caso de error, crear un archivo de texto con información de debug
        error_content = f"""ERROR GENERANDO PDF
========================

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Error: {str(e)}
Tipo de error: {type(e).__name__}

Información de debug:
- Performance data disponible: {performance_data is not None}
- Performance data type: {type(performance_data)}
- Filters: {filters}
- Analysis level: {filters.get('analysis_level') if filters else 'No filters'}

Performance data keys: {list(performance_data.keys()) if isinstance(performance_data, dict) else 'No es dict'}

Traceback completo:
{str(e)}
"""
        
        # Crear archivo de error usando dcc.send_string
        return send_string(error_content, f"error_export_{timestamp}.txt")