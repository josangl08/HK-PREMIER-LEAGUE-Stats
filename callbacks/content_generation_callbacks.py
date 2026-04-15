# ABOUTME: Callbacks for content generation: player card upload/generation, prematch card export.
# ABOUTME: Handles photo upload (rembg), card download (Pillow), and agent batch ZIP generation.

# Standard Library
import base64
import logging
import zipfile
from io import BytesIO
from datetime import date
from pathlib import Path

# Third-party
import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, callback, ctx, html, no_update
from dash.dcc import send_bytes
from flask_login import current_user

# Project
from utils.image_generator import CompositionMotor

logger = logging.getLogger(__name__)

# ── Design tokens (keep in sync with agent_view.py) ──────────────────────────
_BG_PRIMARY   = "#18181A"
_BG_SECONDARY = "#232326"
_BG_TERTIARY  = "#2C2C2E"
_BORDER       = "#3A3A3C"
_ACCENT       = "#93312a"
_ACCENT_LIGHT = "#b84040"
_TEXT         = "#FFFFFF"
_TEXT_MUTED   = "#A7A7A7"

_motor = CompositionMotor()


# ─────────────────────────────────────────────────────────────────────────────
# Feature A — Player Photo Upload
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output('upload-status-msg', 'children'),
    Output('player-cutouts-gallery', 'children'),
    Input('player-photo-upload', 'contents'),
    State('player-photo-upload', 'filename'),
    prevent_initial_call=True,
)
def handle_photo_upload(contents, filename):
    """Decode upload, remove background via rembg, cache cutout, refresh gallery."""
    if not current_user.is_authenticated or current_user.role not in ('player', 'admin'):
        return dbc.Alert("Acceso denegado.", color="danger"), no_update

    player_id = getattr(current_user, 'player_id', None) or current_user.username

    try:
        _content_type, content_string = contents.split(',', 1)
        image_bytes = base64.b64decode(content_string)
        _motor.process_player_photo(player_id, image_bytes)
        status = dbc.Alert(
            f"Silueta generada correctamente ({filename}).",
            color="success",
            duration=4000,
        )
    except RuntimeError as e:
        return dbc.Alert(str(e), color="warning"), no_update
    except Exception as e:
        logger.error(f"Photo upload error for player '{player_id}': {e}")
        return dbc.Alert(f"Error procesando imagen: {str(e)}", color="danger"), no_update

    return status, _build_cutout_gallery(player_id)


@callback(
    Output('player-cutouts-gallery', 'children', allow_duplicate=True),
    Input({"type": "cutout-delete-btn", "index": ALL}, 'n_clicks'),
    prevent_initial_call=True,
)
def delete_cutout(n_clicks_list):
    """Delete the clicked cutout from disk and refresh the gallery."""
    if not any(n_clicks_list):
        return no_update

    if not current_user.is_authenticated or current_user.role not in ('player', 'admin'):
        return no_update

    triggered = ctx.triggered_id
    if not triggered or not isinstance(triggered, dict):
        return no_update

    filename = triggered.get("index")
    if not filename:
        return no_update

    player_id = getattr(current_user, 'player_id', None) or current_user.username
    _motor.delete_cutout(player_id, filename)
    return _build_cutout_gallery(player_id)


@callback(
    Output('player-card-download', 'data'),
    Input('generate-card-btn', 'n_clicks'),
    State('card-size-selector', 'value'),
    State('performance-data-store', 'data'),
    prevent_initial_call=True,
)
def generate_player_card(n_clicks, size, perf_data):
    """Compose player card and trigger download."""
    if not n_clicks:
        return no_update
    if not current_user.is_authenticated or current_user.role not in ('player', 'admin'):
        return no_update

    player_id = getattr(current_user, 'player_id', None) or current_user.username
    stats = _extract_player_stats(perf_data)
    stats.setdefault('name', getattr(current_user, 'player_name', None) or player_id)
    club = stats.get('team') or _get_player_team()

    try:
        png_bytes = _motor.compose_player_card(player_id, stats, club, size or 'square')
    except Exception as e:
        logger.error(f"Card generation error for player '{player_id}': {e}")
        return no_update

    filename = f"{player_id}_card_{date.today().isoformat()}.png"
    return send_bytes(png_bytes, filename)


