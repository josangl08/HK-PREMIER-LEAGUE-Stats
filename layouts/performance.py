from dash import html, dcc
import dash_bootstrap_components as dbc
from layouts.performance_views.shared_components import (
    create_season_selector,
    create_team_selector,
    create_player_selector,
    create_position_filter,
    create_age_range_filter,
    create_export_button,
)


def create_performance_layout():
    """
    Crea el layout del dashboard de performance.
    Versión corregida con mejor espaciado.

    Returns:
        Layout del dashboard de performance
    """

    layout = html.Div(
        [
            dbc.Container(
                [
                    # Header del dashboard
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Div(
                                        [
                                            html.Img(
                                                src="/assets/logo.png",
                                                height="80px",
                                                className="dashboard-logo",
                                            ),
                                            html.H1(
                                                "HK Premier League Performance",
                                                className="dashboard-title",
                                            ),
                                        ],
                                        className="dashboard-header-container",
                                    ),
                                    html.Hr(),
                                ]
                            )
                        ]
                    ),
                    # Panel de control / Filtros mejorado
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Card(
                                        [
                                            dbc.CardHeader(
                                                [
                                                    html.H4(
                                                        "Analysis Filters",
                                                        className="mb-0",
                                                    )
                                                ]
                                            ),
                                            dbc.CardBody(
                                                [
                                                    # Primera fila de filtros
                                                    dbc.Row(
                                                        [
                                                            create_season_selector(),
                                                            create_team_selector(),
                                                            create_player_selector(),
                                                        ],
                                                        className="mb-3",
                                                    ),
                                                    # Segunda fila de filtros
                                                    dbc.Row(
                                                        [
                                                            create_position_filter(),
                                                            create_age_range_filter(),
                                                            create_export_button(),
                                                        ]
                                                    ),
                                                ]
                                            ),
                                        ],
                                        className="mb-4",
                                    )
                                ]
                            )
                        ]
                    ),
                    # Indicadores de estado
                    dbc.Row(
                        [dbc.Col([html.Div(id="status-alerts")])], className="mb-3"
                    ),
                    # Métricas principales (KPIs)
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Card(
                                        [
                                            dbc.CardBody(
                                                [
                                                    html.H4(
                                                        id="kpi-title",
                                                        className="card-title",
                                                    ),
                                                    html.Div(id="main-kpis"),
                                                ]
                                            )
                                        ]
                                    )
                                ]
                            )
                        ],
                        className="mb-4",
                    ),
                    # ===== MODULAR VIEWS CONTAINERS =====
                    # Only ONE view visible at a time
                    # (controlled by view_dispatcher callback)
                    # Each view has its own layout structure and chart IDs
                    # LEAGUE VIEW CONTAINER
                    html.Div(
                        id="league-view-container",
                        children=[],  # Populated dynamically by view_dispatcher
                        style={"display": "none"},  # Initially hidden
                    ),
                    # TEAM VIEW CONTAINER
                    html.Div(
                        id="team-view-container",
                        children=[],  # Populated dynamically by view_dispatcher
                        style={"display": "none"},  # Initially hidden
                    ),
                    # PLAYER VIEW CONTAINER
                    html.Div(
                        id="player-view-container",
                        children=[],  # Populated dynamically by view_dispatcher
                        style={"display": "none"},  # Initially hidden
                    ),
                    # Stores para datos
                    dcc.Store(id="performance-data-store"),
                    dcc.Store(id="chart-data-store"),
                    dcc.Store(id="current-filters-store"),
                    # Download component para PDF
                    dcc.Download(id="download-performance-pdf"),
                ],
                fluid=True,
                className="py-4",
            )
        ],
        className="main-container",
    )

    return layout
