# ABOUTME: Auxiliary helpers for the performance dashboard and position-specific projection metrics.
# ABOUTME: Provides get_position_projection_metrics() and other reusable performance logic.
"""
Funciones auxiliares para el dashboard de performance.
Evita duplicación de código en performance_callbacks.py
"""

from typing import Dict, List, Optional, Any, Tuple
import logging
import numpy as np
import pandas as pd
from utils.common import validate_filters, safe_get_analysis_level

logger = logging.getLogger(__name__)


def get_position_projection_metrics(
    pos_group: str,
    history_df: "pd.DataFrame",
    match_records: List[Dict],
) -> Dict[str, Any]:
    """
    Returns position-specific KPIs for the projection section of the Player Portal.

    Aggregates season-level averages from ``history_df`` and combines them with
    match-by-match context from ``match_records`` to produce the most relevant
    forward-looking metrics per position group.

    Args:
        pos_group:     Position group string ("Forward", "Winger", "Midfielder",
                       "Defender", "Goalkeeper").
        history_df:    Season-level DataFrame (output of _fetch_player_season_history).
        match_records: List of MatchHistory dicts, sorted ascending by date.

    Returns:
        Dict with the following keys depending on position:
        - **GK**:  ``primary_metric``, ``prevented_goals``, ``save_rate``
        - **DF**:  ``primary_metric``, ``padj_interceptions``, ``xcleansheeets``
        - **MF/FW/Winger**: ``primary_metric``, ``xg``, ``xa``, ``expected_minutes``
    """
    empty = history_df.empty if history_df is not None else True

    def _latest(col: str, default: float = 0.0) -> float:
        if empty or col not in history_df.columns:
            return default
        vals = history_df[col].dropna()
        return float(vals.iloc[-1]) if not vals.empty else default

    def _match_avg(key: str, n: int = 5) -> float:
        if not match_records:
            return 0.0
        recent = match_records[-n:]
        vals = [float(r.get(key) or 0) for r in recent]
        return round(float(np.mean(vals)), 3) if vals else 0.0

    if pos_group == "Goalkeeper":
        prevented = _latest("Prevented goals")
        save_rate  = _latest("Save rate, %")
        return {
            "primary_metric": "Prevented goals",
            "prevented_goals": prevented,
            "save_rate": save_rate,
        }

    if pos_group == "Defender":
        padj = _latest("PAdj interceptions per 90")
        # xClean sheets = number of matches with 0 goals conceded in match_records
        if match_records:
            clean_count = sum(
                1 for r in match_records
                if (r.get("goals_conceded") or r.get("goals") or 0) == 0
            )
            xcleansheeets = round(clean_count / max(len(match_records), 1), 3)
        else:
            xcleansheeets = _latest("xClean sheets")
        return {
            "primary_metric": "PAdj interceptions per 90",
            "padj_interceptions": padj,
            "xcleansheeets": xcleansheeets,
        }

    # Forward / Winger / Midfielder
    xg = _latest("xG")
    xa = _latest("xA")
    # Expected minutes = average minutes in last 5 matches, or season average
    expected_minutes = _match_avg("minutes_played") or _latest("Minutes played")
    return {
        "primary_metric": "xG" if pos_group in ("Forward", "Winger") else "xA",
        "xg": xg,
        "xa": xa,
        "expected_minutes": expected_minutes,
    }

def get_streaming_label(url: Optional[str], platform: Optional[str] = None) -> str:
    """
    Returns a user-friendly streaming label based on platform and URL.
    Detects common platforms from URL if platform name is missing.
    """
    if not url:
        return "No Streaming"
    
    # If platform is already provided, use it
    if platform:
        return f"Watch on {platform}"
    
    # Otherwise, detect from URL
    u = url.lower()
    if "facebook.com" in u or "fb.com" in u:
        return "Watch on Facebook"
    if "youtube.com" in u or "youtu.be" in u:
        return "Watch on Youtube"
    if "on.cc" in u or "tv.on.cc" in u:
        return "Watch on On.cc"
    if "now.com" in u:
        return "Watch on Now TV"
        
    return "Watch on Streaming"

def validate_performance_data(performance_data: Any, context: str = "") -> bool:
    """
    Valida datos de performance con logging contextual.
    
    Args:
        performance_data: Datos a validar
        context: Contexto para logging
        
    Returns:
        True si los datos son válidos
    """
    if not performance_data or 'error' in performance_data:
        if context:
            logger.warning(f"Datos no válidos en {context}")
        return False
    return True

