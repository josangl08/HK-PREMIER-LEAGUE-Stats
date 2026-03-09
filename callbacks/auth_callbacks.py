# ABOUTME: Callbacks for login, logout, and user registration flows.
# ABOUTME: Delegates credential validation and user creation to AuthRepository.

import csv as _csv
from pathlib import Path

from dash import Input, Output, State, callback, clientside_callback, html, no_update
import dash_bootstrap_components as dbc
from flask_login import login_user, logout_user
from utils.auth import AuthRepository
from utils.app_context import get_hong_kong_data_manager
from utils.player_index import get_player_index
from dash.exceptions import PreventUpdate
import logging

logger = logging.getLogger(__name__)

# ── CSV season mapping (mirrors player_index constants) ─────────────────────
_SEASON_FILES = {
    "2018-19": "hong_kong_2018_19.csv",
    "2019-20": "hong_kong_2019_20.csv",
    "2020-21": "hong_kong_2020_21.csv",
    "2021-22": "hong_kong_2021_22.csv",
    "2022-23": "hong_kong_2022_23.csv",
    "2023-24": "hong_kong_2023_24.csv",
    "2024-25": "hong_kong_2024_25.csv",
    "2025-26": "hong_kong_2025_26.csv",
}
_CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"


# ── Clientside callback: accent/case-insensitive dropdown search ─────────────
clientside_callback(
    """
    function(search_value, all_options, current_value) {
        if (!all_options || all_options.length === 0) return [];

        var normalize = function(s) {
            return (s || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
        };

        if (!search_value) return all_options;

        var norm_search = normalize(search_value);
        var filtered = all_options.filter(function(opt) {
            return normalize(opt.label).indexOf(norm_search) !== -1;
        });

        // Always keep the currently selected option visible
        if (current_value) {
            var hasSelected = filtered.some(function(opt) { return opt.value === current_value; });
            if (!hasSelected) {
                var selectedOpt = all_options.find(function(opt) { return opt.value === current_value; });
                if (selectedOpt) filtered.unshift(selectedOpt);
            }
        }

        return filtered;
    }
    """,
    Output('reg-player-name-dropdown', 'options'),
    Input('reg-player-name-dropdown', 'search_value'),
    State('player-names-store', 'data'),
    State('reg-player-name-dropdown', 'value'),
)


# ── Clientside callback: role toggle (Player / Agent) ────────────────────────
clientside_callback(
    """
    function(playerClicks, agentClicks) {
        var ctx = dash_clientside.callback_context;
        if (!ctx || !ctx.triggered || ctx.triggered.length === 0) {
            return ['player',
                    {display: 'block'}, {display: 'none'},
                    {backgroundColor:'#93312a',borderColor:'#93312a',color:'white',fontWeight:'bold',width:'50%',borderRadius:'6px 0 0 6px'},
                    {backgroundColor:'transparent',borderColor:'#93312a',color:'#93312a',fontWeight:'bold',width:'50%',borderRadius:'0 6px 6px 0'}];
        }
        var triggeredId = ctx.triggered_id;
        var isAgent = triggeredId === 'reg-role-btn-agent';
        var activeStyle  = {backgroundColor:'#93312a',borderColor:'#93312a',color:'white',fontWeight:'bold',width:'50%'};
        var inactiveStyle = {backgroundColor:'transparent',borderColor:'#93312a',color:'#93312a',fontWeight:'bold',width:'50%'};
        var playerActiveStyle  = Object.assign({}, activeStyle,  {borderRadius:'6px 0 0 6px'});
        var agentActiveStyle   = Object.assign({}, activeStyle,  {borderRadius:'0 6px 6px 0'});
        var playerInactiveStyle = Object.assign({}, inactiveStyle, {borderRadius:'6px 0 0 6px'});
        var agentInactiveStyle  = Object.assign({}, inactiveStyle, {borderRadius:'0 6px 6px 0'});
        return [
            isAgent ? 'agent' : 'player',
            isAgent ? {display:'none'} : {display:'block'},
            isAgent ? {display:'block'} : {display:'none'},
            isAgent ? playerInactiveStyle : playerActiveStyle,
            isAgent ? agentActiveStyle : agentInactiveStyle
        ];
    }
    """,
    Output('reg-role-store', 'data'),
    Output('reg-player-fields', 'style'),
    Output('reg-agent-fields', 'style'),
    Output('reg-role-btn-player', 'style'),
    Output('reg-role-btn-agent', 'style'),
    Input('reg-role-btn-player', 'n_clicks'),
    Input('reg-role-btn-agent', 'n_clicks'),
)


