"""
Callbacks para el dashboard de lesiones - VERSIÓN REFACTORIZADA.
Usa funciones auxiliares para evitar duplicación de código.
"""

from dash import Input, Output, State, callback, html, dash_table, dcc
from dash.dcc.express import send_bytes, send_string
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
from dash.exceptions import PreventUpdate

# Importar nuestras utilidades
from utils.common import (
    validate_data, handle_empty_data, create_error_message, 
    create_kpi_cards_row
)
from utils.injury_helpers import (
    filter_injuries_by_team, filter_injuries_by_period,
    calculate_injury_statistics, get_injury_distribution,
    get_stats_with_fallback, create_distribution_chart_data,
    prepare_table_data, get_monthly_trends_data, get_body_parts_distribution
)
from utils.pdf_generator import SportsPDFGenerator

# Importar gestor de datos
from data.transfermarkt_data_manager import TransfermarktDataManager

# Inicializar el gestor de datos de Transfermarkt
transfermarkt_manager = TransfermarktDataManager(auto_load=True)

# Callback para actualizar opciones de equipos
@callback(
    Output('injury-team-selector', 'options'),
    Input('injury-analysis-type', 'value'),
    prevent_initial_call=False
)
def update_team_options(analysis_type):
    """Actualiza las opciones de equipos para el selector."""
    teams = transfermarkt_manager.get_teams_with_injuries()
    options = [{"label": "Todos los equipos", "value": "all"}]
    options.extend([{"label": team, "value": team} for team in teams])
    return options

# Callback principal para cargar datos
@callback(
    [Output('injury-data-store', 'data'),
     Output('injury-filters-store', 'data')],
    [Input('injury-analysis-type', 'value'),
     Input('injury-team-selector', 'value'),
     Input('injury-period', 'value'),
     Input('injury-refresh-button', 'n_clicks')],
    prevent_initial_call=False
)
def load_injury_data(analysis_type, team, period, n_clicks):
    """Carga y filtra los datos de lesiones desde Transfermarkt."""
    
    # Guardar filtros exactamente como los seleccionó el usuario
    current_filters = {
        'analysis_type': analysis_type,
        'team': team,
        'period': period
    }
    
    # Si se presionó refresh, forzar actualización
    if n_clicks and n_clicks > 0:
        success = transfermarkt_manager.refresh_data(force_scraping=True)
        if not success:
            print("Error al actualizar datos desde Transfermarkt")
    
    # Obtener datos base
    all_injuries = transfermarkt_manager.get_injuries_data()
    
    if not validate_data(all_injuries):
        return [], current_filters
    
    # Aplicar filtros EXACTAMENTE como los seleccionó el usuario
    # Sin lógica "inteligente" que cambie los filtros
    filtered_data = filter_injuries_by_period(all_injuries, period)
    filtered_data = filter_injuries_by_team(filtered_data, team)
    
    # Debug mejorado
    team_name = team if team != 'all' else 'Todos los equipos'
    period_names = {
        '1m': 'Último mes',
        '3m': 'Últimos 3 meses', 
        '6m': 'Últimos 6 meses',
        'season': 'Última temporada',
        'all': 'Todo el historial'
    }
    period_name = period_names.get(period, period)
    
    print(f"Filtros aplicados - Período: {period_name}, Equipo: {team_name}")
    print(f"Datos filtrados: {len(filtered_data)} lesiones de {len(all_injuries)} total")
    
    return filtered_data, current_filters

