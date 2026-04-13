# ABOUTME: Callbacks for the Card Editor Studio — handles template selection, live preview, and 2-design quota AI generation.
# ABOUTME: Implements final card copy to root, metadata persistence, and temporary designs/ cache cleanup on download.

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
from utils.chart_helpers import HKFATheme
from utils.runtime_storage import PLAYER_CARDS_RUNTIME_ROOT, build_player_cards_path, resolve_player_cards_path

logger = logging.getLogger(__name__)

_CARD_DATA_ROOT = PLAYER_CARDS_RUNTIME_ROOT
_ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}

# ---------------------------------------------------------------------------
# Metadata & Quota Helpers
# ---------------------------------------------------------------------------

def _get_card_metadata(player_id: str, milestone_id: str) -> dict:
    """Loads metadata for a specific milestone design session."""
    path = resolve_player_cards_path(player_id, milestone_id, "metadata.json")
    if path and path.exists():
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading metadata for {milestone_id}: {e}")
    return {
        "designs": [],
        "final_card": None,
        "editorial_decision": {},
        "last_design_strategy": {},
    }


def _save_card_metadata(player_id: str, milestone_id: str, data: dict):
    """Persists metadata to disk."""
    path = build_player_cards_path(player_id, milestone_id, "metadata.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving metadata for {milestone_id}: {e}")


def _normalize_editorial_decision(editorial_decision: dict | None) -> dict:
    decision = editorial_decision if isinstance(editorial_decision, dict) else {}
    raw_stats = decision.get("selected_stats") if isinstance(decision.get("selected_stats"), list) else []
    selected_stats = []
    for idx, item in enumerate(raw_stats, start=1):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        value = str(item.get("value") or "").strip()
        if not label or not value:
            continue
        selected_stats.append({
            "label": label,
            "value": value,
            "priority": int(item.get("priority") or idx),
        })
    visual = decision.get("supporting_visual") if isinstance(decision.get("supporting_visual"), dict) else {}
    try:
        confidence = float(decision.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "story_angle": str(decision.get("story_angle") or "consistent_performer"),
        "headline": str(decision.get("headline") or "").strip(),
        "subheadline": str(decision.get("subheadline") or "").strip(),
        "selected_stats": selected_stats[:5],
        "supporting_visual": {
            "type": str(visual.get("type") or "none"),
            "reason": str(visual.get("reason") or "").strip(),
        },
        "confidence": confidence,
    }


def _merge_agent_result_into_state(current_state: dict, result: dict) -> dict:
    new_state = dict(current_state or {})
    design_strategy = result.get("design_strategy") or result.get("ai_proposal") or {}
    editorial_decision = _normalize_editorial_decision(result.get("editorial_decision"))
    new_state.update({
        "generated_card_path": result.get("generated_card_path"),
        "agency_status": result.get("agency_status", "Success"),
        "ai_proposal": design_strategy,
        "design_strategy": design_strategy,
        "editorial_decision": editorial_decision,
    })
    return new_state


# ---------------------------------------------------------------------------
# Background generation state — keyed by player_id
# "_generating": bool  |  "_progress": dict  |  "_result": dict
# ---------------------------------------------------------------------------
_GENERATION_JOBS: dict[str, dict] = {}

# Style Constants for Library UI
_GLASS_BORDER = "rgba(255,255,255,0.10)"
_TEXT_MUTED = "rgba(255,255,255,0.45)"
_ACCENT_CYAN = "#00f2ff"

