# ABOUTME: Stage Action callbacks for the Player Portal Decision Node buttons (Phase 4).
# ABOUTME: Wires all seven dn-* buttons to their respective stage content or download actions.

# Standard Library
import logging
import uuid
from pathlib import Path

# Third-party
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html, no_update
from flask_login import current_user

# Project
from callbacks.agent_callbacks import _run_agent_with_timeout
from layouts.prematch_card import create_prematch_card
from utils.ical_export import build_ical_bytes
from utils.stage_helpers import get_projection_figure, render_image_gallery

logger = logging.getLogger(__name__)

_CARD_CACHE_DIR = Path("data/cache/cards")


def download_ical_callback(n_clicks, context):
    """Builds an ICS calendar file from the active pre-match fixture and triggers download."""
    if not n_clicks or not context:
        return no_update
    if context.get("type") != "pre-match":
        return no_update
    payload = context.get("payload", {})
    ics_bytes = build_ical_bytes(payload)
    home = (payload.get("home_team") or "home").replace(" ", "_")
    away = (payload.get("away_team") or "away").replace(" ", "_")
    filename = f"fixture_{home}_vs_<away>.ics".replace("<away>", away)
    return dcc.send_bytes(ics_bytes, filename=filename, type="text/calendar")


def show_previa_card_callback(n_clicks, context):
    """Renders the Pre-match Card component in the Stage area."""
    if not n_clicks or not context:
        return no_update, no_update
    if context.get("type") != "pre-match":
        return no_update, no_update
    payload = context.get("payload") or None
    return create_prematch_card(payload), {"display": "none"}


def generate_card_callback(n_clicks, context):
    """Generates a player card image via CompositionMotor and shows it in the gallery."""
    if not n_clicks or not context:
        return no_update, no_update
    payload = context.get("payload", {})
    try:
        from utils.image_generator import CompositionMotor

        motor = CompositionMotor()
        player_stats = payload.get("player_stats") or {}
        basic = player_stats.get("basic_info", {})
        player_id = str(
            basic.get("player_id") or basic.get("id") or "player"
        )
        stats = player_stats.get("performance_stats", {})
        club = basic.get("team", "")
        img_bytes = motor.compose_player_card(player_id, stats, club)
        _CARD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        img_path = _CARD_CACHE_DIR / f"{uuid.uuid4().hex}.png"
        img_path.write_bytes(img_bytes)
        return (
            render_image_gallery(str(img_path)),
            {"display": "inline-flex", "alignItems": "center"},
        )
    except Exception as exc:
        logger.error(f"generate_card error: {exc}")
        return dbc.Alert("No se pudo generar la card.", color="warning"), no_update


def caption_ai_callback(n_clicks, context):
    """Invokes the LangGraph agent to generate a social media caption for the match."""
    if not n_clicks or not context:
        return no_update
    if context.get("type") != "post-match":
        return no_update
    payload = context.get("payload", {})
    player_stats = payload.get("player_stats") or {}
    basic = player_stats.get("basic_info", {})
    player_name = basic.get("name") or payload.get("player_name", "el jugador")
    home = payload.get("home_team", "")
    away = payload.get("away_team", "")
    match_label = f"{home} vs {away}" if home and away else "el partido"
    query = (
        f"Genera un caption de redes sociales en español para {player_name} "
        f"tras el partido {match_label}. Máximo 280 caracteres. Incluye emojis."
    )
    agent_result = _run_agent_with_timeout(query, flow="player_analysis")
    if agent_result.get("timeout") or agent_result.get("error"):
        caption_text = f"¡Gran actuación de {player_name}! 💪⚽ #HKPremierLeague"
    else:
        caption_text = agent_result.get(
            "output", f"¡Gran actuación de {player_name}! 💪⚽ #HKPremierLeague"
        )
    return html.Div(
        dbc.Card(
            [
                dbc.CardHeader(
                    [
                        html.I(className="bi bi-pencil-square me-2"),
                        html.Span("Caption AI", className="fw-semibold"),
                    ],
                    className="border-0 py-2",
                ),
                dbc.CardBody(
                    [
                        html.P(
                            caption_text,
                            id="caption-text-content",
                            className="mb-3",
                        ),
                        dcc.Clipboard(
                            target_id="caption-text-content",
                            title="Copiar",
                            style={"display": "inline-block"},
                            className="btn btn-sm btn-outline-secondary",
                        ),
                    ]
                ),
            ],
            className="border-0 shadow-sm",
            color="dark",
            outline=True,
        ),
        className="glass-card",
    )



