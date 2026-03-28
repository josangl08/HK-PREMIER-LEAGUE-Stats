# ABOUTME: Modular Dash components for the Pre-Game and Performance Card Studios.
# ABOUTME: Renders the interactive editor inside the Stage column with glassmorphism design.

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

_PANEL_STYLE = {
    "background": _BG_SECONDARY,
    "border": f"1px solid {_GLASS_BORDER}",
    "borderRadius": "14px",
    "padding": "18px 16px",
    "height": "100%",
}

_SECTION_LABEL_STYLE = {
    "color": _ACCENT_CYAN,
    "fontSize": "0.72rem",
    "fontWeight": "700",
    "letterSpacing": "0.12em",
    "textTransform": "uppercase",
    "marginBottom": "10px",
    "marginTop": "0",
}

_DIVIDER_STYLE = {
    "border": "none",
    "borderTop": f"1px solid {_GLASS_BORDER}",
    "margin": "14px 0",
}

_UPLOAD_STYLE = {
    "border": f"1.5px dashed {_ACCENT_CYAN_BORDER}",
    "borderRadius": "8px",
    "padding": "12px",
    "textAlign": "center",
    "cursor": "pointer",
    "color": _TEXT_MUTED,
    "fontSize": "0.8rem",
    "background": _GLASS_BG,
    "marginTop": "8px",
    "transition": "border-color 0.2s, background 0.2s",
}

_GENERATE_BTN_STYLE = {
    "background": "linear-gradient(135deg, rgba(0,242,255,0.15), rgba(0,242,255,0.05))",
    "border": f"1.5px solid {_ACCENT_CYAN}",
    "color": _ACCENT_CYAN,
    "borderRadius": "999px",
    "fontWeight": "700",
    "fontSize": "0.85rem",
    "letterSpacing": "0.05em",
    "padding": "10px 28px",
    "width": "100%",
}

_SECONDARY_BTN_STYLE = {
    "background": _GLASS_BG,
    "border": f"1px solid {_GLASS_BORDER}",
    "color": "rgba(255,255,255,0.7)",
    "borderRadius": "999px",
    "fontSize": "0.75rem",
    "padding": "6px 16px",
}

_TAB_STYLE = {
    "background": _GLASS_BG,
    "border": f"1px solid {_GLASS_BORDER}",
    "color": "rgba(255,255,255,0.6)",
    "borderRadius": "8px 8px 0 0",
    "fontSize": "0.78rem",
    "padding": "6px 14px",
}

_TAB_ACTIVE_STYLE = {
    "background": _ACCENT_CYAN_FAINT,
    "border": f"1px solid {_ACCENT_CYAN_BORDER}",
    "borderBottom": "none",
    "color": _ACCENT_CYAN,
    "borderRadius": "8px 8px 0 0",
    "fontSize": "0.78rem",
    "fontWeight": "700",
    "padding": "6px 14px",
}

_RADIO_LABEL_STYLE = {"color": "rgba(255,255,255,0.8)", "fontSize": "0.82rem"}
_SELECT_STYLE = {
    "background": "rgba(255,255,255,0.06)",
    "border": f"1px solid {_GLASS_BORDER}",
    "color": "rgba(255,255,255,0.85)",
    "borderRadius": "8px",
    "fontSize": "0.82rem",
}


# ---------------------------------------------------------------------------
# Shared sub-components
# ---------------------------------------------------------------------------

def _photo_album_section():
    return html.Div([
        html.P("PHOTO ALBUM", style=_SECTION_LABEL_STYLE),
        html.Div(id="card-photo-album", className="mt-1"),
        dcc.Upload(
            id="card-photo-upload",
            children=html.Div([
                html.I(className="bi bi-camera me-2"),
                "Drag or ", html.Strong("Select Photo"),
            ]),
            style=_UPLOAD_STYLE,
            multiple=False,
        ),
        html.Div(id="card-upload-status", className="mt-1"),
    ])


def _format_section():
    return html.Div([
        html.P("FORMAT", style=_SECTION_LABEL_STYLE),
        dbc.RadioItems(
            id={"type": "card-format-radio", "index": "format"},
            options=[
                {"label": "1:1", "value": "1:1"},
                {"label": "9:16", "value": "9:16"},
                {"label": "16:9", "value": "16:9"},
            ],
            value="1:1",
            inline=True,
            className="mb-1",
            style={"fontSize": "0.82rem", "color": "rgba(255,255,255,0.8)"},
        ),
    ])


