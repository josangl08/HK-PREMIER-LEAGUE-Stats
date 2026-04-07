# ABOUTME: Global application navbar with role-aware navigation and modern portal styling.
# ABOUTME: Renders contextual actions like insight inbox access and logout controls.

import base64
from pathlib import Path

import dash_bootstrap_components as dbc
from dash import html, dcc
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from models.db_models import Player, PlayerPhoto, User, UserPlayerLink
from utils.db_engine import Session


def _guess_mime_type(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def _get_user_avatar_src(user_id: str) -> str | None:
    """Resolve the user's primary player photo into a browser-safe src."""
    session = Session()
    try:
        stmt = (
            select(User)
            .options(
                joinedload(User.player_link)
                .joinedload(UserPlayerLink.player)
                .joinedload(Player.photos)
            )
            .where(User.id == user_id)
        )
        user = session.execute(stmt).unique().scalar_one_or_none()
        player = user.player_link.player if user and user.player_link and user.player_link.player else None
        if not player or not player.photos:
            return None

        primary_photo = next(
            (photo for photo in player.photos if getattr(photo, "is_primary", False)),
            player.photos[0],
        )

        if primary_photo.photo_data:
            return "data:image/jpeg;base64," + base64.b64encode(primary_photo.photo_data).decode("utf-8")

        for candidate_path in (primary_photo.cutout_path, primary_photo.original_path):
            if candidate_path and Path(candidate_path).is_file():
                mime_type = _guess_mime_type(candidate_path)
                image_bytes = Path(candidate_path).read_bytes()
                return f"data:{mime_type};base64," + base64.b64encode(image_bytes).decode("utf-8")

        return None
    except Exception:
        return None
    finally:
        session.close()


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
                [
                    html.I(className=f"bi {home_icon} portal-navbar__link-icon"),
                    html.Span(home_label),
                ],
                href=home_href,
                active=pathname == home_href,
                className="portal-navbar__link",
            )
        ),
    ]

    if user_role != 'agent':
        nav_items.append(
            dbc.NavItem(
                dbc.NavLink(
                    [
                        html.I(className="bi bi-bar-chart portal-navbar__link-icon"),
                        html.Span("Performance"),
                    ],
                    href="/performance",
                    active=pathname == "/performance",
                    className="portal-navbar__link",
                )
            )
        )

    # Portal Agente — visible for admin and agent roles
    if user_role in ('admin', 'agent'):
        nav_items.append(
            dbc.NavItem(
                dbc.NavLink(
                    [
                        html.I(className="bi bi-person-badge portal-navbar__link-icon"),
                        html.Span("Portal Agente"),
                    ],
                    href="/agent-portal",
                    active=pathname == "/agent-portal",
                    className="portal-navbar__link",
                )
            )
        )

    # AI Insights — visible for admin and player roles only (not agent)
    if user_role in ('admin', 'player'):
        nav_items.append(
            dbc.NavItem(
                dbc.NavLink(
                    [
                        html.I(className="bi bi-cpu portal-navbar__link-icon"),
                        html.Span("AI Insights"),
                    ],
                    href="/ai-insights",
                    active=pathname == "/ai-insights",
                    className="portal-navbar__link",
                )
            )
        )

    # Player Portal — visible for admin only (players already have it as home)
    if user_role == 'admin':
         nav_items.append(
            dbc.NavItem(
                dbc.NavLink(
                    [
                        html.I(className="bi bi-person-circle portal-navbar__link-icon"),
                        html.Span("Player Portal"),
                    ],
                    href="/player-portal",
                    active=pathname == "/player-portal",
                    className="portal-navbar__link",
                )
            )
        )

    avatar_src = _get_user_avatar_src(current_user.id) if is_auth else None
    user_avatar = (
        html.Img(src=avatar_src, alt=current_user.id if is_auth else "User", className="portal-navbar__user-avatar-image")
        if avatar_src
        else html.I(className="bi bi-person-circle")
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
                    className="portal-navbar__icon-btn position-relative" + ("" if pathname == "/player-portal" else " d-none"),
                ),
            ),
            dbc.NavItem(
                html.Div(
                    [
                        html.Span(user_avatar, className="portal-navbar__user-avatar"),
                        html.Span(current_user.id if is_auth else ""),
                    ],
                    className="portal-navbar__user-chip",
                ),
            ),
            dbc.NavItem(
                dbc.Button(
                    [
                        html.I(className="bi bi-box-arrow-right"),
                        "Logout",
                    ],
                    id="logout-button",
                    color="link",
                    size="sm",
                    className="portal-navbar__logout-btn",
                )
            ),
            # Location para manejar el logout
            dcc.Location(id="logout-trigger", refresh=True),
        ],
        className="portal-navbar__actions",
        navbar=True,
    )

    # Crear la barra de navegación completa
    navbar = dbc.Navbar(
        [
            dbc.Container(
                [
                    html.A(
                        html.Div(
                            [
                                html.Div(
                                    html.Img(
                                        src="/assets/logo.png",
                                        alt="HKPL Stats",
                                        className="portal-navbar__brand-logo",
                                    ),
                                    className="portal-navbar__brand-mark",
                                ),
                                html.Div(
                                    [
                                        html.Span("HKPL Stats", className="portal-navbar__brand-title"),
                                        html.Span("Player Intelligence", className="portal-navbar__brand-subtitle"),
                                    ],
                                    className="portal-navbar__brand-copy",
                                ),
                            ],
                            className="portal-navbar__brand",
                        ),
                        href=home_href,
                        className="portal-navbar__brand-link",
                    ),
                    dbc.NavbarToggler(id="navbar-toggler", n_clicks=0, className="portal-navbar__toggler"),
                    dbc.Collapse(
                        [
                            dbc.Nav(nav_items, className="portal-navbar__nav me-auto", navbar=True),
                            nav_right,
                        ],
                        id="navbar-collapse",
                        className="portal-navbar__collapse",
                        navbar=True,
                        is_open=False,
                    ),
                ],
                className="portal-navbar__container",
            ),
        ],
        dark=True,
        className="portal-navbar",
        expand="lg",
    )

    return navbar
