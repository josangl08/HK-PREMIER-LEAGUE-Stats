# ABOUTME: Navigation callback that handles routing, authentication, and role-based access control.
# ABOUTME: Defines ROLE_ALLOWED_PATHS to restrict page access by user role.

from dash import Input, Output, callback, html, no_update
from flask_login import current_user
# Importar layouts
from layouts.home import layout as home_layout
from layouts.login import create_login_form
from layouts.register import create_register_form
from layouts.not_found import layout as not_found_layout
from layouts.performance import create_performance_layout
from layouts.injuries import create_injuries_layout
from components.navbar import create_navbar
try:
    from layouts.ai_insights import create_ai_insights_layout
    _AI_INSIGHTS_AVAILABLE = True
except ImportError:
    _AI_INSIGHTS_AVAILABLE = False

# Rutas que no requieren autenticación
PUBLIC_PATHS = ['/login', '/register']

# Mapa de rutas permitidas por rol (None = acceso total)
ROLE_ALLOWED_PATHS = {
    'admin': None,                                      # Acceso completo a todas las rutas
    'player': ['/performance', '/ai-insights'],
    'agent': ['/agent-portal', '/performance'],         # Sin /ai-insights (predictor callbacks)
}

# Ruta de inicio por defecto para roles sin acceso a '/'
ROLE_DEFAULT_PATH = {
    'player': '/performance',
    'agent': '/agent-portal',
}

_AUTH_VISIBLE = {"display": "block"}
_AUTH_HIDDEN  = {"display": "none"}


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
     Output('navbar-container', 'children'),
     Output('auth-wrapper', 'style'),
     Output('auth-form-content', 'children')],
    [Input('url', 'pathname')]
)
def display_page(pathname):
    """
    Callback principal de navegación.
    Para rutas auth (/login, /register) muestra el auth-wrapper y vacia page-content.
    Solo auth-form-content cambia entre login y register — el shell persiste.
    """
    try:
        is_authenticated = current_user.is_authenticated if current_user else False
        user_role = getattr(current_user, 'role', 'player') if is_authenticated else None
    except Exception:
        is_authenticated = False
        user_role = None

    # Unauthenticated user trying to access protected route → show login form
    if pathname not in PUBLIC_PATHS and not is_authenticated:
        return html.Div(), html.Div(), _AUTH_VISIBLE, create_login_form()

    navbar = create_navbar(pathname) if is_authenticated else html.Div()

    try:
        if pathname == '/login':
            if is_authenticated:
                default = _get_default_path_for_role(user_role)
                return _render_path(default, navbar, user_role), navbar, _AUTH_HIDDEN, no_update
            return html.Div(), html.Div(), _AUTH_VISIBLE, create_login_form()

        elif pathname == '/register':
            if is_authenticated:
                default = _get_default_path_for_role(user_role)
                return _render_path(default, navbar, user_role), navbar, _AUTH_HIDDEN, no_update
            return html.Div(), html.Div(), _AUTH_VISIBLE, create_register_form()

        else:
            # Comprobar permisos de rol para rutas protegidas
            if is_authenticated and not _is_path_allowed(pathname, user_role):
                default = _get_default_path_for_role(user_role)
                return _render_path(default, navbar, user_role), navbar, _AUTH_HIDDEN, no_update

            return _render_path(pathname, navbar, user_role), navbar, _AUTH_HIDDEN, no_update

    except Exception as e:
        error_layout = html.Div([
            html.H1("Error", className="text-center"),
            html.P(f"Ha ocurrido un error: {str(e)}", className="text-center"),
            html.A("Volver al inicio", href="/", className="btn btn-primary")
        ], className="container mt-5")
        return error_layout, navbar, _AUTH_HIDDEN, no_update


def _render_path(pathname: str, navbar, user_role: str = None):
    """Renderiza el layout correspondiente a una ruta."""
    if pathname == '/':
        return home_layout
    elif pathname == '/performance':
        return create_performance_layout()
    elif pathname == '/injuries':
        return create_injuries_layout()
    elif pathname == '/ai-insights':
        if _AI_INSIGHTS_AVAILABLE:
            return create_ai_insights_layout(user_role)
        return html.Div([
            html.H2("AI Insights — Coming Soon", className="text-center mt-5"),
            html.P("This feature is currently being set up.", className="text-center text-muted"),
        ])
    elif pathname == '/agent-portal':
        from layouts.performance_views.agent_view import create_agent_view_layout
        return create_agent_view_layout()
    else:
        return not_found_layout
