# ABOUTME: Modular Dash components for the Pre-Game and Performance Card Studios.
# ABOUTME: Renders the elite graphics editor UI with layer-based controls and absolute positioning.

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
}

_GENERATE_BTN_STYLE = {
    "background": "linear-gradient(135deg, rgba(0,242,255,0.25), rgba(0,242,255,0.1))",
    "border": f"1.5px solid {_ACCENT_CYAN}",
    "color": "white",
    "borderRadius": "6px",
    "fontWeight": "700",
}

_SECONDARY_BTN_STYLE = {
    "background": _GLASS_BG,
    "border": f"1px solid {_GLASS_BORDER}",
    "color": "rgba(255,255,255,0.7)",
    "borderRadius": "6px",
}

_TAB_STYLE = {
    "background": _GLASS_BG,
    "border": f"1px solid {_GLASS_BORDER}",
    "color": "rgba(255,255,255,0.6)",
    "borderRadius": "6px 6px 0 0",
    "fontSize": "0.75rem",
    "padding": "4px 12px",
}

_TAB_ACTIVE_STYLE = {
    "background": _ACCENT_CYAN_FAINT,
    "border": f"1px solid {_ACCENT_CYAN_BORDER}",
    "borderBottom": "none",
    "color": _ACCENT_CYAN,
    "borderRadius": "6px 6px 0 0",
    "fontSize": "0.75rem",
    "fontWeight": "700",
    "padding": "4px 12px",
}

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

def _editor_toolbar(show_repropose=True):
    """Actions toolbar for the right sidebar. Buttons share width equally."""
    buttons = []
    if show_repropose:
        buttons.append(
            dbc.Button(
                [html.I(className="bi bi-arrow-clockwise me-1"), "Redesign"],
                id="card-repropose-btn",
                style={**_SECONDARY_BTN_STYLE, "fontSize": "0.65rem", "width": "100%"},
                n_clicks=0,
            )
        )
    buttons.append(
        dbc.Button(
            [html.I(className="bi bi-floppy me-1"), "Save Style"],
            id="card-save-draft-btn",
            style={**_SECONDARY_BTN_STYLE, "fontSize": "0.65rem", "width": "100%"},
            n_clicks=0,
        )
    )
    buttons.append(
        dbc.Button(
            [html.I(className="bi bi-download me-1"), "Export"],
            id="card-generate-btn",
            color="success",
            style={**_GENERATE_BTN_STYLE, "padding": "4px 12px", "fontSize": "0.65rem", "width": "100%"},
            n_clicks=0,
        )
    )
    return html.Div(buttons, className="d-flex justify-content-between gap-1 mb-3")


def _template_format_row():
    """Optimized row: AI Proposals and Format switching. Base Style is hidden as it's set by the AI Proposal."""
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.P("AI PROPOSALS", style={**_SECTION_LABEL_STYLE, "marginBottom": "5px"}),
                dbc.ButtonGroup([
                    dbc.Button("OPTION 1", id={"type": "card-concept-btn", "index": 0}, size="sm", style=_SECONDARY_BTN_STYLE),
                    dbc.Button("OPTION 2", id={"type": "card-concept-btn", "index": 1}, size="sm", style=_SECONDARY_BTN_STYLE),
                    dbc.Button("OPTION 3", id={"type": "card-concept-btn", "index": 2}, size="sm", style=_SECONDARY_BTN_STYLE),
                ], className="w-100"),
            ], width=12, className="mb-3"),
        ]),
        dbc.Row([
            # Base Style tabs are now hidden but kept in the DOM for internal state tracking if needed
            html.Div([
                dbc.Tabs(id="card-template-tabs", active_tab="A"),
            ], style={"display": "none"}),
            
            dbc.Col([
                html.P("FORMAT", style={**_SECTION_LABEL_STYLE, "marginBottom": "5px", "textAlign": "left"}),
                html.Div([
                    dbc.Tabs(
                        [
                            dbc.Tab(label="1:1", tab_id="1:1", label_style=_TAB_STYLE, active_label_style=_TAB_ACTIVE_STYLE),
                            dbc.Tab(label="9:16", tab_id="9:16", label_style=_TAB_STYLE, active_label_style=_TAB_ACTIVE_STYLE),
                            dbc.Tab(label="16:9", tab_id="16:9", label_style=_TAB_STYLE, active_label_style=_TAB_ACTIVE_STYLE),
                        ],
                        id="card-format-tabs",
                        active_tab="1:1",
                        className="justify-content-start",
                    ),
                ]),
            ], width=12),
        ], className="align-items-end mb-3")
    ])


