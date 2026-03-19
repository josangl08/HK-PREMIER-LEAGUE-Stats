# ABOUTME: Player Portal layout implementing the 'Career Stage' architecture.
# ABOUTME: Timeline (sticky sidebar) drives a dynamic Stage that renders post-match, pre-match, or career-insights scenarios.

from dash import html, dcc
import dash_bootstrap_components as dbc


def _build_timeline_component() -> html.Div:
    """Sticky sidebar timeline — desktop (d-none d-md-flex)."""
    return html.Div(
        id="player-timeline",
        children=[
            html.Div([
                html.I(className="bi bi-clock-history me-2"),
                html.Span("Timeline", className="fw-bold"),
            ], className="mb-3", style={"color": "var(--bs-body-color)"}),
            html.Div(id="timeline-milestones", children=[
                dbc.Spinner(size="sm", color="primary"),
            ]),
        ],
        style={
            "position": "sticky",
            "top": "1rem",
            "maxHeight": "calc(100vh - 80px)",
            "overflowY": "auto",
            "paddingRight": "8px",
        },
    )


def _build_mobile_carousel() -> html.Div:
    """Horizontal pill carousel — mobile only (d-flex d-md-none)."""
    return html.Div(
        id="player-timeline-mobile",
        children=[
            html.Div(id="timeline-pills-mobile", children=[
                dbc.Spinner(size="sm", color="primary"),
            ], className="d-flex gap-2 overflow-auto pb-2"),
        ],
        className="mb-3 d-flex d-md-none",
    )


def _build_stage_component() -> html.Div:
    """Dynamic Stage area with loading wrapper and decision nodes slot."""
    return html.Div([
        dcc.Store(id="timeline-context-store"),
        dcc.Loading(
            id="stage-loading",
            type="circle",
            color="var(--bs-primary)",
            children=html.Div(
                id="stage-content",
                children=[
                    # Default welcome state
                    dbc.Card([
                        dbc.CardBody([
                            html.Div([
                                html.I(className="bi bi-arrow-left-circle fs-1 mb-3",
                                       style={"opacity": "0.4"}),
                                html.H5("Selecciona un hito del Timeline",
                                        className="text-muted"),
                                html.P("Haz clic en un partido, próximo partido o temporada para ver el análisis correspondiente.",
                                       className="text-muted small"),
                            ], className="text-center py-4")
                        ])
                    ], className="border-0 shadow-sm")
                ],
            ),
            className="mb-3",
        ),
        html.Div(id="stage-decision-nodes"),
    ])


def create_player_portal_layout(user_role: str = "player") -> html.Div:
    """
    Returns the full Player Portal layout.
    user_role is passed for server-side conditional rendering (e.g. Dossier button).
    """
    return html.Div([
        dbc.Container([
            # Page header
            dbc.Row([
                dbc.Col([
                    html.H4([
                        html.I(className="bi bi-person-badge me-2"),
                        "Portal del Jugador",
                    ], className="mb-0"),
                    html.Small("Career Stage", className="text-muted"),
                ], className="mb-4"),
            ]),

            # Mobile pill carousel (hidden on desktop)
            _build_mobile_carousel(),

            # Main layout: Timeline (desktop) + Stage
            dbc.Row([
                # Desktop sidebar timeline (hidden on mobile)
                dbc.Col(
                    _build_timeline_component(),
                    width=3,
                    className="d-none d-md-flex flex-column",
                ),
                # Stage (full width on mobile, 9 cols on desktop)
                dbc.Col(
                    _build_stage_component(),
                    width=12,
                    md=9,
                ),
            ]),
        ], fluid=True, className="py-3"),
    ])
