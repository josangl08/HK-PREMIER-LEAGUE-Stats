from dash import Input, Output, callback
import dash_bootstrap_components as dbc
from dash import html
from data import HongKongDataManager
import logging

# Configurar logging
logger = logging.getLogger(__name__)

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

# Callback para mostrar estado del sistema - VERSIÓN CORREGIDA
@callback(
    Output('system-status-info', 'children'),
    [Input('refresh-data-button', 'n_clicks')],
    prevent_initial_call=False
)
def update_system_status(n_clicks):
    """
    Callback que actualiza la información del estado del sistema.
    Versión mejorada para mostrar información de equipos y posiciones.
    """
    try:
        # Inicializar el data manager (sin cargar automáticamente los datos)
        data_manager = HongKongDataManager(auto_load=False, background_preload=False)
        
        # Obtener estado del sistema y verificar actualizaciones
        status = data_manager.get_data_status()
        update_check = data_manager.check_for_updates()
        
        # Crear lista de items de estado
        status_items = []
        
        # Temporada actual - FORMATO CORREGIDO
        current_season = status.get('current_season', 'N/A')
        available_seasons = status.get('available_seasons', [])
        
        # Convertir temporadas a formato corto
        available_seasons_short = [format_season_short(s) for s in available_seasons]
        
        status_items.append(
            dbc.ListGroupItem([
                html.Div([
                    html.Strong("🗓️ Temporada actual: "),
                    html.Span(format_season_short(current_season)),
                    html.Br(),
                    html.Small(f"Disponibles: {', '.join(available_seasons_short)}", 
                              className="text-muted")
                ])
            ])
        )
        
        # Última actualización - VERSIÓN CORREGIDA
        last_update = status.get('last_update')
        if last_update and last_update != '{}':
            # Formatear fecha para mostrar solo fecha y hora
            try:
                if isinstance(last_update, str) and last_update not in ['None', 'null', '{}']:
                    formatted_date = last_update[:19].replace('T', ' ')
                else:
                    formatted_date = 'Nunca'
            except:
                formatted_date = 'Nunca'
        else:
            formatted_date = 'Nunca'
            
        status_items.append(
            dbc.ListGroupItem([
                html.Div([
                    html.Strong("🕐 Última actualización: "),
                    html.Span(formatted_date)
                ])
            ])
        )
        
        # Estado de datos disponibles - VERSIÓN CORREGIDA
        data_available = status.get('processed_data_available', False)
        # Verificar también si hay datos en cache
        if not data_available and status.get('cached_seasons'):
            data_available = current_season in status.get('cached_seasons', [])
        
        status_items.append(
            dbc.ListGroupItem([
                html.Div([
                    html.Strong("💾 Datos disponibles: "),
                    dbc.Badge(
                        "Sí ✓" if data_available else "No ✗", 
                        color="success" if data_available else "danger",
                        className="ms-2"
                    )
                ])
            ])
        )
        
        # Estadísticas de datos (si están disponibles) - MEJORADO
        if 'data_stats' in status and data_available:
            stats = status['data_stats']
            teams_info = ""
            
            # Información de equipos de Hong Kong
            if 'hong_kong_teams' in status and status['hong_kong_teams']:
                teams_list = status['hong_kong_teams']
                teams_info = f" | Equipos: {', '.join(teams_list[:3])}{'...' if len(teams_list) > 3 else ''}"
            
            # Mostrar temporadas en cache en formato corto
            cached_seasons = status.get('cached_seasons', [])
            cached_short = [format_season_short(s) for s in cached_seasons]
            
            status_items.append(
                dbc.ListGroupItem([
                    html.Div([
                        html.Strong("📊 Estadísticas: "),
                        html.Span(f"{stats.get('total_players', 0)} jugadores, {stats.get('total_teams', 0)} equipos"),
                        html.Br(),
                        html.Small(f"En cache: {', '.join(cached_short)}{teams_info}", 
                            className="text-muted")
                    ])
                ])
            )
        
        # Estado de actualización
        if update_check.get('needs_update', False):
            status_items.append(
                dbc.ListGroupItem([
                    html.Div([
                        html.Strong("🔄 Estado: "),
                        dbc.Badge("Actualizaciones disponibles", color="warning", className="ms-2"),
                        html.Br(),
                        html.Small(update_check.get('message', ''), className="text-muted")
                    ])
                ], color="warning")
            )
        else:
            status_items.append(
                dbc.ListGroupItem([
                    html.Div([
                        html.Strong("✅ Estado: "),
                        dbc.Badge("Datos actualizados", color="success", className="ms-2")
                    ])
                ], color="light")
            )
        
        # Si se hizo click en el botón, intentar refrescar los datos
        if n_clicks and n_clicks > 0:
            try:
                refresh_success = data_manager.refresh_data(force_download=True)
                if refresh_success:
                    # Obtener estadísticas actualizadas
                    updated_status = data_manager.get_data_status()
                    teams_count = updated_status.get('data_stats', {}).get('total_teams', 0)
                    players_count = updated_status.get('data_stats', {}).get('total_players', 0)
                    
                    status_items.append(
                        dbc.ListGroupItem([
                            dbc.Alert([
                                html.Strong("✅ Datos actualizados exitosamente"),
                                html.Br(),
                                html.Small(f"Cargados {players_count} jugadores de {teams_count} equipos")
                            ], color="success", className="mb-0")
                        ])
                    )
                else:
                    status_items.append(
                        dbc.ListGroupItem([
                            dbc.Alert("⚠️ Error actualizando datos", color="warning", className="mb-0")
                        ])
                    )
            except Exception as e:
                logger.error(f"Error refrescando datos: {e}")
                status_items.append(
                    dbc.ListGroupItem([
                        dbc.Alert(f"❌ Error: {str(e)}", color="danger", className="mb-0")
                    ])
                )
        
        return dbc.ListGroup(status_items, flush=True)
        
    except Exception as e:
        logger.error(f"Error obteniendo estado del sistema: {e}")
        return dbc.Alert(
            [
                html.H6("❌ Error del Sistema", className="alert-heading"),
                html.P(f"No se pudo obtener el estado del sistema: {str(e)}"),
                html.Hr(),
                html.Small("Verifica que el sistema de datos esté configurado correctamente.", className="text-muted"),
                html.Br(),
                html.Small("Tip: Verifica que los archivos de datos estén disponibles en GitHub.", className="text-muted")
            ],
            color="danger"
        )