def _template_library_section():
    """Section for visual reusable designs."""
    return html.Div([
        html.P("MY SAVED STYLES", style=_SECTION_LABEL_STYLE),
        html.Div(
            id="card-templates-library",
            className="d-flex gap-2 overflow-auto pb-2",
            style={"minHeight": "100px"}
        ),
    ], className="mb-3")


def _advanced_element_editor():
    """Layer editor with visibility toggles integrated into element selection."""
    
    # Define options with icons and colors
    element_options = [
        {"label": "Home Logo", "value": "home_logo", "icon": "bi-house", "color": "#FF4B4B"},
        {"label": "Away Logo", "value": "away_logo", "icon": "bi-flag", "color": "#4B7BFF"},
        {"label": "Match Info", "value": "match_info", "icon": "bi-calendar3", "color": "#FFD700"},
        {"label": "Comp Badge", "value": "comp_badge", "icon": "bi-trophy", "color": "#00f2ff"},
        {"label": "Stream Logo", "value": "stream_logo", "icon": "bi-tv", "color": "#FF8C00"},
        {"label": "Headline", "value": "headline", "icon": "bi-type-h1", "color": "#ffffff"},
        {"label": "Subtitle", "value": "subtitle", "icon": "bi-chat-left-text", "color": "#A0A0A0"},
        {"label": "Player Main", "value": "player_photo", "icon": "bi-person-bounding-box", "color": "#00f2ff"},
        {"label": "Player Name", "value": "player_name", "icon": "bi-tag", "color": "#ffffff"},
    ]

    dropdown_items = []
    for opt in element_options:
        dropdown_items.append(
            dbc.DropdownMenuItem(
                html.Div([
                    html.Div([
                        html.I(className=f"bi {opt['icon']} me-3", style={"color": opt['color'], "fontSize": "1rem"}),
                        html.Span(opt['label'], style={"fontSize": "0.85rem"}),
                    ], 
                    id={"type": "card-element-name-click", "index": opt['value']},
                    className="d-flex align-items-center flex-grow-1 h-100"),
                    
                    dbc.Checkbox(
                        id={"type": "card-element-toggle", "index": opt['value']},
                        value=True,
                        className="ms-3",
                        style={"transform": "scale(1.1)"}
                    )
                ], className="d-flex align-items-center justify-content-between w-100 py-1"),
                toggle=True, 
                className="px-3"
            )
        )

    # Standard marks for 0-100 sliders
    slider_marks = {i: {"label": str(i), "style": {"color": _TEXT_LIGHT, "fontSize": "0.6rem"}} for i in range(0, 101, 10)}

    return html.Div([
        html.P("LAYER CONTROLS", style=_SECTION_LABEL_STYLE),
        
        # Element Selector Dropdown with icons and checkboxes
        dbc.DropdownMenu(
            label=[
                html.I(className="bi bi-layers me-2"),
                html.Span("Select Layer", id="card-element-current-label")
            ],
            children=dropdown_items,
            id="card-element-dropdown",
            color="dark",
            menu_variant="dark",
            className="mb-3 w-100",
            style={"width": "100%"}, 
            toggle_style={
                "background": "rgba(255,255,255,0.06)",
                "border": f"1px solid {_GLASS_BORDER}",
                "textAlign": "left",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "space-between",
                "fontSize": "0.82rem",
                "borderRadius": "8px",
                "padding": "10px 15px",
                "width": "100%" 
            },
            toggleClassName="w-100 custom-dropdown-toggle",
        ),
        
        # Keep a hidden input to track the "active" element for sliders
        dcc.Store(id="card-element-selector", data="headline"),

        # Manual Controls Panel
        html.Div([
            html.Div([
                html.Div([
                    html.Label("Horizontal (X)", style={"fontSize": "0.6rem", "color": _TEXT_LIGHT}),
                    dcc.Slider(
                        id="card-element-x-slider", min=0, max=100, step=1, value=50, className="mb-2",
                        marks=slider_marks
                    ),
                ]),
                
                html.Div([
                    html.Label("Vertical (Y)", style={"fontSize": "0.6rem", "color": _TEXT_LIGHT}),
                    dcc.Slider(
                        id="card-element-y-slider", min=0, max=100, step=1, value=50, className="mb-2",
                        marks=slider_marks
                    ),
                ]),
                
                html.Div([
                    html.Label("Scale / Size", style={"fontSize": "0.6rem", "color": _TEXT_LIGHT}),
                    dcc.Slider(
                        id="card-element-scale-slider", min=10, max=250, step=5, value=100,
                        marks={10: {"label": "10", "style": {"color": _TEXT_LIGHT, "fontSize": "0.6rem"}}, 
                               250: {"label": "250", "style": {"color": _TEXT_LIGHT, "fontSize": "0.6rem"}}}
                    ),
                ]),
            ], id="card-manual-position-controls"),
        ], id="card-element-editor-container", className="p-3", 
           style={"background": "rgba(0,0,0,0.25)", "borderRadius": "10px", "border": "1px solid rgba(255,255,255,0.05)"}),

        # Quick Presets
        html.Div([
            html.Label("Layout Presets", style={"fontSize": "0.65rem", "color": _TEXT_LIGHT, "marginTop": "15px"}),
            dbc.Select(
                id="card-layout-presets",
                options=[
                    {"label": "Classic Matchday", "value": "classic"},
                    {"label": "Hero Centric", "value": "hero"},
                    {"label": "Split Rivalry", "value": "split"},
                    {"label": "Minimalist Data", "value": "minimal"},
                    {"label": "Epic Derby", "value": "derby"},
                ],
                placeholder="Choose distribution...",
                style={**_SELECT_STYLE, "fontSize": "0.75rem"},
            ),
        ]),
    ])


