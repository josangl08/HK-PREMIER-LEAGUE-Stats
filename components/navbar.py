import dash_bootstrap_components as dbc
from dash import html, dcc
from flask_login import current_user

# Crea la barra de navegación
def create_navbar(pathname):
   
    # Definir la estructura de enlaces de navegación
    nav_items = [
        dbc.NavItem(
            dbc.NavLink(
                "Home", 
                href="/", 
                active=pathname == "/"
            )
        ),
        dbc.NavItem(
            dbc.NavLink(
                "Performance", 
                href="/performance", 
                active=pathname == "/performance"
            )
        ),
        dbc.NavItem(
            dbc.NavLink(
                "Injuries", 
                href="/injuries", 
                active=pathname == "/injuries"
            )
        ),
    ]
    
    # Agregar información de usuario y botón de logout
    nav_right = dbc.Nav(
        [
            dbc.NavItem(
                [
                    html.Span(
                        f"User: {current_user.id}" if current_user.is_authenticated else "",
                        className="navbar-text text-light me-3"
                    )
                ],
                className="me-4"
            ),
            dbc.NavItem(
                dbc.Button(
                    "Logout", 
                    id="logout-button",
                    color="danger",
                    size="sm",
                    className="me-1"
                )
            ),
            # Location para manejar el logout
            dcc.Location(id="logout-trigger", refresh=True)
        ],
        navbar=True
    )
    
    # Crear la barra de navegación completa
    navbar = dbc.Navbar(
        [
            dbc.Container(
                [
                    html.A(
                        dbc.Row(
                            [
                                dbc.Col(html.Img(src="/assets/logo.png", height="30px", className="ms-3 me-3"), width="auto"),
                                dbc.Col(dbc.NavbarBrand("HK Premier League Dashboard", className="ms-2"), width="auto"),
                            ],
                            align="center",
                            className="g-0",
                        ),
                        href="/",
                        style={"textDecoration": "none"},
                    ),
                    dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
                    dbc.Collapse(
                        [dbc.Nav(nav_items, className="me-auto", navbar=True), nav_right],
                        id="navbar-collapse",
                        navbar=True,
                        is_open=False
                    ),
                ]
            ),
        ],
        color="primary",
        dark=True,
        className="mb-4",
    )
    
    return navbar