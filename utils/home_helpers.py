"""
Funciones auxiliares para el home dashboard.
Separa la lógica de creación de HTML del callback principal.
"""
import dash_bootstrap_components as dbc
from dash import html
from utils.common import format_season_short, format_datetime
import logging

logger = logging.getLogger(__name__)

def create_performance_section(performance_status):
    """
    Crea la sección de información de performance.
    
    Args:
        performance_status (dict): Estado del sistema de performance
        
    Returns:
        dbc.ListGroupItem: Item con información de performance
    """
    current_season = performance_status.get('current_season', 'N/A')
    available_seasons = performance_status.get('available_seasons', [])
    
    available_seasons_badges = [
        dbc.Badge(format_season_short(s), 
            color="info", 
            className="me-1 mb-1",
            style={"font-size": "0.8rem"}) 
        for s in available_seasons
    ]
    
    return dbc.ListGroupItem([
        html.Div([
            html.Strong("⚽ PERFORMANCE DATA"),
            html.Hr(className="my-2"),
            html.Strong("🗓️ Temporada actual: "),
            dbc.Badge(format_season_short(current_season), color="primary", className="ms-1 mb-2"),
            html.Br(),
            html.Small("Disponibles: ", className="me-1"),
            html.Span(available_seasons_badges)
        ])
    ])

def create_performance_status_section(performance_status):
    """
    Crea la sección de estado de performance.
    
    Args:
        performance_status (dict): Estado del sistema de performance
        
    Returns:
        dbc.ListGroupItem: Item con estado de performance
    """
    last_update_performance = performance_status.get('last_update')
    formatted_date_performance = format_datetime(last_update_performance)
    
    cached_seasons = performance_status.get('cached_seasons', [])
    performance_data_available = len(cached_seasons) > 0
    
    # Estadísticas de performance
    performance_info = []
    if 'data_stats' in performance_status and performance_data_available:
        stats = performance_status['data_stats']
        performance_info = [
            html.Small(f"📊 {stats.get('total_players', 0)} jugadores, {stats.get('total_teams', 0)} equipos"),
            html.Br(),
            html.Small(f"🕐 Actualizado: {formatted_date_performance}")
        ]
    else:
        performance_info = [html.Small("⚠️ Sin datos de performance")]
    
    return dbc.ListGroupItem([
        html.Div([
            html.Strong("📋 Estado Performance: "),
            dbc.Badge(
                "Disponible" if performance_data_available else "No disponible", 
                color="success" if performance_data_available else "danger",
                className="ms-2"
            ),
            html.Br(),
            *performance_info
        ])
    ])

def create_injuries_section(injuries_data, injuries_stats, transfermarkt_manager):
    """
    Crea la sección de información de lesiones.
    
    Args:
        injuries_data (list): Datos de lesiones
        injuries_stats (dict): Estadísticas de lesiones
        transfermarkt_manager: Manager de datos de Transfermarkt
        
    Returns:
        dbc.ListGroupItem: Item con información de lesiones
    """
    injuries_available = len(injuries_data) > 0
    injuries_teams = transfermarkt_manager.get_teams_with_injuries() if injuries_available else []
    
    # Obtener timestamp de lesiones
    last_update_injuries = injuries_stats.get('last_update') if injuries_available else None
    formatted_date_injuries = format_datetime(last_update_injuries)
    
    injuries_info = []
    if injuries_available:
        active_injuries = injuries_stats.get('active_injuries', 0)
        injuries_info = [
            html.Small(f"📊 {len(injuries_data)} lesiones registradas"),
            html.Br(),
            html.Small(f"🏥 {active_injuries} lesiones activas"),
            html.Br(),
            html.Small(f"⚽ {len(injuries_teams)} equipos con lesiones"),
            html.Br(),
            html.Small(f"🕐 Actualizado: {formatted_date_injuries}")
        ]
    else:
        injuries_info = [
            html.Small("⚠️ Sin datos de lesiones"),
            html.Br(),
            html.Small(f"🕐 Último intento: {formatted_date_injuries}")
        ]
    
    return dbc.ListGroupItem([
        html.Div([
            html.Strong("🏥 INJURIES DATA"),
            html.Hr(className="my-2"),
            html.Strong("📋 Estado Lesiones: "),
            dbc.Badge(
                "Disponible" if injuries_available else "No disponible", 
                color="success" if injuries_available else "danger",
                className="ms-2"
            ),
            html.Br(),
            *injuries_info
        ])
    ])

