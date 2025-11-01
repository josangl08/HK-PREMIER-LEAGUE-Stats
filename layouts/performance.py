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
    
    layout = html.Div([
        dbc.Container([
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
        
        # Panel de control / Filtros mejorado
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
                                html.Div(
                                    dcc.Dropdown(
                                        id="season-selector",
                                        options=[],  # Se llena dinámicamente
                                        value="2024-25",
                                        className="mb-3"
                                    ),
                                    className="filter-container"
                                )
                            ], md=4),
                            
                            # Selector de equipo
                            dbc.Col([
                                dbc.Label("Team:", html_for="team-selector"),
                                html.Div(
                                    dcc.Dropdown(
                                        id="team-selector",
                                        placeholder="All teams...",
                                        className="mb-3",
                                        clearable=True
                                    ),
                                    className="filter-container"
                                )
                            ], md=4),
                            
                            # Selector de jugador
                            dbc.Col([
                                dbc.Label("Player:", html_for="player-selector"),
                                html.Div(
                                    dcc.Dropdown(
                                        id="player-selector",
                                        placeholder="All players...",
                                        className="mb-3",
                                        clearable=True
                                    ),
                                    className="filter-container"
                                )
                            ], md=4)
                        ], className="mb-3"),
                        
                        # Segunda fila de filtros
                        dbc.Row([
                            # Filtro por posición
                            dbc.Col([
                                dbc.Label("Position:", html_for="position-filter"),
                                html.Div(
                                    dcc.Dropdown(
                                        id="position-filter",
                                        options=[
                                            {"label": "All Positions", "value": "all"},
                                            {"label": "Goalkeeper", "value": "Goalkeeper"},
                                            {"label": "Defender", "value": "Defender"},
                                            {"label": "Midfielder", "value": "Midfielder"},
                                            {"label": "Winger", "value": "Winger"},
                                            {"label": "Forward", "value": "Forward"}
                                        ],
                                        value="all",
                                        className="mb-3"
                                    ),
                                    className="filter-container"
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
                                        [
                                            html.I(className="bi bi-file-earmark-pdf me-2"),
                                            "Export PDF"
                                        ],
                                        id="export-pdf-button",
                                        color="success",
                                        size="sm"
                                    )
                                ])
                            ], md=4)
                        ])
                    ])
                ], className="mb-4 has-dropdowns")
            ])
        ]),
        
        # Indicadores de estado
        dbc.Row([
            dbc.Col([
                html.Div(id="status-alerts")
            ])
        ], className="mb-3"),  
        
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
        
        # ===== MODULAR VIEWS CONTAINERS =====
        # Only ONE view visible at a time (controlled by view_dispatcher callback)
        # Each view has its own layout structure and chart IDs

        # LEAGUE VIEW CONTAINER
        html.Div(
            id='league-view-container',
            children=[],  # Populated dynamically by view_dispatcher
            style={'display': 'none'}  # Initially hidden
        ),

        # TEAM VIEW CONTAINER
        html.Div(
            id='team-view-container',
            children=[],  # Populated dynamically by view_dispatcher
            style={'display': 'none'}  # Initially hidden
        ),

        # PLAYER VIEW CONTAINER
        html.Div(
            id='player-view-container',
            children=[],  # Populated dynamically by view_dispatcher
            style={'display': 'none'}  # Initially hidden
        ),
        
        # Stores para datos
        dcc.Store(id="performance-data-store"),
        dcc.Store(id="chart-data-store"),
        dcc.Store(id="current-filters-store"),
        
        # Download component para PDF
        dcc.Download(id="download-performance-pdf")

        ], fluid=True, className="py-4")
    ], className="main-container")

    return layout