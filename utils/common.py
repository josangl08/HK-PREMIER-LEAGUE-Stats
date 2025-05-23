"""
Utilidades comunes para toda la aplicación.
"""
from typing import Any, Dict, Union, List
import dash_bootstrap_components as dbc
from dash import html
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def format_season_short(season):
    """
    Convierte formato de temporada de '2024-25' a '24/25'.
    
    Args:
        season (str): Temporada en formato '2024-25'
        
    Returns:
        str: Temporada en formato corto '24/25'
    """
    if not season or '-' not in season:
        return season
    
    try:
        year1, year2 = season.split('-')
        short_year1 = year1[-2:]  # Últimos 2 dígitos
        short_year2 = year2[-2:]  # Últimos 2 dígitos
        return f"{short_year1}/{short_year2}"
    except:
        return season

def format_datetime(dt):
    """
    Formatea datetime para mostrar en la UI.
    
    Args:
        dt: datetime object, string, o None
        
    Returns:
        str: Fecha formateada o 'Nunca'
    """
    if dt is None:
        return 'Nunca'
    
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(dt, str) and dt not in ['None', 'null', '{}']:
        try:
            # Intentar parsear si es string ISO
            parsed_dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            return parsed_dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return dt[:19].replace('T', ' ') if len(dt) >= 19 else dt
    
    return 'Nunca'

def get_current_season():
    """
    Obtiene la temporada actual de forma centralizada.
    
    Returns:
        str: Temporada actual
    """
    return "2024-25"

def validate_filters(filters, default_analysis_level='league'):
    """Valida y normaliza los filtros de performance."""
    if filters is None or not isinstance(filters, dict):
        return {'analysis_level': default_analysis_level}
    
    # Asegurar que analysis_level existe
    if 'analysis_level' not in filters:
        filters['analysis_level'] = default_analysis_level
    
    return filters

def safe_get_analysis_level(filters, default='league'):
    """Obtiene el analysis_level de forma segura."""
    validated_filters = validate_filters(filters, default)
    return validated_filters.get('analysis_level', default)

def validate_data(data: Any, data_name: str = "datos") -> bool:
    """
    Valida que los datos no estén vacíos o sean None.
    
    Args:
        data: Datos a validar
        data_name: Nombre descriptivo de los datos para logging
        
    Returns:
        True si los datos son válidos
    """
    if data is None:
        return False
    
    if isinstance(data, (list, dict)) and len(data) == 0:
        return False
    
    return True

def handle_empty_data(message: str = "No hay datos disponibles") -> html.Div:
    """
    Crea un componente HTML para mostrar cuando no hay datos.
    
    Args:
        message: Mensaje personalizado a mostrar
        
    Returns:
        Componente HTML con el mensaje
    """
    return html.Div([
        html.Div([
            html.I("ℹ️", style={"fontSize": "2rem", "marginBottom": "10px"}),
            html.H5(message, className="text-warning"),
            html.P("Try changing the filters to see more data.", 
                  className="small text-warning")
        ], className="text-center")
    ], className="p-4", style={"minHeight": "200px", "display": "flex", "alignItems": "center", "justifyContent": "center"})

def create_error_message(error: Exception, context: str = "") -> dbc.Alert:
    """
    Crea un mensaje de error consistente para mostrar en callbacks.
    
    Args:
        error: Excepción que ocurrió
        context: Contexto donde ocurrió el error
        
    Returns:
        Componente Alert con el mensaje de error
    """
    error_msg = f"Error {context}: {str(error)}" if context else f"Error: {str(error)}"
    
    return dbc.Alert([
        html.H6("⚠️ Error", className="alert-heading"),
        html.P(error_msg),
        html.Hr(),
        html.Small("If the problem persists, contact the administrator..", className="mb-0")
    ], color="danger")

def safe_division(numerator: float, denominator: float, default: float = 0) -> float:
    """
    Realiza división segura evitando división por cero.
    
    Args:
        numerator: Numerador
        denominator: Denominador
        default: Valor por defecto si denominador es 0
        
    Returns:
        Resultado de la división o valor por defecto
    """
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except (TypeError, ValueError):
        return default

def get_top_items(items_dict: Dict[str, int], top_n: int = 10, default_item: str = "N/A") -> tuple:
    """
    Obtiene los top N elementos de un diccionario de conteos.
    
    Args:
        items_dict: Diccionario con elementos y sus conteos
        top_n: Número de items top a retornar
        default_item: Item por defecto si no hay datos
        
    Returns:
        Tupla con (items, counts, most_common_item)
    """
    if not items_dict:
        return [], [], default_item
    
    # Ordenar por frecuencia
    sorted_items = sorted(items_dict.items(), key=lambda x: x[1], reverse=True)
    
    # Obtener el más común
    most_common_item = sorted_items[0][0] if sorted_items else default_item
    
    # Tomar top N
    if len(sorted_items) > top_n:
        sorted_items = sorted_items[:top_n]
    
    items = [item[0] for item in sorted_items]
    counts = [item[1] for item in sorted_items]
    
    return items, counts, most_common_item

def create_kpi_cards_row(kpi_data: List[Dict]) -> dbc.Row:
    """
    Crea una fila de tarjetas KPI de forma consistente.
    
    Args:
        kpi_data: Lista de diccionarios con formato:
                 [{'value': 100, 'label': 'Total', 'color': 'danger', 'md': 2}, ...]
        
    Returns:
        Fila Bootstrap con las tarjetas KPI
    """
    cards = []
    
    for kpi in kpi_data:
        card = dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(kpi['value'], className=f"text-{kpi.get('color', 'primary')}"),
                    html.P(kpi['label'], className="card-text")
                ])
            ])
        ], md=kpi.get('md', 2))
        
        cards.append(card)
    
    return dbc.Row(cards)