def create_overall_status_section(performance_data_available, injuries_available, data_manager=None, transfermarkt_manager=None):
    """
    Crea la sección de estado general del sistema.
    Versión simplificada que confía en la lógica mejorada de verificación.
    """
    # Estado básico del sistema
    if performance_data_available and injuries_available:
        overall_status = "success"
        overall_message = "All systems operational"
    elif performance_data_available or injuries_available:
        overall_status = "warning" 
        overall_message = "Partial systems operational"
    else:
        overall_status = "danger"
        overall_message = "Systems not available"
    
    # Verificar actualizaciones disponibles 
    updates_available = []
    
    # Verificar actualizaciones de performance
    if performance_data_available and data_manager:
        try:
            performance_updates = data_manager.check_for_updates()
            if performance_updates.get('needs_update', False):
                updates_available.append("Performance data")
                logger.debug(f"🔔 Performance update needed: {performance_updates.get('message')}")
            else:
                logger.debug(f"✅ Performance up to date: {performance_updates.get('message')}")
        except Exception as e:
            logger.warning(f"Error checking performance updates: {e}")
    
    # Crear componente de estado
    status_content = [
        html.Strong("🔧 Status: "),
        dbc.Badge(overall_message, color=overall_status, className="ms-2")
    ]
    
    # Mostrar estado de actualizaciones
    if updates_available:
        status_content.extend([
            html.Br(),
            html.Br(),
            html.Strong("🔔 Updates Available: "),
            html.Br(),
            html.Small(f"• {', '.join(updates_available)} can be updated", className="text-warning")
        ])
        if overall_status == "success":
            overall_status = "info"
    else:
        status_content.extend([
            html.Br(),
            html.Small("✅ All data is up to date", className="text-success")
        ])
    
    return dbc.ListGroupItem([
        html.Div(status_content)
    ], color="light")

def create_update_results_section(performance_updated, injuries_updated, data_manager, transfermarkt_manager, update_errors):
    """
    Crea la sección de resultados de actualización.
    
    Args:
        performance_updated (bool): Si se actualizó performance
        injuries_updated (bool): Si se actualizaron lesiones
        data_manager: Manager de datos de performance
        transfermarkt_manager: Manager de datos de lesiones
        update_errors (list): Lista de errores
        
    Returns:
        dbc.ListGroupItem or None: Item con resultados o None
    """
    if not (performance_updated or injuries_updated or update_errors):
        return None
    
    update_results = []
    
    if performance_updated:
        try:
            updated_status = data_manager.get_data_status()
            teams_count = updated_status.get('data_stats', {}).get('total_teams', 0)
            players_count = updated_status.get('data_stats', {}).get('total_players', 0)
            update_results.append(f"⚽ Performance: {players_count} jugadores de {teams_count} equipos")
        except Exception as e:
            logger.warning(f"Error getting updated performance stats: {e}")
    
    if injuries_updated:
        try:
            updated_injuries = transfermarkt_manager.get_injuries_data()
            injuries_count = len(updated_injuries)
            teams_with_injuries = len(transfermarkt_manager.get_teams_with_injuries())
            update_results.append(f"🏥 Lesiones: {injuries_count} lesiones de {teams_with_injuries} equipos")
        except Exception as e:
            logger.warning(f"Error getting updated injuries stats: {e}")
    
    if update_results:
        # Determinar si fue manual o automático basado en el contexto
        update_type = "Manual" if any("manual" in str(result).lower() for result in update_results) else "Automatic"
        
        return dbc.ListGroupItem([
            dbc.Alert([
                html.Strong(f"✅ {update_type} Data Update Completed"),
                html.Br(),
                *[html.Div([html.Small(result)]) for result in update_results]
            ], color="success", className="mb-0")
        ])                                                                
    elif update_errors:
        return dbc.ListGroupItem([
            dbc.Alert([
                html.Strong("⚠️ Partial Update"),
                html.Br(),
                html.Small("Some systems could not be updated"),
                html.Br(),
                *[html.Div([html.Small(f"• {error}")]) for error in update_errors]
            ], color="warning", className="mb-0")
        ])
    
    return None