# ─────────────────────────────────────────────────────────────────────────────
# Feature B — Pre-match Card Social Export
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output('prematch-card-download', 'data'),
    Input('prematch-dl-btn', 'n_clicks'),
    prevent_initial_call=True,
)
def download_prematch_card(n_clicks):
    """Compose pre-match social card image and trigger download."""
    if not n_clicks:
        return no_update
    if not current_user.is_authenticated:
        return no_update

    fixture = _get_current_fixture()
    if not fixture:
        return no_update

    try:
        png_bytes = _motor.compose_prematch_card(fixture, 'square')
    except Exception as e:
        logger.error(f"Prematch card error: {e}")
        return no_update

    home = (fixture.get('home_team') or 'home').replace(' ', '_')
    away = (fixture.get('away_team') or 'away').replace(' ', '_')
    filename = f"prematch_{home}_vs_{away}_{date.today().isoformat()}.png"
    return send_bytes(png_bytes, filename)


# ─────────────────────────────────────────────────────────────────────────────
# Feature C — Agent Portal Roster & Batch Generation
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output('agent-player-selection', 'value', allow_duplicate=True),
    Input('agent-select-all-btn', 'n_clicks'),
    Input('agent-clear-btn', 'n_clicks'),
    State('agent-player-selection', 'options'),
    prevent_initial_call=True,
)
def handle_select_all_clear(select_clicks, clear_clicks, options):
    """Select all or clear the agent roster checklist."""
    if not options:
        return []
    if ctx.triggered_id == 'agent-select-all-btn':
        return [o['value'] for o in options]
    return []


@callback(
    Output('agent-batch-download', 'data'),
    Input('agent-batch-download-btn', 'n_clicks'),
    State('agent-player-selection', 'value'),
    State('agent-batch-format', 'value'),
    prevent_initial_call=True,
)
def generate_batch(n_clicks, selected_players, fmt):
    """
    Generate player cards and/or PDF dossiers for selected players.
    Packages all files into a ZIP and triggers download.
    """
    if not n_clicks or not selected_players:
        return no_update
    if not current_user.is_authenticated or current_user.role not in ('agent', 'admin'):
        return no_update

    zip_buffer = BytesIO()
    today = date.today().isoformat()
    agent_name = current_user.username

    try:
        dm = _get_data_manager()
        current_season = getattr(dm, 'current_season', '2024-25')

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for player_id in selected_players:
                stats = _get_player_stats_from_dm(dm, player_id)
                club = stats.get('team', '')

                if fmt in ('png', 'both'):
                    try:
                        png_bytes = _motor.compose_player_card(player_id, stats, club, 'square')
                        zf.writestr(f"{player_id}_card.png", png_bytes)
                    except Exception as e:
                        logger.warning(f"Card generation failed for '{player_id}': {e}")

                if fmt in ('pdf', 'both'):
                    try:
                        from utils.pdf_generator import SportsPDFGenerator
                        gen = SportsPDFGenerator()
                        pdf_buf = gen.create_player_dossier(player_id, current_season, _motor)
                        zf.writestr(f"{player_id}_dossier.pdf", pdf_buf.read())
                    except Exception as e:
                        logger.warning(f"Dossier generation failed for '{player_id}': {e}")

        zip_buffer.seek(0)
        filename = f"{agent_name}_batch_{today}.zip"
        return send_bytes(zip_buffer.read(), filename)

    except Exception as e:
        logger.error(f"Batch generation error: {e}")
        return no_update


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_cutout_gallery(player_id: str):
    """Build a gallery of cutout thumbnails from cached PNGs, each with a delete button."""
    cutouts = _motor.get_cutouts(player_id)
    if not cutouts:
        return html.P(
            "No hay siluetas disponibles. Sube una foto para comenzar.",
            className="text-muted small",
        )

    thumbnails = []
    for path in cutouts:
        try:
            filename = Path(path).name
            with open(path, 'rb') as f:
                data = base64.b64encode(f.read()).decode()
            thumbnails.append(
                html.Div([
                    html.Img(
                        src=f"data:image/png;base64,{data}",
                        style={
                            "width": "80px", "height": "80px",
                            "objectFit": "cover", "borderRadius": "8px",
                            "border": "1px solid #3A3A3C",
                            "display": "block",
                        },
                    ),
                    html.Button(
                        html.I(className="bi bi-x"),
                        id={"type": "cutout-delete-btn", "index": filename},
                        n_clicks=0,
                        title="Eliminar imagen",
                        style={
                            "position": "absolute", "top": "2px", "right": "2px",
                            "width": "20px", "height": "20px",
                            "padding": "0", "border": "none",
                            "borderRadius": "50%",
                            "background": "rgba(200,40,40,0.85)",
                            "color": "#fff", "fontSize": "11px",
                            "lineHeight": "1", "cursor": "pointer",
                            "display": "flex", "alignItems": "center", "justifyContent": "center",
                        },
                    ),
                ], style={"position": "relative", "display": "inline-block"})
            )
        except Exception:
            continue

    remaining = _motor.MAX_CUTOUTS - len(cutouts)
    caption = html.Small(
        f"{len(cutouts)}/{_motor.MAX_CUTOUTS} siluetas — {remaining} espacio(s) disponible(s)",
        className="text-muted d-block mt-2",
    )
    return [
        html.Div(thumbnails, className="d-flex flex-wrap gap-2"),
        caption,
    ]


