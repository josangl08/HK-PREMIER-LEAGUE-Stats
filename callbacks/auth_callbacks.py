# ABOUTME: Callbacks for login, logout, and user registration flows.
# ABOUTME: Delegates credential validation and user creation to AuthRepository.

from dash import Input, Output, State, callback, html
from flask_login import login_user, logout_user
from utils.auth import AuthRepository
from utils.app_context import get_hong_kong_data_manager
from dash.exceptions import PreventUpdate
import logging

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
    """Maneja el proceso de login con redirección según el rol del usuario."""
    if n_clicks is None:
        raise PreventUpdate

    try:
        user = AuthRepository.validate_credentials(username, password)

        if user:
            login_user(user)
            logger.info(f"Login exitoso para {username} (role={user.role})")
            # Redirección según rol
            redirect_path = '/' if user.role == 'admin' else '/performance'
            return 'success', redirect_path
        else:
            logger.warning(f"Login fallido para {username}")
            return 'failed', '/login'

    except Exception as e:
        logger.error(f"Error durante el login: {e}")
        return 'failed', '/login'


@callback(
    Output('logout-trigger', 'pathname'),
    Input('logout-button', 'n_clicks'),
    prevent_initial_call=True
)
def logout_callback(n_clicks):
    """Maneja el proceso de logout del usuario."""
    if n_clicks is None:
        raise PreventUpdate

    try:
        logout_user()
        logger.info("Usuario ha cerrado sesión")
        return '/login'
    except Exception as e:
        logger.error(f"Error durante el logout: {e}")
        return '/login'


@callback(
    [Output('register-feedback', 'children'),
     Output('url', 'pathname', allow_duplicate=True)],
    [Input('register-button', 'n_clicks')],
    [State('reg-username-input', 'value'),
     State('reg-password-input', 'value'),
     State('reg-player-name-dropdown', 'value')],
    prevent_initial_call=True
)
def handle_registration(n_clicks, username, password, player_name):
    """
    Maneja el registro de nuevos usuarios.
    Valida que el player_name exista en DataManager antes de crear la cuenta.
    """
    if n_clicks is None:
        raise PreventUpdate

    # Validar campos requeridos
    if not username or not password or not player_name:
        return _error_alert("Todos los campos son obligatorios."), '/register'

    # Validar que el nombre del jugador existe en los datos de Wyscout
    try:
        dm = get_hong_kong_data_manager()
        valid_players = dm.get_player_names()
        if player_name not in valid_players:
            return _error_alert(f"El jugador '{player_name}' no existe en los datos de la liga."), '/register'
    except Exception as e:
        logger.error(f"Error consultando DataManager durante registro: {e}")
        return _error_alert("Error al verificar los datos de jugadores. Inténtalo de nuevo."), '/register'

    # Crear la cuenta
    try:
        created = AuthRepository.create_user(
            username=username,
            password=password,
            role='player',
            player_name=player_name
        )
        if created:
            logger.info(f"Nuevo usuario registrado: {username} (player={player_name})")
            return None, '/login'
        else:
            return _error_alert(f"El nombre de usuario '{username}' ya existe."), '/register'
    except Exception as e:
        logger.error(f"Error durante el registro de {username}: {e}")
        return _error_alert("Error interno al crear la cuenta. Inténtalo de nuevo."), '/register'


def _error_alert(message: str):
    """Genera un componente de alerta de error para el formulario de registro."""
    from dash import dcc
    import dash_bootstrap_components as dbc
    return dbc.Alert(message, color="danger", dismissable=True, className="mb-3")
