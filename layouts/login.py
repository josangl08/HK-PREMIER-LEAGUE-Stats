# ABOUTME: Modern glassmorphism login layout for Dash 4.0 with HKFA aesthetic.
# ABOUTME: Enhanced visual consistency with glass cards and rounded corners.

from dash import html, dcc
import dash_bootstrap_components as dbc

_HKFA_HEADER = html.Div([
    html.Div([
        html.Img(src="/assets/logo_plintel.png", height="64px", className="mb-3"),
        html.H2("PLINTEL", className="fw-bold text-white mb-1"),
        html.P("Sports Analytics Platform", className="text-white-50 small mb-0"),
    ], className="p-4 text-center auth-header-gradient")
])


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
        html.Div([
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
            ], className="p-4 pt-3")
        ], className="auth-glass-card overflow-hidden")
    ], className="fadeIn")


def create_login_layout(login_status=None):
    """Alias de create_login_form() para compatibilidad con importaciones existentes."""
    return create_login_form(login_status)
