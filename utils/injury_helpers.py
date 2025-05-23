"""
Utilidades específicas para el dashboard de lesiones.
Funciones auxiliares para evitar duplicación de código en injury_callbacks.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import plotly.express as px
from dash import dcc, html
import dash_bootstrap_components as dbc

from .common import validate_data, safe_division, get_top_items

def filter_injuries_by_team(injuries: List[Dict], team: Optional[str]) -> List[Dict]:
    """
    Filtra lesiones por equipo.
    
    Args:
        injuries: Lista de lesiones
        team: Nombre del equipo o None/all para todos
        
    Returns:
        Lista filtrada de lesiones
    """
    if not team or team == 'all':
        return injuries
    
    return [injury for injury in injuries if injury.get('team') == team]

def filter_injuries_by_period(injuries: List[Dict], period: str) -> List[Dict]:
    """
    Filtra lesiones por período de tiempo.
    
    Args:
        injuries: Lista de lesiones
        period: Período ('1m', '3m', '6m', 'season', 'all')
        
    Returns:
        Lista filtrada de lesiones
    """
    if period == 'all':
        return injuries
    
    days_map = {'1m': 30, '3m': 90, '6m': 180, 'season': 365}
    days_back = days_map.get(period, 90)
    cutoff_date = datetime.now() - timedelta(days=days_back)
    
    filtered_data = []
    for injury in injuries:
        injury_date_str = injury.get('injury_date')
        if injury_date_str:
            try:
                injury_date = datetime.strptime(injury_date_str, '%Y-%m-%d')
                if injury_date >= cutoff_date:
                    filtered_data.append(injury)
            except:
                # Si hay error parseando fecha, incluir el registro
                filtered_data.append(injury)
        else:
            # Si no hay fecha, incluir el registro
            filtered_data.append(injury)
    
    return filtered_data

def calculate_injury_statistics(injuries: List[Dict]) -> Dict:
    """
    Calcula estadísticas básicas de lesiones.
    
    Args:
        injuries: Lista de lesiones
        
    Returns:
        Diccionario con estadísticas calculadas
    """
    if not validate_data(injuries):
        return {
            'total_injuries': 0,
            'active_injuries': 0,
            'avg_recovery_days': 0,
            'most_common_injury': 'N/A',
            'most_affected_part': 'N/A'
        }
    
    total_injuries = len(injuries)
    active_injuries = len([injury for injury in injuries if injury.get('status') == 'En tratamiento'])
    
    # Días de recuperación promedio
    recovery_days = [injury.get('recovery_days', 0) for injury in injuries if injury.get('recovery_days')]
    avg_recovery_days = safe_division(sum(recovery_days), len(recovery_days))
    
    # Lesión más común
    injury_types = [injury.get('injury_type', 'Desconocida') for injury in injuries]
    injury_counts = {}
    for injury_type in injury_types:
        injury_counts[injury_type] = injury_counts.get(injury_type, 0) + 1
    
    _, _, most_common_injury = get_top_items(injury_counts, 1, "N/A")
    
    # Parte del cuerpo más afectada
    body_parts = [injury.get('body_part', 'Otros') for injury in injuries]
    body_part_counts = {}
    for body_part in body_parts:
        body_part_counts[body_part] = body_part_counts.get(body_part, 0) + 1
    
    _, _, most_affected_part = get_top_items(body_part_counts, 1, "N/A")
    
    return {
        'total_injuries': total_injuries,
        'active_injuries': active_injuries,
        'avg_recovery_days': round(avg_recovery_days, 1),
        'most_common_injury': most_common_injury,
        'most_affected_part': most_affected_part
    }

def get_injury_distribution(injuries: List[Dict], top_n: int = 10) -> Tuple[List[str], List[int]]:
    """
    Obtiene distribución de lesiones por tipo.
    
    Args:
        injuries: Lista de lesiones
        top_n: Número máximo de tipos a retornar
        
    Returns:
        Tupla con (tipos, conteos)
    """
    if not validate_data(injuries):
        return [], []
    
    injury_types = [injury.get('injury_type', 'Desconocida') for injury in injuries]
    injury_counts = {}
    for injury_type in injury_types:
        injury_counts[injury_type] = injury_counts.get(injury_type, 0) + 1
    
    types, counts, _ = get_top_items(injury_counts, top_n)
    return types, counts

def get_stats_with_fallback(manager, selected_team: Optional[str], filtered_data: List[Dict]) -> Dict:
    """
    Obtiene estadísticas usando aggregator o fallback manual.
    Nombre más corto y claro.
    
    Args:
        manager: TransfermarktDataManager
        selected_team: Equipo seleccionado
        filtered_data: Datos ya filtrados
        
    Returns:
        Diccionario con estadísticas
    """
   
    return calculate_injury_statistics(filtered_data)
    
def create_distribution_chart_data(injuries: List[Dict], manager, selected_team: Optional[str]) -> Tuple[List[str], List[int]]:
    """
    Obtiene datos para gráfico de distribución con fallback.
    
    Args:
        injuries: Lista de lesiones
        manager: TransfermarktDataManager
        selected_team: Equipo seleccionado
        
    Returns:
        Tupla con (tipos, conteos)
    """
    
    return get_injury_distribution(injuries)
    

def prepare_table_data(injuries: List[Dict]) -> List[Dict]:
    """
    Prepara datos de lesiones para tabla interactiva.
    
    Args:
        injuries: Lista de lesiones
        
    Returns:
        Lista de diccionarios formateados para DataTable
    """
    if not validate_data(injuries):
        return []
    
    table_data = []
    for injury in injuries:
        row = {
            'Jugador': injury.get('player_name', 'N/A'),
            'Equipo': injury.get('team', 'N/A'),
            'Tipo': injury.get('injury_type', 'N/A'),
            'Zona': injury.get('body_part', 'N/A'),
            'Severidad': injury.get('severity', 'N/A'),
            'Fecha': injury.get('injury_date', ''),
            'Días Rec.': injury.get('recovery_days', 0),
            'Estado': injury.get('status', 'N/A')
        }
        table_data.append(row)
    
    return table_data

def get_monthly_trends_data(injuries: List[Dict]) -> Tuple[List[str], List[int]]:
    """
    Obtiene datos de tendencias mensuales.
    
    Args:
        injuries: Lista de lesiones
        
    Returns:
        Tupla con (meses, conteos)
    """
    if not validate_data(injuries):
        return [], []
    
    # Agrupar por mes
    monthly_counts = {}
    
    for injury in injuries:
        injury_date_str = injury.get('injury_date')
        if injury_date_str:
            try:
                injury_date = datetime.strptime(injury_date_str, '%Y-%m-%d')
                month_key = injury_date.strftime('%Y-%m')
                monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1
            except:
                continue
    
    # Ordenar por fecha
    sorted_months = sorted(monthly_counts.items())
    
    if not sorted_months:
        return [], []
    
    months = [item[0] for item in sorted_months]
    counts = [item[1] for item in sorted_months]
    
    return months, counts

def get_body_parts_distribution(injuries: List[Dict], top_n: int = 8) -> List[Dict]:
    """
    Obtiene distribución de lesiones por partes del cuerpo.
    
    Args:
        injuries: Lista de lesiones
        top_n: Número máximo de partes a retornar
        
    Returns:
        Lista de diccionarios con información de cada parte del cuerpo
    """
    if not validate_data(injuries):
        return []
    
    body_parts = [injury.get('body_part', 'Otros') for injury in injuries]
    body_part_counts = {}
    for part in body_parts:
        body_part_counts[part] = body_part_counts.get(part, 0) + 1
    
    parts, counts, _ = get_top_items(body_part_counts, top_n)
    
    total_injuries = len(injuries)
    result = []
    
    for part, count in zip(parts, counts):
        percentage = safe_division(count * 100, total_injuries)
        result.append({
            'part': part,
            'count': count,
            'percentage': round(percentage, 1)
        })
    
    return result