@callback(
    Output('injury-main-kpis', 'children'),
    [Input('injury-data-store', 'data'),
     Input('injury-team-selector', 'value')]
)
def update_injury_kpis(data, selected_team):
    """Actualiza los KPIs principales del dashboard de lesiones."""
    
    if not validate_data(data):
        # Mensaje específico según el contexto
        if selected_team and selected_team != 'all':
            message = f"No injury data for {selected_team} in the selected period"
        else:
            message = "No injury data for the selected period"
            
        return handle_empty_data(message)
    
    try:
        # Los datos en 'data' ya vienen filtrados por período desde load_injury_data
        # Solo necesitamos aplicar filtro adicional de equipo si es necesario
        filtered_data = filter_injuries_by_team(data, selected_team)
        
        # SIMPLIFICADO: Calcular estadísticas directamente de los datos filtrados
        stats = calculate_injury_statistics(filtered_data)
        
        # Preparar datos para KPIs
        kpi_data = [
            {
                'value': stats['total_injuries'],
                'label': 'Total Lesiones',
                'color': 'danger',
                'md': 2
            },
            {
                'value': stats['active_injuries'],
                'label': 'En Tratamiento',
                'color': 'warning',
                'md': 2
            },
            {
                'value': f"{stats['avg_recovery_days']:.0f}",
                'label': 'Días Promedio Recuperación',
                'color': 'info',
                'md': 2
            },
            {
                'value': stats['most_common_injury'],
                'label': 'Lesión Más Común',
                'color': 'success',
                'md': 3
            },
            {
                'value': stats['most_affected_part'],
                'label': 'Zona Más Afectada',
                'color': 'secondary',
                'md': 3
            }
        ]
        
        return create_kpi_cards_row(kpi_data)
        
    except Exception as e:
        return create_error_message(e, "calculando KPIs")

@callback(
    Output('injury-distribution-chart', 'children'),
    [Input('injury-data-store', 'data'),
     Input('injury-team-selector', 'value')]
)
def update_injury_distribution(data, selected_team):
    """Actualiza el gráfico de distribución de lesiones."""
    
    if not validate_data(data):
        if selected_team and selected_team != 'all':
            message = f"No {selected_team} injuries in the selected period"
        else:
            message = "No injuries in the selected period"
        return handle_empty_data(message)
    
    try:
        # Los datos en 'data' ya vienen filtrados por período
        # Solo aplicar filtro adicional de equipo si es necesario
        filtered_data = filter_injuries_by_team(data, selected_team)
        
        # SIMPLIFICADO: Obtener distribución directamente de los datos filtrados
        types, counts = get_injury_distribution(filtered_data)
        
        if not types:
            return handle_empty_data("Not enough data for the graph")
        
        # Crear título dinámico
        title = "Distribución por Tipo de Lesión"
        if selected_team and selected_team != 'all':
            title += f" - {selected_team}"
        
        # Crear gráfico
        fig = px.bar(
            x=types,
            y=counts,
            title=title,
            labels={'x': 'Tipo de Lesión', 'y': 'Número de Casos'},
            color=counts,
            color_continuous_scale='Reds'
        )
        
        fig.update_layout(
            height=400,
            showlegend=False,
            xaxis_tickangle=-45
        )
        
        return dcc.Graph(figure=fig)
        
    except Exception as e:
        return create_error_message(e, "generando gráfico de distribución")

@callback(
    Output('injury-trends-chart', 'children'),
    [Input('injury-data-store', 'data')]
)
def update_injury_trends(data):
    """Actualiza el gráfico de tendencias temporales de lesiones."""
    
    if not validate_data(data):
        return handle_empty_data()
    
    try:
        # Obtener datos de tendencias usando función auxiliar
        months, counts = get_monthly_trends_data(data)
        
        if not months:
            return handle_empty_data("No data with valid dates available")
        
        # Crear gráfico de líneas
        fig = px.line(
            x=months,
            y=counts,
            title="Tendencia de Lesiones por Mes",
            labels={'x': 'Mes', 'y': 'Número de Lesiones'},
            markers=True
        )
        
        fig.update_layout(height=400)
        
        return dcc.Graph(figure=fig)
        
    except Exception as e:
        return create_error_message(e, "generando gráfico de tendencias")

