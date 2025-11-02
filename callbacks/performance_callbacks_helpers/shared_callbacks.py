# ABOUTME: Shared callbacks for filter state and data loading
# ABOUTME: Foundation callbacks that all views depend on

"""
Foundation callbacks for performance dashboard.

This module contains the core data loading and filter management callbacks
that all other view-specific callbacks depend on.
"""

from dash import Input, Output, callback, html
import dash_bootstrap_components as dbc
from utils.common import format_season_short
from utils.app_context import get_hong_kong_data_manager

# Get the singleton data manager instance from app context
# This avoids creating a duplicate instance and prevents circular imports
# LAZY INITIALIZATION: We call this inside callbacks, not at import time
def _get_data_manager():
    """Lazy getter for data_manager to avoid import-time issues."""
    return get_hong_kong_data_manager()


# Import additional utilities for KPIs
from utils.common import create_kpi_cards_row, safe_get_analysis_level, validate_filters
from utils.performance_helpers import (
    validate_performance_data,
    get_analysis_title,
    create_kpi_structure,
    handle_performance_error
)


# CALLBACK 1: Update selector options (copy from old file, lines 24-53)
@callback(
    [Output('team-selector', 'options'),
     Output('player-selector', 'options')],
    [Input('season-selector', 'value'),
     Input('team-selector', 'value')],
    prevent_initial_call=False
)
def update_selector_options(season, selected_team):
    """
    Actualiza las opciones de equipos y jugadores según la temporada
    y equipo seleccionado.

    DESIGN NOTES:
    - Pure function (no side effects beyond returns)
    - Low latency (should be < 100ms)
    - No data store writes
    - Prevent circular dependencies by keeping logic simple
    """
    # Lazy initialization of data_manager (avoid import-time issues)
    data_manager = _get_data_manager()

    # Actualizar temporada si es necesaria
    if season != data_manager.current_season:
        data_manager.refresh_data(season)

    # Opciones de equipos (siempre disponibles)
    teams = data_manager.get_available_teams()
    team_options = [
        {"label": f"🏆 {team}", "value": team}
        for team in teams
    ]

    # Opciones de jugadores (basado en el equipo seleccionado)
    if selected_team:
        # Jugadores del equipo seleccionado
        players = data_manager.get_available_players(selected_team)
        player_options = [
            {"label": f"👤 {player}", "value": player}
            for player in players
        ]
    else:
        # Todos los jugadores ordenados alfabéticamente
        players = data_manager.get_available_players()
        player_options = [
            {"label": f"👤 {player}", "value": player}
            for player in players
        ]

    return team_options, player_options


# CALLBACK 2: Load performance data (copy from old file, lines 56-177)
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
    """
    Carga los datos de performance según los filtros seleccionados.

    DESIGN NOTES:
    - Only callback that triggers data_manager operations
    - Caches result in performance-data-store
    - Stores filter state for downstream consumption
    - Returns early on validation failure
    - No chart rendering logic (that's downstream)
    """
    # Lazy initialization of data_manager (avoid import-time issues)
    data_manager = _get_data_manager()

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
            # Asegurar que los datos de la temporada actual estén disponibles
            if not data_manager._check_data_availability():
                data_manager.refresh_data(season)

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
                performance_data = (
                    data_manager.aggregator.get_team_statistics(
                        team, position_filter, age_range
                    )
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
                performance_data = (
                    data_manager.aggregator.get_league_statistics(
                        position_filter, age_range
                    )
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
                f"✅ Data successfully loaded - League "
                f"({format_season_short(season)})",
                color="success",
                dismissable=True,
                duration=3000
            )
        elif analysis_level == 'team':
            status_alert = dbc.Alert(
                f"✅ Data successfully loaded - Team: {team} "
                f"({format_season_short(season)})",
                color="success",
                dismissable=True,
                duration=3000
            )
        elif analysis_level == 'player':
            player_message = f"✅ Data successfully loaded - Player: {player}"
            if team:
                player_message += f" ({team})"
            status_alert = dbc.Alert(
                player_message,
                color="success",
                dismissable=True,
                duration=3000
            )

        return (
            performance_data,
            chart_data,
            current_filters,
            status_alert,
            season_options
        )

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


# CALLBACK 3: Main KPIs (shared across all views)
@callback(
    [Output('kpi-title', 'children'),
     Output('main-kpis', 'children')],
    [Input('performance-data-store', 'data'),
     Input('current-filters-store', 'data')],
    prevent_initial_call=False
)
def update_main_kpis(performance_data, filters):
    """
    Actualiza los KPIs principales según los datos.

    DESIGN NOTES:
    - Handles all analysis levels (league/team/player)
    - Returns title and KPI cards
    - Uses helper functions for consistency
    - No guard pattern - works for all levels
    """
    # Validar datos usando función auxiliar
    if not validate_performance_data(performance_data, "KPIs"):
        return "Sin datos disponibles", html.Div("Selecciona filtros válidos")

    try:
        # Obtener título usando función auxiliar
        title = get_analysis_title(filters, performance_data)

        # Validar filtros y obtener nivel de análisis
        filters = validate_filters(filters)
        analysis_level = safe_get_analysis_level(filters)

        # Crear estructura de KPIs usando función auxiliar
        kpi_data = create_kpi_structure(analysis_level, performance_data)

        if not kpi_data:
            return "Datos no disponibles", html.Div("Error procesando datos")

        # Crear fila de KPIs usando utilidad común
        kpis = create_kpi_cards_row(kpi_data)

        return title, kpis

    except Exception as e:
        error_info = handle_performance_error(e, "actualizando KPIs")
        return "Error", html.Div(
            str(error_info.get('error', 'Error desconocido'))
        )
