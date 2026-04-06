from dash import html, dcc
import dash_bootstrap_components as dbc

layout = html.Div([
    dbc.Container([
        # Header - Bienvenida
        dbc.Row([
            dbc.Col([
                html.H1("Welcome to Hong Kong Premier League Dashboard", className="text-center my-4"),
                html.Div([
                html.P([
                    "This application provides sports performance analysis and data management for  ",
                    "teams and athletes in the Hong Kong League. ",
                ], className="lead text-center"),
                
                html.Hr(),
                
                # Tarjetas principales con mejor espaciado
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.H4("Performance Dashboard", className="text-center")),
                            dbc.CardBody([
                                html.Ul([
                                    html.Li([html.I(className="bi bi-bar-chart me-2"), "Full league statistics"]),
                                    html.Li([html.I(className="bi bi-trophy me-2"), "Analysis by team"]),
                                    html.Li([html.I(className="bi bi-person me-2"), "Player profiles"]),
                                    html.Li([html.I(className="bi bi-graph-up me-2"), "Interactive graphics"]),
                                    html.Li([html.I(className="bi bi-file-earmark-pdf me-2"), "Export to PDF"])
                                ]),
                                dbc.Button("Go to Performance", href="/performance", color="success", className="w-100"),
                            ]),
                        ]),
                    ], width=12, md=6, className="mb-4"),
                    
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.H4("Injuries Dashboard", className="text-center")),
                            dbc.CardBody([
                                html.Ul([
                                    html.Li([html.I(className="bi bi-hospital me-2"), "Injury management"]),
                                    html.Li([html.I(className="bi bi-clipboard-data me-2"), "Medical records"]),
                                    html.Li([html.I(className="bi bi-exclamation-triangle me-2"), "Risk analysis"]),
                                    html.Li([html.I(className="bi bi-graph-up-arrow me-2"), "Injury trends"]),
                                    html.Li([html.I(className="bi bi-file-medical me-2"), "Medical reports"])
                                ]),
                                dbc.Button("Disabled", href="", color="secondary", className="w-100 text-light", disabled=True),
                            ]),
                        ], className="greyscale"),
                    ], width=12, md=6, className="mb-4"),
                ]),
                
                html.Hr(),
                
                # Estado del sistema con indicador de carga
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.H5("Estado del Sistema", className="text-center")),
                            dbc.CardBody([
                                # Agregar Loading wrapper para el spinner
                                dcc.Loading(
                                    id="loading-system-status",
                                    children=[html.Div(id="system-status-info")],
                                    type="default",
                                    color="#6ea4da"
                                ),
                                dbc.Button(
                                    [
                                        html.I(className="bi bi-arrow-clockwise me-2"),  # Icono de actualizar
                                        "Update Data"
                                    ],
                                    id="refresh-data-button",
                                    color="primary",
                                    className="mt-2 w-100"
                                ),
                                html.Hr(),
                                html.H6("Transfermarkt Assisted Mode", className="mt-2"),
                                html.Div(id="tm-assisted-session-indicator", className="mb-2"),
                                dcc.Upload(
                                    id="tm-assisted-cookies-upload",
                                    children=dbc.Button("Upload cookies.json", color="light", className="w-100 mb-2"),
                                    multiple=False,
                                ),
                                dcc.Textarea(
                                    id="tm-assisted-cookies-input",
                                    placeholder='Paste Transfermarkt cookies JSON here',
                                    style={
                                        "width": "100%",
                                        "minHeight": "120px",
                                        "fontFamily": "monospace",
                                        "fontSize": "0.85rem",
                                        "backgroundColor": "#f8f9fa",
                                        "color": "#18181A",
                                        "caretColor": "#18181A",
                                        "border": "1px solid rgba(0,0,0,0.14)",
                                        "borderRadius": "0.5rem",
                                        "padding": "0.75rem",
                                    },
                                ),
                                html.Div(id="tm-assisted-json-status", className="mt-2"),
                                dcc.Store(id="tm-assisted-normalized-payload"),
                                dbc.Row([
                                    dbc.Col(
                                        dcc.Dropdown(
                                            id="tm-assisted-scope",
                                            options=[
                                                {"label": "Priority", "value": "priority"},
                                                {"label": "Users", "value": "users"},
                                                {"label": "Post-match", "value": "post-match"},
                                                {"label": "All", "value": "all"},
                                            ],
                                            value="priority",
                                            clearable=False,
                                        ),
                                        md=6,
                                        className="mt-2",
                                    ),
                                    dbc.Col(
                                        dbc.Input(
                                            id="tm-assisted-expires-hours",
                                            type="number",
                                            min=1,
                                            max=72,
                                            step=1,
                                            value=12,
                                            placeholder="Hours",
                                        ),
                                        md=6,
                                        className="mt-2",
                                    ),
                                ], className="g-2"),
                                dbc.Row([
                                    dbc.Col(dbc.Button("Load Assisted Session", id="tm-assisted-load-btn", color="primary", className="w-100 mt-2"), md=3),
                                    dbc.Col(dbc.Button("Run Assisted Refresh", id="tm-assisted-run-btn", color="warning", className="w-100 mt-2"), md=3),
                                    dbc.Col(dbc.Button("Requeue Failed Jobs", id="tm-assisted-requeue-btn", color="info", className="w-100 mt-2"), md=3),
                                    dbc.Col(dbc.Button("Clear Session", id="tm-assisted-clear-btn", color="secondary", className="w-100 mt-2"), md=3),
                                ], className="g-2"),
                                html.Div(id="tm-admin-action-status", className="mt-2"),
                                dcc.Store(id="tm-admin-refresh-trigger"),
                            ])
                        ], className="home-system-shell")
                    ], width=12, className="mb-4")
                ])
                
            ], className="p-4 bg-primary-subtle rounded shadow")
        ], width=12, lg=10, className="mx-auto")
    ])  # Cierra dbc.Row
    ], fluid=True, className="py-4")
], className="main-container")
