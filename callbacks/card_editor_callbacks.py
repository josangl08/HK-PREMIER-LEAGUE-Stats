# ABOUTME: Callbacks for the Card Editor Studio — handles template selection, live preview, AI generation (V2 + V3).
# ABOUTME: V3: maps state["progress"] to 5-phase labelled progress bar when CARD_AGENCY_V3 is active.

# Standard Library
import base64
import io
import json
import logging
import re
import threading
from pathlib import Path
from datetime import datetime, timezone

# Third-party
import dash_bootstrap_components as dbc
from dash import Input, Output, State, ALL, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate
from flask_login import current_user
from sqlalchemy import select

# Internal
from models.db_models import Player, UserPlayerLink, MatchHistory
from utils.db_engine import SessionFactory

logger = logging.getLogger(__name__)

_CARD_DATA_ROOT = Path("data/player_cards")
_ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}

# ---------------------------------------------------------------------------
# Background generation state — keyed by player_id
# "_generating": bool  |  "_progress": dict  |  "_result": dict
# ---------------------------------------------------------------------------
_GENERATION_JOBS: dict[str, dict] = {}

# Style Constants for Library UI
_GLASS_BORDER = "rgba(255,255,255,0.10)"
_TEXT_MUTED = "rgba(255,255,255,0.45)"


# ---------------------------------------------------------------------------
# Data Retrieval Helpers
# ---------------------------------------------------------------------------

def _get_player_id() -> str:
    try:
        return str(current_user.id) if current_user and current_user.is_authenticated else "unknown"
    except Exception:
        return "unknown"


def _get_player_display_name() -> str:
    """Returns the real name of the logged-in player from SQL by joining User -> Link -> Player."""
    user_id = _get_player_id()
    if user_id == "unknown":
        return "PLAYER NAME"
    
    session = SessionFactory()
    try:
        player = session.query(Player).join(UserPlayerLink).filter(UserPlayerLink.user_id == user_id).first()
        if player:
            return player.name
        if hasattr(current_user, "username"):
            return current_user.username
        return "PLAYER NAME"
    except Exception as e:
        logger.error(f"Error fetching player name: {e}")
        return "PLAYER NAME"
    finally:
        session.close()


def _get_player_profile(player_id: str) -> dict:
    """Returns a basic profile dict for the agent."""
    session = SessionFactory()
    try:
        player = session.query(Player).join(UserPlayerLink).filter(UserPlayerLink.user_id == player_id).first()
        if not player:
            player = session.get(Player, player_id)
        if not player: return {}
        return {
            "name": player.name,
            "position": player.position_main,
            "nationality": player.nationality,
            "age": player.age,
        }
    finally:
        session.close()


def _get_match_payload(milestone_id: str | None, milestones_data: list | None) -> dict:
    """Extracts match payload from milestones_data for the given milestone_id."""
    if not milestone_id or not milestones_data:
        return {}
    m = next((item for item in milestones_data if item.get("id") == milestone_id), None)
    return (m or {}).get("payload", {})


