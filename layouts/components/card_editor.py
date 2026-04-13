# ABOUTME: Modular Dash components for the Pre-Game and Performance Card Studios.
# ABOUTME: Renders the elite graphics editor UI with layer-based controls and absolute positioning.

import base64
from pathlib import Path

import dash_bootstrap_components as dbc
from dash import dcc, html

# ---------------------------------------------------------------------------
# Shared design tokens (mirror player_portal.css variables)
# ---------------------------------------------------------------------------
_GLASS_BG = "rgba(255,255,255,0.05)"
_GLASS_BORDER = "rgba(255,255,255,0.10)"
_ACCENT_CYAN = "#00f2ff"
_ACCENT_CYAN_FAINT = "rgba(0,242,255,0.12)"
_ACCENT_CYAN_BORDER = "rgba(0,242,255,0.35)"
_BG_PRIMARY = "#2a2a2a"
_BG_SECONDARY = "#1e1e2e"
_TEXT_MUTED = "rgba(255,255,255,0.45)"
_TEXT_LIGHT = "rgba(255,255,255,0.85)"

_PANEL_STYLE = {
    "background": _BG_SECONDARY,
    "border": f"1px solid {_GLASS_BORDER}",
    "borderRadius": "12px",
    "padding": "12px 14px",
    "height": "100%",
    "display": "flex",
    "flexDirection": "column",
}

_SECTION_LABEL_STYLE = {
    "color": _ACCENT_CYAN,
    "fontSize": "0.65rem",
    "fontWeight": "700",
    "letterSpacing": "0.1em",
    "textTransform": "uppercase",
    "marginBottom": "6px",
    "marginTop": "0",
}

_DIVIDER_STYLE = {
    "border": "none",
    "borderTop": f"1px solid {_GLASS_BORDER}",
    "margin": "10px 0",
}

_UPLOAD_STYLE = {
    "border": f"1.5px dashed {_ACCENT_CYAN_BORDER}",
    "borderRadius": "8px",
    "padding": "8px",
    "textAlign": "center",
    "cursor": "pointer",
    "color": _TEXT_MUTED,
    "fontSize": "0.75rem",
    "background": _GLASS_BG,
    "marginTop": "4px",
}

_GENERATE_BTN_STYLE = {
    "background": "linear-gradient(135deg, rgba(0,242,255,0.25), rgba(0,242,255,0.1))",
    "border": f"1.5px solid {_ACCENT_CYAN}",
    "color": "white",
    "borderRadius": "6px",
    "fontWeight": "700",
    "fontSize": "0.75rem",
}

_SECONDARY_BTN_STYLE = {
    "background": _GLASS_BG,
    "border": f"1px solid {_GLASS_BORDER}",
    "color": "rgba(255,255,255,0.7)",
    "borderRadius": "6px",
    "fontSize": "0.75rem",
}

_TAB_STYLE = {
    "background": _GLASS_BG,
    "border": f"1px solid {_GLASS_BORDER}",
    "color": "rgba(255,255,255,0.6)",
    "borderRadius": "6px 6px 0 0",
    "fontSize": "0.7rem",
    "padding": "3px 10px",
}

_TAB_ACTIVE_STYLE = {
    "background": _ACCENT_CYAN_FAINT,
    "border": f"1px solid {_ACCENT_CYAN_BORDER}",
    "borderBottom": "none",
    "color": _ACCENT_CYAN,
    "borderRadius": "6px 6px 0 0",
    "fontSize": "0.7rem",
    "fontWeight": "700",
    "padding": "3px 10px",
}


# ---------------------------------------------------------------------------
# Shared sub-components
# ---------------------------------------------------------------------------

def _save_toast():
    return dbc.Toast(
        "Design saved to your personal library.",
        id="card-save-toast",
        header="Style Archived",
        icon="success",
        duration=3000,
        is_open=False,
        style={"position": "fixed", "top": "80px", "right": "20px", "zIndex": 9999},
    )


# ---------------------------------------------------------------------------
# Pre-Game Card Studio
# ---------------------------------------------------------------------------

