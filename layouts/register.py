# ABOUTME: Modern registration layout for Dash 4.0 with HKFA aesthetic.
# ABOUTME: Fixed missing register-feedback ID and enhanced visual consistency.

from dash import html, dcc
import dash_bootstrap_components as dbc

_HKFA_HEADER = html.Div([
    html.I(className="bi bi-person-plus-fill fs-1 text-white mb-3"),
    html.H2("Registro Oficial", className="fw-bold text-white mb-0"),
    html.P("Plataforma de IA para la Premier League", className="text-white-50 small mb-0"),
], className="text-center p-4 rounded-top-4",
   style={
       "background": "linear-gradient(180deg, #93312a 0%, #18181A 100%)",
       "borderBottom": "2px solid #3A3A3C"
   })


def create_register_form():
    """
    Devuelve solo el contenido interno de la tarjeta de registro (header + formulario).
    Renderizado dentro del auth-wrapper persistente de app.layout.
    El dcc.Store 'player-names-store' reside en app.layout y se actualiza
    por el navigation callback al entrar en /register.
    """
    return html.Div([
        _HKFA_HEADER,
        html.Div([
            html.Div(id='register-feedback'),
            dbc.Form([
                html.Div([
                    dbc.Label("Nombre de Usuario", className="subtitle mb-2 d-block"),
                    dbc.Input(
                        type="text",
                        id="reg-username-input",
                        placeholder="Elige un usuario único",
                        className="form-control",
                        autoComplete="username"
                    ),
                    html.Div(id='username-feedback'),
                ], className="mb-3"),

                html.Div([
                    dbc.Label("Contraseña", className="subtitle mb-2 d-block"),
                    dbc.Input(
                        type="password",
                        id="reg-password-input",
                        placeholder="Mínimo 8 caracteres",
                        className="form-control",
                        autoComplete="new-password"
                    ),
                    html.Div(id='password-feedback'),
                ], className="mb-3"),

                html.Div([
                    dbc.Label("Confirmar Contraseña", className="subtitle mb-2 d-block"),
                    dbc.Input(
                        type="password",
                        id="reg-confirm-password-input",
                        placeholder="Repite tu contraseña",
                        className="form-control",
                        autoComplete="new-password"
                    ),
                    html.Div(id='confirm-password-feedback'),
                ], className="mb-3"),

                html.Div([
                    dbc.Label("Identidad de Jugador", className="subtitle mb-2 d-block"),
                    dcc.Dropdown(
                        id="reg-player-name-dropdown",
                        options=[],
                        placeholder="Busca tu nombre en la base de datos...",
                        className="mb-2"
                    ),
                    html.Small([
                        html.I(className="bi bi-info-circle-fill me-1"),
                        "Jugadores registrados en la HKPL (todas las temporadas)."
                    ], className="text-muted opacity-75 d-block mt-2")
                ], className="mb-4"),

                dbc.Button(
                    "SOLICITAR CUENTA",
                    id="register-button",
                    color="success",
                    size="lg",
                    className="w-100 fw-bold py-3 mb-4 shadow-sm",
                    style={"letterSpacing": "1px"}
                ),

                html.Div([
                    dcc.Link([
                        html.I(className="bi bi-arrow-left me-2"),
                        "Volver al inicio de sesión"
                    ], href="/login",
                       className="link small d-block text-center text-decoration-none")
                ], className="mt-2")
            ]),
        ], className="p-4 bg-secondary-custom rounded-bottom-4 shadow-lg")
    ], className="fadeIn")


def create_register_layout(player_names=None, register_status=None):
    """Alias de create_register_form() para compatibilidad con importaciones existentes."""
    return create_register_form()
