from dash import html, dcc
import dash_bootstrap_components as dbc

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Welcome to Hong Kong Premier League Dashboard", className="text-center my-4"),
            html.Div([
                html.P([
                    "This application provides sports performance analysis and data management for  ",
                    "teams and athletes in the Hong Kong League. ",
                ], className="lead text-center"),
                
                html.Hr(),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.H4("Performance Dashboard", className="text-center")),
                            dbc.CardBody([
                                html.Ul([
                                    html.Li("📊 Full league statistics"),
                                    html.Li("⚽ Analysis by team"),
                                    html.Li("👤 Player profiles"),
                                    html.Li("📈 Interactive graphics"),
                                    html.Li("📄 Export to PDF")
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
                                    html.Li("🏥 Injury management"),
                                    html.Li("📋 Medical records"),
                                    html.Li("📊 Risk analysis"),
                                    html.Li("📈 Injury trends"),
                                    html.Li("📄 Medical reports")
                                ]),
                                dbc.Button("Go to Injuries", href="/injuries", color="warning", className="w-100"),
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