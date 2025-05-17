from dash import Input, Output, callback, html
from flask_login import current_user
from layouts.home import layout as home_layout
from layouts.login import create_login_layout
from layouts.not_found import layout as not_found_layout
from components.navbar import create_navbar

@callback(
    [Output('page-content', 'children'),
     Output('navbar-container', 'children')],
    [Input('url', 'pathname')]
)
def display_page(pathname):
    # Comprobar si el usuario está autenticado
    is_authenticated = current_user.is_authenticated if current_user else False
    
    # Rutas que no requieren autenticación
    public_paths = ['/login']
    
    # Si la ruta requiere autenticación y el usuario no está autenticado, redirigir a login
    if pathname not in public_paths and not is_authenticated:
        return create_login_layout(), html.Div()
    
    # Mostrar navbar en todas las páginas excepto en login cuando el usuario está autenticado
    navbar = create_navbar(pathname) if is_authenticated else html.Div()
    
    # Enrutamiento basado en la ruta solicitada
    if pathname == '/':
        if not is_authenticated:
            return create_login_layout(), html.Div()
        return home_layout, navbar
    elif pathname == '/performance':
        return html.Div("Dashboard de Performance (Por implementar)"), navbar
    elif pathname == '/injuries':
        return html.Div("Dashboard de Injuries (Por implementar)"), navbar
    elif pathname == '/login':
        if is_authenticated:
            # Si ya está autenticado, redirigir a home
            return home_layout, navbar
        return create_login_layout(), html.Div()
    else:
        return not_found_layout, navbar