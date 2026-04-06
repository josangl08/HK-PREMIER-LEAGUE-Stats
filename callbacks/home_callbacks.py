"""
Callbacks para la página home.
Versión simplificada y modularizada.
"""
import base64
import json
import re
from dash import Input, Output, State, callback, ctx, no_update
import dash_bootstrap_components as dbc
from dash import html
from utils.app_context import (
    get_hong_kong_data_manager,
    get_transfermarkt_data_manager,
    is_transfermarkt_manager_registered,
    set_transfermarkt_data_manager
)
from data.transfermarkt_data_manager import TransfermarktDataManager
from utils.common import format_season_short, format_datetime, get_current_season
from utils.home_helpers import (
    create_performance_section,
    create_performance_status_section,
    create_injuries_section,
    create_overall_status_section,
    create_update_results_section,
    create_transfermarkt_runtime_section,
)
from data.managers.transfermarkt_runtime_manager import TransfermarktRuntimeManager
from models.db_models import MatchUpdateQueue
from scripts.background_match_watcher import MatchWatcher
import logging
from datetime import datetime
import time
from sqlalchemy import func, select
from utils.db_engine import SessionFactory

# Configurar logging
logger = logging.getLogger(__name__)


def initialize_managers():
    """
    Inicializa los managers de datos usando app_context.

    HongKongDataManager debe estar registrado por app.py.
    TransfermarktDataManager se crea aquí si no existe.

    Returns:
        tuple: (data_manager, transfermarkt_manager)
    """
    try:
        # HongKongDataManager debe estar registrado por app.py
        data_manager = get_hong_kong_data_manager()

        # TransfermarktDataManager se crea aquí si no existe
        if not is_transfermarkt_manager_registered():
            logger.info("Inicializando TransfermarktDataManager...")
            transfermarkt_manager = TransfermarktDataManager(auto_load=True)
            set_transfermarkt_data_manager(transfermarkt_manager)
        else:
            transfermarkt_manager = get_transfermarkt_data_manager()

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
        if hasattr(transfermarkt_manager, "supports_injuries_scraping") and not transfermarkt_manager.supports_injuries_scraping():
            return False, "Transfermarkt injuries scraper is not implemented in the current extractor"
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
    Input('url', 'pathname'),
    Input('tm-admin-refresh-trigger', 'data')],
    prevent_initial_call=False
)
def update_system_status(n_clicks, pathname, _tm_refresh_trigger):
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
        
        performance_card = create_performance_section(performance_status)
        performance_status_card = create_performance_status_section(performance_status)
        injuries_card = create_injuries_section(injuries_data, injuries_stats, tm)
        runtime = TransfermarktRuntimeManager()
        tm_runtime = runtime.get_status()
        with get_transfermarkt_runtime_queue_session() as session:
            queue_rows = session.execute(
                select(MatchUpdateQueue.job_type, MatchUpdateQueue.status, func.count())
                .group_by(MatchUpdateQueue.job_type, MatchUpdateQueue.status)
                .order_by(MatchUpdateQueue.job_type, MatchUpdateQueue.status)
            ).all()
        queue_summary = [(f"{row[0]} / {row[1]}", row[2]) for row in queue_rows]
        tm_runtime_card = create_transfermarkt_runtime_section({
            "mode": tm_runtime.mode,
            "status": tm_runtime.status,
            "failure_count": tm_runtime.failure_count,
            "last_success_at": tm_runtime.last_success_at,
            "last_failure_at": tm_runtime.last_failure_at,
            "blocked_at": tm_runtime.blocked_at,
            "cooldown_until": tm_runtime.cooldown_until,
            "assisted_session_loaded_at": tm_runtime.assisted_session_loaded_at,
            "assisted_session_expires_at": tm_runtime.assisted_session_expires_at,
            "block_reason": tm_runtime.block_reason,
        }, queue_summary=queue_summary)
        overall_card = create_overall_status_section(
            performance_data_available, 
            injuries_available, 
            dm,  # data_manager
            tm   # transfermarkt_manager    
        )
        
        # Resultados de actualización (manual o automática)
        update_results_item = create_update_results_section(
            performance_updated, injuries_updated, dm, tm, update_errors
        )
        left_column = dbc.Col(
            [
                html.Div(performance_card, className="mb-3"),
                html.Div(performance_status_card, className="mb-3"),
                html.Div(injuries_card, className="mb-3"),
                html.Div(overall_card, className="mb-3"),
            ],
            md=6,
        )
        right_column = dbc.Col(
            [
                html.Div(tm_runtime_card, className="mb-3"),
            ],
            md=6,
        )

        rows = [
            dbc.Row(
                [left_column, right_column],
                className="g-3 align-items-start",
            ),
        ]
        if update_results_item:
            rows.append(
                dbc.Row(
                    [dbc.Col(update_results_item, md=12, className="mb-3")],
                    className="g-3",
                )
            )
        
        return html.Div(rows)
        
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


