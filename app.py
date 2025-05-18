import os
import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
from flask_login import LoginManager, current_user
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Importar componentes propios
from components.navbar import create_navbar
from layouts.home import layout as home_layout
from layouts.login import create_login_layout
from layouts.not_found import layout as not_found_layout
from utils.auth import User, load_user
from utils.cache import init_cache

# Importar callbacks - esto registrará los callbacks automáticamente
from callbacks import auth_callbacks

# Inicializar la aplicación Dash con tema Bootstrap
app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"}
    ],
)

# Configuraciones básicas
app.title = "Sports Dashboard"
server = app.server
server.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "clave_secreta_predeterminada")

# Inicializar el caché
cache = init_cache(app)

# Configurar autenticación con Flask-Login
login_manager = LoginManager()
login_manager.init_app(server)

@login_manager.user_loader
def load_user_from_id(user_id):
    return load_user(user_id)

# Definir layout de la app con enrutamiento
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='navbar-container'),
    html.Div(id='page-content'),
    
    # Store para estado de login
    dcc.Store(id='login-status', storage_type='session'),
])

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
        return html.Div("Dashboard de Área No Competitiva (Por implementar)"), navbar
    elif pathname == '/login':
        if is_authenticated:
            # Si ya está autenticado, redirigir a home
            return home_layout, navbar
        return create_login_layout(), html.Div()
    else:
        return not_found_layout, navbar

# Punto de entrada
if __name__ == '__main__':
    app.run(debug=os.getenv("DEBUG", "True") == "True")