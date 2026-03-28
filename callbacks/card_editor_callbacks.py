# ABOUTME: Callbacks for the Card Editor Studio — handles template selection, live preview,
# ABOUTME: photo upload/delete, AI caption, draft save, PNG generation, and re-propose.

# Standard Library
import base64
import io
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

# Third-party
import dash_bootstrap_components as dbc
from dash import Input, Output, State, ALL, MATCH, ctx, dcc, html, no_update
from flask_login import current_user
from PIL import Image

logger = logging.getLogger(__name__)

_CARD_DATA_ROOT = Path("data/player_cards")
_ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_player_id() -> str:
    try:
        return str(current_user.id) if current_user and current_user.is_authenticated else "unknown"
    except Exception:
        return "unknown"


def _draft_path(player_id: str, milestone_id: str) -> Path:
    return _CARD_DATA_ROOT / player_id / milestone_id / "card_editor.json"


def _load_draft(player_id: str, milestone_id: str) -> dict | None:
    p = _draft_path(player_id, milestone_id)
    if p.exists():
        try:
            return json.loads(p.read_text("utf-8"))
        except Exception:
            return None
    return None


def _save_draft(player_id: str, milestone_id: str, state: dict) -> bool:
    p = _draft_path(player_id, milestone_id)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, ensure_ascii=False, indent=2), "utf-8")
        return True
    except Exception as exc:
        logger.error(f"_save_draft error: {exc}")
        return False


def _build_preview_layout(editor_state: dict, photos_store: dict) -> html.Div:
    """Builds a Dash approximation of the card for the live preview pane."""
    if not editor_state:
        return html.Div("Sin propuesta cargada.", className="text-muted text-center p-4")

    proposal = editor_state.get("ai_proposal") or {}
    design = proposal.get("design") or {}
    narrative = proposal.get("narrative") or {}
    template = editor_state.get("template") or design.get("template", "A")
    fmt = editor_state.get("format", "1:1")
    layers = design.get("layers") or {}
    typography = design.get("typography") or {}
    hero = typography.get("hero_stat") or {}
    elements = editor_state.get("elements") or design.get("elements") or {}

    # Base colours
    base_color = layers.get("base_color", "#1a1a2e")
    gradient_cfg = layers.get("gradient") or {}
    c1 = gradient_cfg.get("color1", base_color)

    # Aspect ratio wrapper
    aspect_style = {
        "1:1": {"paddingTop": "100%"},
        "9:16": {"paddingTop": "177%"},
        "16:9": {"paddingTop": "56.25%"},
    }.get(fmt, {"paddingTop": "100%"})

    # Selected photo
    selected_idx = editor_state.get("selected_photo_idx")
    photo_src = None
    if selected_idx is not None and template != "C" and elements.get("player_photo", True):
        album = (photos_store or {}).get("album") or []
        for entry in album:
            if entry.get("idx") == selected_idx:
                bg_path = entry.get("bg_removed") or entry.get("original")
                if bg_path and Path(bg_path).exists():
                    with open(bg_path, "rb") as f:
                        photo_src = "data:image/png;base64," + base64.b64encode(f.read()).decode()
                break

    # Hero stat display
    hero_value = str(hero.get("value") or "—")
    hero_label = str(hero.get("label") or "")

    headline = str(narrative.get("headline") or "").upper()

    inner_children = [
        html.Div(
            headline,
            style={
                "position": "absolute", "top": "6%", "left": "50%",
                "transform": "translateX(-50%)",
                "color": "white", "fontWeight": "bold",
                "fontSize": "clamp(10px, 2.5vw, 18px)",
                "textAlign": "center", "width": "90%",
                "textShadow": "0 1px 3px rgba(0,0,0,0.8)",
            }
        ),
    ]

    if template != "C":
        if photo_src:
            inner_children.append(html.Img(
                src=photo_src,
                style={
                    "position": "absolute",
                    "bottom": "25%", "left": "50%",
                    "transform": "translateX(-50%)",
                    "maxHeight": "55%", "maxWidth": "80%",
                    "objectFit": "contain",
                }
            ))
        else:
            # Placeholder silhouette when no photo uploaded
            inner_children.append(html.Div(
                html.I(className="bi bi-person-fill",
                       style={"fontSize": "clamp(48px, 12vw, 96px)", "color": "rgba(255,255,255,0.15)"}),
                style={
                    "position": "absolute",
                    "bottom": "25%", "left": "50%",
                    "transform": "translateX(-50%)",
                    "textAlign": "center",
                }
            ))

    inner_children.append(html.Div([
        html.Span(hero_value, style={
            "display": "block", "fontSize": "clamp(24px, 6vw, 48px)",
            "fontWeight": "900", "color": "white", "lineHeight": "1",
        }),
        html.Span(hero_label, style={
            "display": "block", "fontSize": "clamp(8px, 2vw, 14px)",
            "color": "rgba(255,255,255,0.7)", "letterSpacing": "2px",
        }),
    ], style={
        "position": "absolute", "bottom": "12%", "left": "50%",
        "transform": "translateX(-50%)",
        "textAlign": "center",
    }))

    inner_children.append(html.Div(
        f"Template {template}",
        style={
            "position": "absolute", "top": "4%", "right": "4%",
            "color": "rgba(255,255,255,0.4)", "fontSize": "10px",
        }
    ))

    preview = html.Div(
        html.Div(
            inner_children,
            style={
                "position": "absolute", "inset": "0",
                "background": f"linear-gradient(135deg, {c1}cc, {base_color})",
                "overflow": "hidden",
                "borderRadius": "8px",
            }
        ),
        style={
            "position": "relative",
            "width": "100%",
            **aspect_style,
            "overflow": "hidden",
        },
    )

    reasoning = (proposal.get("narrative") or {}).get("reasoning", "")
    reasoning_block = []
    if reasoning:
        reasoning_block = [
            dbc.Alert(
                [html.I(className="bi bi-lightbulb me-2"), reasoning],
                color="dark",
                className="small mt-2 py-2",
            )
        ]

    return html.Div([preview] + reasoning_block)


