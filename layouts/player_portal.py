# ABOUTME: Player Portal layout implementing the Phase 2 SPA navigation architecture.
# ABOUTME: Renders a .portal-viewport with sliding panels (mobile) and split-screen grid (desktop).

from dash import html, dcc
import dash_bootstrap_components as dbc
from utils.skeleton_components import (
    create_skeleton_timeline,
    create_skeleton_stage,
    create_skeleton_year_navigator,
)


def create_unified_year_navigator() -> html.Div:
    """
    Horizontally scrollable Year Navigator container.
    Content (pills) is populated by update_year_navigator callback.
    """
    return html.Div(
        id="year-navigator-pills",
        children=[create_skeleton_year_navigator()],
    )


def _build_timeline_column() -> html.Div:
    """Timeline column: sticky header (title + year nav) + scrollable milestone list."""
    return html.Div(
        className="timeline-column px-3 pb-3",
        children=[
            html.Div(
                className="sticky-sidebar-header",
                children=[
                    html.Div(
                        [
                            html.I(className="bi bi-clock-history me-2"),
                            html.Span("Timeline", className="fw-bold"),
                        ],
                        className="mb-2",
                        style={"color": "var(--bs-body-color)"},
                    ),
                    create_unified_year_navigator(),
                ],
            ),
            html.Div(
                className="milestone-list-container",
                children=[
                    dcc.Loading(
                        id="timeline-loading",
                        type="dot",
                        children=html.Div(
                            id="timeline-milestones",
                            children=[create_skeleton_timeline(8)],
                        ),
                    ),
                ],
            ),
        ],
    )


def _build_stage_column() -> html.Div:
    """Stage column: back button (mobile only) + dynamic stage content."""
    return html.Div(
        className="stage-column px-3 pb-3",
        children=[
            dcc.Store(id="timeline-context-store"),
            # Back button — visible on mobile when stage panel is active
            html.Div(
                id="portal-back-button",
                style={"display": "none"},
                children=[
                    dbc.Button(
                        [html.I(className="bi bi-arrow-left me-2"), "Volver"],
                        id="portal-back-btn",
                        color="link",
                        size="sm",
                        className="mb-2 ps-0",
                        n_clicks=0,
                    ),
                ],
            ),
            dcc.Loading(
                id="stage-loading",
                type="circle",
                color="var(--bs-primary)",
                children=html.Div(
                    id="stage-content",
                    children=[create_skeleton_stage()],
                ),
                className="mb-3",
            ),
            html.Div(id="stage-decision-nodes"),
        ],
    )


def create_player_portal_layout(user_role: str = "player") -> html.Div:
    """
    Returns the full Player Portal layout.
    user_role is passed for server-side conditional rendering (e.g. Dossier button).
    """
    return html.Div(
        id="player-portal-container",
        children=[
            # Stores (static — populated by callbacks)
            dcc.Store(id="milestones-data-store"),
            dcc.Store(id="selected-year-store", data=None),
            dcc.Store(id="year-nav-scroll-dummy"),
            dcc.Store(id="year-timeline-scroll-dummy"),
            dcc.Store(id="portal-panel-state", data={"panel": "timeline"}),

            dbc.Container(
                [
                    # Page header
                    dbc.Row([
                        dbc.Col([
                            html.H4(
                                [
                                    html.I(className="bi bi-person-badge me-2"),
                                    "Player Portal",
                                ],
                                className="mb-0",
                            ),
                            html.Small("Career Stage", className="text-muted"),
                        ], className="mb-4"),
                    ]),

                    # Portal Viewport — sliding on mobile, grid on desktop
                    html.Div(
                        id="portal-viewport",
                        className="portal-viewport",
                        children=[
                            _build_timeline_column(),
                            _build_stage_column(),
                        ],
                    ),
                ],
                fluid=True,
                className="py-3",
            ),
        ],
    )