def _get_preset_modifiers(preset: str) -> dict:
    """Returns coordinate and scale maps for quick distribution."""
    presets = {
        "classic": {
            "headline": {"x": 50, "y": 15, "scale": 100, "visible": True},
            "home_logo": {"x": 12, "y": 12, "scale": 100, "visible": True},
            "away_logo": {"x": 88, "y": 12, "scale": 100, "visible": True},
            "match_info": {"x": 50, "y": 95, "scale": 100, "visible": True},
            "player_photo": {"x": 50, "y": 95, "scale": 100, "visible": True},
            "comp_badge": {"x": 88, "y": 88, "scale": 80, "visible": True},
            "player_name": {"x": 50, "y": 85, "scale": 100, "visible": True},
            "subtitle": {"x": 50, "y": 25, "scale": 100, "visible": True},
        },
        "hero": {
            "headline": {"x": 50, "y": 25, "scale": 140, "visible": True},
            "player_photo": {"x": 50, "y": 98, "scale": 120, "visible": True},
            "home_logo": {"x": 10, "y": 90, "scale": 80, "visible": True},
            "away_logo": {"x": 90, "y": 90, "scale": 80, "visible": True},
            "comp_badge": {"x": 10, "y": 10, "scale": 70, "visible": True},
            "player_name": {"x": 50, "y": 75, "scale": 120, "visible": True},
            "subtitle": {"x": 50, "y": 35, "scale": 100, "visible": True},
        },
        "split": {
            "headline": {"x": 25, "y": 15, "scale": 100, "visible": True},
            "home_logo": {"x": 15, "y": 35, "scale": 150, "visible": True},
            "away_logo": {"x": 35, "y": 35, "scale": 150, "visible": True},
            "player_photo": {"x": 72, "y": 95, "scale": 110, "visible": True},
            "comp_badge": {"x": 88, "y": 12, "scale": 100, "visible": True},
            "player_name": {"x": 72, "y": 80, "scale": 100, "visible": True},
            "subtitle": {"x": 25, "y": 25, "scale": 100, "visible": True},
        },
        "minimal": {
            "headline": {"x": 50, "y": 50, "scale": 180, "visible": True},
            "player_photo": {"x": 50, "y": 50, "scale": 100, "visible": False},
            "match_info": {"x": 50, "y": 10, "scale": 120, "visible": True},
            "home_logo": {"x": 50, "y": 90, "scale": 60, "visible": False},
            "away_logo": {"x": 50, "y": 90, "scale": 60, "visible": False},
            "player_name": {"x": 50, "y": 80, "scale": 100, "visible": True},
            "subtitle": {"x": 50, "y": 65, "scale": 100, "visible": True},
        },
        "derby": {
            "headline": {"x": 50, "y": 15, "scale": 120, "visible": True},
            "home_logo": {"x": 35, "y": 50, "scale": 220, "visible": True},
            "away_logo": {"x": 65, "y": 50, "scale": 220, "visible": True},
            "player_photo": {"x": 50, "y": 95, "scale": 100, "visible": False},
            "match_info": {"x": 50, "y": 85, "scale": 110, "visible": True},
            "comp_badge": {"x": 50, "y": 32, "scale": 100, "visible": True},
            "player_name": {"x": 50, "y": 70, "scale": 100, "visible": True},
            "subtitle": {"x": 50, "y": 25, "scale": 100, "visible": True},
        }
    }
    return presets.get(preset, presets["classic"])