def _photo_album_section(album=None):
    from callbacks.card_editor_callbacks import _build_album_grid
    return html.Div([
        html.P("MY ASSETS (PHOTOS)", style=_SECTION_LABEL_STYLE),
        html.Div(
            _build_album_grid(album) if album else "No assets.",
            id="card-photo-album",
            className="mt-1",
            style={"maxHeight": "120px", "overflowY": "auto"}
        ),
        dcc.Upload(
            id="card-photo-upload",
            children=html.Div([
                html.I(className="bi bi-cloud-arrow-up me-2"),
                "Upload Cutout",
            ]),
            style=_UPLOAD_STYLE,
            multiple=False,
        ),
        html.Div(id="card-upload-status", className="mt-1"),
    ])


def _ai_insights_container(report_data=None):
    """Dedicated stylized container for Agency Match Intelligence (Report, Caption, Hashtags)."""
    if not report_data or not isinstance(report_data, dict):
        return dbc.Card([
            dbc.CardHeader([
                html.I(className="bi bi-shield-shaded me-2", style={"color": _ACCENT_CYAN}),
                html.Span("AGENCY MATCH INTELLIGENCE", className="fw-bold", style={"fontSize": "0.7rem", "letterSpacing": "1px"}),
            ], className="border-0 bg-transparent py-2"),
            dbc.CardBody([
                html.P("Waiting for Agency Analyst...", className="text-white-50 small mb-0")
            ]),
        ], className="border-0 shadow-lg", style={"background": "rgba(0,242,255,0.03)", "borderLeft": f"3px solid {_ACCENT_CYAN}"})
        
    report = report_data.get("report", "No report available.")
    caption = report_data.get("instagram_caption", "No caption generated.")
    hashtags = report_data.get("hashtags", [])

    return dbc.Card([
        dbc.CardHeader([
            html.I(className="bi bi-shield-shaded me-2", style={"color": _ACCENT_CYAN}),
            html.Span("AGENCY MATCH INTELLIGENCE", className="fw-bold", style={"fontSize": "0.7rem", "letterSpacing": "1px"}),
        ], className="border-0 bg-transparent py-2 d-flex align-items-center"),
        
        dbc.CardBody([
            # 1. Technical Report
            html.Div([
                html.P("TECHNICAL REPORT", style={**_SECTION_LABEL_STYLE, "fontSize": "0.6rem", "marginBottom": "5px"}),
                html.P(report, className="text-white-50 mb-3", style={"fontSize": "0.75rem", "lineHeight": "1.4"}),
            ]),
            
            html.Div(style=_DIVIDER_STYLE),

            # 2. Instagram Copy
            html.Div([
                html.Div([
                    html.P("INSTAGRAM CAPTION", style={**_SECTION_LABEL_STYLE, "fontSize": "0.6rem", "marginBottom": "0"}),
                    dbc.Button(
                        [html.I(className="bi bi-clipboard me-1"), "Copy"], 
                        id="copy-caption-btn", 
                        size="sm", 
                        color="link", 
                        className="p-0 text-info text-decoration-none",
                        style={"fontSize": "0.65rem"}
                    ),
                ], className="d-flex justify-content-between align-items-center mb-2"),
                
                html.Div(caption, className="p-2 mb-2", style={
                    "background": "rgba(0,0,0,0.2)", 
                    "borderRadius": "6px", 
                    "fontSize": "0.7rem",
                    "color": _TEXT_LIGHT,
                    "whiteSpace": "pre-wrap"
                }),
            ]),

            # 3. Hashtags
            html.Div([
                html.Div([
                    html.Span(tag, className="badge me-1 mb-1", style={
                        "background": "rgba(255,255,255,0.05)",
                        "color": _ACCENT_CYAN,
                        "fontWeight": "400",
                        "fontSize": "0.6rem",
                        "border": f"1px solid {_ACCENT_CYAN_BORDER}"
                    }) for tag in hashtags
                ], className="d-flex flex-wrap")
            ], className="mt-2"),
        ]),
        dcc.Clipboard(target_id="instagram-caption-text", id="instagram-caption-clipboard"),
        html.Div(caption, id="instagram-caption-text", style={"display": "none"})
    ], className="border-0 shadow-lg", style={"background": "rgba(0,242,255,0.03)", "borderLeft": f"3px solid {_ACCENT_CYAN}"})


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