# ── Initialize dropdown options when register form mounts ───────────────────
@callback(
    Output('reg-player-name-dropdown', 'options', allow_duplicate=True),
    Input('auth-form-content', 'children'),
    State('player-names-store', 'data'),
    prevent_initial_call=True
)
def init_player_dropdown_on_mount(_, store_data):
    """Puebla el dropdown con todas las opciones al montar el formulario de registro."""
    return store_data or []


# ── Login ────────────────────────────────────────────────────────────────────
@callback(
    [Output('login-feedback', 'children'),
     Output('login-status', 'data'),
     Output('url', 'pathname')],
    [Input('login-button', 'n_clicks')],
    [State('username-input', 'value'),
     State('password-input', 'value')],
    prevent_initial_call=True
)
def login_callback(n_clicks, username, password):
    """Maneja el proceso de login con redirección según el rol del usuario."""
    if n_clicks is None:
        raise PreventUpdate

    if not username or not password:
        return _error_alert("Introduce usuario y contraseña."), no_update, no_update

    try:
        user = AuthRepository.validate_credentials(username, password)

        if user:
            login_user(user)
            logger.info(f"Login exitoso para {username} (role={user.role})")
            redirect_path = '/' if user.role == 'admin' else '/performance'
            return None, 'success', redirect_path
        else:
            logger.warning(f"Login fallido para {username}")
            return _error_alert("Usuario o contraseña incorrectos."), 'failed', no_update

    except Exception as e:
        logger.error(f"Error durante el login: {e}")
        return _error_alert("Error interno. Inténtalo de nuevo."), 'failed', no_update


# ── Logout ───────────────────────────────────────────────────────────────────
@callback(
    Output('logout-trigger', 'pathname'),
    Input('logout-button', 'n_clicks'),
    prevent_initial_call=True
)
def logout_callback(n_clicks):
    """Maneja el proceso de logout del usuario."""
    if n_clicks is None:
        raise PreventUpdate

    try:
        logout_user()
        logger.info("Usuario ha cerrado sesión")
        return '/login'
    except Exception as e:
        logger.error(f"Error durante el logout: {e}")
        return '/login'


# ── Registration ─────────────────────────────────────────────────────────────
MIN_PASSWORD_LENGTH = 8

_NO_AGENT_ERRORS = (no_update, no_update, no_update)


