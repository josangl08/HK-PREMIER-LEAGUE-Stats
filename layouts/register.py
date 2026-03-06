# ABOUTME: Layout for user registration with player selection validation.
# ABOUTME: Part of the auth-multi-usuario change.

from dash import html, dcc
import dash_bootstrap_components as dbc

def create_register_layout(player_names=None, register_status=None):
    """
    Crea el layout de la página de registro.
    
    Args:
        player_names (list, optional): Lista de nombres de jugadores para el dropdown.
        register_status (str, optional): Estado del registro ('failed' si falló).
        
    Returns:
        dbc.Container: Layout completo de la página de registro
    """
    
    # Mensaje de error condicionado al estado de registro
    error_message = None
    if register_status:
        error_message = dbc.Alert(
            register_status,
            color="danger",
            dismissable=True,
            className="mb-3"
        )
    
    # Preparar opciones para el dropdown de jugadores
    player_options = []
    if player_names:
        player_options = [{"label": name, "value": name} for name in sorted(player_names)]
    
    # Layout completo de la página de registro
    layout = dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H2("Create Account", className="text-center mb-4"),
                    html.P("Join the HK Premier League Stats Platform", className="text-center text-muted mb-4"),
                    html.Hr(),

                    # Contenedor de feedback (actualizado por handle_registration callback)
                    html.Div(id='register-feedback',
                             children=error_message if error_message else None),
                    
                    # Formulario de registro
                    dbc.Form([
                        # Username
                        html.Div([
                            dbc.Label("Username", html_for="reg-username-input"),
                            dbc.Input(
                                type="text",
                                id="reg-username-input",
                                placeholder="Choose a username",
                                className="mb-3",
                                autoComplete="username"
                            ),
                        ], className="mb-3"),
                        
                        # Password
                        html.Div([
                            dbc.Label("Password", html_for="reg-password-input"),
                            dbc.Input(
                                type="password",
                                id="reg-password-input",
                                placeholder="Choose a secure password",
                                className="mb-3",
                                autoComplete="new-password"
                            ),
                        ], className="mb-3"),
                        
                        # Player Name Selection (Validation against DataManager)
                        html.Div([
                            dbc.Label("I am Player:", html_for="reg-player-name-dropdown"),
                            dcc.Dropdown(
                                id="reg-player-name-dropdown",
                                options=player_options,
                                placeholder="Select your player name",
                                className="mb-3"
                            ),
                            html.Small("Registration requires associating your account with a real player.", 
                                       className="text-muted")
                        ], className="mb-3"),
                        
                        dbc.Button(
                            "Register", 
                            id="register-button", 
                            color="success", 
                            className="w-100 mt-3"
                        ),
                        
                        html.Div([
                            html.A("Already have an account? Login here", href="/login", 
                                   className="d-block text-center mt-4 small text-decoration-none")
                        ])
                    ]),
                    
                ], className="p-4 bg-light rounded shadow"),
                
            ], width=12, md=6, lg=5, className="mx-auto mt-5")
        ])
    ], fluid=True, className="py-5")
    
    return layout
