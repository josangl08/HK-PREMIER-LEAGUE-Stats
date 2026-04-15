# ABOUTME: Player Portal layout implementing Phase 3 interactive global header and scroll-sync.
# ABOUTME: Features sliding panels, scroll-synced timeline, and non-disruptive card-viewer-modal for generated assets.

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


def _build_timeline_column() -> html.Div:
    """Timeline column: sticky year navigator at top + scrollable milestone list."""
    return html.Div(
        className="timeline-column pb-0",
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
                    html.Div(
                        id="timeline-milestones",
                        children=[create_skeleton_timeline(8)],
                    ),
                ],
            ),
        ],
    )


def _build_stage_column() -> html.Div:
    """Stage column: back button (mobile only) + dynamic stage content + overlay containers."""
    return html.Div(
        className="stage-column px-3 pb-0",
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
            html.Div(
                id="stage-shell",
                className="glass-card stage-shell stage-shell--career",
                children=html.Div(
                    id="stage-content",
                    className="stage-frame",
                    children=[create_skeleton_stage()],
                ),
            ),
            html.Div(id="stage-decision-nodes"),
            html.Div(id="stage-overlay-critical-container", style={"display": "none"}),
            html.Div(id="stage-overlay-contextual-container"),
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
            dcc.Store(id="portal-data-store"),  # Pre-fetched dashboard data (ETL phase 2)
            dcc.Store(id="portal-render-complete-store"),  # Signals phase 2 render done → triggers phase 3 AI
            dcc.Store(id="selected-year-store", data=None),
            dcc.Store(id="year-nav-scroll-dummy"),
            dcc.Store(id="year-timeline-scroll-dummy"),
            dcc.Store(id="prematch-h2h-scroll-dummy"),
            dcc.Store(id="portal-panel-state", data={"panel": "timeline"}),
            dcc.Store(id="timeline-expand-store", data=[]),
            dcc.Store(id="timeline-expand-visual-sync-dummy"),
            dcc.Store(id="timeline-season-observer-dummy"),
            dcc.Store(id="card-expand-store", data={}),
            dcc.Store(id="timeline-pagination-store", storage_type="memory"),
            dcc.Store(id="stage-lucide-refresh-dummy"),
            dcc.Store(id="portal-overlay-store", storage_type="memory", data={"type": "none"}),
            dcc.Store(id="card-editor-state", storage_type="memory"),
            dcc.Store(id="prematch-stage-analysis-store", storage_type="memory"),
            dcc.Store(id="postmatch-stage-analysis-store", storage_type="memory"),
            dcc.Store(id="career-stage-analysis-store", storage_type="memory"),
            dcc.Store(id="season-stage-analysis-store", storage_type="memory"),
            # Stores the player photo album — session only (never share between players)
            dcc.Store(id="player-photos-store", storage_type="session"),
            # Triggers post-generation gallery refresh or download
            dcc.Store(id="card-generation-trigger"),
            dcc.Store(id="career-dashboard-brief-store", storage_type="memory"),
            dcc.Store(id="stage-background-dispatch-store", storage_type="memory"),
            # Keys (player_name + season) for lazy UMAP modal rendering
            dcc.Store(id="season-umap-context-store", storage_type="memory"),
            # Loading color system: pre-flight store for stage dot type (ui/data/ai)
            dcc.Store(id="stage-loading-type-sync-dummy"),
            dcc.Store(id="insight-session-state", storage_type="local"),
            dcc.Store(id="stage-overlay-queue-store", storage_type="session"),
            dcc.Store(id="stage-overlay-primary-store", storage_type="session"),
            # Polls sync status for newly registered players (stops after data is ready)
            dcc.Interval(id="sync-poll-interval", interval=8000, n_intervals=0, max_intervals=30, disabled=True),
            # AI Card Studio polling interval moved to card_editor.py for portability
            _build_sync_status_banner(),

            # ── Persistent UMAP modal ────────────────────────────────────────
            # Lives OUTSIDE stage-content so it is never recreated when stage
            # callbacks rewrite stage-content.children — the graph figure
            # is lazily populated by render_season_umap_on_modal_open.
            dbc.Modal(
                [
                    dbc.ModalHeader(
                        dbc.ModalTitle("Full Profile Map", id="season-umap-modal-title"),
                        close_button=True,
                    ),
                    dbc.ModalBody(
                        [
                            html.Div(id="season-umap-modal-explainer", className="mb-3"),
                            dcc.Loading(
                                dcc.Graph(
                                    id="season-umap-graph",
                                    # Transparent dark initial state so there is no white
                                    # flash while render_season_umap_on_modal_open runs.
                                    figure={
                                        "layout": {
                                            "paper_bgcolor": "rgba(0,0,0,0)",
                                            "plot_bgcolor": "rgba(0,0,0,0)",
                                            "height": 480,
                                            "xaxis": {"visible": False},
                                            "yaxis": {"visible": False},
                                        }
                                    },
                                    config={"displayModeBar": False, "responsive": True},
                                    style={"height": "500px", "minHeight": "500px"},
                                ),
                                type="circle",
                                color="#f5b942",
                                style={"minHeight": "500px"},
                            ),
                        ],
                        className="career-evidence-modal-body",
                    ),
                    dbc.ModalFooter(
                        dbc.Button("Close", id="season-profile-map-close", color="secondary", n_clicks=0)
                    ),
                ],
                id="season-profile-map-modal",
                is_open=False,
                centered=True,
                size="xl",
                scrollable=True,
                className="career-evidence-modal season-umap-modal",
                fade=False,
            ),

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
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle(id="career-evidence-modal-title"), close_button=True),
                    dbc.ModalBody(id="career-evidence-modal-body", className="career-evidence-modal-body"),
                    dbc.ModalFooter(
                        dbc.Button("Close", id="career-evidence-modal-close", color="secondary", n_clicks=0)
                    ),
                ],
                id="career-evidence-modal",
                is_open=False,
                centered=True,
                size="xl",
                scrollable=True,
                className="career-evidence-modal",
                fade=False,
            ),
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle(id="career-kpi-trend-modal-title"), close_button=True),
                    dbc.ModalBody(id="career-kpi-trend-modal-body", className="career-evidence-modal-body"),
                ],
                id="career-kpi-trend-modal",
                is_open=False,
                centered=True,
                size="xl",
                scrollable=True,
                className="career-evidence-modal",
                fade=False,
            ),
            # Insight Inbox Offcanvas (Notification Center)
            dbc.Offcanvas(
                id="insight-inbox-offcanvas",
                placement="end",
                title="Insight History",
                is_open=False,
                children=[
                    html.Div(id="insight-inbox-body"),
                ],
            ),
            # CARD VIEWER MODAL (NON-DISRUPTIVE)
            dbc.Modal(
                [
                    dbc.ModalHeader(
                        html.Div([
                            html.I(**{"data-lucide": "image", "className": "me-2"}),
                            "Matchday Card"
                        ], className="d-flex align-items-center"),
                        close_button=True, 
                        className="border-0 text-white bg-transparent pt-4 px-4"
                    ),
                    dbc.ModalBody(
                        id="card-viewer-modal-content",
                        className="d-flex align-items-center justify-content-center pb-5 px-4 overflow-auto"
                    ),
                ],
                id="card-viewer-modal",
                size="xl",
                centered=True,
                scrollable=True,
                is_open=False,
                # Glass effect configuration - fixed argument name
                content_class_name="glass-card border-0 shadow-none",
                backdrop_class_name="modal-backdrop-blur"
            ),
        ],
    )