def _extract_player_stats(perf_data: dict) -> dict:
    """Extract relevant stats from performance-data-store payload."""
    if not perf_data:
        return {}
    basic = perf_data.get('basic_info', {})
    perf = perf_data.get('performance_stats', {})
    return {
        'name': basic.get('name', ''),
        'team': basic.get('team', ''),
        'goals': perf.get('goals', 0),
        'assists': perf.get('assists', 0),
        'matches_played': perf.get('matches_played', 0),
    }


def _get_player_team() -> str:
    """Retrieve current player's team from their profile in users.json."""
    try:
        from utils.auth import AuthRepository
        user_data = AuthRepository._load_all_users().get(current_user.username, {})
        return user_data.get('player_profile', {}).get('team', '')
    except Exception:
        return ''


def _get_current_fixture() -> dict:
    """Fetch next fixture for current player's team (mirrors fixture_callbacks logic)."""
    try:
        from utils.auth import AuthRepository
        user_data = AuthRepository._load_all_users().get(current_user.username, {})
        team = user_data.get('player_profile', {}).get('team')
        if not team:
            return None
        dm = _get_data_manager()
        return dm.get_next_fixture(team)
    except Exception as e:
        logger.warning(f"Could not fetch fixture: {e}")
        return None


def _get_data_manager():
    from utils.app_context import get_hong_kong_data_manager
    return get_hong_kong_data_manager()


def _get_player_stats_from_dm(dm, player_id: str) -> dict:
    """Extract stats for a player from the data manager."""
    try:
        if hasattr(dm, 'get_player_performance'):
            stats = dm.get_player_performance(player_id, getattr(dm, 'current_season', '2024-25'))
            if stats:
                return stats
    except Exception:
        pass
    return {'name': player_id, 'team': '', 'goals': 0, 'assists': 0, 'matches_played': 0}


# ─────────────────────────────────────────────────────────────────────────────
# Feature C — Agent Roster Management
# ─────────────────────────────────────────────────────────────────────────────

def _load_agent_roster(username: str) -> list:
    """Read managed_players from users.json for the given agent."""
    try:
        from utils.auth import AuthRepository
        users = AuthRepository._load_all_users()
        return list(users.get(username, {}).get('managed_players', []))
    except Exception as e:
        logger.error(f"Error loading roster for '{username}': {e}")
        return []


def _save_agent_roster(username: str, roster: list) -> bool:
    """Persist managed_players list for an agent to users.json."""
    try:
        from utils.auth import AuthRepository
        users = AuthRepository._load_all_users()
        if username in users:
            users[username]['managed_players'] = roster
            AuthRepository._save_all_users(users)
            return True
    except Exception as e:
        logger.error(f"Error saving roster for '{username}': {e}")
    return False


def _build_roster_ui(roster: list):
    """
    Build visual roster list with remove buttons and checklist options.
    Returns (roster_list_children, checklist_options, count_text).
    """
    if not roster:
        empty = html.P(
            "Tu roster está vacío. Añade jugadores usando el buscador.",
            className="text-center py-3",
            style={"color": _TEXT_MUTED, "fontSize": "0.85rem"},
        )
        return empty, [], "Sin jugadores en el roster"

    items = []
    for player_name in roster:
        items.append(
            html.Div([
                html.Div([
                    html.I(className="bi bi-person-fill me-2",
                           style={"color": _ACCENT_LIGHT, "fontSize": "0.9rem"}),
                    html.Span(player_name, style={"color": _TEXT, "fontSize": "0.9rem"}),
                ], className="d-flex align-items-center"),
                dbc.Button(
                    html.I(className="bi bi-x-lg"),
                    id={"type": "agent-remove-btn", "index": player_name},
                    size="sm",
                    color="link",
                    style={"color": _TEXT_MUTED, "padding": "0 4px",
                           "lineHeight": "1", "fontSize": "0.8rem"},
                    n_clicks=0,
                ),
            ], className="d-flex justify-content-between align-items-center",
               style={
                   "padding": "6px 8px",
                   "borderBottom": f"1px solid {_BORDER}",
                   "borderRadius": "4px",
                   "marginBottom": "2px",
               })
        )

    options = [{"label": f"  {p}", "value": p} for p in roster]
    count_text = f"Roster: {len(roster)} jugador{'es' if len(roster) != 1 else ''}"
    return items, options, count_text


