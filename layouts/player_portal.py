# ABOUTME: Player Portal layout implementing Phase 3 interactive global header and scroll-sync.
# ABOUTME: Full-width title header, year nav inside timeline column, sliding panels on mobile.

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


def _build_global_header() -> html.Div:
    """
    Full-width sticky header. Only shows the portal title — no year nav.
    Year navigator has been moved into the timeline column.
    """
    return html.Div(
        className="portal-global-header d-flex align-items-center",
        children=[
            html.I(
                **{"data-lucide": "user-circle", "className": "lucide-header-icon me-2"},
                style={"color": "var(--accent-cyan)"},
            ),
            html.H5("Player Portal", className="mb-0 fw-bold"),
            html.Small(
                "Interactive Career Timeline",
                className="text-muted ms-3 d-none d-md-block",
            ),
        ],
    )


def _build_timeline_column() -> html.Div:
    """Timeline column: sticky year navigator at top + scrollable milestone list."""
    return html.Div(
        className="timeline-column pb-3",
        children=[
            # Year navigator — sticky at top of timeline column, above events
            html.Div(
                create_unified_year_navigator(),
                className="timeline-year-nav px-3",
            ),
            # Scrollable milestone list
            html.Div(
                className="milestone-list-container px-3",
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
            dcc.Store(id="stage-context-snapshot"),
            dcc.Download(id="stage-action-download"),
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
            # Gallery close button — always in DOM (hidden) to avoid Dash 4 Input validation error
            html.Button(
                [html.I(className="bi bi-x-lg me-1"), "Cerrar galería"],
                id="gallery-close-btn",
                style={"display": "none"},
                className="btn btn-sm btn-outline-secondary mb-2",
                n_clicks=0,
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
    Global header is OUTSIDE the container to span the full page width.
    """
    return html.Div(
        id="player-portal-container",
        children=[
            # Stores (Phase 2 & 3)
            dcc.Store(id="milestones-data-store"),
            dcc.Store(id="selected-year-store", data=None),
            dcc.Store(id="year-nav-scroll-dummy"),
            dcc.Store(id="year-timeline-scroll-dummy"),
            dcc.Store(id="portal-panel-state", data={"panel": "timeline"}),
            dcc.Store(id="timeline-expand-store", data=[]),
            dcc.Store(id="active-year-store", data=None),

            # Full-width sticky title header (outside Container)
            _build_global_header(),

            # Portal Viewport — no horizontal padding on container
            dbc.Container(
                html.Div(
                    id="portal-viewport",
                    className="portal-viewport",
                    children=[
                        _build_timeline_column(),
                        _build_stage_column(),
                    ],
                ),
                fluid=True,
                className="py-0 px-0",
            ),
        ],
    )
