# ABOUTME: Callbacks for the Card Editor Studio — handles template selection, live preview,
# ABOUTME: manual layer positioning, AI insights, PNG generation, and asset management.

# Standard Library
import base64
import io
import json
import logging
import re
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
from utils.card_design_agent import DesignBrief # Added import

logger = logging.getLogger(__name__)

_CARD_DATA_ROOT = Path("data/player_cards")
_ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}

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
        # Join UserPlayerLink to Player to get the actual name from the bio profile
        player = session.query(Player).join(UserPlayerLink).filter(UserPlayerLink.user_id == user_id).first()
        if player:
            return player.name
        
        # Fallback to current_user name if it exists but no link
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
        # Note: here player_id might be the user_id or player slug. 
        # For simplicity in this session context, we try resolving via user_id first.
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


def _get_player_history(player_id: str) -> list:
    """Returns recent match history for context."""
    session = SessionFactory()
    try:
        # Resolve player first
        player = session.query(Player).join(UserPlayerLink).filter(UserPlayerLink.user_id == player_id).first()
        pid = player.id if player else player_id
        
        stmt = select(MatchHistory).where(MatchHistory.player_id == pid).order_by(MatchHistory.date.desc()).limit(5)
        matches = session.execute(stmt).scalars().all()
        return [
            {
                "date": m.date.strftime("%Y-%m-%d"),
                "opponent": m.opponent,
                "type": "post-match",
                "payload": {
                    "minutes_played": m.minutes_played,
                    "goals": m.goals,
                    "assists": m.assists,
                    "yellow_cards": m.yellow_cards,
                    "red_cards": m.red_cards,
                    **(m.raw_data or {})
                }
            } for m in matches
        ]
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
    
    # Robust narrative extraction
    raw_narrative = proposal.get("narrative") or {}
    narrative = raw_narrative if isinstance(raw_narrative, dict) else {}
    
    fmt = editor_state.get("format", "1:1")
    tmpl = editor_state.get("template", "A") 
    layers = design.get("layers") or {}
    
    # NEW: Agency Depth Controls
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
        
        style = {
            "position": "absolute",
            "left": f"{x}%",
            "top": f"{y}%",
            "transform": f"translate(-50%, -50%) scale({scale})",
            "zIndex": zIndex, 
            "transition": "all 0.3s cubic-bezier(0.23, 1, 0.32, 1)"
        }
        return style

    # Photo logic
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

    # BUILD THE SANDWICH (Match CSS to Pillow Layers)
    inner_children = [
        # 1. Background Grain
        html.Div(style={"position": "absolute", "inset": "0", "opacity": "0.1", 
                        "backgroundImage": "url('https://www.transparenttextures.com/patterns/asfalt-dark.png')",
                        "zIndex": "1"}),
        
        # 2. BG Typography (Behind Player)
        html.Div(headline_text, 
                 style={**get_style("headline", 50, 35, 200, zIndex="5"), 
                        "display": "none" if headline_depth == "front" else "block",
                        "color": "white", "fontWeight": "900", "fontSize": "6rem",
                        "opacity": "0.3" if headline_depth == "sandwich" else "0.8",
                        "textAlign": "center", "width": "100%", "fontFamily": "Impact, sans-serif"}),

        # 3. Player Shadow Pass
        html.Div(style={**get_style("player_photo", 50, 95, 100, zIndex="7"), 
                        "width": "40%", "height": "10%", "background": "radial-gradient(ellipse, rgba(0,0,0,0.6) 0%, transparent 70%)",
                        "filter": "blur(15px)", "transform": "translate(-50%, 0) scale(1.5)"}) if photo_src else None,

        # 4. The Player Hero
        html.Img(src=photo_src, 
                 style={**get_style("player_photo", 50, 95, 100, zIndex="10"), 
                        "maxHeight": "95%", "maxWidth": "none", 
                        "filter": f"drop-shadow(0 0 20px {glow_color}44)"}) if photo_src else None,

        # 5. FG Typography (Front Pass - Sandwich Effect)
        html.Div(headline_text, 
                 style={**get_style("headline", 50, 35, 200, zIndex="15"), 
                        "display": "block" if headline_depth in ["front", "sandwich"] else "none",
                        "color": "transparent" if headline_depth == "sandwich" else "white",
                        "WebkitTextStroke": f"2px white" if headline_depth == "sandwich" else "none",
                        "fontWeight": "900", "fontSize": "6rem", "textAlign": "center", "width": "100%", "fontFamily": "Impact, sans-serif"}),

        # 6. Atmospheric Glue (Front Smoke)
        html.Div(style={"position": "absolute", "bottom": "0", "left": "0", "right": "0", "height": "30%",
                        "background": "linear-gradient(to top, rgba(0,0,0,0.8), transparent)", "zIndex": "20", "filter": "blur(20px)"}),

        # 7. UI Elements (Logos & Name Plate)
        html.Div(player_name_display, 
                 style={**get_style("player_name", 50, 85, 100, zIndex="30"), 
                        "color": "white", "fontWeight": "800", "fontSize": "1.5rem", 
                        "background": "black", "padding": "5px 25px", "borderRadius": "4px", 
                        "borderLeft": f"5px solid {glow_color}"}),

        # Logos
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

    # ------------------------------------------------------------------ #
    # Element Selection                                                  #
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    # Update state from all UI controls                                  #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("card-editor-state", "data"),
        Input("card-template-tabs", "active_tab"),
        Input("card-format-tabs", "active_tab"),
        Input("card-element-x-slider", "value"),
        Input("card-element-y-slider", "value"),
        Input("card-element-scale-slider", "value"),
        Input("card-layout-presets", "value"),
        Input({"type": "card-photo-thumb", "index": ALL}, "n_clicks"),
        Input({"type": "card-element-toggle", "index": ALL}, "value"),
        Input({"type": "card-user-template", "index": ALL}, "n_clicks"),
        Input({"type": "card-concept-btn", "index": ALL}, "n_clicks"),
        State("card-element-selector", "data"),
        State("card-editor-state", "data"),
        prevent_initial_call=True,
    )
    def update_card_editor_state(active_tab, format_tab, x_val, y_val, scale_val, 
                                 preset_val, photo_clicks, toggle_values, 
                                 template_clicks, concept_clicks, selected_element, current_state):
        state = dict(current_state or {})
        triggered_id = ctx.triggered_id

        if active_tab: state["template"] = active_tab
        if format_tab: state["format"] = format_tab

        # Handle Concept Switching
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "card-concept-btn":
            idx = triggered_id.get("index")
            proposals = state.get("ai_proposals", [])
            if idx < len(proposals):
                state["ai_proposal_idx"] = idx
                state["ai_proposal"] = proposals[idx]
                # Reset layout modifiers to the proposal's defaults
                state["layout_modifiers"] = proposals[idx].get("layout_modifiers", {})
                state["template"] = proposals[idx].get("design", {}).get("template", "A")
                
                # Regenerate background if needed (optional optimization: cache backgrounds)
                state["needs_background_refresh"] = True 
            return state

        # Handle Photo Selection
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "card-photo-thumb":
            state["selected_photo_idx"] = triggered_id.get("index")
            return state

        # Handle Template Library Selection
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "card-user-template":
            tmpl_id = triggered_id.get("index")
            player_id = _get_player_id()
            tmpl_path = _CARD_DATA_ROOT / player_id / "templates" / f"{tmpl_id}.json"
            if tmpl_path.exists():
                try:
                    with open(tmpl_path, "r") as f:
                        saved_tmpl = json.load(f)
                        # Apply common elements: layout_modifiers, template (A/B/C)
                        state["layout_modifiers"] = saved_tmpl.get("layout_modifiers", {})
                        state["template"] = saved_tmpl.get("template", "A")
                        return state
                except Exception as e:
                    logger.error(f"Error applying template: {e}")

        # Handle Presets
        if triggered_id == "card-layout-presets" and preset_val:
            state["layout_modifiers"] = _get_preset_modifiers(preset_val)
            return state

        # Handle Individual Toggles
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "card-element-toggle":
            target = triggered_id.get("index")
            # Find the value for this specific toggle
            triggered_input = ctx.triggered[0]
            val = triggered_input["value"]
            
            if "layout_modifiers" not in state: state["layout_modifiers"] = {}
            if target not in state["layout_modifiers"]: 
                state["layout_modifiers"][target] = {"x": 50, "y": 50, "scale": 100}
            state["layout_modifiers"][target]["visible"] = val
            return state

        # Handle Sliders for the ACTIVE element
        if triggered_id in ["card-element-x-slider", "card-element-y-slider", "card-element-scale-slider"]:
            if "layout_modifiers" not in state: state["layout_modifiers"] = {}
            if selected_element not in state["layout_modifiers"]:
                state["layout_modifiers"][selected_element] = {"visible": True}
            
            state["layout_modifiers"][selected_element].update({
                "x": x_val, "y": y_val, "scale": scale_val
            })

        return state

    # ------------------------------------------------------------------ #
    # Sync Sliders when Active Element changes                           #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("card-element-x-slider", "value"),
        Output("card-element-y-slider", "value"),
        Output("card-element-scale-slider", "value"),
        Input("card-element-selector", "data"),
        State("card-editor-state", "data"),
    )
    def sync_sliders_with_selection(selected_element, editor_state):
        state = editor_state or {}
        proposal = state.get("ai_proposal") or {}
        
        mods = state.get("layout_modifiers", {}).get(selected_element)
        if not mods:
            mods = (proposal.get("layout_modifiers") or {}).get(selected_element)
            
        if not mods:
            return 50, 50, 100
        
        return mods.get("x", 50), mods.get("y", 50), mods.get("scale", 100)

    # ------------------------------------------------------------------ #
    # Save Template to Library with Thumbnail                            #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("card-save-toast", "is_open"),
        Output("card-templates-library", "children"),
        Input("card-save-draft-btn", "n_clicks"),
        State("card-editor-state", "data"),
        State("player-photos-store", "data"),
        State("milestones-data-store", "data"),
        prevent_initial_call=True,
    )
    def save_template_to_library(n_clicks, state, photos_store, milestones_data):
        if not n_clicks or not state: return no_update, no_update
        
        player_id = _get_player_id()
        milestone_id = state.get("milestone_id", "unknown")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        tmpl_id = f"template_{ts}"
        tmpl_dir = _CARD_DATA_ROOT / player_id / "templates"
        tmpl_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Save JSON
        with open(tmpl_dir / f"{tmpl_id}.json", "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
            
        # 2. Generate Thumbnail (Pillow)
        try:
            from utils.card_renderer import compose_card
            photo_path = None
            sel_idx = state.get("selected_photo_idx")
            if sel_idx is not None:
                album = (photos_store or {}).get("album") or []
                for entry in album:
                    if entry.get("idx") == sel_idx:
                        photo_path = entry.get("bg_removed") or entry.get("original")
                        break
            
            # Render a smaller version for the library
            compose_card(
                design_brief=state.get("ai_proposal", {}),
                player_photo_path=photo_path,
                output_dir=str(tmpl_dir),
                format=state.get("format", "1:1"),
                background_image_path=state.get("nanobana_background_path"),
                match_payload=_get_match_payload(milestone_id, milestones_data),
                player_name=str(_get_player_display_name()),
                output_filename=f"{tmpl_id}.png" # Name it same as JSON
            )
        except Exception as e:
            logger.error(f"Thumbnail generation failed: {e}")
            
        return True, _build_template_library_ui(player_id)

    # ------------------------------------------------------------------ #
    # Render Templates Library and Live Preview                          #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output({"type": "studio-element", "index": ALL}, "children"),
        Output("stage-decision-nodes", "children", allow_duplicate=True),
        Output("card-templates-library", "children", allow_duplicate=True),
        Output("card-generation-status", "children"),
        Input("card-editor-state", "data"),
        State("player-photos-store", "data"),
        State("milestones-data-store", "data"),
        prevent_initial_call=True,
    )
    def render_editor_updates(editor_state, photos_store, milestones_data):
        state = editor_state or {}
        if not state.get("editor_active"):
            raise PreventUpdate
            
        num_targets = len(ctx.outputs_list[0]) if ctx.outputs_list and len(ctx.outputs_list) > 0 else 0
        player_id = _get_player_id()
        agency_status = state.get("agency_status", "")
        
        # 1. Templates UI
        library_ui = _build_template_library_ui(player_id)
        
        # 2. Preview UI
        from layouts.components.card_editor import _ai_insights_container
        
        if not state.get("ai_proposal") and state.get("needs_ai"):
            loading_view = html.Div([
                dbc.Spinner(color="info", size="lg"),
                html.P(agency_status or "We are designing your card...", className="mt-3 small text-white-50")
            ], className="d-flex flex-column align-items-center justify-content-center", style={"height": "400px"})
            return [loading_view] * num_targets, _ai_insights_container(None), library_ui, agency_status

        preview = _build_preview_layout(state, photos_store or {}, milestones_data)
        proposal = state.get("ai_proposal") or {}
        
        # Pass the full narrative (report, caption, hashtags) to the intelligence container
        narrative = proposal.get("narrative") or {}
        
        return [preview] * num_targets, _ai_insights_container(narrative), library_ui, agency_status

    # ------------------------------------------------------------------ #
    # Copy Instagram Caption to Clipboard                                #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("instagram-caption-clipboard", "content"),
        Input("copy-caption-btn", "n_clicks"),
        State("instagram-caption-text", "children"),
        prevent_initial_call=True,
    )
    def copy_instagram_caption(n_clicks, caption):
        if not n_clicks: return no_update
        return caption

    # ------------------------------------------------------------------ #
    # Async AI Generation & Background Refresh                           #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("card-editor-state", "data", allow_duplicate=True),
        Input("card-editor-state", "data"),
        State("milestones-data-store", "data"),
        prevent_initial_call=True,
    )
    def trigger_background_ai(state, milestones_data):
        if not state: return no_update
        
        needs_full_ai = state.get("needs_ai")
        needs_bg_only = state.get("needs_background_refresh")
        
        if not needs_full_ai and not needs_bg_only: return no_update

        milestone_id = state.get("milestone_id")
        card_type = state.get("card_type", "pre-match")
        player_id = _get_player_id()
        
        new_state = dict(state)
        new_state["needs_ai"] = False
        new_state["needs_background_refresh"] = False

        try:
            from utils.nanobana_service import generate_nanobana_background, save_nanobana_background
            
            # 1. Full AI Agency Run (Proposals + Initial BG)
            if needs_full_ai:
                from utils.card_design_agent import run_card_design_agent
                from callbacks.player_portal_callbacks import _get_team_colors
                
                match_payload = _get_match_payload(milestone_id, milestones_data)
                match_payload["player_id"] = player_id
                
                home_colors = _get_team_colors(match_payload.get("home_team", ""))
                away_colors = _get_team_colors(match_payload.get("away_team", ""))
                team_colors = {"home": home_colors, "away": away_colors, "player_team": home_colors}

                profile = _get_player_profile(player_id)
                history = _get_player_history(player_id)

                # Detect if player has photos for the agent
                album_data = (state.get("context") or {}).get("available_photos", [])
                if not album_data:
                    from utils.image_processing import get_player_album
                    album_data = get_player_album(player_id)
                
                has_photos = len(album_data) > 0

                proposals = run_card_design_agent(
                    match_payload=match_payload, player_profile=profile,
                    team_colors=team_colors, player_history=history,
                    has_player_photo=has_photos, card_type=card_type
                )
                
                if proposals:
                    new_state["ai_proposals"] = proposals
                    new_state["ai_proposal_idx"] = 0
                    new_state["ai_proposal"] = proposals[0]
                    
                    # CRITICAL FIX: Sync the UI state with the agent's first proposal
                    new_state["layout_modifiers"] = proposals[0].get("layout_modifiers", {})
                    new_state["template"] = proposals[0].get("design", {}).get("template", "A")
                    
                    if new_state.get("selected_photo_idx") is None:
                        # Ensure we auto-select the photo the agent suggests
                        new_state["selected_photo_idx"] = proposals[0].get("selected_photo_idx", 0)
                    
                    prompt = proposals[0].get("nanobana_background_prompt")
                    if prompt:
                        bg_bytes = generate_nanobana_background(prompt)
                        if bg_bytes:
                            bg_path = save_nanobana_background(milestone_id, bg_bytes)
                            new_state["nanobana_background_path"] = bg_path

            # 2. Background-only Refresh (on concept switch)
            elif needs_bg_only:
                proposal = state.get("ai_proposal", {})
                prompt = proposal.get("nanobana_background_prompt")
                if prompt:
                    bg_bytes = generate_nanobana_background(prompt)
                    if bg_bytes:
                        # Append index to avoid cache collisions
                        idx = state.get("ai_proposal_idx", 0)
                        bg_path = save_nanobana_background(f"{milestone_id}_{idx}", bg_bytes)
                        new_state["nanobana_background_path"] = bg_path

            return new_state
        except Exception as exc:
            logger.error(f"trigger_background_ai error: {exc}")
            return new_state

    # ------------------------------------------------------------------ #
    # Asset Library Upload                                               #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("player-photos-store", "data"),
        Output("card-photo-album", "children"),
        Output("card-upload-status", "children"),
        Output("card-editor-state", "data", allow_duplicate=True),
        Input("card-photo-upload", "contents"),
        State("card-photo-upload", "filename"),
        State("player-photos-store", "data"),
        State("card-editor-state", "data"),
        prevent_initial_call=True,
    )
    def upload_player_photo(contents, filename, photos_store, editor_state):
        if not contents: return no_update, no_update, no_update, no_update
        player_id = _get_player_id()
        try:
            header, data = contents.split(",", 1)
            import base64
            image_bytes = base64.b64decode(data)
            from utils.image_processing import save_player_photo
            entry = save_player_photo(player_id, image_bytes, filename or "upload.png")
            store = dict(photos_store or {})
            album = list(store.get("album") or [])
            album.append(entry)
            store["album"] = album
            new_state = dict(editor_state or {})
            new_state["selected_photo_idx"] = entry["idx"]
            return store, _build_album_grid(album), dbc.Alert("Photo ready!", color="success", duration=2000), new_state
        except Exception as e:
            return no_update, no_update, dbc.Alert(f"Upload failed: {e}", color="danger"), no_update

    # ------------------------------------------------------------------ #
    # AI Caption Regeneration                                            #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("card-caption-preview", "value"),
        Input("card-caption-btn", "n_clicks"),
        State("card-caption-tone", "value"),
        State("card-editor-state", "data"),
        prevent_initial_call=True,
    )
    def regenerate_ai_caption(n_clicks, tone, state):
        if not n_clicks: return no_update
        
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            model_name = "gemini-2.0-flash"
            llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.9)
            
            proposal = state.get("ai_proposal", {})
            narrative = proposal.get("narrative", {})
            headline = narrative.get("headline", "MATCHDAY")
            story = narrative.get("supporting_story", "")
            
            prompt = f"""
            Write a single, highly engaging Instagram caption for a professional football match card.
            HEADLINE: {headline}
            STORY: {story}
            TONE: {tone} (pro = elite & focused, hype = energetic & fan-centric)
            
            Include relevant emojis. Keep it under 200 characters. No hashtags (they will be added separately).
            """
            
            response = llm.invoke(prompt)
            return response.content if hasattr(response, "content") else str(response)
            
        except Exception as e:
            logger.error(f"Caption regeneration failed: {e}")
            return "Caption generation unavailable. Try again later."

    # ------------------------------------------------------------------ #
    # Generate PNG                                                       #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("card-download", "data"),
        Output("card-generation-trigger", "data"),
        Output("timeline-pagination-store", "data", allow_duplicate=True),
        Input("card-generate-btn", "n_clicks"),
        State("card-editor-state", "data"),
        State("player-photos-store", "data"),
        State("timeline-pagination-store", "data"),
        State("milestones-data-store", "data"),
        prevent_initial_call=True,
    )
    def generate_and_download_png(n_clicks, editor_state, photos_store, pagination_store, milestones_data):
        if not n_clicks: return no_update, no_update, no_update
        state = editor_state or {}
        milestone_id = state.get("milestone_id", "unknown")
        player_id = _get_player_id()
        from utils.card_renderer import compose_card
        photo_path = None
        sel_idx = state.get("selected_photo_idx")
        if sel_idx is not None:
            album = (photos_store or {}).get("album") or []
            for entry in album:
                if entry.get("idx") == sel_idx:
                    photo_path = entry.get("bg_removed") or entry.get("original")
                    break
        try:
            png_path = compose_card(
                design_brief=state.get("ai_proposal", {}),
                player_photo_path=photo_path,
                output_dir=str(_CARD_DATA_ROOT / player_id / milestone_id),
                format=state.get("format", "1:1"),
                background_image_path=state.get("nanobana_background_path"),
                match_payload=_get_match_payload(milestone_id, milestones_data),
                player_name=str(_get_player_display_name())
            )
            store = dict(pagination_store or {})
            generated = dict(store.get("generated", {}))
            generated[milestone_id] = True
            store["generated"] = generated
            return dcc.send_file(str(png_path)), {"generated": True}, store
        except Exception as e:
            logger.error(f"PNG Generation failed: {e}")
            return no_update, no_update, no_update