def _progress_indicator(id_name="card-generation-status"):
    """Labelled multi-phase progress bar for V3 generation pipeline."""
    return html.Div([
        html.Div(id=f"{id_name}-label", className="small text-info mb-1 font-monospace", style={"fontSize": "0.6rem", "textTransform": "uppercase"}),
        dbc.Progress(
            id=id_name,
            value=0,
            striped=True,
            animated=True,
            color="info",
            style={"height": "4px", "background": "rgba(255,255,255,0.05)", "width": "200px"}
        )
    ], className="ms-auto d-flex flex-column align-items-end")


# ---------------------------------------------------------------------------
# Pre-Game Card Studio
# ---------------------------------------------------------------------------

def create_pre_game_card_studio(milestone_id, match_context, proposals, initial_preview=None, album=None):
    """Renders the high-end Pre-Game Card Studio."""
    return html.Div([
        _save_toast(),

        dbc.Row([
            # ---- Left: Preview Area ----
            dbc.Col([
                html.Div([
                    html.Div([
                        html.I(className="bi bi-calendar3 me-2", style={"color": _ACCENT_CYAN}),
                        html.Span("Matchday Studio", style={"color": "white", "fontWeight": "700", "fontSize": "0.9rem"}),
                    ]),
                    # Live Agency Feed (V3 Progress)
                    _progress_indicator("card-generation-status"),
                    ], className="mb-3 d-flex align-items-center"),


                html.Div(
                    initial_preview or html.Div([
                        dbc.Spinner(color="info"),
                        html.P("Designing elite proposals...", className="mt-3 small text-white-50")
                    ], className="d-flex flex-column align-items-center justify-content-center", style={"height": "450px"}),
                    id={"type": "studio-element", "index": "preview-container"},
                    style={
                        "background": "#05050a",
                        "borderRadius": "16px",
                        "border": f"1px solid {_GLASS_BORDER}",
                        "minHeight": "450px",
                        "overflow": "hidden",
                        "boxShadow": "0 25px 50px rgba(0,0,0,0.6)"
                    }
                ),
                
                # Insights dedicated space will be populated by callback into 'stage-decision-nodes'
                dcc.Download(id="card-download"),
            ], width=8),

            # ---- Right: Sidebar Controls ----
            dbc.Col([
                html.Div([
                    _editor_toolbar(show_repropose=True),
                    _template_format_row(),
                    _template_library_section(),
                    html.Div(style=_DIVIDER_STYLE),
                    _advanced_element_editor(),
                    html.Div(style=_DIVIDER_STYLE),
                    _photo_album_section(album),
                ], style={**_PANEL_STYLE, "overflowY": "auto", "maxHeight": "85vh"}),
            ], width=4),
        ]),
    ], id="card-editor-container", className="px-3 py-2")


