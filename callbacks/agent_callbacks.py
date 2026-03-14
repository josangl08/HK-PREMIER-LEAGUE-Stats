# ABOUTME: Agent interaction callbacks for the HK Premier League.
# ABOUTME: Manages natural language query submission and result rendering.

"""
Agent Callbacks - Controller for the LangGraph Agent UI.
Handles query submission, agent execution, and UI feedback.
"""

import logging
from dash import Input, Output, State, dcc, html, no_update
import dash_bootstrap_components as dbc

from ai_models.agent import create_agent, run_agent

logger = logging.getLogger(__name__)


def register_agent_callbacks(app):
    """
    Registers Dash callbacks for the agent interaction panel.
    """
    
    @app.callback(
        Output("agent-output-display", "children"),
        Output("agent-submit-btn", "n_clicks"),
        Input("agent-submit-btn", "n_clicks"),
        State("agent-query-input", "value"),
        State("agent-flow-selector", "value"),
        prevent_initial_call=True
    )
    def handle_agent_query(n_clicks, query, flow):
        if not n_clicks or not query:
            return no_update, 0
            
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
                ], color="danger", className="mt-3"), 0
            
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
            
            return final_output, 0
            
        except EnvironmentError as exc:
            return dbc.Alert([
                html.H5("Configuration Missing"),
                html.P(str(exc))
            ], color="warning", className="mt-3"), 0
        except Exception as exc:
            logger.error(f"Callback error in handle_agent_query: {exc}")
            return dbc.Alert([
                html.H5("System Error"),
                html.P("An unexpected error occurred while processing your query.")
            ], color="danger", className="mt-3"), 0
