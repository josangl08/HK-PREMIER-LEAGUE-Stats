from dash import html, dcc
import dash_bootstrap_components as dbc

# Crea el layout de la página de login
def create_login_layout(login_status=None):
    
    # Mensaje de error condicionado al estado de login
    error_message = None
    if login_status == 'failed':
        error_message = dbc.Alert(
            "Incorrect username or password. Please try again.",
            color="danger",
            dismissable=True,
            className="mb-3"
        )
    
    # Layout completo de la página de login
    layout = dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H2("Login", className="text-center mb-4"),
                    html.Hr(),
                    
                    # Mensaje de error (si existe)
                    error_message if error_message else html.Div(),
                    
                    # Formulario de login
                    dbc.Form([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("User", html_for="username-input"),
                                dbc.Input(
                                    type="text",
                                    id="username-input",
                                    placeholder="Enter your username",
                                    className="mb-3",
                                    autoComplete="username"
                                ),
                            ])
                        ], className="mb-3"),
                        
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Password", html_for="password-input"),
                                dbc.Input(
                                    type="password",
                                    id="password-input",
                                    placeholder="Enter your password",
                                    className="mb-4",
                                    autoComplete="current-password"
                                ),
                            ])
                        ], className="mb-3"),
                        
                        dbc.Button(
                            "Login", 
                            id="login-button", 
                            color="primary", 
                            className="w-100 mt-3"
                        ),
                        
                        # Store para guardar el estado de login
                        dcc.Store(id='login-status'),
                    ]),
                    
                    html.Div([
                        html.P([
                            "Demostration Credentials: ",
                            html.Strong("admin / admin")
                        ], className="text-muted small text-center mt-4")
                    ])
                    
                ], className="p-4 bg-light rounded shadow"),
                
            ], width=12, md=6, lg=4, className="mx-auto mt-5")
        ])
    ], fluid=True, className="py-5")
    
    return layout