@callback(
    Output('injury-table-container', 'children'),
    [Input('injury-data-store', 'data')]
)
def update_injury_table(data):
    """Actualiza la tabla interactiva de lesiones."""
    
    if not validate_data(data):
        return handle_empty_data("No data with valid dates available")
    
    try:
        # Preparar datos usando función auxiliar
        table_data = prepare_table_data(data)
        
        if not table_data:
            return handle_empty_data()
        
        # Crear tabla interactiva
        table = dash_table.DataTable(
            data=table_data,
            columns=[{'name': col, 'id': col, 'type': 'text'} for col in table_data[0].keys()],
            style_cell={
                'textAlign': 'left',
                'padding': '10px',
                'fontFamily': 'Arial',
                'fontSize': 14
            },
            style_header={
                'backgroundColor': '#dc3545',
                'color': 'white',
                'fontWeight': 'bold',
                'textAlign': 'center'
            },
            style_data_conditional=[ # type: ignore
                {
                    'if': {'filter_query': '{Estado} = "En tratamiento"'},
                    'backgroundColor': '#fff3cd',
                    'color': 'black',
                },
                {
                    'if': {'filter_query': '{Severidad} = "Grave"'},
                    'backgroundColor': '#f8d7da',
                    'color': 'black',
                }
            ],
            page_size=10,
            sort_action='native',
            filter_action='native',
            style_as_list_view=True
        )
        
        return table
        
    except Exception as e:
        return create_error_message(e, "generando tabla")

@callback(
    Output('injury-body-parts-analysis', 'children'),
    [Input('injury-data-store', 'data')]
)
def update_body_parts_analysis(data):
    """Actualiza el análisis de lesiones por partes del cuerpo."""
    
    if not validate_data(data):
        return handle_empty_data("No data with valid dates available")
    
    try:
        
        # Obtener distribución usando función auxiliar
        body_parts_data = get_body_parts_distribution(data)
        
        if not body_parts_data:
            return handle_empty_data()
        
        # Crear lista de elementos
        items = []
        for data_item in body_parts_data:
            items.append(
                dbc.ListGroupItem([
                    html.Div([
                        html.Strong(str(data_item['part'])),
                        html.Span(f" ({data_item['count']})", className="text-muted"),
                        dbc.Progress(
                            value=data_item['percentage'],
                            color="danger",
                            className="mt-1",
                            style={"height": "8px"}
                        ),
                        html.Small(f"{data_item['percentage']:.1f}%", className="text-muted")
                    ])
                ])
            )
        
        return dbc.ListGroup(items, flush=True)
        
    except Exception as e:
        return create_error_message(e, "analizando partes del cuerpo")

@callback(
    Output('injury-risk-analysis', 'children'),
    [Input('injury-data-store', 'data'),
     Input('injury-team-selector', 'value')]
)
def update_injury_risk_analysis(data, selected_team):
    """Actualiza el análisis de riesgo de lesiones."""
    
    if not validate_data(data):
        if selected_team and selected_team != 'all':
            message = f"No {selected_team} injuries in the selected period"
        else:
            message = "No injuries in the selected period"
        return handle_empty_data(message)
    
    try:
        # Si hay equipo seleccionado, mostrar análisis específico
        if selected_team and selected_team != 'all':
            return _create_team_specific_analysis(data, selected_team)
        else:
            return _create_general_risk_analysis(data)
            
    except Exception as e:
        return create_error_message(e, "generando análisis de riesgo")

def _create_team_specific_analysis(data, selected_team):
    """Crea análisis específico para un equipo."""
    team_injuries = filter_injuries_by_team(data, selected_team)
    
    if not team_injuries:
        return handle_empty_data(f"No hay datos de lesiones para el equipo {selected_team}")
    
    # Calcular estadísticas del equipo
    stats = {
        'total_injuries': len(team_injuries),
        'severe_injuries': len([i for i in team_injuries if i.get('severity') == 'Grave']),
        'active_injuries': len([i for i in team_injuries if i.get('status') == 'En tratamiento'])
    }
    
    # Crear gráfico para el equipo
    fig = go.Figure()
    
    metrics = ['Total Lesiones', 'Lesiones Graves', 'Lesiones Activas']
    values = [stats['total_injuries'], stats['severe_injuries'], stats['active_injuries']]
    
    fig.add_trace(go.Bar(
        x=values,
        y=metrics,
        orientation='h',
        marker_color=['#e74c3c', '#c0392b', '#e67e22'],
        text=values,
        textposition='auto'
    ))
    
    fig.update_layout(
        title=f"Análisis de Lesiones - {selected_team}",
        height=400,
        xaxis_title="Número de Lesiones",
        margin=dict(l=150)
    )
    
    return dcc.Graph(figure=fig)

