import dash_bootstrap_components as dbc
from dash import html, dcc
from flask_login import current_user


# Crea la barra de navegación
def create_navbar(pathname):

    # Definir la estructura de enlaces de navegación
    is_auth = current_user.is_authenticated if current_user else False
    user_role = getattr(current_user, 'role', 'player') if is_auth else None
    
    # Determinar ruta de inicio según rol
    home_href = "/"
    if user_role == 'player':
        home_href = "/player-portal"
    elif user_role == 'agent':
        home_href = "/agent-portal"

    home_label = "Home"
    home_icon = "bi-house"
    if user_role == 'player':
        home_label = "Player Portal"
        home_icon = "bi-person-circle"

    nav_items = [
        dbc.NavItem(
            dbc.NavLink(
                [html.I(className=f"bi {home_icon} me-2"), home_label],
                href=home_href,
                active=pathname == home_href,
                className="me-3 text-decoration-none",
            )
        ),
    ]

    if user_role != 'agent':
        nav_items.append(
            dbc.NavItem(
                dbc.NavLink(
                    [html.I(className="bi bi-bar-chart me-2"), "Performance"],
                    href="/performance",
                    active=pathname == "/performance",
                    className="text-decoration-none",
                )
            )
        )

    # Portal Agente — visible for admin and agent roles
    if user_role in ('admin', 'agent'):
        nav_items.append(
            dbc.NavItem(
                dbc.NavLink(
                    [html.I(className="bi bi-person-badge me-2"), "Portal Agente"],
                    href="/agent-portal",
                    active=pathname == "/agent-portal",
                    className="ms-3 text-decoration-none",
                )
            )
        )

    # AI Insights — visible for admin and player roles only (not agent)
    if user_role in ('admin', 'player'):
        nav_items.append(
            dbc.NavItem(
                dbc.NavLink(
                    [html.I(className="bi bi-cpu me-2"), "AI Insights"],
                    href="/ai-insights",
                    active=pathname == "/ai-insights",
                    className="ms-3 text-decoration-none",
                )
            )
        )

    # Player Portal — visible for admin only (players already have it as home)
    if user_role == 'admin':
         nav_items.append(
            dbc.NavItem(
                dbc.NavLink(
                    [html.I(className="bi bi-person-circle me-2"), "Player Portal"],
                    href="/player-portal",
                    active=pathname == "/player-portal",
                    className="ms-3 text-decoration-none",
                )
            )
        )

    # Agregar información de usuario y botón de logout
    nav_right = dbc.Nav(
        [
            dbc.NavItem(
                dbc.Button(
                    [
                        html.I(className="bi bi-bell-fill"),
                        dbc.Badge(
                            id="insight-inbox-count",
                            color="danger",
                            pill=True,
                            className="position-absolute top-0 start-100 translate-middle",
                            style={"fontSize": "0.55rem", "display": "none"},
                        ),
                    ],
                    id="insight-inbox-btn",
                    color="link",
                    className="p-1 position-relative me-3" + ("" if pathname == "/player-portal" else " d-none"),
                    style={"color": "var(--accent-cyan)", "fontSize": "1.1rem"},
                ),
            ),
            dbc.NavItem(
                [
                    html.Span(
                        [
                            html.I(className="bi bi-person-circle text-white me-2"),
                            (
                                f"User: {current_user.id}"
                                if is_auth
                                else ""
                            ),
                        ],
                        className="navbar-text text-white me-3",
                    )
                ],
                className="me-4 align-middle",
            ),
            dbc.NavItem(
                dbc.Button(
                    [
                        html.I(className="bi bi-box-arrow-right text-white me-2"),
                        "Logout",
                    ],
                    id="logout-button",
                    color="secondary",
                    size="sm",
                    className="me-1",
                )
            ),
            # Location para manejar el logout
            dcc.Location(id="logout-trigger", refresh=True),
        ],
        navbar=True,
    )

    # Crear la barra de navegación completa
    navbar = dbc.Navbar(
        [
            dbc.Container(
                [
                    html.A(
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Img(
                                        src="/assets/logo.png",
                                        height="30px",
                                        className="me-2",
                                    ),
                                    width="auto",
                                ),
                                dbc.Col(
                                    dbc.NavbarBrand(
                                        "HKPL Stats", className="ms-1 fw-bold"
                                    ),
                                    width="auto",
                                ),
                            ],
                            align="center",
                            className="g-0",
                        ),
                        href=home_href,
                        className="navbar-brand-link text-decoration-none",
                    ),
                    dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
                    dbc.Collapse(
                        [
                            dbc.Nav(nav_items, className="me-auto", navbar=True),
                            nav_right,
                        ],
                        id="navbar-collapse",
                        navbar=True,
                        is_open=False,
                    ),
                ]
            ),
        ],
        dark=True,
        color="dark",
        className="shadow-sm",
    )

    return navbar
