from dash import Input, Output, State, callback, html, dash_table, dcc
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dash.exceptions import PreventUpdate
import logging

# Importar nuestro nuevo gestor de datos
from data.transfermarkt_data_manager import TransfermarktDataManager

# Configurar logging
logging.basicConfig(level=logging.INFO)

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
    
    # Guardar filtros actuales
    current_filters = {
        'analysis_type': analysis_type,
        'team': team,
        'period': period
    }
    
    # Si se presionó refresh, forzar actualización
    force_refresh = n_clicks and n_clicks > 0
    
    if force_refresh:
        success = transfermarkt_manager.refresh_data(force_scraping=True)
        if not success:
            logging.warning("Error al actualizar datos desde Transfermarkt")
    
    # Obtener datos de lesiones
    all_injuries = transfermarkt_manager.get_injuries_data()
    
    if not all_injuries:
        logging.warning("No hay datos de lesiones disponibles")
        return [], current_filters
    
    # Filtrar datos por período
    filtered_data = []
    
    if period != 'all':
        days_map = {'1m': 30, '3m': 90, '6m': 180, 'season': 365}
        days_back = days_map.get(period, 90)
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        for injury in all_injuries:
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
    else:
        filtered_data = all_injuries
    
    # Filtrar por equipo si se especifica
    if team and team != 'all':
        filtered_data = [injury for injury in filtered_data if injury['team'] == team]
    
    logging.info(f"Datos filtrados: {len(filtered_data)} lesiones de {len(all_injuries)} total")
    return filtered_data, current_filters

# Callback para actualizar KPIs principales
@callback(
    Output('injury-main-kpis', 'children'),
    [Input('injury-data-store', 'data')]
)
def update_injury_kpis(data):
    """Actualiza los KPIs principales del dashboard de lesiones."""
    
    if not data:
        return html.Div("No hay datos disponibles")
    
    # Obtener estadísticas resumidas
    stats = transfermarkt_manager.get_statistics_summary()
    
    # Calcular métricas específicas del filtro aplicado
    total_injuries = len(data)
    active_injuries = len([injury for injury in data if injury['status'] == 'En tratamiento'])
    
    # Calcular promedio de días de recuperación
    recovery_days = [injury['recovery_days'] for injury in data if injury['recovery_days']]
    avg_recovery_days = sum(recovery_days) / len(recovery_days) if recovery_days else 0
    
    # Encontrar lesión más común
    injury_types = [injury['injury_type'] for injury in data]
    most_common_injury = max(set(injury_types), key=injury_types.count) if injury_types else "N/A"
    
    # Encontrar parte más afectada
    body_parts = [injury['body_part'] for injury in data]
    most_affected_part = max(set(body_parts), key=body_parts.count) if body_parts else "N/A"
    
    # Crear KPIs
    kpis = dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(total_injuries, className="text-danger"),
                    html.P("Total Lesiones", className="card-text")
                ])
            ])
        ], md=2),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(active_injuries, className="text-warning"),
                    html.P("En Tratamiento", className="card-text")
                ])
            ])
        ], md=2),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3(f"{avg_recovery_days:.0f}", className="text-info"),
                    html.P("Días Promedio Recuperación", className="card-text")
                ])
            ])
        ], md=2),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H4(most_common_injury, className="text-success", style={'font-size': '1rem'}),
                    html.P("Lesión Más Común", className="card-text")
                ])
            ])
        ], md=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H4(most_affected_part, className="text-secondary", style={'font-size': '1rem'}),
                    html.P("Zona Más Afectada", className="card-text")
                ])
            ])
        ], md=3)
    ])
    
    return kpis