@callback(
    [Output('username-feedback', 'children'),
     Output('password-feedback', 'children'),
     Output('confirm-password-feedback', 'children'),
     Output('register-feedback', 'children'),
     Output('url', 'pathname', allow_duplicate=True),
     Output('agent-fullname-feedback', 'children'),
     Output('agent-agency-feedback', 'children'),
     Output('agent-email-feedback', 'children')],
    [Input('register-button', 'n_clicks')],
    [State('reg-username-input', 'value'),
     State('reg-password-input', 'value'),
     State('reg-confirm-password-input', 'value'),
     State('reg-role-store', 'data'),
     State('reg-player-name-dropdown', 'value'),
     State('reg-agent-fullname-input', 'value'),
     State('reg-agent-agency-input', 'value'),
     State('reg-agent-email-input', 'value'),
     State('reg-agent-license-input', 'value')],
    prevent_initial_call=True
)
def handle_registration(n_clicks, username, password, confirm_password,
                        role, player_name,
                        agent_fullname, agent_agency, agent_email, agent_license):
    """
    Valida y registra un nuevo usuario (player o agent) con mensajes de error por campo.
    Devuelve 8 outputs: username_err, password_err, confirm_err, feedback,
                        pathname, fullname_err, agency_err, email_err.
    """
    if n_clicks is None:
        raise PreventUpdate

    role = role or 'player'

    # ── Validaciones comunes ─────────────────────────────────────────────
    username_err = None
    password_err = None
    confirm_err = None

    if not username or not username.strip():
        username_err = _field_warning("Campo requerido.")

    if not password:
        password_err = _field_warning("Campo requerido.")
    elif len(password) < MIN_PASSWORD_LENGTH:
        password_err = _field_warning(f"Mínimo {MIN_PASSWORD_LENGTH} caracteres.")

    if not confirm_password:
        confirm_err = _field_warning("Campo requerido.")
    elif password and confirm_password != password:
        confirm_err = _field_warning("Las contraseñas no coinciden.")

    if username_err or password_err or confirm_err:
        return (username_err, password_err, confirm_err, None, no_update) + _NO_AGENT_ERRORS

    # ── Rama: Player ─────────────────────────────────────────────────────
    if role == 'player':
        if not player_name:
            return (
                username_err, password_err, confirm_err,
                _error_alert("Debes seleccionar tu identidad de jugador."),
                no_update
            ) + _NO_AGENT_ERRORS

        try:
            player_id = get_player_index().get_player_id(player_name)
            if not player_id:
                return (
                    None, None, None,
                    _error_alert(f"El jugador '{player_name}' no existe en los datos de la liga."),
                    no_update
                ) + _NO_AGENT_ERRORS

            logger.info(f"Player ID resuelto para '{player_name}': {player_id}")
            dm = get_hong_kong_data_manager()
            player_profile = _extract_player_profile(dm, player_name, player_id=player_id)

        except Exception as e:
            logger.error(f"Error consultando DataManager durante registro: {e}")
            return (
                None, None, None,
                _error_alert("Error al verificar los datos de jugadores. Inténtalo de nuevo."),
                no_update
            ) + _NO_AGENT_ERRORS

        try:
            created = AuthRepository.create_user(
                username=username,
                password=password,
                role='player',
                player_name=player_name,
                player_profile=player_profile,
                player_id=player_id,
            )
            if created:
                logger.info(
                    f"Nuevo usuario registrado: {username} "
                    f"(player={player_name}, team={player_profile.get('team', '?')}, "
                    f"season={player_profile.get('season', '?')})"
                )
                return (None, None, None, None, '/login') + _NO_AGENT_ERRORS
            else:
                return (
                    _field_warning(f"El nombre de usuario '{username}' ya está en uso."),
                    None, None, None, no_update
                ) + _NO_AGENT_ERRORS
        except Exception as e:
            logger.error(f"Error durante el registro de {username}: {e}")
            return (
                None, None, None,
                _error_alert("Error interno al crear la cuenta. Inténtalo de nuevo."),
                no_update
            ) + _NO_AGENT_ERRORS

    # ── Rama: Agent ──────────────────────────────────────────────────────
    fullname_err = None
    agency_err = None
    email_err = None

    if not agent_fullname or not agent_fullname.strip():
        fullname_err = _field_warning("Campo requerido.")
    if not agent_agency or not agent_agency.strip():
        agency_err = _field_warning("Campo requerido.")
    if not agent_email or not _validate_email(agent_email):
        email_err = _field_warning("Introduce un correo válido.")

    if fullname_err or agency_err or email_err:
        return (None, None, None, None, no_update, fullname_err, agency_err, email_err)

    agent_profile = {
        'full_name': agent_fullname.strip(),
        'agency': agent_agency.strip(),
        'email': agent_email.strip(),
        'license_number': (agent_license or '').strip() or None,
    }

    try:
        created = AuthRepository.create_user(
            username=username,
            password=password,
            role='agent',
            agent_profile=agent_profile,
        )
        if created:
            logger.info(f"Nuevo agente registrado: {username} (agency={agent_profile['agency']})")
            return (None, None, None, None, '/login') + _NO_AGENT_ERRORS
        else:
            return (
                _field_warning(f"El nombre de usuario '{username}' ya está en uso."),
                None, None, None, no_update
            ) + _NO_AGENT_ERRORS
    except Exception as e:
        logger.error(f"Error durante el registro de agente {username}: {e}")
        return (
            None, None, None,
            _error_alert("Error interno al crear la cuenta. Inténtalo de nuevo."),
            no_update
        ) + _NO_AGENT_ERRORS


# ── Blur validation: password ────────────────────────────────────────────────
@callback(
    Output('password-feedback', 'children', allow_duplicate=True),
    Input('reg-password-input', 'n_blur'),
    State('reg-password-input', 'value'),
    prevent_initial_call=True
)
def validate_password_blur(n_blur, password):
    if not password:
        return None
    if len(password) < MIN_PASSWORD_LENGTH:
        return _field_warning(f"Mínimo {MIN_PASSWORD_LENGTH} caracteres.")
    return None