_SECTION_LABEL_STYLE = {
    "color": _ACCENT_CYAN,
    "fontSize": "0.72rem",
    "fontWeight": "700",
    "letterSpacing": "0.12em",
    "textTransform": "uppercase",
    "marginBottom": "10px",
    "marginTop": "0",
}


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
    try:
        if not editor_state:
            return html.Div("No profile loaded.", className="text-muted text-center p-4")

        proposal = editor_state.get("ai_proposal") or {}
        design = proposal.get("design") or {}
        raw_narrative = proposal.get("narrative") or {}
        narrative = raw_narrative if isinstance(raw_narrative, dict) else {}
        editorial_decision = _normalize_editorial_decision(editor_state.get("editorial_decision"))
        
        fmt = editor_state.get("format", "9:16")
        layers = design.get("layers") or {}
        headline_depth = editor_state.get("headline_depth") or proposal.get("headline_depth", "behind")
        glow_color = layers.get("glow_color", "var(--accent-cyan)")
        
        milestone_id = editor_state.get("milestone_id")
        match_payload = {}
        try:
            if milestones_data:
                match_payload = _get_match_payload(milestone_id, milestones_data)
        except Exception:
            pass

        # Background Logic
        bg_style = {}
        nanobana_bg = editor_state.get("nanobana_background_path")
        if nanobana_bg and Path(nanobana_bg).exists():
            try:
                with open(nanobana_bg, "rb") as f:
                    src = "data:image/png;base64," + base64.b64encode(f.read()).decode()
                    bg_style = {"backgroundImage": f"url({src})", "backgroundSize": "cover", "backgroundPosition": "center"}
            except Exception:
                bg_style = {"background": "#0a1a2f"}
        else:
            # FALLBACK LOGIC: Try to load a template fallback image if it exists, otherwise use refined gradient
            fallback_path = Path("assets/templates/card_fallback.jpg")
            if fallback_path.exists():
                try:
                    with open(fallback_path, "rb") as f:
                        src = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
                        bg_style = {"backgroundImage": f"url({src})", "backgroundSize": "cover", "backgroundPosition": "center"}
                except Exception:
                    pass
            
            if not bg_style:
                base_color = layers.get("base_color")
                c1 = base_color[0] if (isinstance(base_color, list) and base_color) else "#0a1a2f"
                bg_style = {
                    "background": f"linear-gradient(180deg, {c1} 0%, #05050a 100%)",
                    "position": "relative"
                }

        aspect_style = {"1:1": "100%", "9:16": "177.77%", "4:5": "125%", "16:9": "56.25%"}.get(fmt, "100%")
        
        fallback_layouts = {
            "9:16": {
                "headline": {"x": 50, "y": 15, "scale": 120},
                "subtitle": {"x": 50, "y": 22, "scale": 100},
                "home_logo": {"x": 15, "y": 10, "scale": 80},
                "away_logo": {"x": 85, "y": 10, "scale": 80},
                "player_name": {"x": 50, "y": 85, "scale": 110},
                "match_info": {"x": 50, "y": 72, "scale": 100},
                "comp_badge": {"x": 88, "y": 92, "scale": 70},
                "player_photo": {"x": 50, "y": 98, "scale": 120},
            },
            "1:1": {
                "headline": {"x": 50, "y": 18, "scale": 110},
                "subtitle": {"x": 50, "y": 26, "scale": 100},
                "home_logo": {"x": 12, "y": 12, "scale": 80},
                "away_logo": {"x": 88, "y": 12, "scale": 80},
                "player_name": {"x": 50, "y": 88, "scale": 100},
                "match_info": {"x": 50, "y": 76, "scale": 100},
                "comp_badge": {"x": 90, "y": 90, "scale": 70},
                "player_photo": {"x": 50, "y": 95, "scale": 110},
            },
            "4:5": {
                "headline": {"x": 50, "y": 16, "scale": 115},
                "subtitle": {"x": 50, "y": 24, "scale": 100},
                "home_logo": {"x": 15, "y": 12, "scale": 85},
                "away_logo": {"x": 85, "y": 12, "scale": 85},
                "player_name": {"x": 50, "y": 88, "scale": 110},
                "match_info": {"x": 50, "y": 74, "scale": 100},
                "comp_badge": {"x": 90, "y": 92, "scale": 75},
                "player_photo": {"x": 50, "y": 98, "scale": 115},
            }
        }
        
        active_fallback = fallback_layouts.get(fmt, fallback_layouts["1:1"])
        modifiers = editor_state.get("layout_modifiers") or proposal.get("layout_modifiers", {})
        
        def get_style(key, zIndex="10"):
            m = modifiers.get(key, active_fallback.get(key, {}))
            if not m.get("visible", True) and key in modifiers: 
                return {"display": "none"}
            x = m.get("x", 50)
            y = m.get("y", 50)
            scale = m.get("scale", 100) / 100.0
            return {
                "position": "absolute",
                "left": f"{x}%",
                "top": f"{y}%",
                "transform": f"translate(-50%, -50%) scale({scale})",
                "zIndex": zIndex, 
                "transition": "all 0.4s cubic-bezier(0.23, 1, 0.32, 1)"
            }

        photo_src = None
        selected_idx = editor_state.get("selected_photo_idx")
        if selected_idx is not None:
            try:
                album = (photos_store or {}).get("album") or []
                for entry in album:
                    if entry.get("idx") == selected_idx:
                        path = entry.get("bg_removed") or entry.get("original")
                        if path and Path(path).exists():
                            with open(path, "rb") as f:
                                photo_src = "data:image/png;base64," + base64.b64encode(f.read()).decode()
                        break
            except Exception:
                pass

        headline_text = str(editorial_decision.get("headline") or narrative.get("headline") or "MATCHDAY").upper()
        subheadline_text = str(editorial_decision.get("subheadline") or "").upper()
        player_name_display = str(_get_player_display_name()).upper()

        def img_el(src, key, width="140px", zIndex="10"):
            if not src: return None
            return html.Img(src=src, style={**get_style(key, zIndex=zIndex), "width": width, "objectFit": "contain"})

        stats_rows = []
        selected_stats = editorial_decision.get("selected_stats", [])
        if not selected_stats:
            selected_stats = [{"label": "GOALS", "value": "0"}, {"label": "ASSISTS", "value": "0"}, {"label": "RATING", "value": "—"}]
            
        for stat in selected_stats[:5]:
            stats_rows.append(
                html.Div([
                    html.Div(stat["value"], style={"fontWeight": "800", "fontSize": "1.05rem", "lineHeight": "1"}),
                    html.Div(stat["label"], style={"fontSize": "0.58rem", "letterSpacing": "0.08em", "textTransform": "uppercase", "opacity": "0.72"}),
                ], style={
                    "background": "rgba(0,0,0,0.55)", "border": f"1px solid {glow_color}55",
                    "borderRadius": "10px", "padding": "8px 10px", "minWidth": "76px", "textAlign": "center",
                })
            )

        visual_type = str((editorial_decision.get("supporting_visual") or {}).get("type") or "none")
        visual_label = f"{visual_type.upper()} SUPPORT" if visual_type != "none" else ""

        inner_children = [
            html.Div(style={"position": "absolute", "inset": "0", "opacity": "0.1", 
                            "backgroundImage": "url('https://www.transparenttextures.com/patterns/asfalt-dark.png')", "zIndex": "1"}),
            html.Div(headline_text, style={**get_style("headline", zIndex="5"), "display": "none" if headline_depth == "front" else "block",
                            "color": "white", "fontWeight": "900", "fontSize": "6rem", "opacity": "0.5" if headline_depth == "sandwich" else "0.9",
                            "textAlign": "center", "width": "100%", "fontFamily": "Impact, sans-serif", "textShadow": "0 10px 30px rgba(0,0,0,0.5)"}),
            html.Img(src=photo_src, style={**get_style("player_photo", zIndex="10"), "maxHeight": "95%", "maxWidth": "none", 
                            "filter": f"drop-shadow(0 0 20px {glow_color}44)"}) if photo_src else None,
            html.Div(headline_text, style={**get_style("headline", zIndex="15"), "display": "block" if headline_depth in ["front", "sandwich"] else "none",
                            "color": "transparent" if headline_depth == "sandwich" else "white", "WebkitTextStroke": f"2px white" if headline_depth == "sandwich" else "none",
                            "fontWeight": "900", "fontSize": "6rem", "textAlign": "center", "width": "100%", "fontFamily": "Impact, sans-serif"}),
            html.Div(player_name_display, style={**get_style("player_name", zIndex="30"), "color": "white", "fontWeight": "800", "fontSize": "1.5rem", 
                            "background": "black", "padding": "5px 25px", "borderRadius": "4px", "borderLeft": f"5px solid {glow_color}"}),
            html.Div(stats_rows, style={**get_style("match_info", zIndex="31"), "display": "flex" if stats_rows else "none",
                            "gap": "8px", "flexWrap": "wrap", "justifyContent": "center", "width": "84%"}),
            img_el(match_payload.get("home_logo"), "home_logo", width="120px", zIndex="30"),
            img_el(match_payload.get("away_logo"), "away_logo", width="120px", zIndex="30"),
            img_el(match_payload.get("competition_logo"), "comp_badge", width="80px", zIndex="30") if not visual_label else None,
        ]

        return html.Div(inner_children, style={"position": "absolute", "inset": "0", **bg_style, "overflow": "hidden", "borderRadius": "inherit"})
    except Exception as e:
        logger.error(f"Error in _build_preview_layout: {e}", exc_info=True)
        return html.Div([
            html.P("Error rendering preview.", className="text-danger"),
            html.Small(str(e), className="text-white-50")
        ], className="d-flex flex-column align-items-center justify-content-center h-100", style={"background": "#1a0a0a"})