# ---------------------------------------------------------------------------
# Callback registration
# ---------------------------------------------------------------------------

def register_card_editor_callbacks(app):
    """Registers all Card Editor Studio callbacks."""

    # ------------------------------------------------------------------ #
    # 7.1 — Update card-editor-state from UI controls                    #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("card-editor-state", "data"),
        Input("card-template-tabs", "active_tab"),
        Input({"type": "card-element-toggle", "index": ALL}, "value"),
        Input({"type": "card-format-radio", "index": "format"}, "value"),
        Input({"type": "card-stat-highlight", "index": "stat"}, "value"),
        State("card-editor-state", "data"),
        prevent_initial_call=True,
    )
    def update_card_editor_state(active_tab, element_values, format_value, stat_value, current_state):
        """Updates card-editor-state when the player changes template, elements, format, or stat."""
        state = dict(current_state or {})
        triggered_id = ctx.triggered_id

        if active_tab is not None:
            state["template"] = active_tab

        if format_value is not None:
            state["format"] = format_value

        if stat_value is not None:
            state["hero_stat_key"] = stat_value

        # Element toggles — rebuild elements dict from all toggle values
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "card-element-toggle":
            elements = dict(state.get("elements") or {})
            all_ids = [c["id"]["index"] for c in ctx.inputs_list[1]]
            for elem_id, val in zip(all_ids, element_values or []):
                elements[elem_id] = bool(val)
            state["elements"] = elements

        return state

    # ------------------------------------------------------------------ #
    # 7.2 — Render live preview from card-editor-state                   #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("card-preview-container", "children"),
        Input("card-editor-state", "data"),
        State("player-photos-store", "data"),
        prevent_initial_call=True,
    )
    def render_live_preview(editor_state, photos_store):
        """Re-renders the live preview whenever card-editor-state changes."""
        return _build_preview_layout(editor_state or {}, photos_store or {})

    # ------------------------------------------------------------------ #
    # 7.3 — Upload player photo                                          #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("player-photos-store", "data"),
        Output("card-photo-album", "children"),
        Output("card-upload-status", "children"),
        Input("card-photo-upload", "contents"),
        State("card-photo-upload", "filename"),
        State("player-photos-store", "data"),
        prevent_initial_call=True,
    )
    def upload_player_photo(contents, filename, photos_store):
        """Validates, removes background, and saves uploaded photo; updates album grid."""
        if not contents:
            return no_update, no_update, no_update

        player_id = _get_player_id()
        store = dict(photos_store or {})
        album = list(store.get("album") or [])

        # Decode base64 data URL
        try:
            header, data = contents.split(",", 1)
            content_type = header.split(";")[0].split(":")[1] if ":" in header else "image/png"
            image_bytes = base64.b64decode(data)
        except Exception as exc:
            return no_update, no_update, dbc.Alert(f"Error al leer archivo: {exc}", color="danger", duration=4000)

        if content_type not in _ALLOWED_TYPES:
            return no_update, no_update, dbc.Alert("Tipo de archivo no permitido. Usa PNG, JPG o WebP.", color="warning", duration=4000)

        if len(image_bytes) > _MAX_UPLOAD_BYTES:
            return no_update, no_update, dbc.Alert("Archivo demasiado grande (máx. 10 MB).", color="warning", duration=4000)

        result_holder = {}

        def _process():
            try:
                from utils.image_processing import save_player_photo
                entry = save_player_photo(player_id, image_bytes, filename or "photo.png")
                result_holder["entry"] = entry
            except ValueError as ve:
                result_holder["error"] = str(ve)
            except Exception as exc:
                result_holder["error"] = str(exc)

        thread = threading.Thread(target=_process, daemon=True)
        thread.start()
        thread.join(timeout=30)

        if "error" in result_holder:
            return no_update, no_update, dbc.Alert(f"Error: {result_holder['error']}", color="danger", duration=5000)

        entry = result_holder.get("entry")
        if not entry:
            return no_update, no_update, dbc.Alert("Procesamiento de imagen fallido.", color="danger", duration=4000)

        album.append(entry)
        store["album"] = album

        return store, _build_album_grid(album), dbc.Alert("Foto añadida correctamente.", color="success", duration=3000)

    # ------------------------------------------------------------------ #
    # 7.4 — Delete player photo (pattern-matched)                        #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("player-photos-store", "data", allow_duplicate=True),
        Output("card-photo-album", "children", allow_duplicate=True),
        Input({"type": "card-photo-delete-btn", "index": ALL}, "n_clicks"),
        State("player-photos-store", "data"),
        State("card-editor-state", "data"),
        prevent_initial_call=True,
    )
    def delete_player_photo(n_clicks_list, photos_store, editor_state):
        """Deletes a photo from the album and updates the store."""
        if not any(n_clicks_list or []):
            return no_update, no_update

        triggered = ctx.triggered_id
        if not isinstance(triggered, dict) or triggered.get("type") != "card-photo-delete-btn":
            return no_update, no_update

        photo_idx = triggered["index"]
        player_id = _get_player_id()

        try:
            from utils.image_processing import delete_player_photo as _delete, get_player_album
            _delete(player_id, int(photo_idx))
            updated_album = get_player_album(player_id)
        except Exception as exc:
            logger.error(f"delete_player_photo error: {exc}")
            return no_update, no_update

        store = dict(photos_store or {})
        store["album"] = updated_album

        # Clear selected_photo_idx if the deleted photo was selected
        new_editor_state = dict(editor_state or {})
        if new_editor_state.get("selected_photo_idx") == photo_idx:
            new_editor_state.pop("selected_photo_idx", None)

        return store, _build_album_grid(updated_album)

    # ------------------------------------------------------------------ #
    # 7.X — Select photo from album (thumbnail click)                   #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("card-editor-state", "data", allow_duplicate=True),
        Input({"type": "card-photo-thumb", "index": ALL}, "n_clicks"),
        State("card-editor-state", "data"),
        prevent_initial_call=True,
    )
    def select_photo_from_album(n_clicks_list, editor_state):
        """Sets selected_photo_idx in card-editor-state when a thumbnail is clicked."""
        if not n_clicks_list or not any(n_clicks_list):
            return no_update
        triggered = ctx.triggered_id
        if not isinstance(triggered, dict) or triggered.get("type") != "card-photo-thumb":
            return no_update
        state = dict(editor_state or {})
        state["selected_photo_idx"] = triggered["index"]
        return state

    # ------------------------------------------------------------------ #
    # 7.5 — Generate AI caption                                          #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("card-caption-preview", "value"),
        Input("card-caption-btn", "n_clicks"),
        State("card-editor-state", "data"),
        State("milestones-data-store", "data"),
        prevent_initial_call=True,
    )
    def generate_ai_caption(n_clicks, editor_state, milestones_data):
        """Calls the card design agent caption path and updates the caption preview."""
        if not n_clicks:
            return no_update

        state = editor_state or {}
        milestone_id = state.get("milestone_id")
        tone = state.get("caption_tone", "pro")
        proposal = state.get("ai_proposal") or {}
        narrative = proposal.get("narrative") or {}

        # Prefer existing agent caption; re-call agent only if needed
        caption = narrative.get("caption", "")
        hashtags = " ".join(narrative.get("hashtags") or ["#HKFootball"])

        if not caption:
            try:
                from utils.card_design_agent import run_card_design_agent
                match_payload = _get_match_payload(milestone_id, milestones_data)
                proposals = run_card_design_agent(
                    match_payload=match_payload,
                    player_profile={},
                    team_colors={},
                    player_history=[],
                    has_player_photo=bool(state.get("selected_photo_idx") is not None),
                    card_type=state.get("card_type", "post-match"),
                    tone=tone,
                )
                if proposals:
                    caption = (proposals[0].get("narrative") or {}).get("caption", "")
                    hashtags = " ".join((proposals[0].get("narrative") or {}).get("hashtags") or ["#HKFootball"])
            except Exception as exc:
                logger.error(f"generate_ai_caption error: {exc}")
                caption = "No se pudo generar el caption."

        full_caption = f"{caption}\n\n{hashtags}" if hashtags else caption
        return full_caption

    # ------------------------------------------------------------------ #
    # 7.6 — Save draft                                                   #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("card-editor-state", "data", allow_duplicate=True),
        Output("card-save-toast", "is_open"),
        Input("card-save-draft-btn", "n_clicks"),
        State("card-editor-state", "data"),
        prevent_initial_call=True,
    )
    def save_draft(n_clicks, editor_state):
        """Serialises card-editor-state to disk and shows a success toast."""
        if not n_clicks:
            return no_update, False

        state = dict(editor_state or {})
        player_id = _get_player_id()
        milestone_id = state.get("milestone_id", "unknown")

        state["last_saved"] = datetime.now(timezone.utc).isoformat()
        success = _save_draft(player_id, milestone_id, state)
        return state if success else no_update, success

    # ------------------------------------------------------------------ #
    # 7.7 — Generate and download PNG                                    #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("card-download", "data"),
        Output("card-generation-trigger", "data"),
        Output("timeline-pagination-store", "data", allow_duplicate=True),
        Output("card-generate-btn", "disabled"),
        Input("card-generate-btn", "n_clicks"),
        State("card-editor-state", "data"),
        State("player-photos-store", "data"),
        State("timeline-pagination-store", "data"),
        prevent_initial_call=True,
    )
    def generate_and_download_png(n_clicks, editor_state, photos_store, pagination_store):
        """Calls compose_card(), triggers download, updates stores, and marks milestone generated."""
        if not n_clicks:
            return no_update, no_update, no_update, False

        state = editor_state or {}
        player_id = _get_player_id()
        milestone_id = state.get("milestone_id", "unknown")
        fmt = state.get("format", "1:1")
        template = state.get("template", "A")
        proposal = state.get("ai_proposal") or {}

        # Build design brief from editor state
        design_brief = dict(proposal)
        if design_brief.get("design"):
            design_brief["design"] = dict(design_brief["design"])
            design_brief["design"]["template"] = template
            design_brief["design"]["format"] = fmt
            if state.get("elements"):
                design_brief["design"]["elements"] = state["elements"]

        # Find player photo path
        photo_path = None
        selected_idx = state.get("selected_photo_idx")
        if selected_idx is not None and template != "C":
            album = (photos_store or {}).get("album") or []
            for entry in album:
                if entry.get("idx") == selected_idx:
                    photo_path = entry.get("bg_removed") or entry.get("original")
                    break

        output_dir = _CARD_DATA_ROOT / player_id / milestone_id
        try:
            from utils.card_renderer import compose_card
            png_path = compose_card(design_brief, photo_path, str(output_dir), fmt)
        except Exception as exc:
            logger.error(f"generate_and_download_png compose_card error: {exc}")
            return no_update, no_update, no_update, False

        # Trigger browser download
        download = dcc.send_file(str(png_path), filename=f"card_{milestone_id}_{fmt.replace(':', '_')}.png")

        # Update generation trigger
        trigger = {"generated": True, "path": str(png_path), "milestone_id": milestone_id}

        # Update timeline-pagination-store
        store = dict(pagination_store or {})
        generated = dict(store.get("generated") or {})
        generated[milestone_id] = True
        store["generated"] = generated

        return download, trigger, store, False

    # ------------------------------------------------------------------ #
    # 7.8 — Re-propose design via AI agent                               #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("card-editor-state", "data", allow_duplicate=True),
        Output("card-preview-container", "children", allow_duplicate=True),
        Input("card-repropose-btn", "n_clicks"),
        State("card-editor-state", "data"),
        State("milestones-data-store", "data"),
        prevent_initial_call=True,
    )
    def repropose_design(n_clicks, editor_state, milestones_data):
        """Calls the card design agent with current state as constraints and updates proposals."""
        if not n_clicks:
            return no_update, no_update

        state = dict(editor_state or {})
        milestone_id = state.get("milestone_id")
        card_type = state.get("card_type", "post-match")
        match_payload = _get_match_payload(milestone_id, milestones_data)
        player_preferences = {k: v for k, v in state.items() if k in ("template", "elements", "format", "hero_stat_key")}

        try:
            from utils.card_design_agent import run_card_design_agent
            proposals = run_card_design_agent(
                match_payload=match_payload,
                player_profile={},
                team_colors={},
                player_history=[],
                has_player_photo=bool(state.get("selected_photo_idx") is not None),
                card_type=card_type,
                player_preferences=player_preferences,
            )
            if proposals:
                state["ai_proposal"] = proposals[0]
                state["template"] = (proposals[0].get("design") or {}).get("template", state.get("template", "A"))
        except Exception as exc:
            logger.error(f"repropose_design error: {exc}")
            # Keep previous state, show warning in preview
            return state, dbc.Alert(
                "No se pudo obtener una nueva propuesta. Se mantiene el diseño anterior.",
                color="warning",
            )

        preview = _build_preview_layout(state, {})
        return state, preview


