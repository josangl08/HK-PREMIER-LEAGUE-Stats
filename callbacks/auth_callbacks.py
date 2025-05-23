from dash import Input, Output, State, callback
from flask_login import login_user, logout_user
from utils.auth import validate_credentials
from dash.exceptions import PreventUpdate
import logging

# Configurar logging
logger = logging.getLogger(__name__)

@callback(
    [Output('login-status', 'data'),
     Output('url', 'pathname')],
    [Input('login-button', 'n_clicks')],
    [State('username-input', 'value'),
     State('password-input', 'value')],
    prevent_initial_call=True
)
def login_callback(n_clicks, username, password):
    """
    Maneja el proceso de login del usuario.
    
    Args:
        n_clicks: Número de clicks en el botón de login
        username: Nombre de usuario ingresado
        password: Contraseña ingresada
        
    Returns:
        Tuple con el estado del login y la ruta de redirección
    """
    if n_clicks is None:
        raise PreventUpdate
    
    try:
        # Validar las credenciales
        user = validate_credentials(username, password)
        
        if user:
            login_user(user)
            logger.info(f"Usuario {username} ha iniciado sesión exitosamente")
            return 'success', '/'  # Redirigir a la página principal
        else:
            logger.warning(f"Intento de login fallido para {username}")
            return 'failed', '/login'  # Permanecer en la página de login con error
            
    except Exception as e:
        logger.error(f"Error durante el proceso de login: {e}")
        return 'failed', '/login'

@callback(
    Output('logout-trigger', 'pathname'),
    Input('logout-button', 'n_clicks'),
    prevent_initial_call=True
)
def logout_callback(n_clicks):
    """
    Maneja el proceso de logout del usuario.
    
    Args:
        n_clicks: Número de clicks en el botón de logout
        
    Returns:
        Ruta de redirección al login
    """
    if n_clicks is None:
        raise PreventUpdate
    
    try:
        logout_user()
        logger.info("Usuario ha cerrado sesión")
        return '/login'
        
    except Exception as e:
        logger.error(f"Error durante el logout: {e}")
        return '/login'