def get_transfermarkt_runtime_queue_session():
    return SessionFactory()


def _requeue_failed_tm_jobs() -> int:
    with SessionFactory() as session:
        failed_jobs = session.execute(
            select(MatchUpdateQueue).where(MatchUpdateQueue.status == "FAILED")
        ).scalars().all()
        now = datetime.utcnow()
        count = 0
        for job in failed_jobs:
            job.status = "PENDING"
            job.tm_status = "READY"
            job.retry_after = None
            job.last_attempt = None
            job.next_attempt = now
            job.reason = (job.reason or "").strip() or "Requeued from admin"
            count += 1
        session.commit()
        return count


def _requeue_failed_tm_jobs_by_type(job_types: set[str]) -> int:
    with SessionFactory() as session:
        failed_jobs = session.execute(
            select(MatchUpdateQueue).where(
                MatchUpdateQueue.status == "FAILED",
                MatchUpdateQueue.job_type.in_(tuple(job_types)),
            )
        ).scalars().all()
        now = datetime.utcnow()
        count = 0
        for job in failed_jobs:
            job.status = "PENDING"
            job.tm_status = "READY"
            job.retry_after = None
            job.last_attempt = None
            job.next_attempt = now
            job.reason = (job.reason or "").strip() or "Requeued from admin"
            count += 1
        session.commit()
        return count


def _normalize_tm_cookie_payload(raw_value: str):
    raw = (raw_value or "").strip()
    if not raw:
        return None, 0, "Paste a cookies payload to enable assisted mode."

    # Try JSON first
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            if all(isinstance(v, str) for v in parsed.values()):
                normalized = [{"name": k, "value": v} for k, v in parsed.items()]
                return json.dumps(normalized), len(normalized), None
            return json.dumps(parsed), len(parsed), None
        if isinstance(parsed, list):
            normalized = []
            for item in parsed:
                if isinstance(item, dict) and item.get("name") and item.get("value") is not None:
                    normalized.append(
                        {
                            "name": item.get("name"),
                            "value": item.get("value"),
                            "domain": item.get("domain"),
                            "path": item.get("path", "/"),
                            "secure": bool(item.get("secure", True)),
                        }
                    )
            if normalized:
                return json.dumps(normalized), len(normalized), None
            return None, 0, "JSON parsed, but no valid cookie items were found."
    except json.JSONDecodeError:
        pass

    # Fallback: document.cookie / header style
    pairs = []
    for chunk in re.split(r";\s*", raw.replace("\n", ";")):
        if not chunk or "=" not in chunk:
            continue
        name, value = chunk.split("=", 1)
        name = name.strip()
        value = value.strip()
        if name:
            pairs.append({"name": name, "value": value})
    if pairs:
        return json.dumps(pairs), len(pairs), None

    return None, 0, "Unsupported cookie format. Use JSON export or a name=value cookie string."


@callback(
    Output("tm-assisted-cookies-input", "value"),
    Input("tm-assisted-cookies-upload", "contents"),
    State("tm-assisted-cookies-upload", "filename"),
    prevent_initial_call=True,
)
def load_tm_cookie_file(contents, filename):
    if not contents:
        return no_update
    try:
        _, encoded = contents.split(",", 1)
        decoded = base64.b64decode(encoded).decode("utf-8")
        return decoded
    except Exception as e:
        logger.error(f"Could not decode uploaded TM cookies file {filename}: {e}")
        return no_update


@callback(
    Output("tm-assisted-json-status", "children"),
    Output("tm-assisted-normalized-payload", "data"),
    Input("tm-assisted-cookies-input", "value"),
    State("url", "pathname"),
    prevent_initial_call=False,
)
def validate_tm_cookie_json(cookies_value, pathname):
    if pathname != "/":
        return None, None
    normalized, count, error = _normalize_tm_cookie_payload(cookies_value or "")
    if error:
        cls = "text-muted" if not cookies_value else "text-warning"
        return html.Small(error, className=cls), None
    return html.Small(f"Valid cookies payload detected ({count} cookies).", className="text-success"), normalized


