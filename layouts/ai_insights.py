# ABOUTME: Dashboard layout for AI insights (clustering, prediction, similarity).
# ABOUTME: Implements role-based access control and responsive grid components.

# Standard Library
from typing import Optional

# Third-party
import dash_bootstrap_components as dbc
from dash import dcc, html

# Project
from utils.chart_helpers import HKFATheme


def _card(title: str, icon: str, children, card_id: Optional[str] = None) -> dbc.Card:
    """Utility: styled HKFA card with title and icon."""
    kwargs = {"id": card_id} if card_id else {}
    return dbc.Card(
        [
            dbc.CardHeader(
                [html.I(className=f"bi {icon} me-2"), html.Strong(title)],
                style={
                    "backgroundColor": HKFATheme.BG_TERTIARY,
                    "color": HKFATheme.TEXT_PRIMARY,
                    "borderBottom": f"2px solid {HKFATheme.ACCENT_RED}",
                },
            ),
            dbc.CardBody(children, className="p-3"),
        ],
        className="mb-4 shadow-sm",
        style={
            "backgroundColor": HKFATheme.BG_TERTIARY,
            "border": f"1px solid {HKFATheme.BORDER_COLOR}",
        },
        **kwargs,
    )


def _clustering_panel() -> dbc.Card:
    return _card(
        "Player Archetypes — Clustering",
        "bi-diagram-3",
        [
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Label("Feature Lens", className="text-muted small"),
                            dcc.Dropdown(
                                id="ai-clustering-lens-dropdown",
                                options=[
                                    {"label": "Overall", "value": "overall"},
                                    {"label": "Physical", "value": "physical"},
                                    {"label": "Creative", "value": "creative"},
                                    {"label": "Defensive", "value": "defensive"},
                                ],
                                value="overall",
                                clearable=False,
                                className="mb-2",
                            ),
                        ],
                        width=12,
                        md=6,
                    ),
                    dbc.Col(
                        [
                            dbc.Label("Clusters (k)", className="text-muted small"),
                            dcc.Dropdown(
                                id="ai-clustering-k-dropdown",
                                options=[{"label": str(k), "value": k} for k in range(3, 9)],
                                value=5,
                                clearable=False,
                                className="mb-2",
                            ),
                        ],
                        width=12,
                        md=3,
                    ),
                    dbc.Col(
                        dbc.Button(
                            [html.I(className="bi bi-play-circle me-1"), "Run"],
                            id="ai-clustering-btn",
                            color="danger",
                            size="sm",
                            className="mt-4 w-100",
                        ),
                        width=12,
                        md=3,
                    ),
                ],
                className="mb-2",
            ),
            dcc.Loading(
                dcc.Graph(
                    id="ai-clustering-umap-graph",
                    config={"displayModeBar": False},
                    style={"minHeight": "420px"},
                ),
                type="circle",
                color=HKFATheme.ACCENT_RED,
            ),
            html.Div(id="ai-clustering-status", className="text-muted small mt-2"),
        ],
    )


def _predictor_panel() -> dbc.Card:
    return _card(
        "Performance Predictor",
        "bi-graph-up-arrow",
        [
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Label("Player", className="text-muted small"),
                            dcc.Dropdown(
                                id="ai-predictor-player-dropdown",
                                options=[],
                                placeholder="Select a player…",
                                className="mb-2",
                            ),
                        ],
                        width=12,
                        md=4,
                    ),
                    dbc.Col(
                        [
                            dbc.Label("Target Metric", className="text-muted small"),
                            dcc.Dropdown(
                                id="ai-predictor-metric-dropdown",
                                options=[
                                    {"label": "Goals", "value": "Goals"},
                                    {"label": "Assists", "value": "Assists"},
                                    {"label": "xG", "value": "xG"},
                                ],
                                value="Goals",
                                clearable=False,
                                className="mb-2",
                            ),
                        ],
                        width=12,
                        md=3,
                    ),
                    dbc.Col(
                        [
                            dbc.Label("Model", className="text-muted small"),
                            dcc.Dropdown(
                                id="ai-predictor-model-dropdown",
                                options=[
                                    {"label": "TabPFN", "value": "tabpfn"},
                                    {"label": "XGBoost", "value": "xgboost"},
                                ],
                                value="xgboost",
                                clearable=False,
                                className="mb-2",
                            ),
                        ],
                        width=12,
                        md=3,
                    ),
                    dbc.Col(
                        dbc.Button(
                            [html.I(className="bi bi-lightning-charge me-1"), "Predict"],
                            id="ai-predictor-btn",
                            color="danger",
                            size="sm",
                            className="mt-4 w-100",
                        ),
                        width=12,
                        md=2,
                    ),
                ],
                className="mb-2",
            ),
            dcc.Loading(
                [
                    html.Div(id="ai-predictor-result", className="mb-3"),
                    dcc.Graph(
                        id="ai-predictor-shap-graph",
                        config={"displayModeBar": False},
                        style={"minHeight": "300px"},
                    ),
                ],
                type="circle",
                color=HKFATheme.ACCENT_RED,
            ),
        ],
    )


