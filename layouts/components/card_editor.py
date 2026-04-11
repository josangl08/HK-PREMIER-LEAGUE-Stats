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

def create_pre_game_card_studio(milestone_id, match_context, proposals, initial_preview=None, album=None, selected_idx=None):
    """Renders the simplified Pre-Game Card Studio (Imagen 3 full-card generation)."""
    return _create_card_studio_layout(milestone_id, match_context, album, studio_type="pre-match", selected_idx=selected_idx)


def _create_card_studio_layout(milestone_id, match_context, album, studio_type="pre-match", selected_idx=None):
    """Shared layout for both pre-match and post-match card studios."""
    home = match_context.get("home_team") or "—"
    away = match_context.get("away_team") or "—"
    competition = match_context.get("competition") or ""
    date_str = match_context.get("date") or ""

    return html.Div([
        _save_toast(),
        dcc.Download(id="card-download"),

        dbc.Row([
            # ---- Left: Card Preview (8 cols) ----
            dbc.Col([
                # Header
                html.Div([
                    html.Div([
                        html.I(className="bi bi-stars me-2", style={"color": _ACCENT_CYAN}),
                        html.Span("AI Card Studio", style={"color": "white", "fontWeight": "700", "fontSize": "0.9rem"}),
                    ]),
                    html.Div([
                        html.Span(f"{home} vs {away}", style={"color": _ACCENT_CYAN, "fontSize": "0.75rem", "fontWeight": "600"}),
                        html.Span(f"  ·  {competition}", style={"color": "rgba(255,255,255,0.4)", "fontSize": "0.7rem"}) if competition else None,
                        html.Span(f"  ·  {date_str}", style={"color": "rgba(255,255,255,0.4)", "fontSize": "0.7rem"}) if date_str else None,
                    ]),
                ], className="mb-3 d-flex align-items-center justify-content-between"),

                # Preview container — populated by render_editor_updates callback
                html.Div(
                    html.Div([
                        html.I(className="bi bi-stars",
                               style={"fontSize": "2.5rem", "color": _ACCENT_CYAN, "marginBottom": "12px"}),
                        html.P("Select format and photos, then press Design", className="text-white-50 small mb-1"),
                        html.P("AI will generate a unique matchday card", style={"fontSize": "0.7rem", "color": "rgba(255,255,255,0.25)"}),
                    ], className="d-flex flex-column align-items-center justify-content-center h-100",
                       style={"position": "absolute", "inset": "0"}),
                    id={"type": "studio-element", "index": "preview-container"},
                    style={
                        "background": "#05050a",
                        "borderRadius": "16px",
                        "border": f"1px solid {_GLASS_BORDER}",
                        "width": "100%",
                        "paddingTop": "177.77%", # Default 9:16
                        "position": "relative",
                        "overflow": "hidden",
                        "boxShadow": "0 25px 50px rgba(0,0,0,0.6)",
                    },
                ),
            ], width=8),

            # ---- Right: Simple Controls (4 cols) ----
            dbc.Col([
                html.Div([
                    # Action buttons
                    html.Div([
                        dbc.Button(
                            [html.I(className="bi bi-stars me-1"), "Design"],
                            id="card-repropose-btn",
                            style={**_GENERATE_BTN_STYLE, "fontSize": "0.7rem", "width": "100%"},
                            n_clicks=0,
                            className="mb-2",
                        ),
                        dbc.Button(
                            [html.I(className="bi bi-download me-1"), "Download Card"],
                            id="card-generate-btn",
                            color="success",
                            style={**_SECONDARY_BTN_STYLE, "fontSize": "0.7rem", "width": "100%"},
                            n_clicks=0,
                        ),
                    ], className="mb-3"),

                    html.Hr(style=_DIVIDER_STYLE),

                    # Format selector
                    html.P("FORMAT", style=_SECTION_LABEL_STYLE),
                    dbc.Tabs(
                        [
                            dbc.Tab(label="9:16", tab_id="9:16", label_style=_TAB_STYLE, active_label_style=_TAB_ACTIVE_STYLE),
                            dbc.Tab(label="1:1", tab_id="1:1", label_style=_TAB_STYLE, active_label_style=_TAB_ACTIVE_STYLE),
                            dbc.Tab(label="16:9", tab_id="16:9", label_style=_TAB_STYLE, active_label_style=_TAB_ACTIVE_STYLE),
                        ],
                        id="card-format-tabs",
                        active_tab="9:16",
                        className="justify-content-start mb-3",
                    ),

                    html.Hr(style=_DIVIDER_STYLE),

                    # My Photos
                    html.P("MY PHOTOS", style=_SECTION_LABEL_STYLE),
                    html.P(
                        "Upload a photo to include yourself in the design. "
                        "Best results: plain background, full body.",
                        style={"fontSize": "0.68rem", "color": "rgba(255,255,255,0.4)", "marginBottom": "8px"},
                    ),
                    html.Div(
                        _build_album_grid_static(album, selected_idx=selected_idx) if album else html.P("No photos yet", className="text-muted small"),
                        id="card-photo-album",
                        style={"maxHeight": "120px", "overflowY": "auto", "marginBottom": "8px"},
                    ),
                    dcc.Upload(
                        id="card-photo-upload",
                        children=html.Div([
                            html.I(className="bi bi-cloud-arrow-up me-2"),
                            "Upload Photo",
                        ]),
                        style=_UPLOAD_STYLE,
                        multiple=False,
                    ),
                    html.Div(id="card-upload-status", className="mt-1"),

                    # Hidden elements required by existing callbacks
                    dcc.Store(id="card-element-selector", data="headline"),
                    dcc.Store(id="card-ai-signal", data=False), # New signal store
                    dcc.Interval(id="card-generation-interval", interval=4000, n_intervals=0, disabled=True),
                    # Hidden tabs required by update_card_editor_state callback
                    html.Div(dbc.Tabs(id="card-template-tabs", active_tab="A"), style={"display": "none"}),
                    html.Div(id="card-templates-library", style={"display": "none"}),
                    # Hidden sliders (callbacks reference them)
                    html.Div([
                        dcc.Slider(id="card-element-x-slider", min=0, max=100, step=1, value=50),
                        dcc.Slider(id="card-element-y-slider", min=0, max=100, step=1, value=50),
                        dcc.Slider(id="card-element-scale-slider", min=10, max=250, step=5, value=100),
                        dbc.Select(id="card-layout-presets", options=[]),
                    ], style={"display": "none"}),
                ], style={**_PANEL_STYLE, "overflowY": "auto", "maxHeight": "85vh"}),
            ], width=4),
        ]),
    ], id="card-editor-container", className="px-3 py-2")


