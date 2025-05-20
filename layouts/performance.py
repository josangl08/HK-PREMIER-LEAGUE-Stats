from dash import html, dcc
import dash_bootstrap_components as dbc
from datetime import datetime, date

def create_performance_layout():
    """
    Crea el layout del dashboard de performance.
    Versión corregida con mejor espaciado.
    
    Returns:
        Layout del dashboard de performance
    """
    
    layout = dbc.Container([
        # Header del dashboard
        dbc.Row([
            dbc.Col([
                html.H1(
                    "Performance Dashboard", 
                    className="text-center mb-4",
                    style={'color': '#27ae60'}
                ),
                html.Hr()
            ])
        ]),
        
        # Panel de control / Filtros mejorado - MÁS ESPACIADO
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H4("Analysis Filters", className="mb-0")
                    ]),
                    dbc.CardBody([
                        # Primera fila de filtros
                        dbc.Row([
                            # Selector de temporada
                            dbc.Col([
                                dbc.Label("Season:", html_for="season-selector"),
                                dcc.Dropdown(
                                    id="season-selector",
                                    options=[],  # Se llena dinámicamente
                                    value="2024-25",
                                    className="mb-3"
                                )
                            ], md=4),
                            
                            # Selector de equipo
                            dbc.Col([
                                dbc.Label("Team:", html_for="team-selector"),
                                dcc.Dropdown(
                                    id="team-selector",
                                    placeholder="Todos los equipos...",
                                    className="mb-3",
                                    clearable=True
                                )
                            ], md=4),
                            
                            # Selector de jugador
                            dbc.Col([
                                dbc.Label("Player:", html_for="player-selector"),
                                dcc.Dropdown(
                                    id="player-selector",
                                    placeholder="Todos los jugadores...",
                                    className="mb-3",
                                    clearable=True
                                )
                            ], md=4)
                        ], className="mb-3"),  # AGREGAR MARGEN ENTRE FILAS
                        
                        # Segunda fila de filtros
                        dbc.Row([
                            # Filtro por posición
                            dbc.Col([
                                dbc.Label("Position:", html_for="position-filter"),
                                dcc.Dropdown(
                                    id="position-filter",
                                    options=[
                                        {"label": "All Positions", "value": "all"},
                                        {"label": "Golakeeper", "value": "Goalkeeper"},
                                        {"label": "Defender", "value": "Defender"},
                                        {"label": "Midfielder", "value": "Midfielder"},
                                        {"label": "Winger", "value": "Winger"},
                                        {"label": "Forward", "value": "Forward"}
                                    ],
                                    value="all",
                                    className="mb-3"
                                )
                            ], md=4),
                            
                            # Filtro por rango de edad
                            dbc.Col([
                                dbc.Label("Age Range:", html_for="age-range"),
                                dcc.RangeSlider(
                                    id="age-range",
                                    min=15,
                                    max=45,
                                    value=[15, 45],
                                    marks={15: '15', 20: '20', 25: '25', 30: '30', 35: '35', 40: '40', 45: '45'},
                                    tooltip={"placement": "bottom", "always_visible": True},
                                    className="mb-3"
                                )
                            ], md=4),
                            
                            # Botones de acción
                            dbc.Col([
                                dbc.Label("Options:", html_for="action-buttons"),
                                html.Div([
                                    dbc.Button(
                                        "📊 Export PDF",
                                        id="export-pdf-button",
                                        color="success",
                                        size="sm"
                                    )
                                ])
                            ], md=4)
                        ])
                    ])
                ], className="mb-4")  # MANTENER MARGEN INFERIOR
            ])
        ]),
        
        # Indicadores de estado - CON MARGEN
        dbc.Row([
            dbc.Col([
                html.Div(id="status-alerts")
            ])
        ], className="mb-3"),  # AGREGAR MARGEN
        
        # Métricas principales (KPIs) - CON MARGEN
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
        
        # Sección de gráficos principales - CON MARGEN
        dbc.Row([
            # Gráfico principal izquierdo
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Main Chart", className="mb-0")
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
                        html.H5("Secondary Chart", className="mb-0")
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
        
        # Sección de estadísticas detalladas - CON MARGEN
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
                        html.H5("Analysis by positon", className="mb-0")
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
        
        # Gráfico de comparación (condicional para equipos/jugadores) - CON MARGEN
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