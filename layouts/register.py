# ABOUTME: Modern glassmorphism registration layout for Dash 4.0 with HKFA aesthetic.
# ABOUTME: Consistent visual experience with login; supports dynamic role selection.

from dash import html, dcc
import dash_bootstrap_components as dbc

_HKFA_HEADER = html.Div([
    html.Div([
        html.I(className="bi bi-person-plus-fill fs-1 text-white mb-3"),
        html.H2("Registro Oficial", className="fw-bold text-white mb-1"),
        html.P("Plataforma de IA para la Premier League", className="text-white-50 small mb-0"),
    ], className="p-4 text-center auth-header-gradient")
])

_ACTIVE_BTN_STYLE = {
    "backgroundColor": "#93312a", "borderColor": "#93312a", "color": "white",
    "fontWeight": "bold", "width": "50%", "borderRadius": "6px 0 0 6px"
}
_INACTIVE_BTN_STYLE = {
    "backgroundColor": "transparent", "borderColor": "#93312a", "color": "#93312a",
    "fontWeight": "bold", "width": "50%", "borderRadius": "0 6px 6px 0"
}


def create_register_form():
    """
    Devuelve solo el contenido interno de la tarjeta de registro (header + formulario).
    Renderizado dentro del auth-wrapper persistente de app.layout.
    """
    return html.Div([
        html.Div([
            _HKFA_HEADER,
            html.Div([
                html.Div(id='register-feedback'),
                dbc.Form([
                    # ── Role selector ─────────────────────────────────────
                    html.Div([
                        dbc.Label("Tipo de Cuenta", className="subtitle mb-2 d-block"),
                        html.Div([
                            dbc.Button(
                                "Jugador",
                                id='reg-role-btn-player',
                                n_clicks=0,
                                style=_ACTIVE_BTN_STYLE
                            ),
                            dbc.Button(
                                "Agente",
                                id='reg-role-btn-agent',
                                n_clicks=0,
                                style=_INACTIVE_BTN_STYLE
                            ),
                        ], style={"display": "flex"}),
                        dcc.Store(id='reg-role-store', data='player'),
                    ], className="mb-4"),

                    # ── Common fields ─────────────────────────────────────
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

                    # ── Player fields (visible by default) ────────────────
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
                            "Jugadores registrados en la HKPL."
                        ], className="text-muted opacity-75 d-block mt-2")
                    ], id='reg-player-fields', className="mb-4"),

                    # ── Agent fields (hidden by default) ──────────────────
                    html.Div([
                        html.Div([
                            dbc.Label("Nombre Completo", className="subtitle mb-2 d-block"),
                            dbc.Input(
                                type="text",
                                id="reg-agent-fullname-input",
                                placeholder="Tu nombre completo real",
                                className="form-control"
                            ),
                            html.Div(id='agent-fullname-feedback'),
                        ], className="mb-3"),

                        html.Div([
                            dbc.Label("Agencia / Organización", className="subtitle mb-2 d-block"),
                            dbc.Input(
                                type="text",
                                id="reg-agent-agency-input",
                                placeholder="Nombre de tu agencia o club",
                                className="form-control"
                            ),
                            html.Div(id='agent-agency-feedback'),
                        ], className="mb-3"),

                        html.Div([
                            dbc.Label("Correo de Contacto", className="subtitle mb-2 d-block"),
                            dbc.Input(
                                type="email",
                                id="reg-agent-email-input",
                                placeholder="correo@ejemplo.com",
                                className="form-control"
                            ),
                            html.Div(id='agent-email-feedback'),
                        ], className="mb-3"),

                        html.Div([
                            dbc.Label("N° de Licencia HKFA (opcional)", className="subtitle mb-2 d-block"),
                            dbc.Input(
                                type="text",
                                id="reg-agent-license-input",
                                placeholder="Ej. HKFA-2024-0042",
                                className="form-control"
                            ),
                        ], className="mb-3"),
                    ], id='reg-agent-fields', style={'display': 'none'}, className="mb-4"),

                    dbc.Button(
                        "SOLICITAR CUENTA",
                        id="register-button",
                        color="success",
                        size="lg",
                        className="w-100 fw-bold py-3 mb-4",
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
            ], className="p-4 pt-3")
        ], className="auth-glass-card overflow-hidden")
    ], className="fadeIn")


def create_register_layout(player_names=None, register_status=None):
    """Alias de create_register_form() para compatibilidad con importaciones existentes."""
    return create_register_form()