def show_proyectar_callback(n_clicks, context):
    """Renders the season performance projection chart in the Stage."""
    if not n_clicks or not context:
        return no_update
    if context.get("type") != "career":
        return no_update
    payload = context.get("payload", {})
    player_id = payload.get("player_id", "")
    season = payload.get("season", "")
    try:
        fig = get_projection_figure(player_id, season)
        if not fig.data:
            return dbc.Alert(
                f"Datos de proyección no disponibles para {season}.", color="info"
            )
        return html.Div(
            html.Div(
                [
                    html.H6(
                        "Proyección de Temporada",
                        className="fw-bold mb-3 text-success",
                    ),
                    dcc.Graph(
                        figure=fig,
                        config={"displayModeBar": False},
                        className="w-100",
                    ),
                ]
            ),
            className="glass-card",
        )
    except Exception as exc:
        logger.error(f"show_proyectar error: {exc}")
        return dbc.Alert(
            f"Datos de proyección no disponibles para {season}.", color="info"
        )


def export_dossier_pdf_callback(n_clicks, context):
    """Generates and downloads a player PDF dossier (agent role only)."""
    if not n_clicks or not context:
        return no_update, no_update
    user_role = getattr(current_user, "role", "player") if current_user else "player"
    if user_role != "agent":
        return no_update, no_update
    payload = context.get("payload", {})
    player_id = payload.get("player_id", "")
    player_name = payload.get("player_name", player_id)
    season = payload.get("season", "")
    try:
        from utils.image_generator import CompositionMotor
        from utils.pdf_generator import SportsPDFGenerator

        generator = SportsPDFGenerator()
        motor = CompositionMotor()
        buffer = generator.create_player_dossier(player_id, season, motor)
        pdf_bytes = buffer.read()
        safe_name = player_name.replace(" ", "_")
        filename = f"dossier_{safe_name}_{season}.pdf"
        return (
            dcc.send_bytes(pdf_bytes, filename=filename, type="application/pdf"),
            no_update,
        )
    except Exception as exc:
        logger.error(f"export_dossier_pdf error: {exc}")
        return no_update, dbc.Alert(
            "Error al generar el dossier PDF.", color="danger"
        )


def register_stage_action_callbacks(app):
    """Registers all Stage Action callbacks for Decision Node buttons."""

    # 4.2 — dn-ical
    app.callback(
        Output("stage-action-download", "data"),
        Input("dn-ical", "n_clicks"),
        State("stage-context-snapshot", "data"),
        prevent_initial_call=True,
    )(download_ical_callback)

    # 4.3 — dn-previa-card
    app.callback(
        Output("stage-content", "children", allow_duplicate=True),
        Output("gallery-close-btn", "style", allow_duplicate=True),
        Input("dn-previa-card", "n_clicks"),
        State("stage-context-snapshot", "data"),
        prevent_initial_call=True,
    )(show_previa_card_callback)

    # 4.4 — dn-generate-card
    app.callback(
        Output("stage-content", "children", allow_duplicate=True),
        Output("gallery-close-btn", "style", allow_duplicate=True),
        Input("dn-generate-card", "n_clicks"),
        State("stage-context-snapshot", "data"),
        prevent_initial_call=True,
    )(generate_card_callback)

    # 4.5 — dn-caption-ai
    app.callback(
        Output("stage-content", "children", allow_duplicate=True),
        Input("dn-caption-ai", "n_clicks"),
        State("stage-context-snapshot", "data"),
        prevent_initial_call=True,
    )(caption_ai_callback)

    # 4.8 — dn-dossier-pdf
    app.callback(
        Output("stage-action-download", "data", allow_duplicate=True),
        Output("stage-content", "children", allow_duplicate=True),
        Input("dn-dossier-pdf", "n_clicks"),
        State("stage-context-snapshot", "data"),
        prevent_initial_call=True,
    )(export_dossier_pdf_callback)
