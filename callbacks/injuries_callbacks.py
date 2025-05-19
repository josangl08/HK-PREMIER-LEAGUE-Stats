from dash import Input, Output, State, callback, html, dash_table, dcc
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dash.exceptions import PreventUpdate
import random

# Datos simulados para el dashboard de lesiones
# En una aplicación real, estos datos vendrían de una base de datos médica

def generate_sample_injury_data():
    """
    Genera datos simulados de lesiones para demostración.
    En una aplicación real, estos datos vendrían de una base de datos médica.
    """
    
    # Lista de equipos (usando los mismos del sistema principal)
    teams = [
        "Eastern Sports Club", "Kitchee SC", "Lee Man FC", "Southern District FC",
        "HKFC", "Tai Po FC", "Hong Kong FC", "Wofoo Tai Po", "Happy Valley AA",
        "Central Coast FC"
    ]
    
    # Tipos de lesiones comunes en fútbol
    injury_types = [
        "Distensión muscular", "Esguince de tobillo", "Contusión", "Lesión ligamentaria",
        "Fractura", "Tendinitis", "Rotura muscular", "Luxación", "Sobrecarga muscular"
    ]
    
    # Partes del cuerpo afectadas
    body_parts = [
        "Tobillo", "Rodilla", "Isquiotibiales", "Cuádriceps", "Gemelo", "Pie",
        "Cadera", "Espalda baja", "Hombro", "Muñeca", "Cabeza"
    ]
    
    # Severidad de lesiones
    severities = ["Leve", "Moderada", "Grave"]
    severity_weights = [0.6, 0.3, 0.1]  # Más lesiones leves que graves
    
    # Generar datos de muestra
    np.random.seed(42)  # Para reproducibilidad
    n_injuries = 150
    
    data = []
    base_date = datetime.now() - timedelta(days=365)
    
    for i in range(n_injuries):
        # Fecha aleatoria en el último año
        days_offset = np.random.randint(0, 365)
        injury_date = base_date + timedelta(days=days_offset)
        
        # Datos de la lesión
        injury = {
            'id': i + 1,
            'player_name': f"Jugador {i + 1}",
            'team': np.random.choice(teams),
            'injury_type': np.random.choice(injury_types),
            'body_part': np.random.choice(body_parts),
            'severity': np.random.choice(severities, p=severity_weights),
            'injury_date': injury_date,
            'recovery_days': np.random.randint(1, 120),
            'status': np.random.choice(['Recuperado', 'En tratamiento', 'Crónico'], p=[0.7, 0.25, 0.05])
        }
        
        # Calcular fecha de retorno
        if injury['status'] == 'Recuperado':
            injury['return_date'] = injury['injury_date'] + timedelta(days=injury['recovery_days'])
        else:
            injury['return_date'] = None
            
        data.append(injury)
    
    return pd.DataFrame(data)

# Generar datos de muestra
INJURY_DATA = generate_sample_injury_data()

# Callback para actualizar opciones de equipos
@callback(
    Output('injury-team-selector', 'options'),
    Input('injury-analysis-type', 'value'),
    prevent_initial_call=False
)
def update_team_options(analysis_type):
    """Actualiza las opciones de equipos para el selector."""
    teams = INJURY_DATA['team'].unique().tolist()
    options = [{"label": "Todos los equipos", "value": "all"}]
    options.extend([{"label": team, "value": team} for team in sorted(teams)])
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
    """Carga y filtra los datos de lesiones según los filtros seleccionados."""
    
    # Guardar filtros actuales
    current_filters = {
        'analysis_type': analysis_type,
        'team': team,
        'period': period
    }
    
    # Filtrar datos por período
    filtered_data = INJURY_DATA.copy()
    
    if period != 'all':
        days_map = {'1m': 30, '3m': 90, '6m': 180, 'season': 365}
        days_back = days_map.get(period, 90)
        cutoff_date = datetime.now() - timedelta(days=days_back)
        filtered_data = filtered_data[filtered_data['injury_date'] >= cutoff_date]
    
    # Filtrar por equipo si se especifica
    if team and team != 'all':
        filtered_data = filtered_data[filtered_data['team'] == team]
    
    # Convertir dates a strings para serialización JSON
    data_for_store = filtered_data.copy()
    data_for_store['injury_date'] = data_for_store['injury_date'].dt.strftime('%Y-%m-%d')
    data_for_store['return_date'] = data_for_store['return_date'].dt.strftime('%Y-%m-%d') if 'return_date' in data_for_store.columns else None
    
    return data_for_store.to_dict('records'), current_filters

