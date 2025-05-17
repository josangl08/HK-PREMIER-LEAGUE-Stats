import dash_bootstrap_components as dbc
from dash import html

# Crea el menu de navegacion
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
    
    # Agregar enlace de logout
    nav_right = dbc.Nav(
        [
            dbc.NavItem(
                dbc.NavLink(
                    "Log Out", 
                    href="/logout"
                )
            ),
        ],
        className="ml-auto",
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
                                dbc.Col(html.Img(src="/assets/logo.png", height="30px", className="ml-2"), width="auto"),
                                dbc.Col(dbc.NavbarBrand("Sports Dashboard", className="ml-2"), width="auto"),
                            ],
                            align="center",
                            className="g-0",
                        ),
                        href="/",
                        style={"textDecoration": "none"},
                    ),
                    dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
                    dbc.Collapse(
                        [dbc.Nav(nav_items, className="mr-auto", navbar=True), nav_right],
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