def _action_buttons(show_repropose=True):
    buttons = []
    if show_repropose:
        buttons.append(
            dbc.Button(
                [html.I(className="bi bi-arrow-clockwise me-2"), "Re-propose"],
                id="card-repropose-btn",
                style=_SECONDARY_BTN_STYLE,
                className="me-2",
                n_clicks=0,
            )
        )
    buttons.append(
        dbc.Button(
            [html.I(className="bi bi-floppy me-2"), "Save Draft"],
            id="card-save-draft-btn",
            style=_SECONDARY_BTN_STYLE,
            n_clicks=0,
        )
    )
    return html.Div(buttons, className="d-flex mb-3 flex-wrap gap-2")


def _save_toast():
    return dbc.Toast(
        "Draft guardado correctamente.",
        id="card-save-toast",
        header="Guardado",
        icon="success",
        duration=3000,
        is_open=False,
        style={"position": "fixed", "top": "80px", "right": "20px", "zIndex": 9999},
    )


# ---------------------------------------------------------------------------
# Spinner
# ---------------------------------------------------------------------------

def create_card_studio_spinner(card_type="performance"):
    """Returns a spinner with contextual messages for AI generation."""
    return html.Div([
        dbc.Spinner(color="primary", size="lg"),
        html.P("Analizando el partido…", id="card-spinner-text",
               className="mt-3", style={"color": _TEXT_MUTED}),
        dcc.Interval(id="card-spinner-interval", interval=3000),
    ], className="text-center p-5")


# ---------------------------------------------------------------------------
# Pre-Game Card Studio
# ---------------------------------------------------------------------------

def create_pre_game_card_studio(milestone_id, match_context, proposals, initial_preview=None):
    """Renders the Pre-Game Card Studio layout with glassmorphism design."""
    home = match_context.get("home_team", "")
    away = match_context.get("away_team", "")
    comp = match_context.get("competition", "")
    subtitle = f"{home} vs {away}" if home and away else comp

    return html.Div([
        _save_toast(),

        # Header
        html.Div([
            html.Div([
                html.I(className="bi bi-card-image me-2", style={"color": _ACCENT_CYAN}),
                html.Span("Pre-Game Card Studio",
                          style={"color": "white", "fontWeight": "700", "fontSize": "1.05rem"}),
            ]),
            html.Div(subtitle,
                     style={"color": _TEXT_MUTED, "fontSize": "0.78rem", "marginTop": "2px"}),
        ], style={"marginBottom": "16px"}),

        dbc.Row([
            # ---- Left: preview ----
            dbc.Col([
                html.Div(
                    initial_preview or html.Div(
                        "Sin propuesta cargada.",
                        style={"color": _TEXT_MUTED, "padding": "40px", "textAlign": "center"}
                    ),
                    id="card-preview-container",
                    style={
                        "background": "#111120",
                        "borderRadius": "12px",
                        "border": f"1px solid {_GLASS_BORDER}",
                        "minHeight": "320px",
                        "overflow": "hidden",
                    }
                ),
            ], width=8),

            # ---- Right: controls ----
            dbc.Col([
                html.Div([
                    _action_buttons(show_repropose=True),

                    # Templates
                    html.P("TEMPLATES", style=_SECTION_LABEL_STYLE),
                    dbc.Tabs(
                        [
                            dbc.Tab(label="A", tab_id="A",
                                    label_style=_TAB_STYLE,
                                    active_label_style=_TAB_ACTIVE_STYLE),
                            dbc.Tab(label="B", tab_id="B",
                                    label_style=_TAB_STYLE,
                                    active_label_style=_TAB_ACTIVE_STYLE),
                            dbc.Tab(label="C", tab_id="C",
                                    label_style=_TAB_STYLE,
                                    active_label_style=_TAB_ACTIVE_STYLE),
                        ],
                        id="card-template-tabs",
                        active_tab="A",
                        style={"marginBottom": "12px"},
                    ),

                    html.Div(style=_DIVIDER_STYLE),
                    _format_section(),
                    html.Div(style=_DIVIDER_STYLE),
                    _photo_album_section(),

                    # Hidden: satisfies card-stat-highlight Input in shared callback
                    dbc.RadioItems(
                        id={"type": "card-stat-highlight", "index": "stat"},
                        options=[{"label": "Goals", "value": "goals"}],
                        value="goals",
                        style={"display": "none"},
                    ),
                ], style=_PANEL_STYLE),
            ], width=4),
        ]),

        # Bottom bar
        dbc.Row([
            dbc.Col([
                dbc.Button(
                    [html.I(className="bi bi-download me-2"), "GENERATE PNG"],
                    id="card-generate-btn",
                    color="success",
                    style=_GENERATE_BTN_STYLE,
                    className="mt-3",
                    n_clicks=0,
                ),
                dcc.Download(id="card-download"),
            ]),
        ]),
    ], id="card-editor-container")


# ---------------------------------------------------------------------------
# Performance Card Studio
# ---------------------------------------------------------------------------

