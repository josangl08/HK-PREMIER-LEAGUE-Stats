# ABOUTME: Agent interaction callbacks for the HK Premier League.
# ABOUTME: Manages NL query submission, result rendering, and Stage Decision Nodes injection.

"""
Agent Callbacks - Controller for the LangGraph Agent UI.
Handles query submission, agent execution, and UI feedback.
"""

import logging
import threading
from dash import Input, Output, State, dcc, html, no_update
import dash_bootstrap_components as dbc
from flask_login import current_user

from ai_models.agent import create_agent, run_agent

logger = logging.getLogger(__name__)

_AGENT_TIMEOUT_SECONDS = 15


def _run_agent_with_timeout(query: str, flow: str) -> dict:
    """Runs the LangGraph agent in a thread with a hard timeout."""
    result_holder = {}

    def _target():
        try:
            agent = create_agent(flow=flow)
            result_holder["result"] = run_agent(agent, query)
        except Exception as exc:
            result_holder["error"] = str(exc)

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(timeout=_AGENT_TIMEOUT_SECONDS)

    if t.is_alive():
        return {"timeout": True}
    if "error" in result_holder:
        return {"error": result_holder["error"]}
    return result_holder.get("result", {})


def _decision_nodes_post_match(payload: dict) -> list:
    """Returns deterministic Decision Node buttons for post-match context."""
    player_stats = payload.get("player_stats") or {}
    perf = player_stats.get("performance_stats", {})
    xg = perf.get("xg", 0) or 0

    buttons = [
        dbc.Button(
            [html.I(className="bi bi-image me-1"), "Generar Card"],
            id="dn-generate-card",
            color="primary", outline=True, size="sm", className="me-2", n_clicks=0,
        ),
        dbc.Button(
            [html.I(className="bi bi-pencil me-1"), "Caption AI"],
            id="dn-caption-ai",
            color="secondary", outline=True, size="sm", className="me-2", n_clicks=0,
        ),
    ]
    if float(xg) > 0.5:
        buttons.append(dbc.Button(
            [html.I(className="bi bi-search me-1"), "Deep Dive Stats"],
            id="dn-deep-dive",
            color="info", outline=True, size="sm", n_clicks=0,
        ))

    return [html.Div(buttons, className="d-flex flex-wrap gap-2 mt-2")]


def _decision_nodes_pre_match(payload: dict) -> list:
    """Returns deterministic Decision Node buttons for pre-match context."""
    return [html.Div([
        dbc.Button(
            [html.I(className="bi bi-image me-1"), "Card de Previa"],
            id="dn-previa-card",
            color="primary", outline=True, size="sm", className="me-2", n_clicks=0,
        ),
        dbc.Button(
            [html.I(className="bi bi-calendar-check me-1"), "Añadir a iCal"],
            id="dn-ical",
            color="secondary", outline=True, size="sm", n_clicks=0,
        ),
    ], className="d-flex flex-wrap gap-2 mt-2")]


def _decision_nodes_career(payload: dict, user_role: str) -> list:
    """Invokes LangGraph for scouting advice + renders career Decision Nodes."""
    player_name = payload.get("player_name", "el jugador")
    season = payload.get("season", "")

    # Invoke agent with timeout
    query = (
        f"Dame un consejo de scouting conciso para {player_name} "
        f"basado en su rendimiento en la temporada {season}."
    )
    agent_result = _run_agent_with_timeout(query, flow="player_analysis")

    if agent_result.get("timeout"):
        scouting_text = "Análisis de scouting no disponible en este momento. Consulta las estadísticas manualmente."
    elif agent_result.get("error"):
        scouting_text = "No se pudo obtener el análisis de IA."
    else:
        scouting_text = agent_result.get("output", "Sin análisis disponible.")

    scouting_card = dbc.Card([
        dbc.CardHeader([
            html.I(className="bi bi-robot me-2"),
            html.Span("Scouting AI", className="fw-semibold"),
        ], className="border-0 py-2"),
        dbc.CardBody(html.P(scouting_text, className="small mb-0")),
    ], className="border-0 shadow-sm mb-3", color="dark", outline=True)

    buttons = []

    if user_role == "agent":
        buttons.append(dbc.Button(
            [html.I(className="bi bi-file-earmark-pdf me-1"), "Exportar Dossier PDF"],
            id="dn-dossier-pdf",
            color="danger", outline=True, size="sm", className="ms-2", n_clicks=0,
        ))

    return [
        scouting_card,
        html.Div(buttons, className="d-flex flex-wrap gap-2"),
    ]


def register_agent_callbacks(app):
    """
    Registers Dash callbacks for the agent interaction panel.
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

    # ------------------------------------------------------------------ #
    # Original agent query callback                                        #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("agent-output-display", "children"),
        Input("agent-submit-btn", "n_clicks"),
        State("agent-query-input", "value"),
        State("agent-flow-selector", "value"),
        prevent_initial_call=True
    )
    def handle_agent_query(n_clicks, query, flow):
        if not n_clicks or not query:
            return no_update
            
        try:
            # 1. Initialize the agent (cached in ai_models.agent)
            agent = create_agent(flow=flow)
            
            # 2. Run the agentic workflow
            result = run_agent(agent, query)
            
            # 3. Handle errors
            if result.get("error"):
                return dbc.Alert([
                    html.H5("Execution Error"),
                    html.P(result["error"])
                ], color="danger", className="mt-3")
            
            # 4. Format the reasoning steps (optional/expandable)
            steps_display = []
            if result.get("steps"):
                steps_display = [
                    html.Details([
                        html.Summary(f"Reasoning Steps ({len(result['steps'])} tool calls)", className="text-muted small"),
                        html.Ul([
                            html.Li(f"Step: {step['type']} ({', '.join(step.get('calls', []))})", className="small")
                            if step['type'] == 'tool_call' 
                            else html.Li(f"Result: {str(step.get('content', ''))[:100]}...", className="small text-muted")
                            for step in result['steps']
                        ])
                    ], className="mb-3")
                ]
            
            # 5. Format the final output
            final_output = html.Div([
                dbc.Card([
                    dbc.CardHeader("AI Agent Response", className="fw-bold bg-primary text-white"),
                    dbc.CardBody([
                        *steps_display,
                        dcc.Markdown(result.get("output", "No output generated."), className="agent-final-response")
                    ])
                ], className="shadow-sm border-primary mt-3")
            ])
            
            return final_output
            
        except EnvironmentError as exc:
            return dbc.Alert([
                html.H5("Configuration Missing"),
                html.P(str(exc))
            ], color="warning", className="mt-3")
        except Exception as exc:
            logger.error(f"Callback error in handle_agent_query: {exc}")
            return dbc.Alert([
                html.H5("System Error"),
                html.P("An unexpected error occurred while processing your query.")
            ], color="danger", className="mt-3")
