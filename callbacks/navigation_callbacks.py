# ABOUTME: Navigation callback that handles routing, authentication, and role-based access control.
# ABOUTME: Defines ROLE_ALLOWED_PATHS to restrict page access by user role.

from dash import Input, Output, callback, html
from flask_login import current_user
# Importar layouts
from layouts.home import layout as home_layout
from layouts.login import create_login_layout
from layouts.register import create_register_layout
from layouts.not_found import layout as not_found_layout
from layouts.performance import create_performance_layout
from layouts.injuries import create_injuries_layout
from components.navbar import create_navbar
from utils.app_context import get_hong_kong_data_manager

# Rutas que no requieren autenticación
PUBLIC_PATHS = ['/login', '/register']

# Mapa de rutas permitidas por rol (None = acceso total)
ROLE_ALLOWED_PATHS = {
    'admin': None,           # Acceso completo a todas las rutas
    'player': ['/performance'],
    'agent': ['/performance'],
}

# Ruta de inicio por defecto para roles sin acceso a '/'
ROLE_DEFAULT_PATH = {
    'player': '/performance',
    'agent': '/performance',
}


def _get_default_path_for_role(role: str) -> str:
    """Retorna la ruta de inicio según el rol del usuario."""
    return ROLE_DEFAULT_PATH.get(role, '/')


def _is_path_allowed(pathname: str, role: str) -> bool:
    """Verifica si el rol tiene acceso a la ruta solicitada."""
    allowed = ROLE_ALLOWED_PATHS.get(role)
    if allowed is None:
        return True  # admin: acceso total
    return pathname in allowed


@callback(
    [Output('page-content', 'children'),
     Output('navbar-container', 'children')],
    [Input('url', 'pathname')]
)
def display_page(pathname):
    """
    Callback principal de navegación: determina qué página mostrar
    según la URL, estado de autenticación y rol del usuario.
    """
    try:
        is_authenticated = current_user.is_authenticated if current_user else False
        user_role = getattr(current_user, 'role', 'player') if is_authenticated else None
    except Exception:
        is_authenticated = False
        user_role = None

    # Redirigir a login si la ruta requiere autenticación
    if pathname not in PUBLIC_PATHS and not is_authenticated:
        return create_login_layout(), html.Div()

    navbar = create_navbar(pathname) if is_authenticated else html.Div()

    try:
        if pathname == '/login':
            if is_authenticated:
                default = _get_default_path_for_role(user_role)
                return _render_path(default, navbar), navbar
            return create_login_layout(), html.Div()

        elif pathname == '/register':
            if is_authenticated:
                default = _get_default_path_for_role(user_role)
                return _render_path(default, navbar), navbar
            try:
                dm = get_hong_kong_data_manager()
                player_names = dm.get_player_names()
            except Exception:
                player_names = []
            return create_register_layout(player_names=player_names), html.Div()

        else:
            # Comprobar permisos de rol para rutas protegidas
            if is_authenticated and not _is_path_allowed(pathname, user_role):
                default = _get_default_path_for_role(user_role)
                return _render_path(default, navbar), navbar

            return _render_path(pathname, navbar), navbar

    except Exception as e:
        error_layout = html.Div([
            html.H1("Error", className="text-center"),
            html.P(f"Ha ocurrido un error: {str(e)}", className="text-center"),
            html.A("Volver al inicio", href="/", className="btn btn-primary")
        ], className="container mt-5")
        return error_layout, navbar


def _render_path(pathname: str, navbar):
    """Renderiza el layout correspondiente a una ruta."""
    if pathname == '/':
        return home_layout
    elif pathname == '/performance':
        return create_performance_layout()
    elif pathname == '/injuries':
        return create_injuries_layout()
    else:
        return not_found_layout