@callback(
    Output('agent-add-player-dropdown', 'options'),
    Output('agent-roster-list', 'children'),
    Output('agent-player-selection', 'options'),
    Output('agent-player-selection', 'value'),
    Output('agent-roster-count', 'children'),
    Input('url', 'pathname'),
    prevent_initial_call=False,
)
def load_agent_portal(pathname):
    """Populate player search dropdown and roster list on page load."""
    if pathname != '/agent-portal':
        return no_update, no_update, no_update, no_update, no_update
    if not current_user.is_authenticated or current_user.role not in ('agent', 'admin'):
        return [], [], [], [], ""

    try:
        from utils.player_index import get_player_index
        all_names = sorted(get_player_index().get_all_player_names())
        all_options = [{"label": n, "value": n} for n in all_names]
    except Exception:
        all_options = []

    roster = _load_agent_roster(current_user.username)
    roster_ui, checklist_opts, count_text = _build_roster_ui(roster)
    return all_options, roster_ui, checklist_opts, [], count_text


@callback(
    Output('agent-roster-list', 'children', allow_duplicate=True),
    Output('agent-player-selection', 'options', allow_duplicate=True),
    Output('agent-player-selection', 'value', allow_duplicate=True),
    Output('agent-roster-count', 'children', allow_duplicate=True),
    Output('agent-roster-feedback', 'children'),
    Output('agent-add-player-dropdown', 'value'),
    Input('agent-add-player-btn', 'n_clicks'),
    State('agent-add-player-dropdown', 'value'),
    prevent_initial_call=True,
)
def add_player_to_roster(n_clicks, player_name):
    """Add the selected player to the agent's managed_players and refresh the UI."""
    if not n_clicks or not player_name:
        return no_update, no_update, no_update, no_update, no_update, no_update

    if not current_user.is_authenticated or current_user.role not in ('agent', 'admin'):
        return (no_update, no_update, no_update, no_update,
                dbc.Alert("Acceso denegado.", color="danger", duration=3000), no_update)

    roster = _load_agent_roster(current_user.username)

    if player_name in roster:
        feedback = dbc.Alert(
            f"{player_name} ya está en tu roster.", color="warning", duration=3000,
        )
        return no_update, no_update, no_update, no_update, feedback, None

    roster.append(player_name)
    _save_agent_roster(current_user.username, roster)

    roster_ui, checklist_opts, count_text = _build_roster_ui(roster)
    feedback = dbc.Alert(
        [html.I(className="bi bi-check-circle me-2"), f"{player_name} añadido al roster."],
        color="success", duration=3000,
    )
    return roster_ui, checklist_opts, [], count_text, feedback, None


@callback(
    Output('agent-roster-list', 'children', allow_duplicate=True),
    Output('agent-player-selection', 'options', allow_duplicate=True),
    Output('agent-player-selection', 'value', allow_duplicate=True),
    Output('agent-roster-count', 'children', allow_duplicate=True),
    Output('agent-roster-feedback', 'children', allow_duplicate=True),
    Input({"type": "agent-remove-btn", "index": ALL}, 'n_clicks'),
    prevent_initial_call=True,
)
def remove_player_from_roster(n_clicks_list):
    """Remove the clicked player from the agent's roster."""
    if not any(n_clicks_list):
        return no_update, no_update, no_update, no_update, no_update

    if not current_user.is_authenticated or current_user.role not in ('agent', 'admin'):
        return no_update, no_update, no_update, no_update, no_update

    triggered = ctx.triggered_id
    if not triggered or not isinstance(triggered, dict):
        return no_update, no_update, no_update, no_update, no_update

    player_name = triggered.get("index")
    if not player_name:
        return no_update, no_update, no_update, no_update, no_update

    roster = _load_agent_roster(current_user.username)
    if player_name in roster:
        roster.remove(player_name)
        _save_agent_roster(current_user.username, roster)

    roster_ui, checklist_opts, count_text = _build_roster_ui(roster)
    feedback = dbc.Alert(
        [html.I(className="bi bi-trash me-2"), f"{player_name} eliminado del roster."],
        color="secondary", duration=3000,
    )
    return roster_ui, checklist_opts, [], count_text, feedback
