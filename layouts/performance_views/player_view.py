# ABOUTME: Player view layout module for performance dashboard
# ABOUTME: Defines responsive grid structure for 5 player-level charts

"""
Player View Layout Module.

This module creates the layout structure for player-level analysis.
Contains 5 chart containers organized in a responsive Bootstrap grid.

Chart Structure (FINAL_PLAN.md specification):
    1. Radar Chart: Player vs position average with percentile shading
    2. Horizontal Bar: Percentile rankings (top 6-8 metrics)
    3. Scatter Plot: Player efficiency (goals/xG vs assists/xA)
    4. Heatmap: Position-specific performance matrix
    5. Timeline: Performance evolution (multi-season if available)

Grid Design (UX-Optimized):
    Row 1: Chart 1 (6 cols) + Chart 2 (6 cols) - Radar + Percentiles
    Row 2: Chart 3 (6 cols) + Chart 4 (6 cols) - Efficiency + Matrix
    Row 3: Chart 5 (12 cols) - Evolution timeline full width

    Mobile (< 768px): All charts stack vertically (12 cols each)
    Tablet (768-991px): Maintains 6-6 grid for balanced display
    Desktop (>= 992px): Full 6-6 grid for symmetry

Dependencies:
    - dash.html
    - dash_bootstrap_components (for responsive grid)
"""

from dash import html, dcc
import dash_bootstrap_components as dbc


def create_player_view_layout():
    """
    Create player view layout with 5 chart containers in responsive grid.

    Returns:
        dbc.Container: Bootstrap container with responsive chart grid

    Chart IDs:
        - player-chart-1: Radar chart (player vs position avg)
        - player-chart-2: Horizontal bar (percentile rankings)
        - player-chart-3: Scatter plot (efficiency analysis)
        - player-chart-4: Heatmap (position-specific matrix)
        - player-chart-5: Timeline (performance evolution)
    """
    return dbc.Container([
        # ===== ROW 0: PRE-MATCH CARD (Conditional) =====
        dbc.Row([
            dbc.Col([
                html.Div(id='prematch-card-container')
            ], width=12)
        ], className='mb-4'),

        # ===== ROW 1: RADAR + PERCENTILES =====
        dbc.Row([
            # Chart 1: Radar (Player vs Position Average)
            dbc.Col([
                html.Div(
                    id='player-chart-1',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando radar de jugador...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=6, md=6, sm=12),

            # Chart 2: Horizontal Bar (Percentile Rankings)
            dbc.Col([
                html.Div(
                    id='player-chart-2',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando percentiles...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=6, md=6, sm=12)
        ], className='mb-4'),

        # ===== ROW 2: EFFICIENCY SCATTER + HEATMAP =====
        dbc.Row([
            # Chart 3: Scatter Plot (Efficiency)
            dbc.Col([
                html.Div(
                    id='player-chart-3',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando analisis de eficiencia...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=6, md=6, sm=12),

            # Chart 4: Heatmap (Position-Specific Performance)
            dbc.Col([
                html.Div(
                    id='player-chart-4',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando matriz de rendimiento...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=6, md=6, sm=12)
        ], className='mb-4'),

        # ===== ROW 3: EVOLUTION TIMELINE (Full Width) =====
        dbc.Row([
            dbc.Col([
                html.Div(
                    id='player-chart-5',
                    className='chart-container',
                    children=[
                        html.Div(
                            "Cargando evolucion del jugador...",
                            className='text-center text-muted p-5'
                        )
                    ]
                )
            ], width=12, lg=12, md=12, sm=12)
        ], className='mb-4'),

        # ===== ROW 4: CONTENT GENERATION (Mi Card) =====
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H4([html.I(className="bi bi-image me-2"), "Generador de Content: Mi Card"], className="mb-0")
                    ]),
                    dbc.CardBody([
                        dbc.Row([
                            # Left side: Upload & Gallery
                            dbc.Col([
                                html.Label("1. Sube tu foto (recomendado: buena luz, fondo liso)", className="fw-bold"),
                                dcc.Upload(
                                    id='player-photo-upload',
                                    children=html.Div([
                                        'Arrastra o ',
                                        html.A('Selecciona Archivo')
                                    ]),
                                    style={
                                        'width': '100%', 'height': '60px', 'lineHeight': '60px',
                                        'borderWidth': '1px', 'borderStyle': 'dashed',
                                        'borderRadius': '5px', 'textAlign': 'center', 'margin': '10px 0'
                                    },
                                    multiple=False
                                ),
                                html.Div(id='upload-status-msg'),

                                html.Label("2. Tus siluetas (máximo 5)", className="fw-bold mt-3"),
                                html.Div(
                                    id='player-cutouts-gallery',
                                    className="d-flex flex-wrap gap-2 p-2 border rounded bg-light",
                                    style={"minHeight": "100px"},
                                    children=[html.P("No hay siluetas disponibles. Sube una foto para comenzar.", className="text-muted small")]
                                )
                            ], width=12, lg=6),

                            # Right side: Settings & Generate
                            dbc.Col([
                                html.Label("3. Configuración de la Card", className="fw-bold"),
                                dbc.Form([
                                    html.Div([
                                        html.Label("Formato de salida:", className="small text-muted"),
                                        dcc.RadioItems(
                                            id='card-size-selector',
                                            options=[
                                                {'label': ' Cuadrada (Feed)', 'value': 'square'},
                                                {'label': ' Vertical (Story)', 'value': 'story'}
                                            ],
                                            value='square',
                                            labelStyle={'display': 'block', 'marginBottom': '5px'}
                                        ),
                                    ], className="mb-3"),

                                    dbc.Button(
                                        [html.I(className="bi bi-magic me-2"), "Generar y Descargar Card"],
                                        id="generate-card-btn",
                                        color="primary",
                                        className="w-100 mt-2"
                                    ),
                                    dcc.Download(id="player-card-download")
                                ])
                            ], width=12, lg=6)
                        ])
                    ])
                ], className="shadow-sm border-primary")
            ], width=12)
        ], className='mb-5')

    ], fluid=True, className='player-view-container')


# ===== EXPORT FOR CLEAN IMPORTS =====
__all__ = ['create_player_view_layout']