def _build_preview_layout(editor_state: dict, photos_store: dict, milestones_data: list = None) -> html.Div:
    """Builds a professional Dash preview of the card with template-specific logic."""
    if not editor_state:
        return html.Div("No proposal loaded.", className="text-muted text-center p-4")

    proposal = editor_state.get("ai_proposal") or {}
    design = proposal.get("design") or {}
    raw_narrative = proposal.get("narrative") or {}
    narrative = raw_narrative if isinstance(raw_narrative, dict) else {}
    
    fmt = editor_state.get("format", "1:1")
    layers = design.get("layers") or {}
    headline_depth = editor_state.get("headline_depth") or proposal.get("headline_depth", "behind")
    glow_color = layers.get("glow_color", "var(--accent-cyan)")
    
    milestone_id = editor_state.get("milestone_id")
    match_payload = _get_match_payload(milestone_id, milestones_data) if milestones_data else {}

    # Background Logic
    bg_style = {}
    nanobana_bg = editor_state.get("nanobana_background_path")
    if nanobana_bg and Path(nanobana_bg).exists():
        with open(nanobana_bg, "rb") as f:
            src = "data:image/png;base64," + base64.b64encode(f.read()).decode()
            bg_style = {"backgroundImage": f"url({src})", "backgroundSize": "cover", "backgroundPosition": "center"}
    else:
        c1 = layers.get("base_color", ["#1a1a2e"])[0] if isinstance(layers.get("base_color"), list) else "#1a1a2e"
        bg_style = {"background": f"linear-gradient(135deg, {c1}, #000)"}

    aspect_style = {"1:1": "100%", "9:16": "177.77%", "16:9": "56.25%"}.get(fmt, "100%")
    modifiers = editor_state.get("layout_modifiers") or proposal.get("layout_modifiers", {})
    
    def get_style(key, default_x=50, default_y=50, default_scale=100, zIndex="10"):
        m = modifiers.get(key, {})
        if not m.get("visible", True): return {"display": "none"}
        x = m.get("x", default_x)
        y = m.get("y", default_y)
        scale = m.get("scale", default_scale) / 100.0
        return {
            "position": "absolute",
            "left": f"{x}%",
            "top": f"{y}%",
            "transform": f"translate(-50%, -50%) scale({scale})",
            "zIndex": zIndex, 
            "transition": "all 0.3s cubic-bezier(0.23, 1, 0.32, 1)"
        }

    # Photo logic: Prioritize bg_removed
    photo_src = None
    selected_idx = editor_state.get("selected_photo_idx")
    if selected_idx is not None:
        album = (photos_store or {}).get("album") or []
        for entry in album:
            if entry.get("idx") == selected_idx:
                path = entry.get("bg_removed") or entry.get("original")
                if path and Path(path).exists():
                    with open(path, "rb") as f:
                        photo_src = "data:image/png;base64," + base64.b64encode(f.read()).decode()
                break

    headline_text = str(narrative.get("headline", "MATCHDAY")).upper()
    player_name_display = str(_get_player_display_name()).upper()

    def img_el(src, key, def_x, def_y, def_sc, width="140px", zIndex="10"):
        if not src: return None
        return html.Img(src=src, style={**get_style(key, def_x, def_y, def_sc, zIndex=zIndex), "width": width, "objectFit": "contain"})

    inner_children = [
        html.Div(style={"position": "absolute", "inset": "0", "opacity": "0.1", 
                        "backgroundImage": "url('https://www.transparenttextures.com/patterns/asfalt-dark.png')",
                        "zIndex": "1"}),
        html.Div(headline_text, 
                 style={**get_style("headline", 50, 35, 200, zIndex="5"), 
                        "display": "none" if headline_depth == "front" else "block",
                        "color": "white", "fontWeight": "900", "fontSize": "6rem",
                        "opacity": "0.3" if headline_depth == "sandwich" else "0.8",
                        "textAlign": "center", "width": "100%", "fontFamily": "Impact, sans-serif"}),
        html.Div(style={**get_style("player_photo", 50, 95, 100, zIndex="7"), 
                        "width": "40%", "height": "10%", "background": "radial-gradient(ellipse, rgba(0,0,0,0.6) 0%, transparent 70%)",
                        "filter": "blur(15px)", "transform": "translate(-50%, 0) scale(1.5)"}) if photo_src else None,
        html.Img(src=photo_src, 
                 style={**get_style("player_photo", 50, 95, 100, zIndex="10"), 
                        "maxHeight": "95%", "maxWidth": "none", 
                        "filter": f"drop-shadow(0 0 20px {glow_color}44)"}) if photo_src else None,
        html.Div(headline_text, 
                 style={**get_style("headline", 50, 35, 200, zIndex="15"), 
                        "display": "block" if headline_depth in ["front", "sandwich"] else "none",
                        "color": "transparent" if headline_depth == "sandwich" else "white",
                        "WebkitTextStroke": f"2px white" if headline_depth == "sandwich" else "none",
                        "fontWeight": "900", "fontSize": "6rem", "textAlign": "center", "width": "100%", "fontFamily": "Impact, sans-serif"}),
        html.Div(style={"position": "absolute", "bottom": "0", "left": "0", "right": "0", "height": "30%",
                        "background": "linear-gradient(to top, rgba(0,0,0,0.8), transparent)", "zIndex": "20", "filter": "blur(20px)"}),
        html.Div(player_name_display, 
                 style={**get_style("player_name", 50, 85, 100, zIndex="30"), 
                        "color": "white", "fontWeight": "800", "fontSize": "1.5rem", 
                        "background": "black", "padding": "5px 25px", "borderRadius": "4px", 
                        "borderLeft": f"5px solid {glow_color}"}),
        img_el(match_payload.get("home_logo"), "home_logo", 15, 15, 100, width="120px", zIndex="30"),
        img_el(match_payload.get("away_logo"), "away_logo", 85, 15, 100, width="120px", zIndex="30"),
        img_el(match_payload.get("competition_logo"), "comp_badge", 88, 88, 80, width="80px", zIndex="30"),
    ]

    return html.Div(
        html.Div(inner_children, style={"position": "absolute", "inset": "0", **bg_style, "overflow": "hidden"}),
        style={"position": "relative", "width": "100%", "paddingTop": aspect_style, "borderRadius": "16px", "overflow": "hidden", "boxShadow": "0 30px 60px rgba(0,0,0,0.5)"}
    )


