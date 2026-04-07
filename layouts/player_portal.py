# ABOUTME: Player Portal layout implementing Phase 3 interactive global header and scroll-sync.
# ABOUTME: Full-width title header, year nav inside timeline column, sliding panels on mobile.

from dash import html, dcc
import dash_bootstrap_components as dbc
from utils.skeleton_components import (
    create_skeleton_timeline,
    create_skeleton_stage,
    create_skeleton_year_navigator,
)


def _build_sync_status_banner() -> html.Div:
    """
    Subtle inline banner shown while the player's Transfermarkt data is being resolved.
    Hidden by default; shown/updated by the sync-poll callback.
    """
    return html.Div(
        id="sync-status-banner",
        style={"display": "none"},
        className="sync-status-banner",
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
                        delay_show=250,
                        color="var(--accent-cyan)",
                        parent_className="timeline-loading-parent",
                        parent_style={"width": "100%", "display": "block"},
                        style={"width": "100%", "display": "block"},
                        overlay_style={
                            "visibility": "visible",
                            "filter": "none",
                            "background": "transparent",
                            "display": "flex",
                            "alignItems": "flex-start",
                            "justifyContent": "flex-end",
                            "padding": "6px 8px",
                        },
                        className="timeline-loading-frame",
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
    """Stage column: back button (mobile only) + dynamic stage content + overlay containers."""
    return html.Div(
        className="stage-column px-3 pb-3",
        style={"position": "relative"},
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
                type="dot",
                delay_show=250,
                color="var(--accent-cyan)",
                parent_className="stage-loading-parent",
                parent_style={"width": "100%", "display": "block"},
                style={"width": "100%", "display": "block"},
                overlay_style={
                    "visibility": "visible",
                    "filter": "none",
                    "background": "transparent",
                    "display": "flex",
                    "alignItems": "flex-start",
                    "justifyContent": "flex-end",
                    "padding": "8px 10px",
                },
                className="stage-loading-frame mb-3",
                children=html.Div(
                    id="stage-shell",
                    className="glass-card glass-career stage-shell",
                    children=html.Div(
                        id="stage-content",
                        className="stage-frame",
                        children=[create_skeleton_stage()],
                    ),
                ),
            ),
            html.Div(id="stage-decision-nodes"),
            # ── T1 overlay: initially hidden, shown by portal-load callback ──────
            html.Div(id="ai-overlay-t1-container", style={"display": "none"}),
            # ── T2 overlays: absolute-positioned cards over stage column ─────────
            html.Div(id="ai-overlay-t2-container"),
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
            dcc.Store(id="prematch-h2h-scroll-dummy"),
            dcc.Store(id="portal-panel-state", data={"panel": "timeline"}),
            dcc.Store(id="timeline-expand-store", data=[]),
            dcc.Store(id="active-year-store", data=None),
            dcc.Store(id="card-expand-store", data={}),
            dcc.Store(id="timeline-pagination-store", storage_type="memory"),
            dcc.Store(id="stage-lucide-refresh-dummy"),
            dcc.Store(id="card-editor-state", storage_type="memory"),
            # Stores the player photo album (original paths, bgrm paths, selections)
            dcc.Store(id="player-photos-store", storage_type="local"),
            # Triggers post-generation gallery refresh or download
            dcc.Store(id="card-generation-trigger"),
            # Career Intelligence overlay stores
            dcc.Store(id="insight-session-state", storage_type="local"),
            dcc.Store(id="t2-overlay-queue", storage_type="session"),
            dcc.Store(id="t1-signal-store", storage_type="session"),
            # Polls sync status for newly registered players (stops after data is ready)
            dcc.Interval(id="sync-poll-interval", interval=8000, n_intervals=0, max_intervals=30, disabled=True),

            # Full-width sticky title header (outside Container)
            _build_global_header(),
            _build_sync_status_banner(),

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
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle(id="season-asset-modal-title"), close_button=True),
                    dbc.ModalBody(
                        html.Div(
                            html.Img(
                                id="season-asset-modal-image",
                                style={
                                    "maxWidth": "100%",
                                    "maxHeight": "70vh",
                                    "objectFit": "contain",
                                    "display": "block",
                                    "margin": "0 auto",
                                },
                            ),
                            className="text-center",
                        )
                    ),
                ],
                id="season-asset-modal",
                is_open=False,
                centered=True,
                size="lg",
            ),
        ],
    )
