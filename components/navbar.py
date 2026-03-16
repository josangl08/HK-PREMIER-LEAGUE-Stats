import dash_bootstrap_components as dbc
from dash import html, dcc
from flask_login import current_user


# Crea la barra de navegación
def create_navbar(pathname):

    # Definir la estructura de enlaces de navegación
    user_role = getattr(current_user, 'role', None) if current_user.is_authenticated else None
    nav_items = [
        dbc.NavItem(
            dbc.NavLink(
                [html.I(className="bi bi-house me-2"), "Home"],
                href="/",
                active=pathname == "/",
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

    # Agregar información de usuario y botón de logout
    nav_right = dbc.Nav(
        [
            dbc.NavItem(
                [
                    html.Span(
                        [
                            html.I(className="bi bi-person-circle text-white me-2"),
                            (
                                f"User: {current_user.id}"
                                if current_user.is_authenticated
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
                                #    dbc.Col(
                                #        html.Img(
                                #            src="/assets/logo.png",
                                #            height="50px",
                                #            className="ms-3 me-3",
                                #        ),
                                #        width="auto",
                                #    ),
                                #    dbc.Col(
                                #        dbc.NavbarBrand(
                                #            "HK Premier League Stats", className="ms-2"
                                #        ),
                                #        width="auto",
                                #    ),
                            ],
                            align="center",
                            className="g-0",
                        ),
                        href="/",
                        className="navbar-brand-link",
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
        className="mb-4",
    )

    return navbar