# ---------------------------------------------------------------------------
# Callback registration
# ---------------------------------------------------------------------------

def register_card_editor_callbacks(app):
    """Registers all Card Editor Studio callbacks."""

    # 1. Combined State Update & AI Trigger signal
    @app.callback(
        Output("card-editor-state", "data", allow_duplicate=True),
        Output("card-ai-signal", "data", allow_duplicate=True),
        Input("card-repropose-btn", "n_clicks"),
        Input("card-generate-btn", "n_clicks"),
        Input("card-format-tabs", "active_tab"),
        Input({"type": "card-photo-thumb", "index": ALL}, "n_clicks"),
        Input({"type": "card-history-thumb", "index": ALL}, "n_clicks"),
        Input("card-stats-selection", "value"),
        State("card-editor-state", "data"),
        prevent_initial_call='initial_duplicate',
    )
    def update_card_studio_state(n_repropose, n_generate, format_tab,
                                 photo_clicks, history_clicks, manual_stats, current_state):
        if not current_state:
            return no_update, no_update
            
        state = dict(current_state)
        triggered_id = ctx.triggered_id
        player_id = _get_player_id()
        milestone_id = state.get("milestone_id")
        
        # Initial call or no interaction
        if not triggered_id:
            # Sync with persistent metadata on load
            meta = _get_card_metadata(player_id, milestone_id)
            state["design_history"] = meta.get("designs", [])
            state["final_card"] = meta.get("final_card")
            state["editorial_decision"] = _normalize_editorial_decision(
                state.get("editorial_decision") or meta.get("editorial_decision") or {}
            )
            state["design_strategy"] = state.get("design_strategy") or meta.get("last_design_strategy") or {}
            
            if format_tab and state.get("format") != format_tab:
                state["format"] = format_tab
                return state, no_update
            return state, no_update

        # 1. Stats Selection
        if triggered_id == "card-stats-selection":
            state["selected_stats_manual"] = manual_stats
            return state, no_update

        # 2. Handle Design History Selection
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "card-history-thumb":
            selected_path = triggered_id.get("index")
            state["generated_card_path"] = selected_path
            state["generating"] = False
            return state, no_update

        # 3. UI Changes
        if triggered_id == "card-format-tabs":
            state["format"] = format_tab
            return state, no_update

        if isinstance(triggered_id, dict) and triggered_id.get("type") == "card-photo-thumb":
            state["selected_photo_idx"] = triggered_id.get("index")
            return state, no_update

        # 4. AI Trigger (Design)
        if triggered_id == "card-repropose-btn":
            if not n_repropose: return no_update, no_update
            
            # Quota Check (Max 2 designs)
            meta = _get_card_metadata(player_id, milestone_id)
            if len(meta.get("designs", [])) >= 2:
                state["agency_status"] = "Límite alcanzado: ya tienes 2 diseños para este partido. Descarga uno para continuar."
                state["generating"] = False
                return state, no_update

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
                match_payload["milestone_id"] = milestone_id
                match_payload["card_type"] = state.get("card_type", "pre-match")
                profile = _get_player_profile(player_id)

                forced = state.get("selected_stats_manual") or []

                # Progress callback to update global state
                def on_progress(p):
                    if player_id in _GENERATION_JOBS:
                        _GENERATION_JOBS[player_id]["_progress"] = p

                result = run_card_design_agent(
                    match_payload=match_payload,
                    player_profile=profile,
                    card_format=state.get("format", "9:16"),
                    forced_stats=forced if forced else None,
                    on_progress=on_progress
                )
                
                if result.get("generated_card_path"):
                    _GENERATION_JOBS[player_id]["_result"] = {
                        "generated_card_path": result["generated_card_path"],
                        "agency_status": result.get("agency_status", "Success"),
                        "ai_proposal": result.get("design_strategy", {}),
                        "design_strategy": result.get("design_strategy", {}),
                        "editorial_decision": result.get("editorial_decision", {}),
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
        milestone_id = state.get("milestone_id")
        job = _GENERATION_JOBS.get(player_id)
        if not job: return no_update, True

        new_state = dict(state)
        if job.get("_progress"): new_state["progress"] = job["_progress"]

        if job.get("_generating"):
            return new_state, False

        result = job.get("_result")
        if result:
            new_path = result.get("generated_card_path")
            new_state = _merge_agent_result_into_state(new_state, result)
            new_state["generating"] = False
            
            # PERSISTENCE: Add to designs history in metadata.json
            meta = _get_card_metadata(player_id, milestone_id)
            designs = list(meta.get("designs", []))
            if new_path and new_path not in designs:
                designs.append(new_path)
            meta["designs"] = designs
            meta["editorial_decision"] = _normalize_editorial_decision(result.get("editorial_decision", {}))
            meta["last_design_strategy"] = result.get("design_strategy") or result.get("ai_proposal") or {}
            _save_card_metadata(player_id, milestone_id, meta)
            
            new_state["design_history"] = designs
            _GENERATION_JOBS.pop(player_id, None)
            return new_state, True

        if job.get("_error"):
            new_state["agency_status"] = f"Error: {job['_error']}"
            new_state["generating"] = False
            _GENERATION_JOBS.pop(player_id, None)
            return new_state, True

        raise PreventUpdate

    # 4. Render Live Preview & Visor logic
    @app.callback(
        Output({"type": "studio-element", "index": ALL}, "children"),
        Output({"type": "studio-element", "index": ALL}, "style"),
        Output("card-photo-album", "children", allow_duplicate=True),
        Output("card-history-gallery", "children"),
        Output("card-repropose-btn", "disabled"),
        Output("card-stats-selection", "options"),
        Output("card-stats-selection", "value"),
        Output("card-stats-selection", "disabled"),
        Output("card-stats-selection", "placeholder"),
        Input("card-editor-state", "data"),
        State("player-photos-store", "data"),
        State("milestones-data-store", "data"),
        prevent_initial_call='initial_duplicate',
    )
    def render_editor_updates(editor_state, photos_store, milestones_data):
        if not editor_state or not editor_state.get("editor_active"):
            raise PreventUpdate

        state = editor_state
        num_targets = 1
        if ctx.outputs_list and len(ctx.outputs_list) > 0:
            first_out = ctx.outputs_list[0]
            if isinstance(first_out, list):
                num_targets = len(first_out)
        
        if num_targets == 0: num_targets = 1
        
        album = (photos_store or {}).get("album") or []
        sel_idx = state.get("selected_photo_idx")
        album_grid = _build_album_grid(album, selected_idx=sel_idx)
        
        # Design History Gallery
        history = state.get("design_history", [])
        active_card = state.get("generated_card_path")
        history_gallery = _build_history_gallery(history, active_card)
        
        # Stats Dropdown Logic
        stats_options = []
        stats_value = state.get("selected_stats_manual")
        stats_disabled = len(history) == 0 # Disabled on first attempt
        stats_placeholder = "Agente decidiendo..." if stats_disabled else "Selecciona 4-7 estadísticas"
        
        if not stats_disabled:
            stats_options = _get_available_stats_options(milestones_data, state.get("milestone_id"))

        # Quota Button State:
        # - Disabled if 2 designs exist (quota) OR currently generating
        # - On 2nd attempt: disabled ONLY if partial invalid selection (1-3 stats)
        #   0 stats = agent decides → allowed; 4-7 stats = user decides → allowed
        design_disabled = len(history) >= 2 or state.get("generating", False)
        if not stats_disabled and not design_disabled:
            manual_count = len(stats_value or [])
            if 0 < manual_count < 4 or manual_count > 7:  # partial/excess = invalid
                design_disabled = True

        # Aspect Ratio logic - Using native CSS aspect-ratio for geometric perfection
        fmt = state.get("format", "9:16")
        aspect_ratios = {"1:1": "1/1", "9:16": "9/16", "4:5": "4/5", "16:9": "16/9"}
        active_ratio = aspect_ratios.get(fmt, "9/16")
        
        container_style = {
            "background": "#05050a",
            "borderRadius": "20px",
            "border": "1px solid rgba(255,255,255,0.1)",
            "height": "100%", 
            "aspectRatio": active_ratio, 
            "width": "auto", 
            "position": "relative",
            "overflow": "hidden",
            "boxShadow": "0 20px 40px rgba(0,0,0,0.5)",
            "transition": "all 0.4s cubic-bezier(0.23, 1, 0.32, 1)",
            "margin": "0 auto"
        }

        # Case: Generating
        if state.get("generating"):
            progress = state.get("progress") or {}
            content = html.Div([
                html.I(className="bi bi-stars animate-glass-pulse", style={"fontSize": "2.5rem", "color": "#00f2ff", "marginBottom": "16px"}),
                html.P(progress.get("phase", "Generando..."), className="text-white fw-bold mb-3 small"),
                dbc.Progress(value=progress.get("pct", 15), max=100, striped=True, animated=True, color="info", style={"height": "6px", "width": "200px"}),
            ], className="d-flex flex-column align-items-center justify-content-center h-100",
               style={"position": "absolute", "inset": "0", "background": "rgba(0,0,0,0.8)"})
            return ([content] * num_targets, [container_style] * num_targets, album_grid, 
                    history_gallery, design_disabled, stats_options, stats_value, stats_disabled, stats_placeholder)

        # Case: Final Result (Current selected design from history or new generation)
        card_path = state.get("generated_card_path")
        if card_path and Path(card_path).exists():
            with open(card_path, "rb") as f:
                src = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
            
            # For final result, we just fill the container with the image
            img = html.Img(src=src, style={"width": "100%", "height": "100%", "objectFit": "cover", "display": "block", "borderRadius": "inherit"})
            return ([img] * num_targets, [container_style] * num_targets, album_grid, 
                    history_gallery, design_disabled, stats_options, stats_value, stats_disabled, stats_placeholder)

        # Case: Status/Error message (quota, generation error)
        agency_status = state.get("agency_status", "")
        if agency_status and not agency_status.startswith("Starting") and "Success" not in agency_status:
            icon = "bi bi-exclamation-triangle" if "Error" in agency_status else "bi bi-info-circle"
            color = "#ff4d6d" if "Error" in agency_status else "#00f2ff"
            status_overlay = html.Div([
                html.I(className=f"{icon} mb-2", style={"fontSize": "1.8rem", "color": color}),
                html.P(agency_status, className="text-white small text-center px-3 mb-0", style={"lineHeight": "1.4"}),
            ], className="d-flex flex-column align-items-center justify-content-center h-100",
               style={"position": "absolute", "inset": "0", "background": "rgba(5,5,10,0.92)", "borderRadius": "inherit"})
            preview_div = _build_preview_layout(state, photos_store, milestones_data)
            wrapped = html.Div([preview_div, status_overlay], style={"position": "relative", "height": "100%"})
            return ([wrapped] * num_targets, [container_style] * num_targets, album_grid,
                    history_gallery, design_disabled, stats_options, stats_value, stats_disabled, stats_placeholder)

        # Case: Live Preview (Blueprint / Fallback)
        preview_div = _build_preview_layout(state, photos_store, milestones_data)
        return ([preview_div] * num_targets, [container_style] * num_targets, album_grid,
                history_gallery, design_disabled, stats_options, stats_value, stats_disabled, stats_placeholder)

    # 6. Expand Preview Modal logic
    @app.callback(
        Output("card-viewer-modal", "is_open", allow_duplicate=True),
        Output("card-viewer-modal-content", "children", allow_duplicate=True),
        Input("card-expand-preview-btn", "n_clicks"),
        State("card-editor-state", "data"),
        State("player-photos-store", "data"),
        State("milestones-data-store", "data"),
        prevent_initial_call=True
    )
    def expand_editor_preview(n, state, photos, milestones):
        if not n: return no_update, no_update
        
        # Build the preview for the modal
        card_path = state.get("generated_card_path")
        if card_path and Path(card_path).exists():
            with open(card_path, "rb") as f:
                src = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
            # Very large image for inspection, allowing scroll in modal body
            content = html.Img(src=src, className="img-fluid rounded", style={"width": "100%", "maxWidth": "1000px", "boxShadow": "0 20px 40px rgba(0,0,0,0.5)"})
        else:
            preview = _build_preview_layout(state, photos, milestones)
            fmt = state.get("format", "9:16")
            ratios = {"1:1": 1.0, "9:16": 0.5625, "4:5": 0.8, "16:9": 1.777}
            ratio = ratios.get(fmt, 0.5625)
            
            # In modal we want it much larger (e.g. 120vh) to allow scrolling and detailed view
            content = html.Div(
                preview,
                style={
                    "height": "120vh",
                    "width": f"calc(120vh * {ratio})",
                    "position": "relative",
                    "borderRadius": "24px",
                    "overflow": "hidden",
                    "boxShadow": "0 25px 50px rgba(0,0,0,0.5)",
                    "background": "#0a1a2f",
                    "margin": "0 auto"
                }
            )
        return True, content

    # 7. Upload
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

    # 7. Delete Photo
    @app.callback(
        Output("player-photos-store", "data", allow_duplicate=True),
        Output("card-photo-album", "children", allow_duplicate=True),
        Output("card-editor-state", "data", allow_duplicate=True),
        Input({"type": "card-photo-delete", "index": ALL}, "n_clicks"),
        State("player-photos-store", "data"),
        State("card-editor-state", "data"),
        prevent_initial_call=True,
    )
    def delete_player_photo_callback(delete_clicks, photos_store, editor_state):
        if not any(n for n in (delete_clicks or []) if n):
            raise PreventUpdate
        triggered = ctx.triggered_id
        if not isinstance(triggered, dict) or triggered.get("type") != "card-photo-delete":
            raise PreventUpdate
        idx_to_delete = triggered["index"]
        player_id = _get_player_id()
        from utils.image_processing import delete_player_photo, get_player_album
        delete_player_photo(player_id, idx_to_delete)
        updated_album = get_player_album(player_id)
        store = dict(photos_store or {})
        store["album"] = updated_album
        new_state = dict(editor_state or {})
        if new_state.get("selected_photo_idx") == idx_to_delete:
            new_state["selected_photo_idx"] = updated_album[0]["idx"] if updated_album else None
        sel_idx = new_state.get("selected_photo_idx")
        return store, _build_album_grid(updated_album, selected_idx=sel_idx), new_state

    # 8. PNG Download & Finalize
    @app.callback(
        Output("card-download", "data"),
        Output("timeline-pagination-store", "data", allow_duplicate=True),
        Output("card-editor-state", "data", allow_duplicate=True),
        Input("card-generate-btn", "n_clicks"),
        State("card-editor-state", "data"),
        State("timeline-pagination-store", "data"),
        prevent_initial_call=True,
    )
    def download_generated_card(n_clicks, state, pagination_store):
        if not n_clicks: return no_update, no_update, no_update
        path_str = state.get("generated_card_path")
        if path_str and Path(path_str).exists():
            player_id = _get_player_id()
            milestone_id = state.get("milestone_id", "unknown")
            
            # FINAL STORAGE: Copy from designs/ to root as final_card.jpg
            import shutil
            source_path = Path(path_str)
            target_path = build_player_cards_path(player_id, milestone_id) / "final_card.jpg"
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                shutil.copy2(source_path, target_path)
                final_path_str = str(target_path)
            except Exception as e:
                logger.error(f"Error copying final card: {e}")
                final_path_str = path_str # Fallback to original path if copy fails

            # PERSISTENCE: Mark as final card
            meta = _get_card_metadata(player_id, milestone_id)
            meta["final_card"] = final_path_str
            
            # CACHE CLEANUP: Delete designs/ subfolder
            designs_dir = source_path.parent
            if designs_dir.name == "designs":
                try:
                    shutil.rmtree(designs_dir)
                    # Clear history list in metadata since files are gone
                    meta["designs"] = [] 
                except Exception as e:
                    logger.error(f"Error clearing designs cache: {e}")

            _save_card_metadata(player_id, milestone_id, meta)
            
            # Update local state
            new_state = dict(state)
            new_state["final_card"] = final_path_str
            new_state["generated_card_path"] = final_path_str
            new_state["design_history"] = []

            store = dict(pagination_store or {})
            generated = dict(store.get("generated", {}))
            generated[milestone_id] = True
            store["generated"] = generated
            return dcc.send_file(final_path_str), store, new_state
        return no_update, no_update, no_update

    # 9. Body scroll lock when expand modal is open
    app.clientside_callback(
        """
        function(is_open) {
            document.body.style.overflow = is_open ? 'hidden' : '';
            return window.dash_clientside.no_update;
        }
        """,
        Output("card-viewer-modal", "style"),
        Input("card-viewer-modal", "is_open"),
        prevent_initial_call=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_history_gallery(history: list, active_path: str = None) -> html.Div:
    """Builds a small gallery of previously generated designs."""
    if not history: return None
    
    thumbs = []
    for path_str in history:
        if not Path(path_str).exists(): continue
        
        with open(path_str, "rb") as f:
            src = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
            
        is_active = (path_str == active_path)
        thumbs.append(html.Img(
            src=src,
            id={"type": "card-history-thumb", "index": path_str},
            style={
                "width": "50px", "height": "80px", "objectFit": "cover",
                "marginRight": "8px", "borderRadius": "4px", "cursor": "pointer",
                "border": f"2px solid {'#00f2ff' if is_active else 'rgba(255,255,255,0.1)'}",
                "opacity": "1" if is_active else "0.6",
                "transition": "all 0.2s"
            }
        ))
    
    return html.Div([
        html.P("DESIGN HISTORY", style=_SECTION_LABEL_STYLE),
        html.Div(thumbs, className="d-flex overflow-auto pb-2")
    ], className="mt-3")


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
            thumbs.append(html.Div([
                html.Img(
                    src=src,
                    id={"type": "card-photo-thumb", "index": idx},
                    style={
                        "width": "100%", "height": "100%",
                        "objectFit": "contain", "objectPosition": "center",
                        "cursor": "pointer", "borderRadius": "4px",
                        "padding": "4px",
                    }
                ),
                html.Button(
                    "×",
                    id={"type": "card-photo-delete", "index": idx},
                    n_clicks=0,
                    style={
                        "position": "absolute", "top": "2px", "right": "2px",
                        "width": "16px", "height": "16px",
                        "padding": "0", "lineHeight": "14px", "fontSize": "12px",
                        "background": "rgba(237,28,36,0.85)", "color": "white",
                        "border": "none", "borderRadius": "50%", "cursor": "pointer",
                        "display": "flex", "alignItems": "center", "justifyContent": "center",
                        "zIndex": "10",
                    }
                ),
            ], style={
                "position": "relative", "width": "64px", "height": "64px",
                "margin": "3px", "borderRadius": "6px",
                "background": "rgba(255,255,255,0.05)",
                "border": f"2px solid {'#00f2ff' if is_selected else 'rgba(255,255,255,0.1)'}",
                "boxShadow": "0 0 8px rgba(0,242,255,0.6)" if is_selected else "none",
                "transition": "border 0.15s",
                "flexShrink": "0",
            }))
    return html.Div(thumbs, style={"display": "flex", "flexWrap": "wrap", "gap": "2px"})


def _build_template_library_ui(player_id: str) -> list:
    return [html.P("Saved styles.", className="text-muted small")]


def _get_available_stats_options(milestones_data, milestone_id):
    """Extracts all performance stats for the dropdown."""
    payload = _get_match_payload(milestone_id, milestones_data)
    if not payload: return []
    
    # 1. Main high-level stats
    stats_dict = {
        "Goals": payload.get("goals", 0),
        "Assists": payload.get("assists", 0),
        "Rating": payload.get("rating", "—"),
        "Minutes": f"{payload.get('minutes_played', 0)}'",
    }
    
    # 2. Add Match Stats sub-dict
    match_stats = payload.get("match_stats") or {}
    for k, v in match_stats.items():
        # Human friendly labels
        label = k.replace("_", " ").title()
        if label not in stats_dict:
            stats_dict[label] = v
            
    options = []
    for label, val in stats_dict.items():
        if val in [0, "0", "0'", "—", None]: continue # Hide empty
        options.append({
            "label": f"{label}: {val}",
            "value": {"label": label, "value": str(val)}
        })
    return options
