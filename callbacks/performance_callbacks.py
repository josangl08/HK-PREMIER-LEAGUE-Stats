from dash import Input, Output, State, callback, html, dash_table, dcc, no_update
import dash_bootstrap_components as dbc
from dash.dcc.express import send_bytes, send_string
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from dash.exceptions import PreventUpdate
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
    
    # Validación de filtros
    if filters is None or not isinstance(filters, dict):
        filters = {'analysis_level': 'league'}
    
    analysis_level = filters.get('analysis_level', 'league')
    
    try:
        # NIVEL LIGA: Gráfico de goles por equipo
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
        
        # NIVEL EQUIPO: Distribución de minutos o análisis de equipo
        elif analysis_level == 'team':
            team_name = filters.get('team', 'Equipo')
            
            # Primera opción: Distribución de minutos por jugador
            if 'player_minutes' in chart_data:
                data = chart_data['player_minutes']
                
                fig = px.bar(
                    x=data['players'],
                    y=data['minutes'],
                    title=f"Minutos Jugados por Jugador - {team_name}",
                    labels={'x': 'Jugadores', 'y': 'Minutos'},
                    color=data['minutes'],
                    color_continuous_scale='Greens'
                )
                fig.update_layout(
                    height=400, 
                    showlegend=False,
                    xaxis={'categoryorder':'total descending'}
                )
                fig.update_xaxes(tickangle=45)
                return dcc.Graph(figure=fig)
            
            # Segunda opción: Si hay squad_analysis
            elif 'squad_analysis' in chart_data:
                squad_data = chart_data.get('squad_analysis', {})
                
                # Verificar si hay datos de edad
                if 'age_stats' in squad_data:
                    age_data = squad_data['age_stats']
                    
                    # Crear un gráfico de radar para distribución de edad
                    age_labels = ['Youngest', 'Average', 'Oldest']
                    age_values = [
                        age_data.get('youngest', 0),
                        age_data.get('average', 0),
                        age_data.get('oldest', 0)
                    ]
                    
                    # Crear gráfico de gauge para edades
                    fig = go.Figure()
                    
                    fig.add_trace(go.Indicator(
                        mode = "gauge+number",
                        value = age_data.get('average', 0),
                        title = {'text': f"Edad Promedio - {team_name}"},
                        gauge = {
                            'axis': {'range': [15, 40]},
                            'bar': {'color': "#2ecc71"},
                            'steps': [
                                {'range': [15, 23], 'color': "#3498db"},  # Jóvenes
                                {'range': [23, 30], 'color': "#2ecc71"},  # Madurez
                                {'range': [30, 40], 'color': "#f39c12"}   # Veteranos
                            ],
                            'threshold': {
                                'line': {'color': "red", 'width': 4},
                                'thickness': 0.75,
                                'value': age_data.get('average', 0)
                            }
                        }
                    ))
                    
                    fig.update_layout(
                        height=400,
                        margin=dict(l=20, r=20, t=50, b=20)
                    )
                    
                    return dcc.Graph(figure=fig)
            
            # Tercera opción: Crear un gráfico genérico si no hay datos específicos
            return html.Div([
                html.H4(f"Análisis de Equipo - {team_name}", className="text-center"),
                html.P("Seleccione diferentes filtros para ver análisis detallados del equipo", 
                    className="text-center text-muted")
            ], className="p-5 text-center")
        
        # NIVEL JUGADOR: SOLUCIÓN PARA EL RADAR CHART
        if analysis_level == 'player' and 'player_vs_position_radar' in chart_data:
            data = chart_data['player_vs_position_radar']
            player_name = filters.get('player', 'Jugador')
            
            # Extraer datos del radar
            metrics = data.get('metrics', [])
            player_values = data.get('player_values', [])
            position_avg = data.get('position_avg', [])
            
            # Verificar datos suficientes
            if not metrics or not player_values or not position_avg:
                return html.Div("No hay datos suficientes para el radar chart", className="text-center p-4")
            
            # NORMALIZACIÓN MEJORADA
            # Para cada métrica, calculamos un factor para amplificar las diferencias
            normalized_player = []
            normalized_position = []
            
            for i, metric in enumerate(metrics):
                if i < len(player_values) and i < len(position_avg):
                    # Obtener valores
                    p_val = player_values[i]
                    pos_val = position_avg[i]
                    
                    # Si ambos valores son cercanos a cero, usamos valores base
                    if abs(p_val) < 0.001 and abs(pos_val) < 0.001:
                        normalized_player.append(30)  # Valor base arbitrario
                        normalized_position.append(25)  # Ligeramente menor para comparación
                        continue
                    
                    # Calculamos el valor máximo para la normalización
                    max_val = max(p_val, pos_val) * 1.2
                    
                    # Si la diferencia entre valores es muy pequeña, amplificamos
                    if abs(p_val - pos_val) < max_val * 0.1:  # Si la diferencia es menor al 10%
                        # Calculamos la diferencia relativa y la amplificamos
                        base = min(p_val, pos_val)
                        diff = abs(p_val - pos_val)
                        
                        # Amplificamos la diferencia (hacemos que sea al menos 20% del valor base)
                        amplified_diff = max(diff, base * 0.2)
                        
                        if p_val >= pos_val:
                            normalized_player.append(base + amplified_diff)
                            normalized_position.append(base)
                        else:
                            normalized_player.append(base)
                            normalized_position.append(base + amplified_diff)
                    else:
                        # Si la diferencia ya es significativa, normalizamos proporcional a 90
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
                line=dict(color='#2980b9', width=3)  # Azul y más gruesa
            ))
            
            # Añadir trace de posición
            fig.add_trace(go.Scatterpolar(
                r=normalized_position,
                theta=metrics,
                fill='toself',
                name='Promedio Posición',
                line=dict(color='#e74c3c', width=2, dash='dot'),  # Roja y punteada
                opacity=0.65
            ))
            
            # Configuración del layout
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100],  # Fijamos escala de 0 a 100
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
                height=500,  # Hacerlo más grande
                margin=dict(t=80, b=100, l=80, r=80),  # Más espacio
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
            return html.Div("Gráfico no disponible para estos filtros", className="text-center p-4")
            
    except Exception as e:
        return html.Div([
            html.H4("Error en el Gráfico Principal", className="text-center text-danger"),
            html.Pre(f"Error: {str(e)}", className="border p-2 bg-light small")
        ])