def _build_album_grid_static(album: list, selected_idx=None):
    """Static album grid with clickable thumbnails and selection border."""
    if not album:
        return html.P("No photos yet", className="text-muted small")
    thumbs = []
    for entry in album:
        idx = entry.get("idx", 0)
        path = entry.get("bg_removed") or entry.get("original")
        if path and Path(path).exists():
            with open(path, "rb") as f:
                src = "data:image/png;base64," + base64.b64encode(f.read()).decode()
            is_selected = (selected_idx is not None and idx == selected_idx)
            thumbs.append(html.Img(
                src=src,
                id={"type": "card-photo-thumb", "index": idx},
                style={
                    "width": "60px", "height": "60px", "objectFit": "cover",
                    "margin": "2px", "borderRadius": "4px", "cursor": "pointer",
                    "border": f"2px solid {'#00f2ff' if is_selected else 'transparent'}",
                    "boxShadow": "0 0 8px rgba(0,242,255,0.6)" if is_selected else "none",
                    "transition": "border 0.15s",
                }
            ))
    return html.Div(thumbs, className="d-flex flex-wrap")


# ---------------------------------------------------------------------------
# Performance Card Studio (Post-Match)
# ---------------------------------------------------------------------------

def create_performance_card_studio(milestone_id, match_context, proposals, initial_preview=None, album=None, selected_idx=None):
    """Renders the simplified Performance Card Studio (Imagen 3 full-card generation)."""
    return _create_card_studio_layout(milestone_id, match_context, album, studio_type="post-match", selected_idx=selected_idx)
