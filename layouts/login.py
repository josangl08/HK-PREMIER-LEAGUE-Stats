# ABOUTME: Modern login layout for Dash 4.0 with HKFA aesthetic.
# ABOUTME: Removed demo credentials and enhanced visual consistency with gradients.

from dash import html, dcc
import dash_bootstrap_components as dbc

_HKFA_HEADER = html.Div([
    html.I(className="bi bi-shield-lock-fill fs-1 text-white mb-3"),
    html.H2("HK Premier League", className="fw-bold text-white mb-0"),
    html.P("Sports Analytics Platform", className="text-white-50 small mb-0"),
], className="text-center p-4 rounded-top-4",
   style={
       "background": "linear-gradient(180deg, #93312a 0%, #18181A 100%)",
       "borderBottom": "2px solid #3A3A3C"
   })


def create_login_form(login_status=None):
    """
    Devuelve solo el contenido interno de la tarjeta de login (header + formulario).
    Renderizado dentro del auth-wrapper persistente de app.layout.
    """
    error_message = None
    if login_status == 'failed':
        error_message = dbc.Alert(
            "Credenciales incorrectas. Inténtalo de nuevo.",
            color="danger",
            dismissable=True,
            className="mb-4 border-start border-danger border-4 fw-medium"
        )

    return html.Div([
        _HKFA_HEADER,
        html.Div([
            html.Div(id='login-feedback'),
            dbc.Form([
                html.Div([
                    dbc.Label("Usuario", className="subtitle mb-2 d-block"),
                    dbc.Input(
                        type="text",
                        id="username-input",
                        placeholder="Introduce tu usuario",
                        className="form-control",
                        autoComplete="username"
                    ),
                ], className="mb-4"),

                html.Div([
                    dbc.Label("Contraseña", className="subtitle mb-2 d-block"),
                    dbc.Input(
                        type="password",
                        id="password-input",
                        placeholder="Introduce tu contraseña",
                        className="form-control",
                        autoComplete="current-password"
                    ),
                ], className="mb-4"),

                dbc.Button(
                    "ACCEDER AL PANEL",
                    id="login-button",
                    color="primary",
                    size="lg",
                    className="w-100 fw-bold py-3 mt-2",
                    style={"letterSpacing": "1px"}
                ),

                html.Div([
                    html.P([
                        "¿Eres nuevo en la liga? ",
                        dcc.Link("Solicitar acceso", href="/register",
                                 className="link fw-bold text-decoration-none")
                    ], className="text-center mt-4 small mb-0")
                ]),
            ]),
        ], className="p-4 bg-secondary-custom rounded-bottom-4 shadow-lg")
    ], className="fadeIn")


def create_login_layout(login_status=None):
    """Alias de create_login_form() para compatibilidad con importaciones existentes."""
    return create_login_form(login_status)
