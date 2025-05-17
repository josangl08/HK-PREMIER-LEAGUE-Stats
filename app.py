import os
import dash
from dash import html
import dash_bootstrap_components as dbc
from flask_login import LoginManager, login_required
from flask import redirect, url_for
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Importar componentes propios
from components.navbar import create_navbar
from layouts.home import layout as home_layout
from layouts.not_found import layout as not_found_layout
from utils.auth import User, load_user

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

# Configurar autenticación con Flask-Login
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = "/login"

@login_manager.user_loader
def load_user_from_id(user_id):
    return load_user(user_id)

# Definir layout de la app con enrutamiento
app.layout = html.Div([
    dash.dcc.Location(id='url', refresh=False),
    html.Div(id='navbar-container'),
    html.Div(id='page-content')
])

# Callback para enrutamiento
@app.callback(
    [dash.Output('page-content', 'children'),
     dash.Output('navbar-container', 'children')],
    [dash.Input('url', 'pathname')]
)
def display_page(pathname):
    # Mostrar navbar en todas las páginas excepto en login
    navbar = create_navbar(pathname)
    
    # Enrutamiento básico
    if pathname == '/':
        return home_layout, navbar
    elif pathname == '/performance':
        # Esta página se implementará más tarde
        return html.Div("Dashboard de Performance (Por implementar)"), navbar
    elif pathname == '/noncompetitive':
        # Esta página se implementará más tarde
        return html.Div("Dashboard de Área No Competitiva (Por implementar)"), navbar
    elif pathname == '/login':
        # No mostrar navbar en la página de login
        return html.Div("Página de login (Por implementar)"), html.Div()
    else:
        return not_found_layout, navbar

# Punto de entrada
if __name__ == '__main__':
    app.run(debug=os.getenv("DEBUG", "True") == "True")