# Callback para actualizar KPIs principales
@callback(
    Output('injury-main-kpis', 'children'),
    [Input('injury-data-store', 'data')]
)
def update_injury_kpis(data):
    """Actualiza los KPIs principales del dashboard de lesiones."""
    
    if not data:
        return html.Div("No hay datos disponibles")
    
    df = pd.DataFrame(data)
    
    # Calcular métricas
    total_injuries = len(df)
    active_injuries = len(df[df['status'] == 'En tratamiento'])
    avg_recovery_days = df['recovery_days'].mean()
    most_common_injury = df['injury_type'].mode().iloc[0] if not df.empty else "N/A"
    most_affected_part = df['body_part'].mode().iloc[0] if not df.empty else "N/A"
    
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
    
    df = pd.DataFrame(data)
    
    # Crear gráfico de barras de tipos de lesiones
    injury_counts = df['injury_type'].value_counts()
    
    fig = px.bar(
        x=injury_counts.index,
        y=injury_counts.values,
        title="Distribución por Tipo de Lesión",
        labels={'x': 'Tipo de Lesión', 'y': 'Número de Casos'},
        color=injury_counts.values,
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
    
    df = pd.DataFrame(data)
    df['injury_date'] = pd.to_datetime(df['injury_date'])
    
    # Agrupar por mes
    df['month'] = df['injury_date'].dt.to_period('M')
    monthly_counts = df.groupby('month').size().reset_index(name='count')
    monthly_counts['month_str'] = monthly_counts['month'].astype(str)
    
    # Crear gráfico de líneas
    fig = px.line(
        monthly_counts,
        x='month_str',
        y='count',
        title="Tendencia de Lesiones por Mes",
        labels={'month_str': 'Mes', 'count': 'Número de Lesiones'},
        markers=True
    )
    
    fig.update_layout(height=400)
    
    return dcc.Graph(figure=fig)

# Callback para tabla de lesiones
@callback(
    Output('injury-table-container', 'children'),
    [Input('injury-data-store', 'data')]
)
def update_injury_table(data):
    """Actualiza la tabla interactiva de lesiones."""
    
    if not data:
        return html.Div("No hay datos disponibles")
    
    df = pd.DataFrame(data)
    
    # Preparar datos para la tabla
    table_df = df[['player_name', 'team', 'injury_type', 'body_part', 'severity', 'injury_date', 'recovery_days', 'status']].copy()
    table_df.columns = ['Jugador', 'Equipo', 'Tipo', 'Zona', 'Severidad', 'Fecha', 'Días Rec.', 'Estado']
    
    # Convertir a diccionario con tipos explícitos
    table_records = []
    for _, row in table_df.iterrows():
        record = {}
        for col in table_df.columns:
            record[col] = str(row[col]) if pd.notna(row[col]) else ""
        table_records.append(record)
    
    # Crear tabla interactiva
    table = dash_table.DataTable(
        data=table_records,
        columns=[{'name': col, 'id': col, 'type': 'text'} for col in table_df.columns],
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
    
    df = pd.DataFrame(data)
    
    # Contar lesiones por parte del cuerpo
    body_part_counts = df['body_part'].value_counts()
    
    # Crear lista de elementos
    items = []
    for part, count in body_part_counts.head(8).items():
        percentage = (count / len(df)) * 100
        
        items.append(
            dbc.ListGroupItem([
                html.Div([
                    html.Strong(str(part)),  # Convertir a string explícitamente
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
    
    df = pd.DataFrame(data)
    
    # Análisis de riesgo por equipo
    team_risk = df.groupby('team').agg({
        'injury_type': 'count',
        'recovery_days': 'mean',
        'severity': lambda x: (x == 'Grave').sum()
    }).reset_index()
    
    team_risk.columns = ['team', 'total_injuries', 'avg_recovery', 'severe_injuries']
    team_risk['risk_score'] = (
        team_risk['total_injuries'] * 0.4 +
        team_risk['avg_recovery'] * 0.003 +
        team_risk['severe_injuries'] * 2
    )
    
    team_risk = team_risk.sort_values('risk_score', ascending=False)
    
    # Crear gráfico de barras horizontales
    fig = px.bar(
        team_risk.head(8),
        x='risk_score',
        y='team',
        orientation='h',
        title="Índice de Riesgo por Equipo",
        labels={'risk_score': 'Índice de Riesgo', 'team': 'Equipo'},
        color='risk_score',
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
        df = pd.DataFrame(data)
        summary_stats = {
            'active_injuries': len(df[df['status'] == 'En tratamiento']),
            'avg_recovery_days': df['recovery_days'].mean(),
            'most_common_injury': df['injury_type'].mode().iloc[0] if not df.empty else "N/A",
            'most_affected_part': df['body_part'].mode().iloc[0] if not df.empty else "N/A"
        }
        
        # Generar PDF
        pdf_generator = SportsPDFGenerator()
        pdf_buffer = pdf_generator.create_injury_report(data, filters, summary_stats)
        
        # Generar nombre de archivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"reporte_lesiones_{timestamp}.pdf"
        
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
        filename = f"reporte_lesiones_{timestamp}.csv"
        
        # Agregar información de filtros al DataFrame
        filter_info = f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
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