# ---------------------------------------------------------------------------
# Album grid helper
# ---------------------------------------------------------------------------

def _build_album_grid(album: list) -> html.Div:
    """Builds the photo album grid component."""
    if not album:
        return html.P("Sin fotos. Sube una foto para empezar.", className="text-muted small")

    thumbnails = []
    for entry in album:
        idx = entry.get("idx", 0)
        photo_path = entry.get("bg_removed") or entry.get("original")
        src = ""
        if photo_path and Path(photo_path).exists():
            try:
                with open(photo_path, "rb") as f:
                    src = "data:image/png;base64," + base64.b64encode(f.read()).decode()
            except Exception:
                src = ""

        thumbnails.append(
            html.Div([
                html.Img(
                    src=src,
                    style={"width": "100%", "height": "80px", "objectFit": "cover",
                           "borderRadius": "4px", "cursor": "pointer"},
                    id={"type": "card-photo-thumb", "index": idx},
                    n_clicks=0,
                ),
                dbc.Button(
                    html.I(className="bi bi-x"),
                    id={"type": "card-photo-delete-btn", "index": idx},
                    size="sm", color="danger", outline=True,
                    style={"width": "100%", "marginTop": "2px", "padding": "1px 0"},
                    n_clicks=0,
                ),
            ], style={"width": "80px"}, className="me-2 mb-2")
        )

    return html.Div(thumbnails, className="d-flex flex-wrap")


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _get_match_payload(milestone_id: str | None, milestones_data: list | None) -> dict:
    """Extracts match payload from milestones_data for the given milestone_id."""
    if not milestone_id or not milestones_data:
        return {}
    m = next((item for item in milestones_data if item.get("id") == milestone_id), None)
    return (m or {}).get("payload", {})
