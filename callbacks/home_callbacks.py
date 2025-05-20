from dash import Input, Output, callback
import dash_bootstrap_components as dbc
from dash import html
from data import HongKongDataManager
import logging
from datetime import datetime, timedelta
import json
from pathlib import Path

# Configurar logging
logger = logging.getLogger(__name__)

# Initialize global data_manager
data_manager = None

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

# Callback para mostrar estado del sistema
@callback(
    Output('system-status-info', 'children'),
    [Input('refresh-data-button', 'n_clicks'),
    Input('url', 'pathname')],  # Añadir input del URL para ejecutar al cargar
    prevent_initial_call=False
)
def update_system_status(n_clicks, pathname):
    """
    Callback que actualiza la información del estado del sistema.
    Versión mejorada con badges para todas las temporadas y mejor manejo de estados.
    """
    # Ignorar el pathname, solo lo usamos para que el callback se ejecute al cargar
    if pathname != "/":
        return None  # No hacer nada si no estamos en home
    
    # Variable global para mantener el data_manager entre llamadas
    global data_manager
    
    try:
        # Inicializar solo si no existe
        if 'data_manager' not in globals() or data_manager is None:
            data_manager = HongKongDataManager(auto_load=True, background_preload=True)

        # Si se hizo click en actualizar, forzar refresco
        if n_clicks and n_clicks > 0:
            # Marcar como solicitud manual (internamente se guardará este timestamp)
            data_manager.last_update[f"{data_manager.current_season}_manual"] = datetime.now()
            data_manager._save_update_timestamps()
            data_manager.refresh_data(force_download=True)
        
        # Forzar explícitamente la temporada 2024-25
        if data_manager.current_season != "2024-25":
            # Guardar la temporada actual para restaurarla después
            current = data_manager.current_season
            
            # Cargar datos de 2024-25
            data_manager.refresh_data("2024-25", force_download=False)
            
            # Obtener estado con los datos correctos
            status = data_manager.get_data_status()
            
            # Restaurar la temporada solo si es reciente (actualizada en el último mes)
            restore_season = False
            if current in data_manager.last_update:
                try:
                    last_update_str = data_manager.last_update[current]
                    if isinstance(last_update_str, str):
                        last_update = datetime.fromisoformat(last_update_str)
                        one_month_ago = datetime.now() - timedelta(days=30)
                        
                        # Solo restaurar temporadas recientes
                        if last_update > one_month_ago:
                            restore_season = True
                    elif isinstance(last_update_str, datetime):
                        # Si ya es un objeto datetime
                        one_month_ago = datetime.now() - timedelta(days=30)
                        if last_update_str > one_month_ago:
                            restore_season = True
                except Exception as e:
                    logger.warning(f"Error verificando timestamp de {current}: {e}")
            
            # Solo restaurar si cumple los criterios
            if restore_season:
                logger.info(f"Restaurando temporada reciente: {current}")
                data_manager.refresh_data(current, force_download=False)
            else:
                logger.info(f"No se restaura temporada {current} por ser antigua o problemática")
        else:
            status = data_manager.get_data_status()
        
        # Asegurar que la UI siempre muestre 2024-25
        status['current_season'] = "2024-25"
        
        # Extraer manualmente el timestamp del archivo para mostrar la fecha correcta
        timestamp_file = Path(data_manager.extractor.cache_dir) / "update_timestamps.json"
        if timestamp_file.exists():
            try:
                with open(timestamp_file, 'r') as f:
                    timestamps_data = json.load(f)
                    if "2024-25" in timestamps_data:
                        # Formatear el timestamp para mostrar
                        timestamp_str = timestamps_data["2024-25"]
                        formatted_date = timestamp_str[:19].replace('T', ' ')
                        # Sobreescribir el timestamp en el status
                        status['last_update'] = formatted_date
            except Exception as e:
                logger.error(f"Error leyendo timestamp file: {e}")
        
        # Obtener estado del sistema y verificar actualizaciones
        update_check = data_manager.check_for_updates()
        
        # Crear lista de items de estado
        status_items = []
        
        # Temporada actual con formato mejorado
        current_season = status.get('current_season', 'N/A')
        available_seasons = status.get('available_seasons', [])
        
        # Convertir temporadas a formato corto y crear badges
        available_seasons_badges = [
            dbc.Badge(format_season_short(s), 
                color="info", 
                className="me-1 mb-1",
                style={"font-size": "0.8rem"}) 
            for s in available_seasons
        ]
        
        status_items.append(
            dbc.ListGroupItem([
                html.Div([
                    html.Strong("🗓️ Temporada actual: "),
                    dbc.Badge(format_season_short(current_season), color="primary", className="ms-1"),
                    html.Br(),
                    html.Small("Disponibles: ", className="text-muted me-1"),
                    html.Span(available_seasons_badges)
                ])
            ])
        )
        
        # Última actualización
        last_update = status.get('last_update')
        formatted_date = 'Nunca'
        if last_update:
            # Asegurar que sea un objeto datetime antes de formatearlo
            if isinstance(last_update, datetime):
                formatted_date = last_update.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(last_update, str) and last_update not in ['None', 'null', '{}']:
                formatted_date = last_update[:19].replace('T', ' ')
                    
        status_items.append(
            dbc.ListGroupItem([
                html.Div([
                    html.Strong("🕐 Última actualización: "),
                    html.Span(formatted_date, className="fst-italic")
                ])
            ])
        )
        
        # Verificación más robusta de datos disponibles
        raw_data_available = status.get('raw_data_available', False)
        processed_data_available = status.get('processed_data_available', False)
        cached_seasons = status.get('cached_seasons', [])
        data_available = processed_data_available or len(cached_seasons) > 0
        
        status_items.append(
            dbc.ListGroupItem([
                html.Div([
                    html.Strong("💾 Datos disponibles: "),
                    dbc.Badge(
                        "Sí ✓" if data_available else "No ✗", 
                        color="success" if data_available else "danger",
                        className="ms-2"
                    ),
                    html.Br(),
                    html.Small(f"Temporadas en caché: {len(cached_seasons)}", className="text-muted"),
                    html.Br(),
                    html.Div([
                        dbc.Badge(format_season_short(s), color="secondary", className="me-1 mb-1")
                        for s in cached_seasons
                    ], style={"margin-top": "5px"})
                ])
            ])
        )
        
        # Estadísticas de datos (si están disponibles)
        if 'data_stats' in status and data_available:
            stats = status['data_stats']
            
            # Información de equipos
            teams_list_str = ""
            if 'hong_kong_teams' in status and status['hong_kong_teams']:
                teams_list = status['hong_kong_teams']
                #teams_list_str = f"{', '.join(teams_list)}"

            available_teams_badges = [
            dbc.Badge(format_season_short(t), 
                color="info", 
                className="me-1 mb-1",
                style={"font-size": "0.8rem"}) 
            for t in teams_list
            ]    
            
            status_items.append(
                dbc.ListGroupItem([
                    html.Div([
                        html.Strong("📊 Estadísticas: "),
                        dbc.Badge(format_season_short(current_season), color="primary", className="ms-1 me-2"),
                        html.Span(f"{stats.get('total_players', 0)} jugadores, {stats.get('total_teams', 0)} equipos"),
                        html.Br(),
                        html.Small("Equipos: ", className="text-muted"),
                        html.Span(available_teams_badges)
                    ])
                ])
            )
        
        # Estado de actualización (ahora coherente con datos disponibles)
        needs_update = update_check.get('needs_update', False)
        if not data_available:
            # Si no hay datos, el estado es "Datos no disponibles"
            status_items.append(
                dbc.ListGroupItem([
                    html.Div([
                        html.Strong("⚠️ Estado: "),
                        dbc.Badge("Datos no disponibles", color="danger", className="ms-2"),
                        html.Br(),
                        html.Small("Se requiere cargar datos", className="text-muted")
                    ])
                ], color="danger")
            )
        elif needs_update:
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
        
        # Si se hizo click en el botón, mostrar resultado del refresco
        if n_clicks and n_clicks > 0:
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
        
        return dbc.ListGroup(status_items, flush=True)
        
    except Exception as e:
        # En caso de error, mostrar mensaje de error
        return dbc.Alert(
            [
                html.H6("❌ Error del Sistema", className="alert-heading"),
                html.P(f"No se pudo obtener el estado del sistema: {str(e)}"),
                html.Hr(),
                html.Small("Verifica que el sistema de datos esté configurado correctamente.", className="text-muted"),
            ],
            color="danger"
        )