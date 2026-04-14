# ABOUTME: Overlay components for tiered stage-intelligence surfaces rendered in the portal stage column.
# ABOUTME: Provides shared critical and contextual presentation builders that consume the normalized overlay contract.

from typing import Any, Mapping
from dash import html
import dash_bootstrap_components as dbc

def _overlay_value(signal: Mapping[str, Any], key: str, default: str = "") -> str:
    return str(signal.get(key) or default)


def render_critical_overlay(signal: Mapping[str, Any]) -> html.Div:
    """
    Renders the shared critical overlay surface.

    Layout: fixed full-viewport backdrop → centered card with animated gradient,
    title, body text, and two buttons ("Entendido" dismiss + cta_label action).
    Initially shown; hidden via callback on dismiss.
    """
    return html.Div(
        id="stage-overlay-critical-backdrop",
        className="stage-overlay-critical-backdrop",
        children=[
            html.Div(
                className="stage-overlay-critical-card",
                children=[
                    # Header row
                    html.Div(
                        className="d-flex align-items-center mb-3",
                        children=[
                            html.I(
                                className="bi bi-stars me-2",
                                style={"fontSize": "1.2rem", "color": "#f6c453"},
                            ),
                            html.Span(
                                f"Stage Intelligence · {_overlay_value(signal, 'stage', 'career').title()}",
                                style={
                                    "fontSize": "0.75rem",
                                    "fontWeight": "600",
                                    "color": "#f6c453",
                                    "textTransform": "uppercase",
                                    "letterSpacing": "1px",
                                },
                            ),
                        ],
                    ),
                    # Title
                    html.H5(
                        _overlay_value(signal, "title"),
                        className="mb-2 fw-bold",
                        style={"color": "#ffffff"},
                    ),
                    # Body
                    html.P(
                        _overlay_value(signal, "body"),
                        className="mb-4",
                        style={"color": "rgba(255,255,255,0.85)", "fontSize": "0.9rem", "lineHeight": "1.6"},
                    ),
                    # Action buttons
                    html.Div(
                        className="d-flex gap-2",
                        children=[
                            dbc.Button(
                                _overlay_value(signal, "cta_label", "Ver análisis"),
                                id={
                                    "type": "stage-overlay-critical-btn",
                                    "action": "cta",
                                    "evidence_key": _overlay_value(signal, "evidence_key", "career_arc"),
                                },
                                color="primary",
                                size="sm",
                                className="flex-grow-1",
                                n_clicks=0,
                            ),
                            dbc.Button(
                                "Entendido",
                                id={"type": "stage-overlay-critical-btn", "action": "dismiss", "evidence_key": ""},
                                color="outline-light",
                                size="sm",
                                className="flex-shrink-0",
                                n_clicks=0,
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def render_contextual_overlay(signal: Mapping[str, Any], signal_index: int = 0) -> html.Div:
    """
    Renders the shared contextual panel overlay card.

    Layout: absolute-positioned card floating over the stage column,
    with a dismiss [×] button, title, body text, and optional CTA link.

    Parameters
    ----------
    signal       : Shared overlay contract item to render.
    signal_index : 0-based index in the visible queue (used for stagger delay).
    """
    stagger_delay = f"{signal_index * 400}ms"
    dismiss_id = {"type": "stage-overlay-contextual-dismiss", "index": signal_index}

    return html.Div(
        className="stage-overlay-contextual-floating",
        style={"animationDelay": stagger_delay},
        children=[
            html.Div(
                className="stage-overlay-contextual-floating__inner",
                children=[
                    # Top row: title + dismiss button
                    html.Div(
                        className="d-flex align-items-start justify-content-between mb-2",
                        children=[
                            html.Span(
                                _overlay_value(signal, "title"),
                                style={
                                    "fontWeight": "700",
                                    "fontSize": "0.82rem",
                                    "color": "#ffffff",
                                    "lineHeight": "1.3",
                                    "flex": "1",
                                    "marginRight": "8px",
                                },
                            ),
                            html.Button(
                                "×",
                                id=dismiss_id,
                                n_clicks=0,
                                className="stage-overlay-contextual-floating__dismiss",
                                title="Cerrar",
                            ),
                        ],
                    ),
                    # Body
                    html.P(
                        _overlay_value(signal, "body"),
                        style={
                            "fontSize": "0.78rem",
                            "color": "rgba(255,255,255,0.80)",
                            "lineHeight": "1.5",
                            "margin": "0 0 10px 0",
                        },
                    ),
                    # CTA link
                    dbc.Button(
                        [
                            _overlay_value(signal, "cta_label", "Ver análisis"),
                            html.I(className="bi bi-arrow-right ms-1", style={"fontSize": "0.7rem"}),
                        ],
                        id={
                            "type": "stage-overlay-contextual-cta",
                            "index": signal_index,
                            "evidence_key": _overlay_value(signal, "evidence_key", "career_arc"),
                        },
                        color="link",
                        className="p-0 stage-overlay-contextual-floating__cta",
                        n_clicks=0,
                    ) if _overlay_value(signal, "cta_label") else None,
                ],
            ),
        ],
    )