def _similarity_panel() -> dbc.Card:
    return _card(
        "Similar Players",
        "bi-people",
        [
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Label("Player", className="text-muted small"),
                            dcc.Dropdown(
                                id="ai-similarity-player-dropdown",
                                options=[],
                                placeholder="Select a player…",
                                className="mb-2",
                            ),
                        ],
                        width=12,
                        md=5,
                    ),
                    dbc.Col(
                        [
                            dbc.Label("Season filter (optional)", className="text-muted small"),
                            dcc.Dropdown(
                                id="ai-similarity-season-dropdown",
                                options=[],
                                placeholder="All seasons",
                                multi=True,
                                className="mb-2",
                            ),
                        ],
                        width=12,
                        md=5,
                    ),
                    dbc.Col(
                        dbc.Button(
                            [html.I(className="bi bi-search me-1"), "Find"],
                            id="ai-similarity-btn",
                            color="danger",
                            size="sm",
                            className="mt-4 w-100",
                        ),
                        width=12,
                        md=2,
                    ),
                ],
                className="mb-2",
            ),
            dcc.Loading(
                html.Div(id="ai-similarity-result"),
                type="circle",
                color=HKFATheme.ACCENT_RED,
            ),
            # Hidden store for click-through navigation
            dcc.Store(id="ai-similarity-nav-store"),
        ],
    )


def create_ai_insights_layout(role: Optional[str] = None) -> html.Div:
    """
    Creates the AI Insights dashboard layout with role-gated panels.

    Panels by role:
      - admin : Clustering + Predictor + Similarity
      - agent : Clustering + Similarity
      - player: Predictor (own data) + Similarity

    Args:
        role: Authenticated user role string ('admin', 'agent', 'player').

    Returns:
        Dash layout Div.
    """
    role = (role or "player").lower()
    show_clustering = role in ("admin", "agent")
    show_predictor = role in ("admin", "player")
    show_similarity = True  # all roles

    panels = []

    # ── Row 1: Clustering (left) + Predictor (right) for admin ──────────────
    top_row_cols = []
    if show_clustering:
        top_row_cols.append(
            dbc.Col(_clustering_panel(), width=12, lg=6 if show_predictor else 12)
        )
    if show_predictor:
        top_row_cols.append(
            dbc.Col(_predictor_panel(), width=12, lg=6 if show_clustering else 12)
        )

    if top_row_cols:
        panels.append(dbc.Row(top_row_cols, className="mb-2"))

    # ── Row 2: Similarity (full width) ──────────────────────────────────────
    if show_similarity:
        panels.append(dbc.Row(dbc.Col(_similarity_panel(), width=12)))

    return html.Div(
        [
            # Page header
            dbc.Row(
                dbc.Col(
                    [
                        html.H2(
                            [html.I(className="bi bi-cpu me-2"), "AI Intelligence Insights"],
                            className="mb-1",
                            style={"color": HKFATheme.TEXT_PRIMARY},
                        ),
                        html.P(
                            "Machine learning-powered player analysis.",
                            className="text-muted mb-4",
                        ),
                    ],
                    width=12,
                )
            ),
            # Panels
            *panels,
            # Populates player/season dropdowns on page load
            dcc.Store(id="ai-insights-role-store", data=role),
        ],
        className="container-fluid py-4",
        style={"backgroundColor": HKFATheme.BG_PRIMARY, "minHeight": "100vh"},
    )
