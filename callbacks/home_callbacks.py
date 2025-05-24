"""
Callbacks para la página home.
Versión simplificada y modularizada.
"""
from dash import Input, Output, callback
import dash_bootstrap_components as dbc
from dash import html
from data import HongKongDataManager
from data.transfermarkt_data_manager import TransfermarktDataManager
from utils.common import format_season_short, format_datetime, get_current_season
from utils.home_helpers import (
    create_performance_section,
    create_performance_status_section,
    create_injuries_section,
    create_overall_status_section,
    create_update_results_section
)
import logging
from datetime import datetime
import time

# Configurar logging
logger = logging.getLogger(__name__)

# Initialize global data_managers
data_manager = None
transfermarkt_manager = None

def initialize_managers():
    """
    Inicializa los managers de datos si no existen.
    
    Returns:
        tuple: (data_manager, transfermarkt_manager)
    """
    global data_manager, transfermarkt_manager
    
    try:
        if data_manager is None:
            logger.info("Inicializando HongKongDataManager...")
            data_manager = HongKongDataManager(auto_load=True)
        
        if transfermarkt_manager is None:
            logger.info("Inicializando TransfermarktDataManager...")
            transfermarkt_manager = TransfermarktDataManager(auto_load=True)
            
        return data_manager, transfermarkt_manager
        
    except Exception as e:
        logger.error(f"Error inicializando managers: {e}")
        raise

def update_performance_data(data_manager, force_update=False):
    """
    Actualiza los datos de performance.
    
    Args:
        data_manager: Manager de datos de performance
        force_update (bool): Si forzar la actualización
        
    Returns:
        tuple: (success, error_message)
    """
    try:
        
        success = data_manager.refresh_data(force_download=force_update)
        
        if success:
            logger.info("✅ Datos de performance actualizados exitosamente")
            return True, None
        else:
            error_msg = "Error actualizando datos de performance"
            logger.error(error_msg)
            return False, error_msg
            
    except Exception as e:
        error_msg = f"Error en performance: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def update_injuries_data(transfermarkt_manager, force_update=False):
    """
    Actualiza los datos de lesiones.
    
    Args:
        transfermarkt_manager: Manager de datos de lesiones
        force_update (bool): Si forzar la actualización
        
    Returns:
        tuple: (success, error_message)
    """
    try:
        if force_update:
            transfermarkt_manager._save_manual_update_timestamp(datetime.now())
        
        success = transfermarkt_manager.refresh_data(force_scraping=force_update)
        
        if success:
            logger.info("✅ Datos de lesiones actualizados exitosamente")
            return True, None
        else:
            error_msg = "Error actualizando datos de lesiones"
            logger.error(error_msg)
            return False, error_msg
            
    except Exception as e:
        error_msg = f"Error en lesiones: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

@callback(
    Output('system-status-info', 'children'),
    [Input('refresh-data-button', 'n_clicks'),
    Input('url', 'pathname')],
    prevent_initial_call=False
)
def update_system_status(n_clicks, pathname):
    """
    Callback principal que actualiza la información del estado del sistema.
    Versión optimizada sin verificaciones duplicadas.
    """
    # Solo ejecutar en la página home
    if pathname != "/":
        return None
    
    try:
        # Mostrar loading si se está actualizando
        if n_clicks and n_clicks > 0:
            time.sleep(1.0)  # Pausa para mostrar el spinner
        
        # Inicializar managers
        dm, tm = initialize_managers()
        
        # Variables para tracking de actualizaciones
        performance_updated = False
        injuries_updated = False
        update_errors = []
        
        # VERIFICACIÓN ÚNICA - Evitar duplicaciones
        is_manual_update = n_clicks and n_clicks > 0
        performance_needs_auto_update = dm.should_check_for_updates() if not is_manual_update else False
        injuries_needs_auto_update = tm._should_update_data() if not is_manual_update else False
        
        # Log de estado para debugging
        if is_manual_update:
            logger.info("🔄 Actualización MANUAL solicitada")
        elif performance_needs_auto_update or injuries_needs_auto_update:
            logger.info("🤖 Actualización AUTOMÁTICA programada detectada")
        
        # ACTUALIZACIÓN MANUAL
        if is_manual_update:
            logger.info("🔄 Ejecutando actualización manual...")
            
            # Actualizar performance
            perf_success, perf_error = update_performance_data(dm, force_update=True)
            if perf_success:
                performance_updated = True
            elif perf_error:
                update_errors.append(perf_error)
            
            # Actualizar injuries
            inj_success, inj_error = update_injuries_data(tm, force_update=True)
            if inj_success:
                injuries_updated = True
            elif inj_error:
                update_errors.append(inj_error)
                
        # ACTUALIZACIÓN AUTOMÁTICA (solo si es necesario)
        elif performance_needs_auto_update or injuries_needs_auto_update:
            logger.info("🤖 Ejecutando actualización automática...")
            
            # Performance - SOLO si necesita actualización
            if performance_needs_auto_update:
                update_check = dm.check_for_updates()
                if update_check.get('needs_update', False):
                    logger.info("🤖 Actualizando performance automáticamente...")
                    perf_success, perf_error = update_performance_data(dm, force_update=True)
                    if perf_success:
                        performance_updated = True
                        logger.info("🤖 Performance actualizada automáticamente")
                    elif perf_error:
                        update_errors.append(f"Auto-update performance: {perf_error}")
            
            # Injuries - SOLO si necesita actualización
            if injuries_needs_auto_update:
                logger.info("🤖 Actualizando injuries automáticamente...")
                inj_success, inj_error = update_injuries_data(tm, force_update=True)
                if inj_success:
                    injuries_updated = True
                    logger.info("🤖 Injuries actualizadas automáticamente")
                elif inj_error:
                    update_errors.append(f"Auto-update injuries: {inj_error}")
        
        # MODO SOLO LECTURA (no hay actualizaciones necesarias)
        else:
            logger.debug("📖 Modo solo lectura - no hay actualizaciones programadas")
        
        # Obtener estados actuales
        performance_status = dm.get_data_status()
        injuries_data = tm.get_injuries_data()
        injuries_stats = tm.get_statistics_summary()
        
        # Verificar disponibilidad de datos
        cached_seasons = performance_status.get('cached_seasons', [])
        performance_data_available = len(cached_seasons) > 0
        injuries_available = len(injuries_data) > 0
        
        # Crear secciones usando las funciones auxiliares
        status_items = []
        
        # Sección de performance
        status_items.append(create_performance_section(performance_status))
        status_items.append(create_performance_status_section(performance_status))
        
        # Sección de injuries
        status_items.append(create_injuries_section(injuries_data, injuries_stats, tm))
        
        # Estado general
        status_items.append(create_overall_status_section(
            performance_data_available, 
            injuries_available, 
            dm,  # data_manager
            tm   # transfermarkt_manager    
        ))
        
        # Resultados de actualización (manual o automática)
        update_results_item = create_update_results_section(
            performance_updated, injuries_updated, dm, tm, update_errors
        )
        if update_results_item:
            status_items.append(update_results_item)
        
        return dbc.ListGroup(status_items, flush=True)
        
    except Exception as e:
        # Error handler simplificado
        logger.error(f"Error en update_system_status: {e}")
        return dbc.Alert(
            [
                html.H6("❌ System Error", className="alert-heading"),
                html.P(f"Could not retrieve system status: {str(e)}"),
                html.Hr(),
                html.Small("Please verify that the data system is properly configured.", className="text-muted"),
            ],
            color="danger"
        )