# Callback para gráfico secundario
@callback(
    Output('secondary-chart-container', 'children'),
    [Input('chart-data-store', 'data'),
    Input('current-filters-store', 'data')]
)
def update_secondary_chart(chart_data, filters):
    """Actualiza el gráfico secundario con una visualización de edad vs rendimiento."""
    
    if not chart_data:
        return html.Div("No hay datos disponibles", className="text-center p-4")
    
    # VALIDAR QUE FILTERS NO SEA None
    if filters is None or not isinstance(filters, dict):
        filters = {'analysis_level': 'league'}
    
    analysis_level = filters.get('analysis_level', 'league')
    
    try:
        # NUEVO: Gráfico de Dispersión de Edad vs. Rendimiento (para nivel liga)
        if analysis_level == 'league' and 'age_performance' in chart_data:
            data = chart_data.get('age_performance', {})
            
            if data and 'ages' in data and 'goals' in data:
                # Crear un DataFrame para facilitar el manejo
                df = pd.DataFrame({
                    'Edad': data['ages'],
                    'Goles': data['goals'],
                    'Jugadores': data['players'],
                    'Posición': data.get('positions', ['Unknown'] * len(data['ages'])),
                    'Equipo': data.get('teams', ['Unknown'] * len(data['ages']))
                })
                
                # Calcular promedio de goles por edad para añadir línea de tendencia
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
                    text=df['Jugadores'] + '<br>Equipo: ' + df['Equipo'] + '<br>Posición: ' + df['Posición'],
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
        
        # Original: Distribución por posición (fallback)
        elif analysis_level == 'league' and 'position_distribution' in chart_data:
            data = chart_data['position_distribution']
            fig = px.pie(
                values=data['counts'],
                names=data['positions'],
                title="Distribución por Posición"
            )
            fig.update_layout(height=400)
            return dcc.Graph(figure=fig)
        
        # Gráfico para equipo - Edad vs Goles (original)
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
        
        # Gráfico para jugador - Percentiles (original)
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
    
    # VALIDAR QUE FILTERS NO SEA None
    if filters is None or not isinstance(filters, dict):
        filters = {'analysis_level': 'league'}
    
    analysis_level = filters.get('analysis_level', 'league')
    
    try:
        # NIVEL LIGA: Tabs con top performers por diferentes métricas
        if analysis_level == 'league' and 'top_performers' in performance_data:
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
        
        # NIVEL EQUIPO: Lista de jugadores clave del equipo
        elif analysis_level == 'team':
                team_name = filters.get('team', 'Equipo')
                
                # Verificar estructura de datos del equipo
                # Primero, intentar con top_players
                if 'top_players' in performance_data:
                    top_players = performance_data['top_players']
                    
                    # Crear cards para los jugadores destacados (verificando cada clave)
                    card_content = []
                    
                    # Máximo goleador
                    if 'top_scorer' in top_players and top_players['top_scorer']:
                        scorer = top_players['top_scorer']
                        card_content.append(
                            dbc.Card([
                                dbc.CardHeader("Máximo Goleador"),
                                dbc.CardBody([
                                    html.H5(scorer.get('name', 'N/A'), className="card-title"),
                                    html.P(f"{scorer.get('goals', 0)} goles", className="card-text"),
                                    html.Small(scorer.get('position', ''), className="text-muted")
                                ])
                            ], className="h-100")
                        )
                    
                    # Máximo asistente
                    if 'top_assister' in top_players and top_players['top_assister']:
                        assister = top_players['top_assister']
                        card_content.append(
                            dbc.Card([
                                dbc.CardHeader("Máximo Asistente"),
                                dbc.CardBody([
                                    html.H5(assister.get('name', 'N/A'), className="card-title"),
                                    html.P(f"{assister.get('assists', 0)} asistencias", className="card-text"),
                                    html.Small(assister.get('position', ''), className="text-muted")
                                ])
                            ], className="h-100")
                        )
                    
                    # Jugador con más minutos
                    if 'most_played' in top_players and top_players['most_played']:
                        played = top_players['most_played']
                        card_content.append(
                            dbc.Card([
                                dbc.CardHeader("Más Minutos"),
                                dbc.CardBody([
                                    html.H5(played.get('name', 'N/A'), className="card-title"),
                                    html.P(f"{played.get('minutes', 0)} minutos", className="card-text"),
                                    html.Small(f"{played.get('matches', 0)} partidos", className="text-muted")
                                ])
                            ], className="h-100")
                        )
                    
                    # Si no encontramos cards, crear una alternativa
                    if not card_content:
                        # Si top_players existe pero está vacío, crear tarjeta genérica
                        return html.Div([
                            html.H4(f"Jugadores Destacados - {team_name}", className="text-center mb-3"),
                            dbc.Alert(
                                "No hay datos detallados disponibles para los jugadores de este equipo",
                                color="info"
                            )
                        ])
                    
                    # Crear filas con las cards
                    rows = []
                    for i in range(0, len(card_content), 2):
                        cards_in_row = card_content[i:i+2]
                        row = dbc.Row([
                            dbc.Col(card, md=6, className="mb-3")
                            for card in cards_in_row
                        ])
                        rows.append(row)
                    
                    return html.Div([
                        html.H4(f"Jugadores Destacados - {team_name}", className="text-center mb-3"),
                        html.Div(rows)
                    ])
                
                # Si no hay top_players, usar datos de overview
                if 'overview' in performance_data:
                    overview = performance_data['overview']
                    
                    # Crear una tarjeta de estadísticas del equipo
                    return html.Div([
                        html.H4(f"Estadísticas del Equipo - {team_name}", className="text-center mb-3"),
                        dbc.Card([
                            dbc.CardHeader("Resumen del Equipo"),
                            dbc.CardBody([
                                dbc.Row([
                                    dbc.Col([
                                        html.H5("Estadísticas Ofensivas", className="mb-3"),
                                        html.P([
                                            html.Strong("Total Goles: "), 
                                            html.Span(overview.get('total_goals', 0))
                                        ]),
                                        html.P([
                                            html.Strong("Total Asistencias: "), 
                                            html.Span(overview.get('total_assists', 0))
                                        ]),
                                        html.P([
                                            html.Strong("Goles por Jugador: "), 
                                            html.Span(f"{overview.get('goals_per_player', 0):.2f}")
                                        ])
                                    ], md=6),
                                    dbc.Col([
                                        html.H5("Estadísticas del Plantel", className="mb-3"),
                                        html.P([
                                            html.Strong("Jugadores: "), 
                                            html.Span(overview.get('total_players', 0))
                                        ]),
                                        html.P([
                                            html.Strong("Edad Promedio: "), 
                                            html.Span(f"{overview.get('avg_age', 0):.1f} años")
                                        ]),
                                        html.P([
                                            html.Strong("Minutos Totales: "), 
                                            html.Span(overview.get('total_minutes', 0))
                                        ])
                                    ], md=6)
                                ])
                            ])
                        ])
                    ])
                
                # Fallback final
                return html.Div([
                    html.H4(f"Equipo: {team_name}", className="text-center"),
                    dbc.Alert(
                        "No se encontraron datos de jugadores destacados para este equipo.",
                        color="warning"
                    )
                ])
                
            
        # Fallback: Buscar datos de squad_analysis
        elif 'squad_analysis' in performance_data:
            squad = performance_data.get('squad_analysis', {})
            
            # Crear un informe de equipo con los datos disponibles
            info_sections = []
            
            # Distribución por posición
            if 'position_distribution' in squad:
                pos_dist = squad['position_distribution']
                pos_items = [
                    html.Li(f"{pos}: {count} jugadores")
                    for pos, count in pos_dist.items()
                ]
                
                info_sections.append(
                    dbc.Card([
                        dbc.CardHeader("Distribución por Posición"),
                        dbc.CardBody([
                            html.Ul(pos_items)
                        ])
                    ], className="mb-3")
                )
            
            # Distribución por edad
            if 'age_stats' in squad:
                age_stats = squad['age_stats']
                
                info_sections.append(
                    dbc.Card([
                        dbc.CardHeader("Estadísticas de Edad"),
                        dbc.CardBody([
                            html.P([
                                html.Strong("Promedio: "), 
                                f"{age_stats.get('average', 0):.1f} años"
                            ]),
                            html.P([
                                html.Strong("Jugador más joven: "), 
                                f"{age_stats.get('youngest', 0)} años"
                            ]),
                            html.P([
                                html.Strong("Jugador más veterano: "), 
                                f"{age_stats.get('oldest', 0)} años"
                            ])
                        ])
                    ], className="mb-3")
                )
            
            # Organizar cards en columnas
            # Extract team name from filters
            team_name = filters.get('team', 'Equipo')
            return html.Div([
                html.H4(f"Análisis de Plantel - {team_name}", className="mb-3"),
                dbc.Row([
                    dbc.Col(section, md=6) for section in info_sections
                ])
            ])
            
        # NIVEL JUGADOR: Tarjeta de perfil del jugador
        elif analysis_level == 'player' and 'basic_info' in performance_data:
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
                            html.H6(f"{team} | {position}", className="card-subtitle text-muted mb-3"),
                            html.Div([
                                html.P([
                                    html.Strong("Edad: "), 
                                    html.Span(f"{player_info.get('age', 'N/A')} años")
                                ]),
                                html.P([
                                    html.Strong("Partidos: "), 
                                    html.Span(player_info.get('matches_played', 'N/A'))
                                ]),
                                html.P([
                                    html.Strong("Minutos: "), 
                                    html.Span(player_info.get('minutes_played', 'N/A'))
                                ])
                            ])
                        ], md=6),
                        
                        # Columna de estadísticas
                        dbc.Col([
                            html.H5("Estadísticas Ofensivas", className="card-title"),
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
                                    html.Span(f"{performance_stats.get('minutes_per_match', 0):.1f}")
                                ])
                            ])
                        ], md=6)
                    ])
                ])
            ])
            
            return profile_card
        
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
                        html.P(f"Players: {stats['player_count']}", className="card-text"),
                        html.P([
                            html.Span(f"Goals: {stats['total_goals']}", className="card-text"),
                            html.Span(" | ", className="text-muted mx-1"),
                            html.Span(f"Assists: {stats['total_assists']}", className="card-text")
                        ]),
                        html.P(f"Avg. Age: {stats['avg_age']}", className="card-text"),
                        html.Small(f"Avg. Minutes: {stats['avg_minutes']}", className="text-muted")
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
     Output('comparison-chart-title', 'children'),
     Output('comparison-chart-container', 'children')],
    [Input('current-filters-store', 'data'),
     Input('performance-data-store', 'data'),
     Input('chart-data-store', 'data')],
    prevent_initial_call=True
)
def update_comparison_chart(filters, performance_data, chart_data):
    """Actualiza el gráfico de comparación y su visibilidad."""

    # Valores por defecto (siempre devolver estos tres valores)
    default_style = {"display": "none"}
    default_title = ""
    default_content = html.Div()
    
    # Validación de filtros
    if filters is None or not isinstance(filters, dict):
        return default_style, default_title, default_content
    
    analysis_level = filters.get('analysis_level', 'league')
    
    # Para nivel liga, ocultar esta sección
    if analysis_level == 'league':
        return default_style, default_title, default_content
    
    # Verificar disponibilidad de datos
    if not performance_data or not chart_data:
        return {"display": "block"}, f"Comparación - {analysis_level.title()}", html.Div(
            "No hay datos disponibles para la comparación", className="text-center p-4"
        )
    
    try:
        # NIVEL EQUIPO: Comparación del equipo con la liga
        if analysis_level == 'team':
            team_name = filters.get('team', 'Equipo')
            
            # Si tenemos overview
            if 'overview' in performance_data:
                overview = performance_data['overview']
                
                # Definir las métricas a comparar
                metrics = ["Goles", "Asistencias", "Jugadores", "Edad Promedio"]
                
                # Valores del equipo
                team_values = [
                    overview.get('total_goals', 0),
                    overview.get('total_assists', 0),
                    overview.get('total_players', 0),
                    overview.get('avg_age', 0)
                ]
                
                # Valores de la liga (referencia)
                # Usar valores reales si están disponibles, si no, estimaciones
                league_values = [
                    overview.get('league_avg_goals', 15),
                    overview.get('league_avg_assists', 10),
                    overview.get('league_avg_players', 20),
                    overview.get('league_avg_age', 25)
                ]
                
                # Crear subplots para manejar las diferentes escalas
                fig = make_subplots(
                    rows=len(metrics),
                    cols=1,
                    subplot_titles=metrics,
                    vertical_spacing=0.05
                )
                
                # Colores
                colors = {
                    'team': '#3498db',  # Azul
                    'league': '#e74c3c'  # Rojo
                }
                
                # Añadir barras para cada métrica
                for i, metric in enumerate(metrics):
                    # Valores para esta métrica
                    team_val = team_values[i]
                    league_val = league_values[i]
                    
                    # Formatear valores si es necesario (por ejemplo, para edad promedio)
                    if metric == "Edad Promedio":
                        team_val = round(team_val, 1)
                        league_val = round(league_val, 1)
                    
                    # Añadir barras para equipo y liga
                    fig.add_trace(
                        go.Bar(
                            x=[team_val],
                            y=[team_name],
                            orientation='h',
                            name=team_name if i == 0 else None,
                            marker_color=colors['team'],
                            showlegend=i == 0
                        ),
                        row=i+1, col=1
                    )
                    
                    fig.add_trace(
                        go.Bar(
                            x=[league_val],
                            y=["Promedio Liga"],
                            orientation='h',
                            name="Promedio Liga" if i == 0 else None,
                            marker_color=colors['league'],
                            showlegend=i == 0
                        ),
                        row=i+1, col=1
                    )
                
                # Actualizar layout
                fig.update_layout(
                    height=100 + 150 * len(metrics),  # Altura dinámica
                    title_text=f"Comparación de {team_name} vs Promedio de Liga",
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
                
                # Ajustar el rango de cada subplot individualmente
                for i in range(len(metrics)):
                    # Determinar el valor máximo para cada métrica
                    max_val = max(team_values[i], league_values[i]) * 1.1
                    
                    # Ajustar el rango del eje x
                    fig.update_xaxes(range=[0, max_val], row=i+1, col=1)
                
                return {"display": "block"}, f"Comparación - {team_name}", dcc.Graph(figure=fig)
            
            # Fallback si no hay datos
            return {"display": "block"}, f"Comparación - {team_name}", html.Div(
                "No hay datos suficientes para la comparación", className="text-center p-4"
            )
        
        # NIVEL JUGADOR: Gráfico de comparación mejorado
        elif analysis_level == 'player':
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
                        
                        # Formatos más cortos para métricas
                        display_metric = metric.replace("_", " ").title()
                        if len(display_metric) > 15:  # Si es muy largo
                            display_metric = display_metric[:15] + "..."
                        
                        metrics.append(display_metric)
                        player_values.append(player_val)
                        position_values.append(position_val)
                        league_values.append(league_val)
                
                if metrics:
                    # Crear gráfico de barras horizontales normalizado
                    # Para cada métrica, creamos un gráfico separado para tener escalas apropiadas
                    fig = make_subplots(
                        rows=len(metrics),
                        cols=1,
                        subplot_titles=metrics,
                        vertical_spacing=0.05
                    )
                    
                    # Colores
                    colors = {
                        'player': '#3498db',  # Azul
                        'position': '#e74c3c',  # Rojo
                        'league': '#2ecc71'   # Verde
                    }
                    
                    # Añadir barras para cada métrica
                    for i, metric in enumerate(metrics):
                        # Valores para esta métrica
                        p_val = player_values[i]
                        pos_val = position_values[i]
                        l_val = league_values[i]
                        
                        # Añadir barras para jugador, posición y liga
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
                        height=100 + 150 * len(metrics),  # Altura dinámica
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
                    
                    return {"display": "block"}, f"Comparación - {player_name}", dcc.Graph(figure=fig)
            
            # Fallback
            return {"display": "block"}, f"Comparación - {player_name}", html.Div(
                "No hay datos suficientes para la comparación", className="text-center p-4"
            )
        
        # Default para cualquier otro caso
        return default_style, default_title, default_content
        
    except Exception as e:
        # En caso de error, devolvemos valores válidos con un mensaje de error
        return {"display": "block"}, "Error en Comparación", html.Div([
            dbc.Alert(
                [
                    html.H4("Error al generar comparación", className="alert-heading"),
                    html.P(f"Detalle: {str(e)}"),
                    html.Hr(),
                    html.P(
                        "Intente con diferentes filtros o jugadores.",
                        className="mb-0"
                    )
                ],
                color="danger"
            )
        ])

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