def _create_general_risk_analysis(data):
    """Crea análisis general de riesgo por equipos."""
    # Calcular estadísticas por equipo
    team_stats = {}
    
    for injury in data:
        team = injury.get('team', 'Desconocido')
        
        if team not in team_stats:
            team_stats[team] = {
                'total_injuries': 0,
                'severe_injuries': 0,
                'recovery_days': [],
                'active_injuries': 0
            }
        
        # Incrementar contadores
        team_stats[team]['total_injuries'] += 1
        
        if injury.get('severity') == 'Grave':
            team_stats[team]['severe_injuries'] += 1
        
        if injury.get('recovery_days'):
            team_stats[team]['recovery_days'].append(injury.get('recovery_days', 0))
        
        if injury.get('status') == 'En tratamiento':
            team_stats[team]['active_injuries'] += 1
    
    # Calcular índice de riesgo y crear lista ordenada
    team_risk = []
    
    for team, stats in team_stats.items():
        from utils.common import safe_division
        
        avg_recovery = safe_division(sum(stats['recovery_days']), len(stats['recovery_days']))
        
        # Fórmula de riesgo
        risk_score = (
            stats['total_injuries'] * 0.4 +
            stats['severe_injuries'] * 2 +
            stats['active_injuries'] * 1.5 +
            avg_recovery * 0.01
        )
        
        team_risk.append({
            'team': team,
            'risk_score': risk_score
        })
    
    # Ordenar y tomar top 8
    team_risk.sort(key=lambda x: x['risk_score'], reverse=True)
    if len(team_risk) > 8:
        team_risk = team_risk[:8]
    
    # Crear gráfico
    teams = [item['team'] for item in team_risk]
    risks = [item['risk_score'] for item in team_risk]
    
    fig = px.bar(
        x=risks,
        y=teams,
        orientation='h',
        title="Índice de Riesgo por Equipo",
        labels={'x': 'Índice de Riesgo', 'y': 'Equipo'},
        color=risks,
        color_continuous_scale='Reds'
    )
    
    fig.update_layout(height=400, showlegend=False)
    
    return dcc.Graph(figure=fig)

@callback(
    Output('download-injury-report', 'data'),
    [Input('injury-export-button', 'n_clicks')],
    [State('injury-data-store', 'data'),
     State('injury-filters-store', 'data')],
    prevent_initial_call=True
)
def export_injury_report(n_clicks, data, filters):
    """Exporta el reporte de lesiones a PDF."""
    
    if n_clicks is None:
        raise PreventUpdate
    
    if not validate_data(data):
        raise PreventUpdate
    
    try:
        # Calcular estadísticas usando función auxiliar
        stats = calculate_injury_statistics(data)
        
        # Generar PDF
        pdf_generator = SportsPDFGenerator()
        pdf_buffer = pdf_generator.create_injury_report(data, filters, stats)
        
        # Generar nombre de archivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"reporte_lesiones_transfermarkt_{timestamp}.pdf"
        
        # Usar dcc.send_bytes para consistencia con performance_callbacks
     
        return send_bytes(pdf_buffer.getvalue(), filename)
        
    except Exception as e:
        # Fallback a CSV
        df = pd.DataFrame(data)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"reporte_lesiones_transfermarkt_{timestamp}.csv"
        
        filter_info = f"# Generado desde Transfermarkt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        filter_info += f"# Error generando PDF: {str(e)}\n\n"
        
        csv_string = filter_info + df.to_csv(index=False)
        
        return send_string(csv_string, filename)