@callback(
    Output("tm-assisted-session-indicator", "children"),
    Input("url", "pathname"),
    Input("tm-admin-refresh-trigger", "data"),
    prevent_initial_call=False,
)
def update_tm_assisted_indicator(pathname, _refresh):
    if pathname != "/":
        return None
    runtime = TransfermarktRuntimeManager()
    status = runtime.get_status()
    has_cookies = bool(runtime.get_cookie_payload())
    if has_cookies:
        expiry = format_datetime(status.assisted_session_expires_at)
        return html.Div([
            html.Small("Assisted session: "),
            dbc.Badge("Loaded", color="success", className="ms-1"),
            html.Small(f"Expires: {expiry}", className="ms-2 text-muted"),
        ])
    return html.Div([
        html.Small("Assisted session: "),
        dbc.Badge("Not loaded", color="secondary", className="ms-1"),
    ])


@callback(
    Output("tm-admin-action-status", "children"),
    Output("tm-admin-refresh-trigger", "data"),
    Input("tm-assisted-load-btn", "n_clicks"),
    Input("tm-assisted-run-btn", "n_clicks"),
    Input("tm-assisted-requeue-btn", "n_clicks"),
    Input("tm-assisted-clear-btn", "n_clicks"),
    State("tm-assisted-cookies-input", "value"),
    State("tm-assisted-normalized-payload", "data"),
    State("tm-assisted-scope", "value"),
    State("tm-assisted-expires-hours", "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def handle_tm_admin_actions(load_clicks, run_clicks, requeue_clicks, clear_clicks, cookies_value, normalized_payload, scope, expires_hours, pathname):
    if pathname != "/":
        return no_update, no_update

    action = ctx.triggered_id
    runtime = TransfermarktRuntimeManager()

    try:
        if action == "tm-assisted-load-btn":
            if not normalized_payload:
                return dbc.Alert("Paste or upload a valid cookies payload first.", color="warning", className="mb-0"), no_update
            runtime.store_cookie_payload(normalized_payload, created_by="admin-ui")
            runtime.activate_assisted_mode(expires_in_hours=int(expires_hours or 12))
            return dbc.Alert("Transfermarkt assisted session loaded.", color="success", className="mb-0"), datetime.now().isoformat()

        if action == "tm-assisted-clear-btn":
            runtime.clear_cookie_payload()
            runtime.deactivate_assisted_mode()
            return dbc.Alert("Transfermarkt assisted session cleared.", color="secondary", className="mb-0"), datetime.now().isoformat()

        if action == "tm-assisted-requeue-btn":
            requeued = _requeue_failed_tm_jobs()
            return dbc.Alert(f"Requeued {requeued} failed Transfermarkt jobs.", color="info", className="mb-0"), datetime.now().isoformat()

        if action == "tm-assisted-run-btn":
            if not runtime.get_cookie_payload():
                return dbc.Alert("No assisted cookies loaded. Load a valid session first.", color="warning", className="mb-0"), no_update
            runtime.activate_assisted_mode(expires_in_hours=int(expires_hours or 12))
            watcher = MatchWatcher()
            if scope in {"priority", "all"}:
                requeued = _requeue_failed_tm_jobs_by_type({"post_match_history", "user_priority_refresh"})
                watcher.discover_finished_matches()
                watcher.enqueue_user_priority_refresh()
            if scope in {"users", "all"}:
                watcher.enqueue_user_priority_refresh()
            if scope in {"post-match", "all"}:
                watcher.discover_finished_matches()
            if scope == "all":
                watcher.enqueue_upcoming_opponents()
            if scope == "all":
                watcher.enqueue_current_season_bootstrap()
            watcher.process_queue()
            message = f"Assisted refresh executed for scope '{scope}'."
            if scope == "priority":
                message += f" Requeued {requeued} failed priority jobs."
            return dbc.Alert(message, color="info", className="mb-0"), datetime.now().isoformat()
    except Exception as e:
        logger.error(f"Error handling TM admin action: {e}")
        return dbc.Alert(f"Transfermarkt action failed: {e}", color="danger", className="mb-0"), datetime.now().isoformat()

    return no_update, no_update