# ---------------------------------------------------------------------------
# Performance Card Studio (Post-Match)
# ---------------------------------------------------------------------------

def create_performance_card_studio(milestone_id, match_context, proposals, initial_preview=None, album=None):
    """Renders the high-end Performance Card Studio."""
    return html.Div([
        _save_toast(),

        dbc.Row([
            # ---- Left: Preview Area ----
            dbc.Col([
                html.Div([
                    html.Div([
                        html.I(className="bi bi-calendar3 me-2", style={"color": _ACCENT_CYAN}),
                        html.Span("Matchday Studio", style={"color": "white", "fontWeight": "700", "fontSize": "0.9rem"}),
                    ]),
                    # Live Agency Feed (V3 Progress)
                    _progress_indicator("card-generation-status"),
                    ], className="mb-3 d-flex align-items-center"),


                html.Div(
                    initial_preview or html.Div([
                        dbc.Spinner(color="info"),
                        html.P("Analyzing stats and designing...", className="mt-3 small text-white-50")
                    ], className="d-flex flex-column align-items-center justify-content-center", style={"height": "450px"}),
                    id={"type": "studio-element", "index": "preview-container"},
                    style={
                        "background": "#05050a",
                        "borderRadius": "16px",
                        "border": f"1px solid {_GLASS_BORDER}",
                        "minHeight": "450px",
                        "overflow": "hidden",
                    }
                ),
                
                dcc.Download(id="card-download"),
            ], width=8),

            # ---- Right: Sidebar Controls ----
            dbc.Col([
                html.Div([
                    _editor_toolbar(show_repropose=True),
                    _template_format_row(),
                    _template_library_section(),
                    html.Div(style=_DIVIDER_STYLE),
                    _advanced_element_editor(),
                    html.Div(style=_DIVIDER_STYLE),

                    # AI Caption
                    html.P("AI COPYWRITING", style=_SECTION_LABEL_STYLE),
                    dbc.InputGroup([
                        dbc.Select(id="card-caption-tone", options=[
                            {"label": "Professional", "value": "pro"},
                            {"label": "Hype / Fan", "value": "hype"},
                        ], value="pro", style={**_SELECT_STYLE, "maxWidth": "120px"}),
                        dbc.Button(html.I(className="bi bi-magic"), id="card-caption-btn", style=_SECONDARY_BTN_STYLE),
                    ]),
                    dbc.Textarea(id="card-caption-preview", className="mt-2", rows=2, style={**_SELECT_STYLE, "fontSize": "0.7rem"}),

                    html.Div(style=_DIVIDER_STYLE),
                    _photo_album_section(album),
                ], style={**_PANEL_STYLE, "overflowY": "auto", "maxHeight": "85vh"}),
            ], width=4),
        ]),
    ], id="card-editor-container", className="px-3 py-2")