# ---------------------------------------------------------------------------
# Helpers for Dynamic UI
# ---------------------------------------------------------------------------

def _build_album_grid(album: list) -> html.Div:
    if not album: return html.P("No assets.", className="text-muted small")
    thumbs = []
    for entry in album:
        idx = entry.get("idx", 0)
        path = entry.get("bg_removed") or entry.get("original")
        if path and Path(path).exists():
            with open(path, "rb") as f:
                src = "data:image/png;base64," + base64.b64encode(f.read()).decode()
            thumbs.append(html.Img(src=src, id={"type": "card-photo-thumb", "index": idx}, 
                                   style={"width": "60px", "height": "60px", "objectFit": "cover", "margin": "2px", "cursor": "pointer", "borderRadius": "4px"}))
    return html.Div(thumbs, className="d-flex flex-wrap")


def _build_template_library_ui(player_id: str) -> list:
    """Reads saved JSON templates and returns a list of visual thumbnails."""
    tmpl_dir = _CARD_DATA_ROOT / player_id / "templates"
    if not tmpl_dir.exists():
        return [html.P("No saved templates.", className="text-muted small")]
    
    # Get all .json files
    files = sorted(tmpl_dir.glob("*.json"), reverse=True)
    if not files:
        return [html.P("No saved templates.", className="text-muted small")]
    
    thumbs = []
    for f in files:
        tmpl_id = f.stem
        img_path = tmpl_dir / f"{tmpl_id}.png"
        
        # Default source if image doesn't exist
        src = "https://via.placeholder.com/100x100?text=No+Preview"
        if img_path.exists():
            with open(img_path, "rb") as img_f:
                src = "data:image/png;base64," + base64.b64encode(img_f.read()).decode()
        
        thumbs.append(
            html.Div([
                html.Img(
                    src=src,
                    id={"type": "card-user-template", "index": tmpl_id},
                    style={
                        "width": "80px",
                        "height": "80px",
                        "objectFit": "cover",
                        "borderRadius": "8px",
                        "border": f"2px solid {_GLASS_BORDER}",
                        "cursor": "pointer",
                        "transition": "transform 0.2s"
                    },
                    className="hover-scale"
                ),
                html.P(tmpl_id.split("_")[-1], style={"fontSize": "0.55rem", "textAlign": "center", "marginTop": "4px", "color": _TEXT_MUTED})
            ], className="d-flex flex-column align-items-center me-2")
        )
    return thumbs