def create_pre_game_card_studio(milestone_id, match_context, album=None, selected_idx=None, initial_preview=None):
    """Renders the simplified Pre-Game Card Studio (Imagen 3 full-card generation)."""
    return _create_card_studio_layout(milestone_id, match_context, album, studio_type="pre-match", selected_idx=selected_idx, initial_preview=initial_preview)


def create_performance_card_studio(milestone_id, match_context, album=None, selected_idx=None, initial_preview=None):
    """Renders the simplified Performance Card Studio (Imagen 3 full-card generation)."""
    return _create_card_studio_layout(milestone_id, match_context, album, studio_type="post-match", selected_idx=selected_idx, initial_preview=initial_preview)


def _create_card_studio_layout(milestone_id, match_context, album, studio_type="pre-match", selected_idx=None, initial_preview=None):
    """Internal factory for the Studio UI."""
    home = match_context.get("home_team") or "—"
    away = match_context.get("away_team") or "—"
    competition = match_context.get("competition") or ""
    date_str = match_context.get("date") or ""

    # Initial loading content if no preview provided
    if not initial_preview:
        initial_preview = html.Div([
            html.I(className="bi bi-stars animate-glass-pulse",
                   style={"fontSize": "2.2rem", "color": _ACCENT_CYAN, "marginBottom": "12px", "opacity": "0.8"}),
            html.H5("AI Design Studio", className="text-white fw-bold mb-1"),
            html.P("Preparando lienzo...", className="text-white-50 small mb-0"),
        ], className="d-flex flex-column align-items-center justify-content-center h-100",
           style={"position": "absolute", "inset": "0", "background": "#0a1a2f"})

    return html.Div([
        dbc.Row([
            # ---- Left: High-Fidelity Preview (8 cols) ----
            dbc.Col([
                html.Div([
                    html.Div([
                        html.I(className="bi bi-stars me-2", style={"color": _ACCENT_CYAN}),
                        html.Span("AI Card Studio", style={"color": "white", "fontWeight": "700", "fontSize": "0.85rem"}),
                    ]),
                    html.Div([
                        html.Span(f"{home} vs {away}", style={"color": _ACCENT_CYAN, "fontSize": "0.7rem", "fontWeight": "600"}),
                        html.Span(f"  ·  {competition}", style={"color": "rgba(255,255,255,0.4)", "fontSize": "0.65rem"}) if competition else None,
                    ], className="d-none d-sm-block"),
                ], className="mb-2 d-flex align-items-center justify-content-between"),

                # ---- Preview Visor (Responsive height) ----
                html.Div(
                    [
                        # Centering wrapper
                        html.Div(
                            [
                                # Main ID'd container — height/width/aspect managed by callback
                                html.Div(
                                    initial_preview,
                                    id={"type": "studio-element", "index": "preview-container"},
                                    style={
                                        "borderRadius": "20px",
                                        "border": f"1px solid {_GLASS_BORDER}",
                                        "position": "relative",
                                        "overflow": "hidden",
                                        "boxShadow": "0 20px 40px rgba(0,0,0,0.5)",
                                        "background": "#05050a",
                                        "height": "100%",
                                        "width": "auto",
                                        "aspectRatio": "9/16",
                                        "maxHeight": "100%",
                                    },
                                ),
                            ],
                            className="d-flex justify-content-center align-items-center h-100",
                        ),
                        
                        # Expand action
                        dbc.Button(
                            [html.I(className="bi bi-arrows-angle-expand me-1"), "Expandir"],
                            id="card-expand-preview-btn",
                            size="sm",
                            className="position-absolute",
                            style={
                                "bottom": "15px", "right": "15px", "zIndex": "100",
                                "background": "rgba(0,0,0,0.6)", "backdropFilter": "blur(8px)",
                                "border": "1px solid rgba(255,255,255,0.15)",
                                "borderRadius": "20px", "padding": "4px 12px",
                                "color": "white", "fontWeight": "600", "fontSize": "0.65rem"
                            }
                        )
                    ],
                    style={
                        "background": "rgba(0,0,0,0.2)",
                        "borderRadius": "24px",
                        "flex": "1",
                        "minHeight": "0",
                        # Concrete height so height:100% resolves for the portrait card child
                        "height": "calc(var(--portal-desktop-height) - 80px)",
                        "position": "relative",
                        "display": "flex",
                        "alignItems": "center",
                        "justifyContent": "center",
                        "overflow": "hidden",
                        "padding": "12px"
                    },
                ),
            ], width=8, className="d-flex flex-column", style={"minHeight": "0"}),

            # ---- Right: Simple Controls (4 cols) ----
            dbc.Col([
                html.Div([
                    # Action buttons
                    html.Div([
                        dbc.Button(
                            [html.I(className="bi bi-stars me-2"), "Design"],
                            id="card-repropose-btn",
                            style={**_GENERATE_BTN_STYLE, "width": "100%", "padding": "8px"},
                            n_clicks=0,
                            className="mb-2",
                        ),
                        dbc.Button(
                            [html.I(className="bi bi-download me-2"), "Download Card"],
                            id="card-generate-btn",
                            color="success",
                            style={**_SECONDARY_BTN_STYLE, "width": "100%", "padding": "8px"},
                            n_clicks=0,
                        ),
                    ], className="mb-2"),

                    html.Hr(style=_DIVIDER_STYLE),

                    # Format selector
                    html.P("FORMAT", style=_SECTION_LABEL_STYLE),
                    dbc.Tabs(
                        [
                            dbc.Tab(label="9:16", tab_id="9:16", label_style=_TAB_STYLE, active_label_style=_TAB_ACTIVE_STYLE),
                            dbc.Tab(label="1:1", tab_id="1:1", label_style=_TAB_STYLE, active_label_style=_TAB_ACTIVE_STYLE),
                            dbc.Tab(label="4:5", tab_id="4:5", label_style=_TAB_STYLE, active_label_style=_TAB_ACTIVE_STYLE),
                        ],
                        id="card-format-tabs",
                        active_tab="9:16",
                        className="justify-content-start mb-2",
                    ),

                    # Photo selection
                    html.P("PHOTOS", style=_SECTION_LABEL_STYLE),
                    html.Div(id="card-photo-album", style={"maxHeight": "140px", "overflowY": "auto", "marginBottom": "10px"}),
                    
                    dcc.Upload(
                        id="card-photo-upload",
                        children=html.Div([
                            html.I(className="bi bi-cloud-arrow-up me-2"),
                            "Upload Photo",
                        ]),
                        style=_UPLOAD_STYLE,
                        multiple=False,
                    ),
                    html.Div(id="card-upload-status", className="small mt-1"),

                    html.Hr(style=_DIVIDER_STYLE),

                    # Stats selection
                    html.P("HIGHLIGHT STATS", style=_SECTION_LABEL_STYLE),
                    dcc.Dropdown(
                        id="card-stats-selection",
                        multi=True,
                        disabled=True,
                        placeholder="Agent choosing stats...",
                        className="card-studio-stats-dropdown mb-2",
                    ),

                    html.Hr(style=_DIVIDER_STYLE),

                    # Design History Gallery (below stats, not pushed to bottom)
                    html.P("HISTORY", style=_SECTION_LABEL_STYLE),
                    html.Div(id="card-history-gallery", style={"overflowY": "auto", "maxHeight": "160px"}),

                ], style=_PANEL_STYLE)
            ], width=4, className="h-100"),
        ], className="g-3 h-100"), # Use small gap and full height

        # Hidden stores for studio state
        dcc.Store(id="card-element-selector", data="player_photo"),
        dcc.Store(id="card-ai-signal", data=False),
        # AI Card Studio polling interval (now local to the editor to ensure it's always in DOM when needed)
        dcc.Interval(id="card-generation-interval", interval=2000, disabled=True),
        dcc.Download(id="card-download"),
        _save_toast(),
    ], className="card-studio-container p-0 h-100", style={"height": "100%", "overflow": "hidden"})
