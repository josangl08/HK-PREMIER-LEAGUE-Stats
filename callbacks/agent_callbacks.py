# ABOUTME: Stage Decision Node callbacks for the Player Portal.
# ABOUTME: Injects deterministic stage actions from timeline context without relying on the legacy LangGraph chat agent.

import logging
from dash import Input, Output, State, html, no_update
import dash_bootstrap_components as dbc
from flask_login import current_user

logger = logging.getLogger(__name__)


def _decision_nodes_post_match(payload: dict) -> list:
    """Returns deterministic Decision Node buttons for post-match context."""
    player_stats = payload.get("player_stats") or {}
    perf = player_stats.get("performance_stats", {})
    xg = perf.get("xg", 0) or 0

    # dn-generate-card and dn-caption-ai removed: superseded by the Card Studio
    # (action node pill on each match card now opens the full Card Studio)
    buttons = []
    if float(xg) > 0.5:
        buttons.append(dbc.Button(
            [html.I(className="bi bi-search me-1"), "Deep Dive Stats"],
            id="dn-deep-dive",
            color="info", outline=True, size="sm", n_clicks=0,
        ))

    return [html.Div(buttons, className="d-flex flex-wrap gap-2 mt-2")]


def _decision_nodes_pre_match(payload: dict) -> list:
    """Returns deterministic Decision Node buttons for pre-match context."""
    return []


def _decision_nodes_career(payload: dict, user_role: str) -> list:
    """Returns career Decision Node buttons. AI scouting reserved for agent role (future)."""
    buttons = []

    if user_role == "agent":
        buttons.append(dbc.Button(
            [html.I(className="bi bi-file-earmark-pdf me-1"), "Exportar Dossier PDF"],
            id="dn-dossier-pdf",
            color="danger", outline=True, size="sm", n_clicks=0,
        ))

    return [html.Div(buttons, className="d-flex flex-wrap gap-2")]


def register_agent_callbacks(app):
    """
    Registers Dash callbacks for stage decision nodes.
    """
    
    # ------------------------------------------------------------------ #
    # 7.1–7.4  Decision Nodes: context-aware action buttons in Stage      #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("stage-decision-nodes", "children"),
        Output("stage-context-snapshot", "data"),
        Input("timeline-context-store", "data"),
        prevent_initial_call=True,
    )
    def update_decision_nodes(context):
        """Injects Decision Node buttons into the Stage based on active timeline context."""
        if not context:
            return no_update, no_update

        user_role = getattr(current_user, "role", "player") if current_user else "player"
        m_type = context.get("type")
        payload = context.get("payload", {})

        try:
            if m_type == "post-match":
                return _decision_nodes_post_match(payload), context
            elif m_type == "pre-match":
                return _decision_nodes_pre_match(payload), context
            elif m_type == "career":
                return _decision_nodes_career(payload, user_role), context
        except Exception as exc:
            logger.error(f"update_decision_nodes error: {exc}")
            return dbc.Alert("Error al cargar las acciones.", color="danger", className="small"), no_update

        return no_update, no_update