# ── Blur validation: confirm password ───────────────────────────────────────
@callback(
    Output('confirm-password-feedback', 'children', allow_duplicate=True),
    Input('reg-confirm-password-input', 'n_blur'),
    State('reg-confirm-password-input', 'value'),
    State('reg-password-input', 'value'),
    prevent_initial_call=True
)
def validate_confirm_password_blur(n_blur, confirm, password):
    if not confirm or not password:
        return None
    if confirm != password:
        return _field_warning("Las contraseñas no coinciden.")
    return None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_player_profile(dm, player_name: str, player_id: str = None) -> dict:
    """
    Extrae datos de perfil para asociar al usuario en el momento del registro.
    Intenta la temporada actual vía aggregator; si el jugador no está activo,
    lee el CSV de la última temporada disponible del índice histórico.
    """
    # Intento 1: temporada actual via aggregator
    try:
        overview = dm.get_player_overview(player_name)
        basic = overview.get('basic_info', {})
        if any(v is not None for v in basic.values()):
            return {
                'team': basic.get('team'),
                'position': basic.get('position'),
                'position_group': basic.get('position_group'),
                'age': basic.get('age'),
                'foot': basic.get('foot'),
                'height': basic.get('height'),
                'weight': basic.get('weight'),
                'market_value': basic.get('market_value'),
                'season': dm.current_season,
            }
    except Exception as e:
        logger.warning(f"Lookup en temporada actual fallido para '{player_name}': {e}")

    # Intento 2: última temporada disponible en el índice histórico
    if player_id:
        player_info = get_player_index().get_player_info(player_id)
        if player_info and player_info.get('seasons'):
            last_season = sorted(player_info['seasons'])[-1]
            logger.info(f"Leyendo perfil de '{player_name}' desde CSV de {last_season}")
            profile = _read_profile_from_csv(player_name, last_season)
            if profile:
                return profile

    logger.warning(f"No se encontró perfil para '{player_name}' en ninguna temporada.")
    return {}


def _read_profile_from_csv(player_name: str, season: str) -> dict:
    """Lee el perfil de un jugador directamente desde el CSV cacheado de una temporada."""
    csv_path = _CACHE_DIR / _SEASON_FILES.get(season, '')
    if not csv_path.exists():
        logger.warning(f"CSV no encontrado para temporada {season}: {csv_path}")
        return {}

    try:
        with open(csv_path, encoding='utf-8-sig') as f:
            reader = _csv.DictReader(f)
            for row in reader:
                if row.get('Player', '').strip() == player_name:
                    team = (
                        row.get('Team within selected timeframe', '').strip()
                        or row.get('Team', '').strip()
                        or None
                    )
                    pos = row.get('Position', '').strip() or None

                    def _int(val):
                        v = (val or '').strip()
                        return int(v) if v else None

                    return {
                        'team': team,
                        'position': pos,
                        'position_group': _infer_position_group(pos or ''),
                        'age': _int(row.get('Age')),
                        'foot': row.get('Foot', '').strip() or None,
                        'height': _int(row.get('Height')),
                        'weight': _int(row.get('Weight')),
                        'market_value': _int(row.get('Market value')),
                        'season': season,
                    }
    except Exception as e:
        logger.warning(f"Error leyendo CSV para '{player_name}' ({season}): {e}")

    return {}


def _infer_position_group(position: str) -> str | None:
    """Deduce el grupo de posición a partir de los códigos de posición de Wyscout."""
    pos = position.lower()
    if 'gk' in pos:
        return 'Goalkeeper'
    if any(p in pos for p in ['cb', 'lb', 'rb', 'wb']):
        return 'Defender'
    if any(p in pos for p in ['dm', 'cm', 'am', 'lm', 'rm']):
        return 'Midfielder'
    if any(p in pos for p in ['lw', 'rw', 'cf', 'ss', 'st', 'fw']):
        return 'Forward'
    return None


def _validate_email(email: str) -> bool:
    """Validación básica de formato de email — sin dependencias externas."""
    email = (email or '').strip()
    return bool(email) and '@' in email and '.' in email.split('@')[-1]


def _field_warning(message: str):
    """Genera un aviso de error a nivel de campo."""
    return html.Small(message, className="text-danger d-block mt-1")


def _error_alert(message: str):
    """Genera un componente de alerta de error para el formulario de registro."""
    return dbc.Alert(message, color="danger", dismissable=True, className="mb-3")
