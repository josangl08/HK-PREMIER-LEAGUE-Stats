from dash import Input, Output, State, callback
from flask_login import login_user, logout_user, current_user
from utils.auth import validate_credentials
import dash
from dash.exceptions import PreventUpdate

# Callback para manejar el login
@callback(
    [Output('login-status', 'data'),
     Output('url', 'pathname')],
    [Input('login-button', 'n_clicks')],
    [State('username-input', 'value'),
     State('password-input', 'value')],
    prevent_initial_call=True
)
def login_callback(n_clicks, username, password):
    if n_clicks is None:
        raise PreventUpdate
    
    # Validar las credenciales
    user = validate_credentials(username, password)
    
    if user:
        login_user(user)
        return 'success', '/'  # Redirigir a la página principal
    else:
        return 'failed', '/login'  # Permanecer en la página de login con error

# Callback para manejar el logout
@callback(
    Output('logout-trigger', 'pathname'),
    Input('logout-button', 'n_clicks'),
    prevent_initial_call=True
)
def logout_callback(n_clicks):
    if n_clicks is None:
        raise PreventUpdate
    
    logout_user()
    return '/login'