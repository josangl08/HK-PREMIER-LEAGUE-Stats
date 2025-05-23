from dash import html
import dash_bootstrap_components as dbc

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1([
                "404 - Page not found",  # Ahora todo en español
                html.Span("🔍", className="ms-2")  # Emoji de búsqueda
            ], className="text-center my-4"),
            
            html.Div([
                html.P([
                    "Sorry, the page you are looking for does not exist or is not available."
                ], className="lead text-center"),
                
                html.Hr(),
                
                html.P([
                    "Please try navigating through the main menu or return to the home page."
                ], className="text-center text-muted mb-3"),
                
                dbc.Button([
                    html.I(className="fas fa-home me-2"),  # Icono de casa
                    "Volver al inicio"  # Texto más claro
                ], href="/", color="primary", className="d-block mx-auto"),
            ], className="p-4 bg-light rounded shadow")
        ], width=12, lg=6, className="mx-auto")
    ])
], fluid=True, className="py-4")