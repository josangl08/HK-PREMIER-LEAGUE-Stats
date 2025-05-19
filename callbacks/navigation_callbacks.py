from dash import Input, Output, callback, html
from flask_login import current_user
# Importar layouts
from layouts.home import layout as home_layout
from layouts.login import create_login_layout
from layouts.not_found import layout as not_found_layout
from layouts.performance import create_performance_layout
from layouts.injuries import create_injuries_layout
from components.navbar import create_navbar

@callback(
    [Output('page-content', 'children'),
     Output('navbar-container', 'children')],
    [Input('url', 'pathname')]
)
def display_page(pathname):
    """
    Callback principal de navegación que determina qué página mostrar
    basándose en la URL actual y el estado de autenticación del usuario.
    """
    # Comprobar si el usuario está autenticado
    try:
        is_authenticated = current_user.is_authenticated if current_user else False
    except:
        # En caso de error con current_user, asumir no autenticado
        is_authenticated = False
    
    # Rutas que no requieren autenticación
    public_paths = ['/login']
    
    # Si la ruta requiere autenticación y el usuario no está autenticado, redirigir a login
    if pathname not in public_paths and not is_authenticated:
        return create_login_layout(), html.Div()
    
    # Mostrar navbar en todas las páginas excepto en login cuando el usuario está autenticado
    navbar = create_navbar(pathname) if is_authenticated else html.Div()
    
    # Enrutamiento basado en la ruta solicitada
    try:
        if pathname == '/':
            if not is_authenticated:
                return create_login_layout(), html.Div()
            return home_layout, navbar
        elif pathname == '/performance':
            return create_performance_layout(), navbar
        elif pathname == '/injuries':
            return create_injuries_layout(), navbar
        elif pathname == '/login':
            if is_authenticated:
                # Si ya está autenticado, redirigir a home
                return home_layout, navbar
            return create_login_layout(), html.Div()
        else:
            return not_found_layout, navbar
    except Exception as e:
        # En caso de error, mostrar página de error
        error_layout = html.Div([
            html.H1("Error", className="text-center"),
            html.P(f"Ha ocurrido un error: {str(e)}", className="text-center"),
            html.A("Volver al inicio", href="/", className="btn btn-primary")
        ], className="container mt-5")
        return error_layout, navbar