# ---------------------------------------------------------------------------
# Callback registration
# ---------------------------------------------------------------------------

def register_card_editor_callbacks(app):
    """Registers all Card Editor Studio callbacks."""

    # 1. Element Selection Layer logic
    @app.callback(
        Output("card-element-selector", "data"),
        Output("card-element-current-label", "children"),
        Input({"type": "card-element-name-click", "index": ALL}, "n_clicks"),
        State("card-element-selector", "data"),
        prevent_initial_call=True,
    )
    def update_active_element(n_clicks_list, current_active):
        if not ctx.triggered_id: return no_update, no_update
        triggered = ctx.triggered_id
        if isinstance(triggered, dict) and triggered.get("type") == "card-element-name-click":
            new_active = triggered.get("index")
            label = new_active.replace("_", " ").title()
            return new_active, label
        return no_update, no_update

    # 2. Combined State Update & AI Trigger signal
    @app.callback(
        Output("card-editor-state", "data", allow_duplicate=True),
        Output("card-ai-signal", "data", allow_duplicate=True),
        Input("card-repropose-btn", "n_clicks"),
        Input("card-generate-btn", "n_clicks"),
        Input("card-format-tabs", "active_tab"),
        Input("card-template-tabs", "active_tab"),
        Input("card-layout-presets", "value"),
        Input({"type": "card-photo-thumb", "index": ALL}, "n_clicks"),
        State("card-editor-state", "data"),
        prevent_initial_call='initial_duplicate',
    )
    def update_card_studio_state(n_repropose, n_generate, format_tab, template_tab, 
                                 preset_val, photo_clicks, current_state):
        if not current_state:
            return no_update, no_update
            
        state = dict(current_state)
        triggered_id = ctx.triggered_id
        
        # Initial call or no interaction
        if not triggered_id:
            # Sync initial format if provided by tabs but not in state
            if format_tab and state.get("format") != format_tab:
                state["format"] = format_tab
                return state, no_update
            return no_update, no_update

        # UI Changes
        if triggered_id == "card-format-tabs":
            state["format"] = format_tab
            return state, no_update
            
        if triggered_id == "card-template-tabs":
            state["template"] = template_tab
            return state, no_update

        if triggered_id == "card-layout-presets" and preset_val:
            state["layout_modifiers"] = _get_preset_modifiers(preset_val)
            return state, no_update

        if isinstance(triggered_id, dict) and triggered_id.get("type") == "card-photo-thumb":
            state["selected_photo_idx"] = triggered_id.get("index")
            return state, no_update

        # AI Trigger (Design or Download)
        if triggered_id in ["card-repropose-btn", "card-generate-btn"]:
            # If it's Download and we already have a result, don't trigger AI again
            if triggered_id == "card-generate-btn" and state.get("generated_card_path"):
                return no_update, no_update

            # Trigger AI process
            state["generating"] = True
            state["generated_card_path"] = None
            state["progress"] = {"phase": "Iniciando Agencia Elite...", "pct": 10}
            return state, True

        return no_update, no_update

    # 3. AI Background Thread Management (Consolidated)
    @app.callback(
        Output("card-editor-state", "data", allow_duplicate=True),
        Output("card-ai-signal", "data", allow_duplicate=True),
        Output("card-generation-interval", "disabled", allow_duplicate=True),
        Input("card-ai-signal", "data"),
        State("card-editor-state", "data"),
        State("milestones-data-store", "data"),
        prevent_initial_call=True,
    )
    def trigger_background_ai(signal_active, state, milestones_data):
        if not signal_active or not state:
            raise PreventUpdate

        player_id = _get_player_id()
        milestone_id = state.get("milestone_id")

        if (_GENERATION_JOBS.get(player_id) or {}).get("_generating"):
            return no_update, False, False

        _GENERATION_JOBS[player_id] = {
            "_generating": True,
            "_progress": {"phase": "Agencia Elite en marcha...", "pct": 15},
            "_result": None,
            "_error": None,
        }

        def _run_generation():
            from utils.card_design_agent import run_card_design_agent
            try:
                match_payload = _get_match_payload(milestone_id, milestones_data)
                match_payload["player_id"] = player_id
                match_payload["selected_photo_idx"] = state.get("selected_photo_idx")
                profile = _get_player_profile(player_id)
                
                # Progress callback to update global state
                def on_progress(p):
                    if player_id in _GENERATION_JOBS:
                        _GENERATION_JOBS[player_id]["_progress"] = p

                result = run_card_design_agent(
                    match_payload=match_payload,
                    player_profile=profile,
                    card_format=state.get("format", "9:16"),
                    on_progress=on_progress
                )
                
                if result.get("generated_card_path"):
                    _GENERATION_JOBS[player_id]["_result"] = {
                        "generated_card_path": result["generated_card_path"],
                        "agency_status": result.get("agency_status", "Success"),
                        "ai_proposal": result.get("design_strategy", {})
                    }
                else:
                    _GENERATION_JOBS[player_id]["_error"] = result.get("error", "Error en Nano Banana")
            except Exception as exc:
                logger.error(f"Card generation error: {exc}", exc_info=True)
                _GENERATION_JOBS[player_id]["_error"] = str(exc)
            finally:
                _GENERATION_JOBS[player_id]["_generating"] = False

        threading.Thread(target=_run_generation, daemon=True).start()
        return no_update, False, False 

    # 4. Polling interval
    @app.callback(
        Output("card-editor-state", "data", allow_duplicate=True),
        Output("card-generation-interval", "disabled", allow_duplicate=True),
        Input("card-generation-interval", "n_intervals"),
        State("card-editor-state", "data"),
        prevent_initial_call=True,
    )
    def poll_generation_progress(n_intervals, state):
        if not state: raise PreventUpdate
        player_id = _get_player_id()
        job = _GENERATION_JOBS.get(player_id)
        if not job: return no_update, True

        new_state = dict(state)
        if job.get("_progress"): new_state["progress"] = job["_progress"]

        if job.get("_generating"):
            return new_state, False

        result = job.get("_result")
        if result:
            new_state.update(result)
            new_state["generating"] = False
            _GENERATION_JOBS.pop(player_id, None)
            return new_state, True

        if job.get("_error"):
            new_state["agency_status"] = f"Error: {job['_error']}"
            new_state["generating"] = False
            _GENERATION_JOBS.pop(player_id, None)
            return new_state, True

        raise PreventUpdate

    # 5. Render Live Preview & Visor logic
    @app.callback(
        Output({"type": "studio-element", "index": ALL}, "children"),
        Output({"type": "studio-element", "index": ALL}, "style"),
        Output("card-templates-library", "children", allow_duplicate=True),
        Output("card-photo-album", "children", allow_duplicate=True),
        Input("card-editor-state", "data"),
        State("player-photos-store", "data"),
        State("milestones-data-store", "data"),
        prevent_initial_call='initial_duplicate',
    )
    def render_editor_updates(editor_state, photos_store, milestones_data):
        if not editor_state or not editor_state.get("editor_active"):
            raise PreventUpdate

        state = editor_state
        num_targets = 0
        if ctx.outputs_list and len(ctx.outputs_list) > 0:
            num_targets = len(ctx.outputs_list[0])
        
        album = (photos_store or {}).get("album") or []
        sel_idx = state.get("selected_photo_idx")
        album_grid = _build_album_grid(album, selected_idx=sel_idx)

        # Aspect Ratio logic
        fmt = state.get("format", "9:16")
        aspect_style = {"1:1": "100%", "9:16": "177.77%", "16:9": "56.25%"}.get(fmt, "177.77%")
        
        container_style = {
            "background": "#05050a",
            "borderRadius": "16px",
            "border": "1px solid rgba(255,255,255,0.1)",
            "width": "100%",
            "paddingTop": aspect_style,
            "position": "relative",
            "overflow": "hidden",
            "boxShadow": "0 25px 50px rgba(0,0,0,0.6)",
            "transition": "padding-top 0.4s cubic-bezier(0.23, 1, 0.32, 1)"
        }

        # Case: Generating
        if state.get("generating"):
            progress = state.get("progress") or {}
            content = html.Div([
                html.I(className="bi bi-stars", style={"fontSize": "2.5rem", "color": "#00f2ff", "marginBottom": "16px"}),
                html.P(progress.get("phase", "Generando..."), className="text-white fw-bold mb-3 small"),
                dbc.Progress(value=progress.get("pct", 15), max=100, striped=True, animated=True, color="info", style={"height": "6px", "width": "200px"}),
            ], className="d-flex flex-column align-items-center justify-content-center h-100",
               style={"position": "absolute", "inset": "0", "background": "rgba(0,0,0,0.8)"})
            return [content] * num_targets, [container_style] * num_targets, no_update, album_grid

        # Case: Final Result
        card_path = state.get("generated_card_path")
        if card_path and Path(card_path).exists():
            with open(card_path, "rb") as f:
                src = "data:image/png;base64," + base64.b64encode(f.read()).decode()
            final_style = {**container_style, "paddingTop": "0", "height": "auto"}
            img = html.Img(src=src, style={"width": "100%", "display": "block", "borderRadius": "16px"})
            return [img] * num_targets, [final_style] * num_targets, no_update, album_grid

        # Case: Live Preview
        preview_div = _build_preview_layout(state, photos_store, milestones_data)
        return [preview_div.children] * num_targets, [container_style] * num_targets, no_update, album_grid

    # 6. Upload
    @app.callback(
        Output("player-photos-store", "data"),
        Output("card-photo-album", "children"),
        Output("card-upload-status", "children"),
        Output("card-editor-state", "data", allow_duplicate=True),
        Output("card-ai-signal", "data", allow_duplicate=True),
        Input("card-photo-upload", "contents"),
        State("card-photo-upload", "filename"),
        State("player-photos-store", "data"),
        State("card-editor-state", "data"),
        prevent_initial_call=True,
    )
    def upload_player_photo(contents, filename, photos_store, editor_state):
        if not contents: return no_update, no_update, no_update, no_update, no_update
        player_id = _get_player_id()
        try:
            header, data = contents.split(",", 1)
            image_bytes = base64.b64decode(data)
            from utils.image_processing import save_player_photo
            entry = save_player_photo(player_id, image_bytes, filename or "upload.png")
            store = dict(photos_store or {})
            album = list(store.get("album") or [])
            album.append(entry)
            store["album"] = album
            
            new_state = dict(editor_state or {})
            new_state["selected_photo_idx"] = entry["idx"]
            new_state["generating"] = False
            new_state["generated_card_path"] = None
            
            return store, _build_album_grid(album, selected_idx=entry["idx"]), dbc.Alert("Photo uploaded! Click Design to generate your card.", color="success", duration=3000), new_state, no_update
        except Exception as e:
            return no_update, no_update, dbc.Alert(f"Error: {e}", color="danger"), no_update, no_update

    # 7. PNG Download
    @app.callback(
        Output("card-download", "data"),
        Output("timeline-pagination-store", "data", allow_duplicate=True),
        Input("card-generate-btn", "n_clicks"),
        State("card-editor-state", "data"),
        State("timeline-pagination-store", "data"),
        prevent_initial_call=True,
    )
    def download_generated_card(n_clicks, state, pagination_store):
        if not n_clicks: return no_update, no_update
        path_str = state.get("generated_card_path")
        if path_str and Path(path_str).exists():
            milestone_id = state.get("milestone_id", "unknown")
            store = dict(pagination_store or {})
            generated = dict(store.get("generated", {}))
            generated[milestone_id] = True
            store["generated"] = generated
            return dcc.send_file(path_str), store
        return no_update, no_update


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_album_grid(album: list, selected_idx=None) -> html.Div:
    if not album: return html.P("No photos yet.", className="text-muted small")
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
                    "margin": "2px", "cursor": "pointer", "borderRadius": "4px",
                    "border": f"2px solid {'#00f2ff' if is_selected else 'transparent'}",
                    "boxShadow": "0 0 8px rgba(0,242,255,0.6)" if is_selected else "none",
                    "transition": "border 0.15s",
                }
            ))
    return html.Div(thumbs, className="d-flex flex-wrap")


def _build_template_library_ui(player_id: str) -> list:
    return [html.P("Saved styles.", className="text-muted small")]
