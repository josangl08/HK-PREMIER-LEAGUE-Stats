# ABOUTME: Agent interaction panel layout for the HK Premier League.
# ABOUTME: Provides natural language input and styled output for agentic reasoning.

"""
Agent Panel Layout - Interactive UI for the LangGraph Agent.
Includes query input, flow selector, and output display area.
"""

from dash import dcc, html
import dash_bootstrap_components as dbc


def create_agent_panel():
    """
    Creates the main layout for the Agent interaction tab.
    
    Returns:
        A styled html.Div containing the agent interaction components.
    """
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.H4("⚽ AI Scouting & Content Agent", className="mb-3"),
                html.P([
                    "Ask our AI agent for advanced player scouting or post-match content automation. ",
                    "The agent uses LangGraph and Gemini Flash to orchestrate complex data analysis tasks."
                ], className="text-muted mb-4"),
                
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Label("Select Agent Flow:", className="fw-bold mb-1"),
                                dcc.Dropdown(
                                    id="agent-flow-selector",
                                    options=[
                                        {"label": "🔍 Scouting Flow (Player Search)", "value": "scouting"},
                                        {"label": "📝 Content Flow (Reports & Captions)", "value": "content"},
                                    ],
                                    value="scouting",
                                    clearable=False,
                                    className="mb-3"
                                ),
                            ], width=12),
                        ]),
                        
                        html.Label("Enter your query:", className="fw-bold mb-1"),
                        dcc.Textarea(
                            id="agent-query-input",
                            placeholder="Example: 'Find all midfielders from Lee Man under 25 and generate a performance card for the best one.'",
                            style={"width": "100%", "height": "120px"},
                            className="form-control mb-3"
                        ),
                        
                        dbc.Button(
                            [dbc.Spinner(size="sm"), " Submit Query"],
                            id="agent-submit-btn",
                            color="primary",
                            className="w-100",
                            n_clicks=0
                        ),
                    ])
                ], className="shadow-sm mb-4"),
                
                # Output area
                html.Div(id="agent-output-display", className="mt-4")
            ], width=12, lg=10, className="mx-auto")
        ])
    ], className="p-4")
