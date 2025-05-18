from dash import html, dcc
import dash_bootstrap_components as dbc
from datetime import datetime, date

def create_performance_layout():
    """
    Crea el layout del dashboard de performance.
    
    Returns:
        Layout del dashboard de performance
    """
    
    layout = dbc.Container([
        # Header del dashboard
        dbc.Row([
            dbc.Col([
                html.H1(
                    "Dashboard de Performance", 
                    className="text-center mb-4",
                    style={'color': '#2c3e50'}
                ),
                html.Hr()
            ])
        ]),
        
        # Panel de control / Filtros
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H4("Filtros de Análisis", className="mb-0")
                    ]),
                    dbc.CardBody([
                        dbc.Row([
                            # Selector de nivel de análisis
                            dbc.Col([
                                dbc.Label("Nivel de Análisis:", html_for="analysis-level"),
                                dcc.Dropdown(
                                    id="analysis-level",
                                    options=[
                                        {"label": "🏆 Liga Completa", "value": "league"},
                                        {"label": "⚽ Equipo Específico", "value": "team"},
                                        {"label": "👤 Jugador Individual", "value": "player"}
                                    ],
                                    value="league",
                                    className="mb-3"
                                )
                            ], md=4),
                            
                            # Selector de equipo (condicional)
                            dbc.Col([
                                dbc.Label("Equipo:", html_for="team-selector"),
                                dcc.Dropdown(
                                    id="team-selector",
                                    placeholder="Selecciona un equipo...",
                                    className="mb-3",
                                    disabled=True
                                )
                            ], md=4),
                            
                            # Selector de jugador (condicional)
                            dbc.Col([
                                dbc.Label("Jugador:", html_for="player-selector"),
                                dcc.Dropdown(
                                    id="player-selector",
                                    placeholder="Selecciona un jugador...",
                                    className="mb-3",
                                    disabled=True
                                )
                            ], md=4)
                        ]),
                        
                        dbc.Row([
                            # Filtro por posición
                            dbc.Col([
                                dbc.Label("Posición:", html_for="position-filter"),
                                dcc.Dropdown(
                                    id="position-filter",
                                    options=[
                                        {"label": "Todas las posiciones", "value": "all"},
                                        {"label": "Portero", "value": "Goalkeeper"},
                                        {"label": "Defensor", "value": "Defender"},
                                        {"label": "Mediocampista", "value": "Midfielder"},
                                        {"label": "Extremo", "value": "Winger"},
                                        {"label": "Delantero", "value": "Forward"}
                                    ],
                                    value="all",
                                    className="mb-3"
                                )
                            ], md=4),
                            
                            # Filtro por rango de edad
                            dbc.Col([
                                dbc.Label("Rango de Edad:", html_for="age-range"),
                                dcc.RangeSlider(
                                    id="age-range",
                                    min=16,
                                    max=40,
                                    value=[16, 40],
                                    marks={16: '16', 20: '20', 25: '25', 30: '30', 35: '35', 40: '40'},
                                    tooltip={"placement": "bottom", "always_visible": True},
                                    className="mb-3"
                                )
                            ], md=4),
                            
                            # Botones de acción
                            dbc.Col([
                                dbc.Label("Acciones:", html_for="action-buttons"),
                                html.Div([
                                    dbc.Button(
                                        "🔄 Actualizar",
                                        id="refresh-button",
                                        color="primary",
                                        size="sm",
                                        className="me-2"
                                    ),
                                    dbc.Button(
                                        "📊 Exportar PDF",
                                        id="export-pdf-button",
                                        color="success",
                                        size="sm"
                                    )
                                ])
                            ], md=4)
                        ])
                    ])
                ], className="mb-4")
            ])
        ]),
        
        # Indicadores de estado
        dbc.Row([
            dbc.Col([
                html.Div(id="status-alerts")
            ])
        ]),
        
        # Métricas principales (KPIs)
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4(id="kpi-title", className="card-title"),
                        html.Div(id="main-kpis")
                    ])
                ])
            ])
        ], className="mb-4"),
        
        # Sección de gráficos principales
        dbc.Row([
            # Gráfico principal izquierdo
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Análisis Principal", className="mb-0")
                    ]),
                    dbc.CardBody([
                        dcc.Loading(
                            id="loading-main-chart",
                            children=[html.Div(id="main-chart-container")],
                            type="default"
                        )
                    ])
                ])
            ], md=6),
            
            # Gráfico secundario derecho
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Análisis Secundario", className="mb-0")
                    ]),
                    dbc.CardBody([
                        dcc.Loading(
                            id="loading-secondary-chart",
                            children=[html.Div(id="secondary-chart-container")],
                            type="default"
                        )
                    ])
                ])
            ], md=6)
        ], className="mb-4"),
        
        # Sección de estadísticas detalladas
        dbc.Row([
            # Tabla de top performers
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Top Performers", className="mb-0")
                    ]),
                    dbc.CardBody([
                        dcc.Loading(
                            id="loading-top-performers",
                            children=[html.Div(id="top-performers-container")],
                            type="default"
                        )
                    ])
                ])
            ], md=6),
            
            # Estadísticas por posición
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Análisis por Posición", className="mb-0")
                    ]),
                    dbc.CardBody([
                        dcc.Loading(
                            id="loading-position-analysis",
                            children=[html.Div(id="position-analysis-container")],
                            type="default"
                        )
                    ])
                ])
            ], md=6)
        ], className="mb-4"),
        
        # Gráfico de comparación (condicional para equipos/jugadores)
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5(id="comparison-chart-title", className="mb-0")
                    ]),
                    dbc.CardBody([
                        dcc.Loading(
                            id="loading-comparison-chart",
                            children=[html.Div(id="comparison-chart-container")],
                            type="default"
                        )
                    ])
                ], id="comparison-card", style={"display": "none"})
            ])
        ], className="mb-4"),
        
        # Stores para datos
        dcc.Store(id="performance-data-store"),
        dcc.Store(id="chart-data-store"),
        dcc.Store(id="current-filters-store"),
        
        # Download component para PDF
        dcc.Download(id="download-performance-pdf")
        
    ], fluid=True, className="py-4")
    
    return layout