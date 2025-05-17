from dash import html
import dash_bootstrap_components as dbc

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("404 - Página not found", className="text-center my-4"),
            html.Div([
                html.P([
                    "Sorry, the page you are looking for does not exist or is not available."
                ], className="lead text-center"),
                
                html.Hr(),
                
                dbc.Button("Back to top", href="/", color="primary", className="d-block mx-auto"),
            ], className="p-4 bg-light rounded shadow")
        ], width=12, lg=6, className="mx-auto")
    ])
], fluid=True, className="py-4")