# Callback para gráfico de distribución de lesiones
@callback(
    Output('injury-distribution-chart', 'children'),
    [Input('injury-data-store', 'data')]
)
def update_injury_distribution(data):
    """Actualiza el gráfico de distribución de lesiones."""
    
    if not data:
        return html.Div("No hay datos disponibles")
    
    # Contar tipos de lesiones
    injury_types = [injury['injury_type'] for injury in data]
    injury_counts = {}
    for injury_type in injury_types:
        injury_counts[injury_type] = injury_counts.get(injury_type, 0) + 1
    
    # Ordenar por frecuencia
    sorted_injuries = sorted(injury_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Tomar top 10
    if len(sorted_injuries) > 10:
        sorted_injuries = sorted_injuries[:10]
    
    types = [item[0] for item in sorted_injuries]
    counts = [item[1] for item in sorted_injuries]
    
    # Crear gráfico de barras
    fig = px.bar(
        x=types,
        y=counts,
        title="Distribución por Tipo de Lesión",
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

# Callback para gráfico de tendencias temporales
@callback(
    Output('injury-trends-chart', 'children'),
    [Input('injury-data-store', 'data')]
)
def update_injury_trends(data):
    """Actualiza el gráfico de tendencias temporales de lesiones."""
    
    if not data:
        return html.Div("No hay datos disponibles")
    
    # Agrupar por mes
    monthly_counts = {}
    
    for injury in data:
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
        return html.Div("No hay datos con fechas válidas disponibles")
    
    months = [item[0] for item in sorted_months]
    counts = [item[1] for item in sorted_months]
    
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

# Callback para tabla de lesiones (sin cambios significativos)
@callback(
    Output('injury-table-container', 'children'),
    [Input('injury-data-store', 'data')]
)
def update_injury_table(data):
    """Actualiza la tabla interactiva de lesiones."""
    
    if not data:
        return html.Div("No hay datos disponibles")
    
    # Preparar datos para la tabla
    table_data = []
    for injury in data:
        row = {
            'Jugador': injury['player_name'],
            'Equipo': injury['team'],
            'Tipo': injury['injury_type'],
            'Zona': injury['body_part'],
            'Severidad': injury['severity'],
            'Fecha': injury['injury_date'] or '',
            'Días Rec.': injury['recovery_days'],
            'Estado': injury['status']
        }
        table_data.append(row)
    
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

# Callback para análisis por partes del cuerpo
@callback(
    Output('injury-body-parts-analysis', 'children'),
    [Input('injury-data-store', 'data')]
)
def update_body_parts_analysis(data):
    """Actualiza el análisis de lesiones por partes del cuerpo."""
    
    if not data:
        return html.Div("No hay datos disponibles")
    
    # Contar lesiones por parte del cuerpo
    body_parts = [injury['body_part'] for injury in data]
    body_part_counts = {}
    for part in body_parts:
        body_part_counts[part] = body_part_counts.get(part, 0) + 1
    
    # Ordenar por frecuencia
    sorted_parts = sorted(body_part_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Crear lista de elementos
    items = []
    total_injuries = len(data)
    
    for part, count in sorted_parts[:8]:  # Top 8
        percentage = (count / total_injuries) * 100
        
        items.append(
            dbc.ListGroupItem([
                html.Div([
                    html.Strong(str(part)),
                    html.Span(f" ({count})", className="text-muted"),
                    dbc.Progress(
                        value=percentage,
                        color="danger",
                        className="mt-1",
                        style={"height": "8px"}
                    ),
                    html.Small(f"{percentage:.1f}%", className="text-muted")
                ])
            ])
        )
    
    return dbc.ListGroup(items, flush=True)

# Callback para análisis de riesgo
@callback(
    Output('injury-risk-analysis', 'children'),
    [Input('injury-data-store', 'data')]
)
def update_injury_risk_analysis(data):
    """Actualiza el análisis de riesgo de lesiones."""
    
    if not data:
        return html.Div("No hay datos disponibles")
    
    # Análisis de riesgo por equipo
    team_stats = {}
    
    for injury in data:
        team = injury['team']
        if team not in team_stats:
            team_stats[team] = {
                'total_injuries': 0,
                'severe_injuries': 0,
                'avg_recovery_days': [],
                'active_injuries': 0
            }
        
        team_stats[team]['total_injuries'] += 1
        
        if injury['severity'] == 'Grave':
            team_stats[team]['severe_injuries'] += 1
        
        if injury['recovery_days']:
            team_stats[team]['avg_recovery_days'].append(injury['recovery_days'])
        
        if injury['status'] == 'En tratamiento':
            team_stats[team]['active_injuries'] += 1
    
    # Calcular índice de riesgo
    team_risk = []
    for team, stats in team_stats.items():
        avg_recovery = sum(stats['avg_recovery_days']) / len(stats['avg_recovery_days']) if stats['avg_recovery_days'] else 0
        
        # Fórmula de riesgo basada en múltiples factores
        risk_score = (
            stats['total_injuries'] * 0.4 +
            stats['severe_injuries'] * 2 +
            stats['active_injuries'] * 1.5 +
            avg_recovery * 0.01
        )
        
        team_risk.append({
            'team': team,
            'risk_score': risk_score,
            'total_injuries': stats['total_injuries'],
            'severe_injuries': stats['severe_injuries'],
            'active_injuries': stats['active_injuries']
        })
    
    # Ordenar por riesgo
    team_risk.sort(key=lambda x: x['risk_score'], reverse=True)
    
    # Tomar top 8
    team_risk = team_risk[:8]
    
    # Crear gráfico de barras horizontales
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
    
    fig.update_layout(
        height=400,
        showlegend=False
    )
    
    return dcc.Graph(figure=fig)

# Callback para exportar reporte
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
    
    if not data:
        raise PreventUpdate
    
    try:
        from utils.pdf_generator import SportsPDFGenerator
        
        # Calcular estadísticas de resumen
        total_injuries = len(data)
        active_injuries = len([injury for injury in data if injury['status'] == 'En tratamiento'])
        
        recovery_days = [injury['recovery_days'] for injury in data if injury['recovery_days']]
        avg_recovery_days = sum(recovery_days) / len(recovery_days) if recovery_days else 0
        
        injury_types = [injury['injury_type'] for injury in data]
        most_common_injury = max(set(injury_types), key=injury_types.count) if injury_types else "N/A"
        
        body_parts = [injury['body_part'] for injury in data]
        most_affected_part = max(set(body_parts), key=body_parts.count) if body_parts else "N/A"
        
        summary_stats = {
            'total_injuries': total_injuries,
            'active_injuries': active_injuries,
            'avg_recovery_days': avg_recovery_days,
            'most_common_injury': most_common_injury,
            'most_affected_part': most_affected_part
        }
        
        # Generar PDF
        pdf_generator = SportsPDFGenerator()
        pdf_buffer = pdf_generator.create_injury_report(data, filters, summary_stats)
        
        # Generar nombre de archivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"reporte_lesiones_transfermarkt_{timestamp}.pdf"
        
        return {
            'content': pdf_buffer.getvalue(),
            'filename': filename,
            'type': 'application/pdf'
        }
        
    except Exception as e:
        # En caso de error, exportar como CSV
        df = pd.DataFrame(data)
        
        # Generar nombre de archivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"reporte_lesiones_transfermarkt_{timestamp}.csv"
        
        # Agregar información de filtros al DataFrame
        filter_info = f"Generado desde Transfermarkt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        filter_info += f"Filtros aplicados: Tipo={filters.get('analysis_type', 'N/A')}, "
        filter_info += f"Equipo={filters.get('team', 'Todos')}, Período={filters.get('period', 'N/A')}\n"
        filter_info += f"Error generando PDF: {str(e)}\n\n"
        
        # Convertir DataFrame a CSV
        csv_string = filter_info + df.to_csv(index=False)
        
        return {
            'content': csv_string,
            'filename': filename,
            'type': 'text/csv'
        }