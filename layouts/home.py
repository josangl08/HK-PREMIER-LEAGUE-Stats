from dash import html
import dash_bootstrap_components as dbc

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Welcome to Sports Dashboard", className="text-center my-4"),
            html.Div([
                html.P([
                    "This application provides sports performance analysis and data management for ",
                    "‘teams and athletes. Navigate through the different sections to explore detailed analysis ",
                    "and interactive visualisations."
                ], className="lead text-center"),
                
                html.Hr(),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.H4("Performance Dashboard", className="text-center")),
                            dbc.CardBody([
                                html.P([
                                    "Detailed performance analysis of athletes and teams with ",
                                    "key metrics and interactive visualisations."
                                ]),
                                dbc.Button("Go to Performance", href="/performance", color="primary"),
                            ]),
                        ]),
                    ], width=12, md=6, className="mb-4"),
                    
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.H4("Injuries", className="text-center")),
                            dbc.CardBody([
                                html.P([
                                    "Injury management.",
                                ]),
                                dbc.Button("Go to Injuries", href="/injuries", color="primary"),
                            ]),
                        ]),
                    ], width=12, md=6, className="mb-4"),
                ]),
            ], className="p-4 bg-light rounded shadow")
        ], width=12, lg=8, className="mx-auto") 
    ])
], fluid=True, className="py-4")