# ABOUTME: Overlay components for the 3-tier Career Intelligence overlay system.
# ABOUTME: Provides render_t1_overlay (modal) and render_t2_overlay (floating panel) using OverlaySignal dataclass.

from dash import html
import dash_bootstrap_components as dbc

from utils.career_intelligence import OverlaySignal


def render_t1_overlay(signal: OverlaySignal) -> html.Div:
    """
    Renders the T1 Critical Alert overlay.

    Layout: fixed full-viewport backdrop → centered card with animated gradient,
    title, body text, and two buttons ("Entendido" dismiss + cta_label action).
    Initially shown; hidden via callback on dismiss.
    """
    return html.Div(
        id="ai-overlay-t1-backdrop",
        className="ai-overlay-t1-backdrop",
        children=[
            html.Div(
                className="ai-overlay-t1-card",
                children=[
                    # Header row
                    html.Div(
                        className="d-flex align-items-center mb-3",
                        children=[
                            html.I(
                                className="bi bi-stars me-2",
                                style={"fontSize": "1.2rem", "color": "#00f2ff"},
                            ),
                            html.Span(
                                "Inteligencia de Carrera",
                                style={
                                    "fontSize": "0.75rem",
                                    "fontWeight": "600",
                                    "color": "#00f2ff",
                                    "textTransform": "uppercase",
                                    "letterSpacing": "1px",
                                },
                            ),
                        ],
                    ),
                    # Title
                    html.H5(
                        signal.title,
                        className="mb-2 fw-bold",
                        style={"color": "#ffffff"},
                    ),
                    # Body
                    html.P(
                        signal.body,
                        className="mb-4",
                        style={"color": "rgba(255,255,255,0.85)", "fontSize": "0.9rem", "lineHeight": "1.6"},
                    ),
                    # Action buttons
                    html.Div(
                        className="d-flex gap-2",
                        children=[
                            dbc.Button(
                                signal.cta_label,
                                id={"type": "ai-overlay-t1-btn", "action": "cta"},
                                color="primary",
                                size="sm",
                                className="flex-grow-1",
                                n_clicks=0,
                            ),
                            dbc.Button(
                                "Entendido",
                                id={"type": "ai-overlay-t1-btn", "action": "dismiss"},
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


def render_t2_overlay(signal: OverlaySignal, signal_index: int = 0) -> html.Div:
    """
    Renders a T2 Contextual Panel overlay card.

    Layout: absolute-positioned card floating over the stage column,
    with a dismiss [×] button, title, body text, and optional CTA link.

    Parameters
    ----------
    signal       : OverlaySignal to render.
    signal_index : 0-based index in the visible queue (used for stagger delay).
    """
    stagger_delay = f"{signal_index * 400}ms"
    dismiss_id = {"type": "ai-overlay-t2-dismiss", "index": signal_index}

    return html.Div(
        className="ai-overlay-t2",
        style={"animationDelay": stagger_delay},
        children=[
            html.Div(
                className="ai-overlay-t2__inner",
                children=[
                    # Top row: title + dismiss button
                    html.Div(
                        className="d-flex align-items-start justify-content-between mb-2",
                        children=[
                            html.Span(
                                signal.title,
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
                                className="ai-overlay-t2__dismiss",
                                title="Cerrar",
                            ),
                        ],
                    ),
                    # Body
                    html.P(
                        signal.body,
                        style={
                            "fontSize": "0.78rem",
                            "color": "rgba(255,255,255,0.80)",
                            "lineHeight": "1.5",
                            "margin": "0 0 10px 0",
                        },
                    ),
                    # CTA link
                    html.A(
                        [
                            signal.cta_label,
                            html.I(className="bi bi-arrow-right ms-1", style={"fontSize": "0.7rem"}),
                        ],
                        id={"type": "ai-overlay-t2-cta", "index": signal_index},
                        href="#",
                        style={
                            "fontSize": "0.75rem",
                            "color": "#00f2ff",
                            "textDecoration": "none",
                            "fontWeight": "600",
                        },
                    ) if signal.cta_label else None,
                ],
            ),
        ],
    )