def get_analysis_title(filters: Dict, performance_data: Dict) -> str:
    """
    Genera título dinámico basado en filtros y datos.
    
    Args:
        filters: Filtros aplicados
        performance_data: Datos de performance
        
    Returns:
        Título formateado
    """
    filters = validate_filters(filters)
    analysis_level = safe_get_analysis_level(filters)
    season = filters.get('season', 'N/A')
    
    # Crear sufijo de filtros
    filter_info = []
    if filters.get('position_filter') and filters.get('position_filter') != 'all':
        filter_info.append(f"Pos: {filters['position_filter']}")
    if filters.get('age_range') and filters['age_range'] != [15, 45]:
        filter_info.append(f"Edad: {filters['age_range'][0]}-{filters['age_range'][1]}")
    
    filter_suffix = f" ({', '.join(filter_info)})" if filter_info else ""
    
    # Generar título según nivel
    if analysis_level == 'league':
        return f"Liga de Hong Kong - {season}{filter_suffix}"
    elif analysis_level == 'team' and 'overview' in performance_data:
        team_name = performance_data['overview'].get('team_name', 'Equipo')
        return f"{team_name} - {season}{filter_suffix}"
    elif analysis_level == 'player' and 'basic_info' in performance_data:
        player_name = performance_data['basic_info'].get('name', 'Jugador')
        return f"{player_name} - {season}"
    else:
        return "Datos no disponibles"

def create_kpi_structure(analysis_level: str, data: Dict) -> List[Dict]:
    """
    Crea estructura de KPIs basada en el nivel de análisis.
    
    Args:
        analysis_level: Nivel de análisis ('league', 'team', 'player')
        data: Datos a procesar
        
    Returns:
        Lista de diccionarios con estructura de KPIs
    """
    if analysis_level == 'league' and 'overview' in data:
        overview = data['overview']
        return [
            {'value': overview.get('total_players', 0), 'label': 'Jugadores', 'color': 'primary', 'md': 2},
            {'value': overview.get('total_teams', 0), 'label': 'Equipos', 'color': 'success', 'md': 2},
            {'value': overview.get('total_goals', 0), 'label': 'Goles Totales', 'color': 'warning', 'md': 2},
            {'value': overview.get('total_assists', 0), 'label': 'Asistencias', 'color': 'info', 'md': 2},
            {'value': f"{overview.get('average_age', 0)}", 'label': 'Edad Promedio', 'color': 'secondary', 'md': 2},
            {'value': f"{overview.get('avg_goals_per_player', 0)}", 'label': 'Goles/Jugador', 'color': 'primary', 'md': 2}
        ]
    
    elif analysis_level == 'team' and 'overview' in data:
        overview = data['overview']
        return [
            {'value': overview.get('total_players', 0), 'label': 'Jugadores', 'color': 'primary', 'md': 3},
            {'value': overview.get('total_goals', 0), 'label': 'Goles Totales', 'color': 'warning', 'md': 3},
            {'value': overview.get('total_assists', 0), 'label': 'Asistencias', 'color': 'info', 'md': 3},
            {'value': f"{overview.get('avg_age', 0)}", 'label': 'Edad Promedio', 'color': 'secondary', 'md': 3}
        ]
    
    elif analysis_level == 'player' and 'basic_info' in data:
        basic_info = data['basic_info']
        performance_stats = data.get('performance_stats', {})
        return [
            {'value': basic_info.get('age', 'N/A'), 'label': 'Edad', 'color': 'primary', 'md': 2},
            {'value': basic_info.get('matches_played', 0), 'label': 'Partidos', 'color': 'success', 'md': 2},
            {'value': performance_stats.get('goals', 0), 'label': 'Goles', 'color': 'warning', 'md': 2},
            {'value': performance_stats.get('assists', 0), 'label': 'Asistencias', 'color': 'info', 'md': 2},
            {'value': basic_info.get('position_group', 'N/A'), 'label': 'Posición', 'color': 'secondary', 'md': 2},
            {'value': f"{performance_stats.get('minutes_per_match', 0):.0f}", 'label': 'Min/Partido', 'color': 'primary', 'md': 2}
        ]
    
    return []

def handle_performance_error(error: Exception, context: str) -> Dict:
    """
    Maneja errores de performance de forma consistente.
    
    Args:
        error: Excepción ocurrida
        context: Contexto del error
        
    Returns:
        Diccionario con estructura de error
    """
    logger.error(f"Error en {context}: {str(error)}")
    return {"error": f"Error {context}: {str(error)}"}

def get_chart_config(chart_type: str, data: Dict, title: str) -> Dict:
    """
    Genera configuración estándar para gráficos.
    
    Args:
        chart_type: Tipo de gráfico
        data: Datos para el gráfico
        title: Título del gráfico
        
    Returns:
        Configuración del gráfico
    """
    base_config = {
        'title': title,
        'height': 400,
        'showlegend': False
    }
    
    if chart_type == 'bar':
        base_config.update({
            'color_continuous_scale': 'Blues',
            'labels': {'x': 'Elementos', 'y': 'Valores'}
        })
    elif chart_type == 'pie':
        base_config['height'] = 400
    elif chart_type == 'scatter':
        base_config.update({
            'labels': {'x': 'X', 'y': 'Y'},
            'hover_name': 'Elemento'
        })
    
    return base_config