# ABOUTME: AI Insight Card component for the Player Portal timeline.
# ABOUTME: Displays a summary of an AI-generated insight with an animated gradient background.

from typing import Dict, Any
from dash import html
import dash_bootstrap_components as dbc

def render_ai_insight_card(
    milestone_payload: Dict[str, Any],
    milestone_id: str,
) -> html.Div:
    """
    Renders an AI Insight card with an animated gradient background.
    Triggers a Stage deep-dive on click.
    """
    title = milestone_payload.get("title", "AI Insight")
    summary = milestone_payload.get("summary", "New tactical analysis available.")
    
    return html.Div(
        html.Div(
            [
                html.Div("AI Insight", className="ai-insight-tag"),
                html.Div(title, className="ai-insight-card__title"),
                html.Div(summary, className="ai-insight-card__summary"),
            ],
            className="ai-insight-card__overlay"
        ),
        id={"type": "ai-insight-card", "index": milestone_id},
        className="ai-insight-card glass-card",
        style={"cursor": "pointer"},
        n_clicks=0
    )
