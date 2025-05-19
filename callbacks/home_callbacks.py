from dash import Input, Output, callback
import dash_bootstrap_components as dbc
from dash import html
from data import HongKongDataManager
import logging

# Configurar logging
logger = logging.getLogger(__name__)

# Callback para mostrar estado del sistema
@callback(
    Output('system-status-info', 'children'),
    [Input('refresh-data-button', 'n_clicks')],
    prevent_initial_call=False
)
def update_system_status(n_clicks):
    """
    Callback que actualiza la información del estado del sistema.
    Se ejecuta al cargar la página y cuando se hace click en el botón de actualizar.
    """
    try:
        # Inicializar el data manager (sin cargar automáticamente los datos)
        data_manager = HongKongDataManager(auto_load=False)
        
        # Obtener estado del sistema y verificar actualizaciones
        status = data_manager.get_data_status()
        update_check = data_manager.check_for_updates()
        
        # Crear lista de items de estado
        status_items = []
        
        # Temporada actual
        status_items.append(
            dbc.ListGroupItem([
                html.Div([
                    html.Strong("🗓️ Temporada actual: "),
                    html.Span(status.get('current_season', 'N/A'))
                ])
            ])
        )
        
        # Última actualización
        last_update = status.get('last_update')
        if last_update:
            # Formatear fecha para mostrar solo fecha y hora
            formatted_date = last_update[:19].replace('T', ' ')
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
        
        # Estado de datos disponibles
        data_available = status.get('processed_data_available', False)
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
        
        # Estadísticas de datos (si están disponibles)
        if 'data_stats' in status and data_available:
            stats = status['data_stats']
            status_items.append(
                dbc.ListGroupItem([
                    html.Div([
                        html.Strong("📊 Estadísticas: "),
                        html.Span(f"{stats.get('total_players', 0)} jugadores, {stats.get('total_teams', 0)} equipos")
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
                refresh_success = data_manager.refresh_data()
                if refresh_success:
                    status_items.append(
                        dbc.ListGroupItem([
                            dbc.Alert("✅ Datos actualizados exitosamente", color="success", className="mb-0")
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
                html.Small("Verifica que el sistema de datos esté configurado correctamente.", className="text-muted")
            ],
            color="danger"
        )