def create_performance_card_studio(milestone_id, match_context, proposals, initial_preview=None):
    """Renders the Performance Card Studio (Post-Match) layout with glassmorphism design."""
    home = match_context.get("home_team", "")
    away = match_context.get("away_team", "")
    score = match_context.get("score", "")
    subtitle = f"{home} {score} {away}" if score else f"{home} vs {away}"

    return html.Div([
        _save_toast(),

        # Header
        html.Div([
            html.Div([
                html.I(className="bi bi-trophy me-2", style={"color": _ACCENT_CYAN}),
                html.Span("Performance Card Studio",
                          style={"color": "white", "fontWeight": "700", "fontSize": "1.05rem"}),
            ]),
            html.Div(subtitle,
                     style={"color": _TEXT_MUTED, "fontSize": "0.78rem", "marginTop": "2px"}),
        ], style={"marginBottom": "16px"}),

        dbc.Row([
            # ---- Left: preview ----
            dbc.Col([
                html.Div(
                    initial_preview or html.Div(
                        "Sin propuesta cargada.",
                        style={"color": _TEXT_MUTED, "padding": "40px", "textAlign": "center"}
                    ),
                    id="card-preview-container",
                    style={
                        "background": "#111120",
                        "borderRadius": "12px",
                        "border": f"1px solid {_GLASS_BORDER}",
                        "minHeight": "320px",
                        "overflow": "hidden",
                    }
                ),
            ], width=8),

            # ---- Right: controls ----
            dbc.Col([
                html.Div([
                    _action_buttons(show_repropose=True),

                    # Templates
                    html.P("TEMPLATES", style=_SECTION_LABEL_STYLE),
                    dbc.Tabs(
                        [
                            dbc.Tab(label="A", tab_id="A",
                                    label_style=_TAB_STYLE,
                                    active_label_style=_TAB_ACTIVE_STYLE),
                            dbc.Tab(label="B", tab_id="B",
                                    label_style=_TAB_STYLE,
                                    active_label_style=_TAB_ACTIVE_STYLE),
                            dbc.Tab(label="C", tab_id="C",
                                    label_style=_TAB_STYLE,
                                    active_label_style=_TAB_ACTIVE_STYLE),
                        ],
                        id="card-template-tabs",
                        active_tab="A",
                        style={"marginBottom": "12px"},
                    ),

                    html.Div(style=_DIVIDER_STYLE),
                    _format_section(),
                    html.Div(style=_DIVIDER_STYLE),

                    # Stats to highlight
                    html.P("STAT TO HIGHLIGHT", style=_SECTION_LABEL_STYLE),
                    dbc.RadioItems(
                        id={"type": "card-stat-highlight", "index": "stat"},
                        options=[
                            {"label": "Goals", "value": "goals"},
                            {"label": "Assists", "value": "assists"},
                            {"label": "Rating", "value": "rating"},
                            {"label": "Minutes", "value": "minutes_played"},
                        ],
                        value="goals",
                        style={"fontSize": "0.82rem", "color": "rgba(255,255,255,0.8)"},
                    ),

                    html.Div(style=_DIVIDER_STYLE),

                    # AI Caption
                    html.P("AI CAPTION", style=_SECTION_LABEL_STYLE),
                    dbc.Select(
                        id="card-caption-tone",
                        options=[
                            {"label": "Professional", "value": "pro"},
                            {"label": "Hype", "value": "hype"},
                            {"label": "Humble", "value": "humble"},
                        ],
                        value="pro",
                        style=_SELECT_STYLE,
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-magic me-2"), "Generate Caption"],
                        id="card-caption-btn",
                        style={**_SECONDARY_BTN_STYLE, "width": "100%", "marginTop": "8px"},
                        n_clicks=0,
                    ),
                    dbc.Textarea(
                        id="card-caption-preview",
                        className="mt-2",
                        placeholder="Your AI caption will appear here…",
                        style={
                            "background": "rgba(255,255,255,0.04)",
                            "border": f"1px solid {_GLASS_BORDER}",
                            "color": "rgba(255,255,255,0.85)",
                            "borderRadius": "8px",
                            "fontSize": "0.8rem",
                            "minHeight": "80px",
                        },
                        rows=3,
                    ),

                    html.Div(style=_DIVIDER_STYLE),
                    _photo_album_section(),
                ], style=_PANEL_STYLE),
            ], width=4),
        ]),

        # Bottom bar
        dbc.Row([
            dbc.Col([
                dbc.Button(
                    [html.I(className="bi bi-download me-2"), "GENERATE PNG"],
                    id="card-generate-btn",
                    color="success",
                    style=_GENERATE_BTN_STYLE,
                    className="mt-3",
                    n_clicks=0,
                ),
                dcc.Download(id="card-download"),
            ]),
        ]),
    ], id="card-editor-container")
