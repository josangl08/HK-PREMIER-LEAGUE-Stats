from dash import html, dcc
import dash_bootstrap_components as dbc

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Welcome to Hong Kong Premier League Dashboard", className="text-center my-4"),
            html.Div([
                html.P([
                    "Esta aplicación proporciona análisis de performance deportiva y gestión de datos para ",
                    "equipos y atletas de la Liga de Hong Kong. Navega por las diferentes secciones para explorar ",
                    "análisis detallados y visualizaciones interactivas."
                ], className="lead text-center"),
                
                html.Hr(),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.H4("Dashboard de Performance", className="text-center")),
                            dbc.CardBody([
                                html.Ul([
                                    html.Li("📊 Estadísticas de liga completa"),
                                    html.Li("⚽ Análisis por equipo"),
                                    html.Li("👤 Perfiles de jugadores"),
                                    html.Li("📈 Gráficos interactivos"),
                                    html.Li("📄 Exportación a PDF")
                                ]),
                                dbc.Button("Ir a Performance", href="/performance", color="primary", className="w-100"),
                            ]),
                        ]),
                    ], width=12, md=6, className="mb-4"),
                    
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.H4("Dashboard de Injuries", className="text-center")),
                            dbc.CardBody([
                                html.Ul([
                                    html.Li("🏥 Gestión de lesiones"),
                                    html.Li("📋 Historiales médicos"),
                                    html.Li("📊 Análisis de riesgos"),
                                    html.Li("📈 Tendencias de lesiones"),
                                    html.Li("📄 Reportes médicos")
                                ]),
                                dbc.Button("Ir a Injuries", href="/injuries", color="success", className="w-100"),
                            ]),
                        ]),
                    ], width=12, md=6, className="mb-4"),
                ]),
                
                html.Hr(),
                
                # Sección de información del sistema
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.H5("Estado del Sistema", className="text-center")),
                            dbc.CardBody([
                                html.Div(id="system-status-info"),
                                dbc.Button(
                                    "Actualizar Datos", 
                                    id="refresh-data-button", 
                                    color="info", 
                                    size="sm", 
                                    className="mt-2 w-100"
                                )
                            ])
                        ])
                    ], width=12, md=8, className="mx-auto")
                ])
                
            ], className="p-4 bg-secondary-subtle rounded shadow")
        ], width=12, lg=10, className="mx-auto") 
    ])
], fluid=True, className="py-4")