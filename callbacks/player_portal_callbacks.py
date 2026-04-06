# ABOUTME: Callbacks for the Player Portal Phase 3 interactive timeline with client-side expand/collapse and scroll-sync.
# ABOUTME: Handles Timeline population, milestone selection, Stage rendering, sliding panels, year-scroll, and Action Node gallery.

import logging
from dash import Input, Output, State, callback, html, no_update, ALL, ctx, dcc
import dash_bootstrap_components as dbc
from flask_login import current_user

from data.aggregators.timeline_aggregator import TimelineAggregator
from data.aggregators.hong_kong_aggregator import get_h2h_record
from utils.stage_helpers import (
    render_post_match,
    render_pre_match,
    render_career_insights,
    render_career_overview,
    render_player_dashboard,
    get_cached_image_path,
    render_image_gallery,
    _get_position_group,
)
from utils.performance_helpers import get_streaming_label
from utils.app_context import get_hong_kong_data_manager
from utils.competition_helpers import normalize_competition, get_competition_logo

import html as _html_lib

logger = logging.getLogger(__name__)

# Static team color palette — sourced from official club identity (Badge and Kits)
_TEAM_COLORS = {
    "kitchee": {
        "badge": ["#14236b", "#e7b330", "#848cb2"],
        "kit_home": ["#091e47", "#db5d96", "#0a468c"],
        "kit_away": ["#dfdeeb", "#eb4380"],
        "colour1": "#14236b",
        "colour2": "#e7b330"
    },
    "kitchee sc": {
        "badge": ["#14236b", "#e7b330", "#848cb2"],
        "kit_home": ["#091e47", "#db5d96", "#0a468c"],
        "kit_away": ["#dfdeeb", "#eb4380"],
        "colour1": "#14236b",
        "colour2": "#e7b330"
    },
    "eastern": {
        "badge": ["#224283", "#d3242b", "#e6c8cd"],
        "kit_home": ["#1e407e"],
        "kit_away": ["#d0d0d5"],
        "colour1": "#224283",
        "colour2": "#d3242b"
    },
    "eastern aa": {
        "badge": ["#224283", "#d3242b", "#e6c8cd"],
        "kit_home": ["#1e407e"],
        "kit_away": ["#d0d0d5"],
        "colour1": "#224283",
        "colour2": "#d3242b"
    },
    "eastern sc": {
        "badge": ["#224283", "#d3242b", "#e6c8cd"],
        "kit_home": ["#1e407e"],
        "kit_away": ["#d0d0d5"],
        "colour1": "#224283",
        "colour2": "#d3242b"
    },
    "eastern district": {
        "badge": ["#e1e3e5", "#0d1c35", "#646d78"],
        "kit_home": ["#16233a", "#d5dbe0", "#387287"],
        "kit_away": ["#e9363a", "#f7e4e7", "#e68184"],
        "colour1": "#0d1c35",
        "colour2": "#e1e3e5"
    },
    "lee man": {
        "badge": ["#e7b844", "#1b2180", "#e30513"],
        "kit_home": ["#edcc55"],
        "kit_away": ["#1f2837", "#edcc55"],
        "colour1": "#e7b844",
        "colour2": "#1b2180"
    },
    "lee man fc": {
        "badge": ["#e7b844", "#1b2180", "#e30513"],
        "kit_home": ["#edcc55"],
        "kit_away": ["#1f2837", "#edcc55"],
        "colour1": "#e7b844",
        "colour2": "#1b2180"
    },
    "southern district": {
        "badge": ["#b91329", "#064276", "#e0cbcd"],
        "kit_home": ["#d81d3b", "#e9d6da", "#632c38"],
        "kit_away": ["#2b3854", "#b8c7e7"],
        "colour1": "#b91329",
        "colour2": "#064276"
    },
    "southern": {
        "badge": ["#b91329", "#064276", "#e0cbcd"],
        "kit_home": ["#d81d3b", "#e9d6da", "#632c38"],
        "kit_away": ["#2b3854", "#b8c7e7"],
        "colour1": "#b91329",
        "colour2": "#064276"
    },
    "rangers": {
        "badge": ["#a7e1fa", "#05a6e8", "#5ac5f1"],
        "kit_home": ["#2179c0", "#c6cedc", "#04266e"],
        "kit_away": ["#b55384", "#d4c4d8", "#2f2142"],
        "colour1": "#05a6e8",
        "colour2": "#a7e1fa"
    },
    "hk rangers": {
        "badge": ["#a7e1fa", "#05a6e8", "#5ac5f1"],
        "kit_home": ["#2179c0", "#c6cedc", "#04266e"],
        "kit_away": ["#b55384", "#d4c4d8", "#2f2142"],
        "colour1": "#05a6e8",
        "colour2": "#a7e1fa"
    },
    "tai po": {
        "badge": ["#134726", "#b4bc8e", "#60856e"],
        "kit_home": ["#124b62", "#c0c2c4", "#2191a4"],
        "kit_away": ["#75446b", "#e0d4d4"],
        "colour1": "#134726",
        "colour2": "#b4bc8e"
    },
    "north district": {
        "badge": ["#272860", "#cb2220", "#dcc9cb"],
        "kit_home": ["#8f131d", "#251216", "#dfcfd6"],
        "kit_away": ["#ac8616", "#202021", "#c1c7b3"],
        "colour1": "#272860",
        "colour2": "#cb2220"
    },
    "hong kong football club": {
        "badge": ["#d1dee6", "#6182ae", "#06448b"],
        "kit_home": ["#343246"],
        "kit_away": ["#ededec"],
        "colour1": "#06448b",
        "colour2": "#6182ae"
    },
    "hkfc": {
        "badge": ["#d1dee6", "#6182ae", "#06448b"],
        "kit_home": ["#343246"],
        "kit_away": ["#ededec"],
        "colour1": "#06448b",
        "colour2": "#6182ae"
    },
    "kowloon city": {
        "badge": ["#c0940c"],
        "kit_home": ["#74171d", "#d8c9b4", "#1f1817"],
        "kit_away": ["#b5ae94", "#151411", "#e7e5dd"],
        "colour1": "#c0940c",
        "colour2": "#1f1817"
    },
}


def _get_team_colors(team_name: str) -> dict:
    """Returns team color dict {badge, kit_home, kit_away, colour1, colour2} for a given team name."""
    if not team_name:
        return {}
    key = team_name.lower().strip()
    return _TEAM_COLORS.get(key, {})


# Hex color palettes per competition — sourced from official branding
_COMPETITION_COLOR_MAP = {
    "HK Premier League": ["#ac0c34", "#1c1c1c", "#b40c34"],
    "Sapling Cup": ["#153465", "#c1cf31", "#78ac46"],
    "Senior Shield": ["#050505", "#b8b8b8", "#444444"],
    "HKFA Cup": ["#bb9d5e", "#bcbcbc", "#bcbcc4"],
    "AFC Cup": ["#c6bcb6", "#318cd6", "#191c1a", "#61af69", "#eb8b3e"],
    "AFC Champions League Two": ["#111112", "#cec9c1", "#218ec2", "#f7a240", "#959b9e"],
    "AFC Champions League": ["#111112", "#cec9c1", "#218ec2", "#f7a240", "#959b9e"],
}


def _normalize_comp(raw: str) -> str:
    """Normalize a competition name using central helper."""
    return normalize_competition(raw)


def _competition_logo_url(competition: str):
    """Return local web path for competition logo, or None if not mapped."""
    return get_competition_logo(competition)


def _competition_color(competition: str) -> str:
    """Return primary hex color for a competition name."""
    palette = _COMPETITION_COLOR_MAP.get(_normalize_comp(competition), ["#0d6efd"])
    return palette[0]


def _comp_badge(competition: str) -> "html.Span | None":
    """Return a styled Span badge with the competition name."""
    comp = _normalize_comp(competition)
    if not comp:
        return None
    bg_color = _competition_color(comp)
    # Determine text color based on background brightness (simplified)
    # For now, white text for dark/vibrant backgrounds, black for very light ones
    text_color = "#ffffff"
    light_bgs = [
        "#cec9c1", "#bcbcbc", "#d1dee6", "#ededec", "#e1e3e5", 
        "#c6bcb6", "#bb9d5e", "#d0d0d5", "#f7e4e7"
    ]
    if bg_color.lower() in [c.lower() for c in light_bgs]:
        text_color = "#18181a"

    return html.Span(
        comp,
        className="small px-2 py-0 rounded-1 fw-semibold",
        style={
            "backgroundColor": bg_color,
            "color": text_color,
            "fontSize": "0.7rem",
            "display": "inline-block",
            "lineHeight": "1.4",
        }
    )


def _competition_logo_img(competition: str, logo_url: str = None):
    """Return a small competition logo img element, or text abbreviation if no asset available."""
    comp = _normalize_comp(competition)
    # Prefer explicit logo_url if provided (e.g. from DB/TM), fallback to local mapping
    logo = logo_url if logo_url else get_competition_logo(competition)

    if not logo:
        if comp:
            return html.Span(
                comp[:4].upper(),
                id="image-overlay",
                className="competition-logo-img small fw-semibold portal-text-muted",
                style={
                    "fontSize": "0.55rem",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "width": "40px",
                    "height": "40px",
                },
                title=comp,
            )
        return None

    return html.Img(
        src=logo,
        id="image-overlay",
        className="competition-logo-img",
        style={"width": "40px", "height": "40px", "objectFit": "contain"},
        title=comp,
    )


def _clean_url(url: str) -> str:
    """Unescape HTML entities in a URL and strip trailing quotes/whitespace."""
    if not url:
        return url
    return _html_lib.unescape(url).rstrip('"').strip()


_ICON_MAP = {
    "pre-match": "calendar-plus",
    "post-match": "bar-chart-2",
    "career": "trophy",
    "ai-insight": "zap",
}

_COLOR_MAP = {
    "pre-match": "primary",
    "post-match": "success",
    "career": "warning",
    "ai-insight": "secondary",
}

_GLASS_CLASS_MAP = {
    "pre-match": "glass-prematch",
    "career": "glass-career",
}


def _get_glass_class(milestone: dict) -> str:
    """Returns the glass context modifier class for a milestone."""
    m_type = milestone.get("type", "career")
    status = milestone.get("confirmation_status") or milestone.get(
        "payload", {}
    ).get("confirmation_status", "")
    
    if status == "LIVE":
        return "glass-danger"
    if status == "Pending Update":
        return "glass-prematch" # Reuse blue for pending
        
    if m_type == "post-match":
        return "glass-success" if status == "Confirmed" else "glass-prematch"
    return _GLASS_CLASS_MAP.get(m_type, "glass-career")


def _lucide(name: str) -> html.I:
    """Returns a Lucide icon element."""
    return html.I(**{"data-lucide": name, "className": "lucide-inline-icon me-1"})


def _team_pill(name: str, logo_url, reverse: bool = False) -> html.Div:
    """Small team block: logo + name (or name + logo when reverse=True)."""
    
    resolved_logo = None
    
    # 1. Intentar resolver localmente por nombre
    if name:
        # Normalización: minúsculas, guiones/espacios a _, quitar puntos
        normalized = name.lower().replace(" ", "_").replace("-", "_").replace(".", "")
        # Caso especial para North District
        if "north" in normalized:
            normalized = "north_dt"
            
        local_file = f"{normalized}.png"
        # Ruta física para comprobación (ajustada relativa a este archivo)
        from pathlib import Path
        root_dir = Path(__file__).parent.parent
        assets_path = root_dir / "assets" / "team_logos" / local_file
        if assets_path.exists():
            resolved_logo = f"/assets/team_logos/{local_file}"

    # 2. Si no hay local, usar la URL proporcionada
    if not resolved_logo and logo_url:
        resolved_logo = logo_url

    if resolved_logo:
        badge = html.Img(
            src=resolved_logo,
            style={
                "width": "28px",
                "height": "28px",
                "objectFit": "contain",
                "borderRadius": "50%",
            },
        )
    else:
        badge = html.Span(
            (name or "?")[:2].upper(),
            className="fw-bold",
            style={
                "display": "inline-flex",
                "alignItems": "center",
                "justifyContent": "center",
                "width": "28px",
                "height": "28px",
                "borderRadius": "50%",
                "background": "var(--background-secondary, #2a2a3e)",
                "fontSize": "0.6rem",
                "flexShrink": "0",
            },
        )
    label = html.Span(
        name or "?",
        className="small text-truncate me-1" if reverse else "small text-truncate ms-1",
        style={"maxWidth": "70px"},
    )
    children = [label, badge] if reverse else [badge, label]
    return html.Div(children, className="d-flex align-items-center")


def _build_header_label(
    m_type: str, milestone: dict, payload: dict, matches: list, date_str: str
) -> list:
    """
    Returns the content for the flex-grow-1 area of the milestone header_row.
    This is the COLLAPSED (always visible) state per card type.

    Career  → SEASON label + PJ/G/A/Min summary
    Pre-match → competition badge + kickoff + home VS away teams
    Post-match → competition badge + date + result + home vs away
    """
    if m_type == "career":
        season = payload.get("season", "")
        stats = payload.get("stats", {})

        # Use pre-calculated stats if available, otherwise fallback to counting matches
        pj = stats.get("matches_played", len(matches))
        goals = stats.get("goals", sum(int(m.get("goals", 0) or 0) for m in matches))
        assists = stats.get(
            "assists", sum(int(m.get("assists", 0) or 0) for m in matches)
        )
        minutes = stats.get(
            "minutes_played", sum(int(m.get("minutes_played", 0) or 0) for m in matches)
        )
        yellow = stats.get("yellow_cards", sum(int(m.get("yellow_cards", 0) or 0) for m in matches))
        red = stats.get("red_cards", sum(int(m.get("red_cards", 0) or 0) for m in matches))

        return [
            dbc.Badge(
                f"Season {season}",
                color="warning",
                className="small fw-semibold text-dark mb-1",
            ),
            html.Div(
                [
                    # Partidos
                    html.Div([
                        html.I(className="bi bi-calendar-check me-1", style={"fontSize": "0.9rem"}),
                        html.Span(str(pj)),
                    ], className="portal-text-muted d-flex align-items-center me-2"),
                    
                    # Minutos
                    html.Div([
                        html.I(className="bi bi-stopwatch me-1", style={"fontSize": "0.9rem"}),
                        html.Span(str(minutes)),
                    ], className="portal-text-muted d-flex align-items-center me-2"),

                    # Goles
                    html.Div([
                        html.Img(src="/assets/icons/soccer-ball.svg", style={"width": "14px", "height": "14px", "opacity": "0.85"}, className="me-1"),
                        html.Span(str(goals)),
                    ], className="portal-text-muted d-flex align-items-center me-2"),

                    # Asistencias
                    html.Div([
                        html.I(**{"data-lucide": "sport-shoe"}, style={"width": "14px", "height": "14px", "opacity": "0.85"}, className="me-1"),
                        html.Span(str(assists)),
                    ], className="portal-text-muted d-flex align-items-center me-2"),

                    # Amarillas
                    html.Div([
                        html.I(className="bi bi-square me-1", style={"fontSize": "0.8rem", "color": "#f4c351"}),
                        html.Span(str(yellow)),
                    ], className="portal-text-muted d-flex align-items-center me-2"),

                    # Rojas
                    html.Div([
                        html.I(className="bi bi-square me-1", style={"fontSize": "0.8rem", "color": "#ef6b6b"}),
                        html.Span(str(red)),
                    ], className="portal-text-muted d-flex align-items-center"),
                ],
                className="d-flex align-items-center flex-wrap mt-1",
                style={"gap": "4px", "marginLeft": "16px"}
            ),
        ]

    if m_type == "pre-match":
        competition = _normalize_comp(payload.get("competition", ""))
        kickoff = payload.get("kickoff_display", date_str)
        home = payload.get("home_team", "Home")
        away = payload.get("away_team", "Away")
        home_logo = payload.get("home_logo")
        away_logo = payload.get("away_logo")
        status = payload.get("confirmation_status")
        badge = _comp_badge(competition)
        
        status_pill = None
        if status == "LIVE":
            status_pill = dbc.Badge("LIVE", color="danger", className="ms-2 animate-glass-pulse")
        elif status == "Pending Update":
            status_pill = dbc.Badge("Awaiting Stats", color="warning", className="ms-2 text-dark")
            
        return [
            html.Div([
                html.Div(badge, className="card-row--competition") if badge else None,
                status_pill
            ], className="d-flex align-items-center mb-1") if (badge or status_pill) else None,
            html.Div(
                [
                    _team_pill(home, home_logo),
                    html.Span("vs", className="portal-text-muted mx-2 small"),
                    _team_pill(away, away_logo, reverse=True),
                ],
                className="d-flex align-items-center card-row--teams",
            ),
            html.Div(
                [_lucide("clock"), html.Small(kickoff, className="ms-1")],
                className="d-flex align-items-center portal-text-muted",
            ),
        ]

    # post-match
    competition = _normalize_comp(payload.get("competition", ""))
    kickoff = payload.get("kickoff_display", date_str)
    home = payload.get("home_team", "Home")
    away = payload.get("away_team", "Away")
    home_logo = payload.get("home_logo")
    away_logo = payload.get("away_logo")
    result = payload.get("result")  # e.g. "2:1" from TM

    badge = _comp_badge(competition)

    # Row 2: home logo | home name | result | away name | away logo
    score_el = html.Span(
        result if result else "- : -",
        className="fw-bold small mx-2",
        style={"color": "var(--text-primary, #fff)", "whiteSpace": "nowrap"},
    )
    match_row = html.Div(
        [
            _team_pill(home, home_logo),
            score_el,
            _team_pill(away, away_logo, reverse=True),
        ],
        className="d-flex align-items-center card-row--teams",
    )

    return [
        html.Div(badge, className="card-row--competition") if badge else None,
        match_row,
        html.Div(
            [_lucide("clock"), html.Small(kickoff, className="ms-1")],
            className="d-flex align-items-center portal-text-muted",
        ),
    ]


def _build_collapse_content(
    m_type: str, payload: dict, matches: list, milestone_id: str = ""
) -> html.Div:
    """
    Builds the EXPANDED detail panel (milestone-body) per card type.

    Career  → competition breakdown (from TM match history) + match list
    Pre-match → stadium | streaming | AI win prob bar | H2H record
    Post-match → stadium + player performance OR absence reason
    """
    if m_type == "pre-match":
        # 6.3 — compute H2H
        home = payload.get("home_team", "")
        away = payload.get("away_team", "")
        h2h = None
        if home and away:
            try:
                h2h = get_h2h_record(home, away, last_n=3)
            except Exception:
                pass

        rows = []
        status = payload.get("confirmation_status")
        if status == "LIVE":
            rows.append(
                html.Div(
                    [
                        _lucide("activity"),
                        html.Small("Match in progress. Performance data will be available after official confirmation.", 
                                   className="text-danger fw-bold"),
                    ],
                    className="d-flex align-items-center gap-1 mb-2 border border-danger border-opacity-25 rounded p-1",
                    style={"backgroundColor": "rgba(220, 53, 69, 0.05)"}
                )
            )
        elif status == "Pending Update":
            rows.append(
                html.Div(
                    [
                        _lucide("clock"),
                        html.Small("Finished. Awaiting official statistics update from Transfermarkt.", 
                                   className="text-warning fw-bold"),
                    ],
                    className="d-flex align-items-center gap-1 mb-2 border border-warning border-opacity-25 rounded p-1",
                    style={"backgroundColor": "rgba(255, 193, 7, 0.05)"}
                )
            )

        stadium = payload.get("stadium")
        streaming_url = payload.get("streaming_url")
        streaming_platform = payload.get("streaming_platform")
        if stadium:
            rows.append(
                html.Div(
                    [
                        _lucide("map-pin"),
                        html.Small(stadium, className="portal-text-muted"),
                    ],
                    className="d-flex align-items-center gap-1 mb-1",
                )
            )
        if streaming_url:
            platform_label = get_streaming_label(streaming_url, streaming_platform)
            rows.append(
                html.Div(
                    [
                        _lucide("tv"),
                        html.A(
                            platform_label if platform_label else "Watch Stream",
                            href=_clean_url(streaming_url),
                            target="_blank",
                            rel="noopener noreferrer",
                            className="small text-primary",
                        ),
                    ],
                    className="d-flex align-items-center gap-1 mb-1",
                )
            )
        else:
            rows.append(
                html.Div(
                    [
                        _lucide("tv-off"),
                        html.Small(
                            "No Streaming",
                            className="portal-text-muted",
                        ),
                    ],
                    className="d-flex align-items-center gap-1 mb-1",
                )
            )
        # AI Win Prob (stub at 50%)
        win_prob = payload.get("win_probability", 50)
        rows.append(
            html.Div(
                [
                    html.Small(
                        [_lucide("bar-chart-2"), f"Win prob: {win_prob}%"],
                        className="portal-text-muted d-block mb-1",
                    ),
                    dbc.Progress(
                        value=win_prob,
                        max=100,
                        color="success" if win_prob >= 50 else "warning",
                        style={"height": "5px"},
                        className="mb-1",
                    ),
                ],
                className="mb-1",
            )
        )
        # H2H
        if h2h and h2h.get("matches_found", 0) > 0:
            h2h_txt = (
                f"H2H (last {h2h['matches_found']}): "
                f"{h2h['wins']}V – {h2h['draws']}E – {h2h['losses']}D"
            )
        else:
            h2h_txt = "H2H: sin datos"
        rows.append(
            html.Div(
                [_lucide("shield"), html.Small(h2h_txt, className="portal-text-muted")],
                className="d-flex align-items-center gap-1",
            )
        )
        return html.Div(rows, className="px-2 pb-2 pt-1")

    if m_type == "post-match":
        rows = []
        stadium = payload.get("stadium")
        if stadium:
            rows.append(
                html.Div(
                    [
                        _lucide("map-pin"),
                        html.Small(stadium, className="portal-text-muted"),
                    ],
                    className="d-flex align-items-center gap-1 mb-1",
                )
            )

        minutes = int(payload.get("minutes_played", 0) or 0)
        goals = int(payload.get("goals", 0) or 0)
        assists = int(payload.get("assists", 0) or 0)
        own_goals = int(payload.get("own_goals", 0) or 0)
        yellow = int(payload.get("yellow_cards", 0) or 0)
        red = int(payload.get("red_cards", 0) or 0)
        position = payload.get("position", "N/A")
        sub_in = payload.get("subbed_in")
        sub_out = payload.get("subbed_out")

        absence_reason = payload.get("absence_reason")

        if minutes > 0:
            # Position Line
            rows.append(
                html.Div(
                    [
                        html.Small(
                            [
                                _lucide("user"),
                                html.Span(
                                    f"Pos: {position}", className="fw-bold text-white"
                                ),
                            ],
                            className="portal-text-muted me-auto",
                        ),
                    ],
                    className="d-flex align-items-center mb-2",
                )
            )

            # Core Stats Row - Unificado con Season Cards
            stat_parts = [
                html.Div([
                    html.I(className="bi bi-stopwatch me-1", style={"fontSize": "0.85rem"}),
                    html.Span(f"{minutes}'"),
                ], className="portal-text-muted d-flex align-items-center me-3"),
                
                html.Div([
                    html.Img(src="/assets/icons/soccer-ball.svg", style={"width": "14px", "height": "14px", "opacity": "0.85"}, className="me-1"),
                    html.Span(f"{goals}G"),
                ], className="portal-text-muted d-flex align-items-center me-3"),

                html.Div([
                    html.I(**{"data-lucide": "sport-shoe"}, style={"width": "14px", "height": "14px", "opacity": "0.85"}, className="me-1"),
                    html.Span(f"{assists}A"),
                ], className="portal-text-muted d-flex align-items-center"),
            ]
            if own_goals > 0:
                stat_parts.append(
                    html.Small(
                        [html.I(className="bi bi-exclamation-triangle me-1"), f"{own_goals} OG"],
                        className="text-danger ms-3",
                    )
                )

            rows.append(
                html.Div(
                    stat_parts, className="d-flex flex-wrap align-items-center mb-2"
                )
            )

            # Cards and Substitution Line - Unificado
            detail_parts = []
            if yellow > 0:
                detail_parts.append(
                    html.Div([
                        html.I(className="bi bi-square me-1", style={"fontSize": "0.8rem", "color": "#f4c351"}),
                        html.Span(f"{yellow} Yellow"),
                    ], className="portal-text-muted d-flex align-items-center me-3", style={"fontSize": "0.8rem"})
                )
            if red > 0:
                detail_parts.append(
                    html.Div([
                        html.I(className="bi bi-square me-1", style={"fontSize": "0.8rem", "color": "#ef6b6b"}),
                        html.Span(f"{red} Red"),
                    ], className="portal-text-muted d-flex align-items-center", style={"fontSize": "0.8rem"})
                )

            sub_info = []
            if sub_in is not None:
                sub_info.append(
                    html.Small(
                        [_lucide("log-in"), f"In: {sub_in}'"],
                        className="text-success me-2",
                    )
                )
            if sub_out is not None:
                sub_info.append(
                    html.Small(
                        [_lucide("log-out"), f"Out: {sub_out}'"],
                        className="text-warning",
                    )
                )

            if detail_parts or sub_info:
                rows.append(
                    html.Div(
                        [
                            html.Div(
                                detail_parts, className="d-flex align-items-center"
                            ),
                            html.Div(
                                sub_info, className="ms-auto d-flex align-items-center"
                            ),
                        ],
                        className="d-flex align-items-center",
                    )
                )
        else:
            # Absence visualization
            _ABSENCE_LABELS = {
                "No convocado": ("secondary", "Not Summoned"),
                "not_summoned": ("secondary", "Not Summoned"),
                "Lesionado": ("warning", "Injury"),
                "injured": ("warning", "Injury"),
                "Suspendido": ("danger", "Suspension"),
                "suspended": ("danger", "Suspension"),
                "Banquillo": ("info", "Bench (Unused)"),
                "bench": ("info", "Bench (Unused)"),
            }
            reason_raw = absence_reason or "No jugado"
            badge_info = _ABSENCE_LABELS.get(reason_raw, ("light", reason_raw))

            rows.append(
                html.Div(
                    [
                        _lucide("user-x"),
                        dbc.Badge(
                            badge_info[1], color=badge_info[0], className="small"
                        ),
                    ],
                    className="d-flex align-items-center gap-2",
                )
            )

        return html.Div(
            rows
            or [html.Small("Sin detalles.", className="portal-text-muted fst-italic")],
            className="px-2 pb-2 pt-1",
        )

    # career — competition breakdown only (match list suppressed per spec)
    rows = []
    if matches:
        comp_agg: dict = {}
        for m in matches:
            # ONLY count as a played match if minutes > 0
            mins = int(m.get("minutes_played", 0) or 0)
            if mins <= 0:
                continue

            comp = m.get("competition", "Other")
            if comp not in comp_agg:
                comp_agg[comp] = {"pj": 0, "goals": 0, "assists": 0, "minutes": 0, "yellow": 0, "red": 0}
            
            comp_agg[comp]["pj"] += 1
            comp_agg[comp]["goals"] += int(m.get("goals", 0) or 0)
            comp_agg[comp]["assists"] += int(m.get("assists", 0) or 0)
            comp_agg[comp]["minutes"] += mins
            comp_agg[comp]["yellow"] += int(m.get("yellow_cards", 0) or 0)
            comp_agg[comp]["red"] += int(m.get("red_cards", 0) or 0)

        rows.append(
            html.Small(
                "Competition breakdown",
                className="portal-text-muted text-uppercase fw-bold d-block mb-2",
                style={"fontSize": "0.6rem", "letterSpacing": "0.05em"},
            )
        )
        for comp, stats in comp_agg.items():
            # Competition Logo with Tooltip
            logo_el = _competition_logo_img(comp)
            
            # Ajustamos el tamaño para el breakdown (un poco más pequeño que en el header)
            if hasattr(logo_el, "style"):
                logo_el.style.update({
                    "width": "32px", 
                    "height": "32px"
                })

            logo_container = html.Div(
                logo_el,
                title=comp,
                className="me-2 flex-shrink-0"
            )

            rows.append(
                html.Div(
                    [
                        logo_container,
                        html.Div(
                            [
                                # MP
                                html.Div([
                                    html.I(className="bi bi-calendar-check me-1", style={"fontSize": "0.75rem"}),
                                    html.Span(str(stats['pj'])),
                                ], className="portal-text-muted d-flex align-items-center me-2", style={"fontSize": "0.7rem"}),
                                
                                # Min
                                html.Div([
                                    html.I(className="bi bi-stopwatch me-1", style={"fontSize": "0.75rem"}),
                                    html.Span(str(stats['minutes'])),
                                ], className="portal-text-muted d-flex align-items-center me-2", style={"fontSize": "0.7rem"}),

                                # Goals
                                html.Div([
                                    html.Img(src="/assets/icons/soccer-ball.svg", style={"width": "12px", "height": "14px", "opacity": "0.8"}, className="me-1"),
                                    html.Span(str(stats['goals'])),
                                ], className="portal-text-muted d-flex align-items-center me-2", style={"fontSize": "0.7rem"}),

                                # Assists
                                html.Div([
                                    html.I(**{"data-lucide": "sport-shoe"}, style={"width": "12px", "height": "12px", "opacity": "0.8"}, className="me-1"),
                                    html.Span(str(stats['assists'])),
                                ], className="portal-text-muted d-flex align-items-center me-2", style={"fontSize": "0.7rem"}),

                                # Yellow
                                html.Div([
                                    html.I(className="bi bi-square me-1", style={"fontSize": "0.7rem", "color": "#f4c351"}),
                                    html.Span(str(stats['yellow'])),
                                ], className="portal-text-muted d-flex align-items-center me-2", style={"fontSize": "0.7rem"}),

                                # Red
                                html.Div([
                                    html.I(className="bi bi-square me-1", style={"fontSize": "0.7rem", "color": "#ef6b6b"}),
                                    html.Span(str(stats['red'])),
                                ], className="portal-text-muted d-flex align-items-center", style={"fontSize": "0.7rem"}),
                            ],
                            className="d-flex align-items-center flex-wrap flex-grow-1",
                        ),
                    ],
                    className="d-flex align-items-center border-bottom border-secondary border-opacity-25 py-2",
                )
            )
    else:
        rows.append(
            html.Small(
                "No match data available.", className="portal-text-muted fst-italic"
            )
        )

    return html.Div(rows, className="pb-1 pt-1 px-2")


def _render_action_node_pill(
    m_type: str, milestone_id: str, is_generated: bool
) -> html.Div:
    """Factory: Action Node pill component below a match card with connector line."""
    if m_type == "pre-match":
        label = "View Pre-Game Card" if is_generated else "Generate Pre-Game Card"
        icon = "image"
        color = "primary"
    elif m_type == "post-match":
        label = "View Performance Card" if is_generated else "Generate Performance Card"
        icon = "trophy"
        color = "success"
    else:
        return None
    return html.Div(
        [
            html.Div(className=f"action-node-connector action-node-connector-{color}"),
            html.Button(
                [
                    html.I(
                        **{"data-lucide": icon, "className": "lucide-inline-icon me-1"}
                    ),
                    label,
                ],
                id={"type": "action-node-pill", "index": milestone_id},
                className=f"action-node-pill action-node-pill-{color} glass-card",
                n_clicks=0,
            ),
        ],
        className="action-node-container",
    )


def _render_milestone_item(
    milestone: dict,
    initial_open: bool = False,
    generated_set: set = None,
    hidden: bool = False,
) -> html.Div:
    """Renders a single timeline milestone as a Lucide-icon circle + connector + glass card.

    Structure: .timeline-event > [.event-node | .event-card-column]
    The event-circle (inside event-node) carries the Lucide icon and doubles as the
    Action Node trigger for the image gallery.
    """
    milestone_id = milestone.get("id", "unknown")
    m_type = milestone.get("type", "career")

    lucide_icon = _ICON_MAP.get(m_type, "circle")
    payload = milestone.get("payload", {})
    matches = payload.get("matches", [])
    
    # Timeline accent color is TYPE-based (circle, line, button border).
    # Special case: LIVE status uses 'danger' color.
    status = payload.get("confirmation_status")
    if status == "LIVE":
        color = "danger"
    else:
        color = _COLOR_MAP.get(m_type, "secondary")
        
    glass_cls = _get_glass_class(milestone)

    date_str = ""
    year_str = ""
    if milestone.get("date"):
        try:
            from datetime import datetime

            if isinstance(milestone["date"], str):
                dt = datetime.fromisoformat(milestone["date"].replace("Z", "+00:00"))
            else:
                dt = milestone["date"]
            date_str = dt.strftime("%d/%m/%Y")
            year_str = str(dt.year)
        except Exception:
            date_str = str(milestone["date"])[:10]
            year_str = str(milestone["date"])[:4]

    # ── Event Circle: Lucide icon + Action Node trigger ──────────────────
    cached_image = get_cached_image_path(milestone_id)
    status = payload.get("confirmation_status")
    
    circle_cls = f"event-circle event-circle-{color}"
    if cached_image or status == "LIVE":
        circle_cls += " animate-glass-pulse"
    event_circle = html.Div(
        html.I(**{"data-lucide": lucide_icon, "className": "lucide-event-icon"}),
        id={"type": "action-node", "index": milestone_id},
        className=circle_cls,
        n_clicks=0,
    )

    # Hidden span for select_milestone callback compat
    milestone_trigger = html.Span(
        id={"type": "timeline-milestone", "index": milestone_id},
        n_clicks=0,
        style={"display": "none"},
    )

    # ── Body: Expanded detail or custom AI card ─────────────────────────
    if m_type == "ai-insight":
        from layouts.components.ai_insight_card import render_ai_insight_card

        right_col = render_ai_insight_card(payload, milestone_id)
    else:
        # ── Header: type-specific collapsed state ─────────────────────────────
        header_label_content = _build_header_label(
            m_type, milestone, payload, matches, date_str
        )

        if m_type in ("pre-match", "post-match"):
            # ── Right Action Stack: Logo (top) + Arrow (bottom) ──────────────
            comp_logo_el = _competition_logo_img(
                payload.get("competition", ""), payload.get("competition_logo")
            )

            # We wrap both in a flex-column anchored to the bottom-right
            right_action_stack = html.Div(
                [
                    html.Div(
                        comp_logo_el,
                        className="competition-logo-container",
                        style={"marginTop": "2px"} if comp_logo_el else {},
                    ),
                    html.Div(
                        html.I(
                            **{
                                "data-lucide": "arrow-right-circle",
                                "className": "lucide-detail-icon",
                            }
                        ),
                        id={"type": "milestone-detail-btn", "index": milestone_id},
                        className=f"event-detail-btn event-detail-btn-{color}",
                        n_clicks=0,
                        title="Ver Detalle",
                        style={"cursor": "pointer"},
                    ),
                ],
                style={
                    "display": "flex",
                    "flexDirection": "column",
                    "alignItems": "flex-end",
                    "justifyContent": "space-between",  # Push logo to top, arrow to bottom
                    "padding": "0 0 0 0",
                    "gridColumn": "2",
                    "gridRow": "1 / 3",  # span full height to allow vertical distribution
                },
            )

            header_row = html.Div(
                [
                    html.Div(
                        header_label_content,
                        id={"type": "timeline-milestone-text", "index": milestone_id},
                        style={"cursor": "pointer", "gridRow": "1 / 3"},  # spans both rows
                    ),
                    right_action_stack,
                ],
                id={"type": "milestone-header", "index": milestone_id},
                className="milestone-header",
                style={
                    "display": "grid",
                    "gridTemplateColumns": "1fr auto",
                    "gridTemplateRows": "1fr auto",
                    "minHeight": "80px",
                    "padding": "5px 0 0 0",
                    "cursor": "pointer",
                },
                n_clicks=0,
            )
        else:
            # Career card: arrow sits inline at the right
            detail_btn = html.Div(
                html.I(
                    **{
                        "data-lucide": "arrow-right-circle",
                        "className": "lucide-detail-icon",
                    }
                ),
                id={"type": "milestone-detail-btn", "index": milestone_id},
                className=f"event-detail-btn event-detail-btn-{color} flex-shrink-0",
                n_clicks=0,
                title="Ver Detalle",
                style={"cursor": "pointer"},
            )
            header_row = html.Div(
                [
                    html.Div(
                        header_label_content,
                        className="flex-grow-1",
                        id={"type": "timeline-milestone-text", "index": milestone_id},
                        style={"cursor": "pointer"},
                    ),
                    detail_btn,
                ],
                id={"type": "milestone-header", "index": milestone_id},
                className="d-flex align-items-center gap-2 py-1 px-0",
                n_clicks=0,
                style={"cursor": "pointer"},
            )

        milestone_body = html.Div(
            _build_collapse_content(m_type, payload, matches, milestone_id=milestone_id),
            id={"type": "milestone-body", "index": milestone_id},
            className="milestone-body",
        )

        event_card = html.Div(
            [header_row, milestone_body],
            className=f"event-card event-card-{color} glass-card {glass_cls}",
        )

        # Action Node pill for pre/post-match only
        action_node_pill = None
        if m_type in ("pre-match", "post-match"):
            is_generated = bool(generated_set and milestone_id in generated_set)
            action_node_pill = _render_action_node_pill(
                m_type, milestone_id, is_generated
            )

        if action_node_pill:
            right_col = html.Div(
                [event_card, action_node_pill],
                className="event-card-column",
            )
        else:
            right_col = event_card

    year_cls_val = milestone.get("group_year") or year_str
    year_cls = f" year-{year_cls_val}" if year_cls_val else ""
    hidden_cls = " timeline-item-hidden" if hidden else ""
    expanded_cls = " is-expanded" if initial_open else ""
    hidden_style = {"display": "none"} if hidden else {}

    return html.Div(
        className=f"timeline-event{year_cls}{hidden_cls}{expanded_cls}",
        style=hidden_style,
        children=[
            html.Div(
                className=f"event-node event-node-{color}",
                children=[event_circle, milestone_trigger],
            ),
            right_col,
        ],
    )


def register_player_portal_callbacks(app):
    """Registers all Player Portal callbacks."""

    # ------------------------------------------------------------------ #
    # Sync-status banner + interval enable/disable                        #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("sync-status-banner", "children"),
        Output("sync-status-banner", "style"),
        Output("sync-poll-interval", "disabled"),
        Input("url", "pathname"),
        Input("sync-poll-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_sync_banner(pathname, _n):
        """Checks player sync status and shows a subtle informational banner."""
        hidden = {"display": "none"}
        if pathname != "/player-portal":
            return no_update, hidden, True

        player_id = getattr(current_user, "player_id", None)
        if not player_id:
            return no_update, hidden, True

        status = _get_player_sync_status(player_id)
        state = status.get("state", "ready")

        if state == "ready":
            return None, hidden, True

        if state == "no_data":
            content = [
                html.Span(className="sync-dot sync-dot--pending"),
                html.Span("Setting up your profile — your stats will appear shortly."),
            ]
        elif state == "no_history":
            content = [
                html.Span(className="sync-dot sync-dot--loading"),
                html.Span("Loading your match history — this may take a moment."),
            ]
        else:  # no_tm_link
            content = [
                html.I(className="bi bi-info-circle me-2", style={"fontSize": "0.8rem", "opacity": "0.6"}),
                html.Span("League stats available. Individual match detail will be added once your profile is linked."),
            ]

        banner_style = {"display": "flex"}
        # no_tm_link is a static state — no background process will resolve it, stop polling
        interval_disabled = (state == "no_tm_link")
        return content, banner_style, interval_disabled

    # ------------------------------------------------------------------ #
    # ETL → milestones-data-store                                         #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("milestones-data-store", "data"),
        Input("url", "pathname"),
        Input("sync-poll-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_timeline(pathname, _n):
        """Fetches timeline milestones and stores serialized data."""
        if pathname != "/player-portal":
            return no_update

        try:
            player_id = getattr(current_user, "player_id", None)
            if not player_id:
                return None

            aggregator = TimelineAggregator(data_manager=get_hong_kong_data_manager())
            milestones = aggregator.get_player_timeline(player_id)

            if not milestones:
                return []

            return _serialize_milestones(milestones)

        except Exception as e:
            logger.error(f"update_timeline error: {e}")
            return None

    # ------------------------------------------------------------------ #
    # milestones-data-store + selected-year-store → year-navigator-pills  #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("year-navigator-pills", "children"),
        Input("milestones-data-store", "data"),
        Input("selected-year-store", "data"),
        prevent_initial_call=True,
    )
    def update_year_navigator(milestones_data, selected_year):
        """Builds year pill buttons from available milestone years; marks active year."""
        if not milestones_data:
            return []

        years = sorted(
            {
                m.get("group_year") or str(m.get("date", ""))[:4]
                for m in milestones_data
                if m.get("group_year") or m.get("date")
            },
            reverse=True,
        )
        if not years:
            return []

        pills = []
        for year in years:
            is_active = year == str(selected_year) if selected_year else False
            pills.append(
                html.Button(
                    [html.Span(className="year-nav-icon"), year],
                    id={"type": "year-chip", "year": year},
                    className=f"year-nav-pill {'active' if is_active else ''}".strip(),
                    n_clicks=0,
                )
            )
        return pills

    # ------------------------------------------------------------------ #
    # Clientside: scroll year pill bar to active/current year             #
    # ------------------------------------------------------------------ #
    app.clientside_callback(
        """
        function(children, selected_year) {
            if (!children || children.length === 0) return null;
            var targetYear = selected_year ? selected_year.toString() : new Date().getFullYear().toString();
            setTimeout(function() {
                var bar = document.getElementById('year-navigator-pills');
                if (!bar) return;
                var buttons = bar.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                    if (buttons[i].textContent.trim() === targetYear) {
                        buttons[i].scrollIntoView({behavior: 'smooth', inline: 'center', block: 'nearest'});
                        break;
                    }
                }
            }, 150);
            return null;
        }
        """,
        Output("year-nav-scroll-dummy", "data"),
        Input("year-navigator-pills", "children"),
        Input("selected-year-store", "data"),
        prevent_initial_call=True,
    )

    # ------------------------------------------------------------------ #
    # Clientside: scroll milestone list to selected year section          #
    # ------------------------------------------------------------------ #
    app.clientside_callback(
        """
        function(selected_year) {
            if (!selected_year) return null;
            setTimeout(function() {
                var container = document.querySelector('.milestone-list-container');
                if (!container) return;
                var target = container.querySelector('.year-' + selected_year);
                if (target) {
                    target.scrollIntoView({behavior: 'smooth', block: 'start'});
                }
            }, 150);
            return null;
        }
        """,
        Output("year-timeline-scroll-dummy", "data"),
        Input("selected-year-store", "data"),
        prevent_initial_call=True,
    )

    # ------------------------------------------------------------------ #
    # Year chip click → selected-year-store                               #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("selected-year-store", "data"),
        Input({"type": "year-chip", "year": ALL}, "n_clicks"),
        State("selected-year-store", "data"),
        prevent_initial_call=True,
    )
    def select_year(n_clicks_list, current_year):
        """Updates selected year filter; deselects if the same year is clicked again."""
        if not ctx.triggered_id:
            return no_update
        triggered = ctx.triggered_id
        if isinstance(triggered, dict) and triggered.get("type") == "year-chip":
            # Guard: Dash 4 fires ALL-pattern callbacks when components are dynamically
            # added to the DOM (n_clicks=0). Only process genuine user clicks.
            trigger_value = ctx.triggered[0].get("value", 0) if ctx.triggered else 0
            if not trigger_value:
                return no_update
            year = triggered["year"]
            return None if year == str(current_year) else year
        return no_update

    # ------------------------------------------------------------------ #
    # milestones-data-store + timeline-pagination-store → timeline        #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("timeline-milestones", "children"),
        Output("timeline-expand-store", "data"),
        Input("milestones-data-store", "data"),
        prevent_initial_call=True,
    )
    def render_timeline_milestones(milestones_data):
        """
        Renders milestone items grouped by season in .season-section divs.
        Career milestones act as season headers; match groups visibility
        is controlled by the is-expanded class on the season-group-container.
        """
        if not milestones_data:
            # Show contextual empty state based on sync status
            player_id = getattr(current_user, "player_id", None)
            if player_id:
                status = _get_player_sync_status(player_id)
                state = status.get("state", "ready")
                if state == "no_data":
                    empty_msg = html.Div([
                        html.Span(className="sync-dot sync-dot--pending me-2"),
                        html.Span("Your profile is being set up. Match history will appear here shortly.", className="portal-text-muted small"),
                    ], className="d-flex align-items-center px-3 py-4")
                    return [empty_msg], []
                elif state == "no_history":
                    empty_msg = html.Div([
                        html.Span(className="sync-dot sync-dot--loading me-2"),
                        html.Span("Loading your match history — check back in a moment.", className="portal-text-muted small"),
                    ], className="d-flex align-items-center px-3 py-4")
                    return [empty_msg], []
            return no_update, no_update

        from collections import defaultdict

        groups = defaultdict(list)
        for m in milestones_data:
            # group_year now contains season strings like "2025-26"
            year = m.get("group_year") or str(m.get("date", ""))[:4] or "unknown"
            groups[year].append(m)

        sorted_years = sorted(groups.keys(), reverse=True)
        most_recent_year = sorted_years[0] if sorted_years else None

        # expand_ids: only career milestones in the most recent year start open
        expand_ids = []
        if most_recent_year:
            for m in groups[most_recent_year]:
                if m.get("type") == "career" and m.get("id"):
                    expand_ids.append(m["id"])

        sections = []
        for year in sorted_years:
            is_recent = year == most_recent_year
            year_milestones = groups[year]

            # Separate career anchor from match milestones
            career_m = next(
                (m for m in year_milestones if m.get("type") == "career"), None
            )
            match_milestones = [m for m in year_milestones if m.get("type") != "career"]

            items = []

            # Career milestone as season header
            if career_m:
                career_item = _render_milestone_item(career_m, initial_open=is_recent)
                career_id = career_m.get("id")
            else:
                career_item = None
                career_id = None

            # Render ALL match milestones; first 5 visible, rest hidden.
            if match_milestones:
                match_items = [
                    _render_milestone_item(m, initial_open=False, hidden=(i >= 5))
                    for i, m in enumerate(match_milestones)
                ]
                if len(match_milestones) > 5:
                    match_items.append(
                        html.Div(
                            [
                                html.Div(className="load-more-axis-spacer"),
                                html.Div(
                                    html.Button(
                                        [
                                            html.I(**{"data-lucide": "chevrons-down", "className": "lucide-inline-icon me-1"}),
                                            "Load More",
                                        ],
                                        id={"type": "load-more-btn", "year": year},
                                        className="load-more-pill",
                                        n_clicks=0,
                                    ),
                                    className="load-more-card-col",
                                ),
                            ],
                            className="load-more-row",
                        )
                    )

                matches_group_kwargs = {"className": "season-matches-group"}
                if career_id:
                    matches_group_kwargs["id"] = {"type": "season-matches-group", "index": career_id}
                matches_group = html.Div(match_items, **matches_group_kwargs)

                if career_item:
                    # Wrap career + matches in a container that controls match visibility via is-expanded class
                    expanded_cls = " is-expanded" if is_recent else ""
                    items.append(
                        html.Div(
                            [career_item, matches_group],
                            className=f"season-group-container{expanded_cls}",
                            **{"data-career-id": career_id}
                        )
                    )
                else:
                    items.extend(match_items)
            elif career_item:
                # Career-only section (no match milestones yet) — still render the career card
                items.append(career_item)

            sections.append(
                html.Div(
                    id=f"season-{year}",
                    className="season-section",
                    **{"data-year": year},
                    children=items,
                )
            )
        return sections, expand_ids

    # ------------------------------------------------------------------ #
    # Load More — clientside DOM reveal (no server roundtrip)             #
    # Shows next 10 .timeline-item-hidden items in the clicked season.    #
    # Hides the Load More button when no hidden items remain.             #
    # ------------------------------------------------------------------ #
    app.clientside_callback(
        """
        function(n_clicks_list) {
            var triggered = dash_clientside.callback_context.triggered_id;
            if (!triggered || triggered.type !== 'load-more-btn') {
                return window.dash_clientside.no_update;
            }

            // Guard: only proceed on a real click (n_clicks > 0).
            // Dash 4.0 ALL-pattern callbacks can fire spuriously on component
            // registration with all values at 0; a real click always has at least one > 0.
            if (!n_clicks_list || !n_clicks_list.some(function(v) { return v > 0; })) {
                return window.dash_clientside.no_update;
            }

            var year = triggered.year;
            var season = document.querySelector('.season-section[data-year="' + year + '"]');
            if (!season) return window.dash_clientside.no_update;

            var hiddenItems = season.querySelectorAll('.timeline-item-hidden');
            var shown = 0;
            for (var i = 0; i < hiddenItems.length && shown < 10; i++) {
                hiddenItems[i].style.removeProperty('display');
                hiddenItems[i].classList.remove('timeline-item-hidden');
                shown++;
            }

            var remaining = season.querySelectorAll('.timeline-item-hidden');
            if (remaining.length === 0) {
                var row = season.querySelector('.load-more-row');
                if (row) row.style.display = 'none';
            }

            return window.dash_clientside.no_update;
        }
        """,
        Output("timeline-pagination-store", "data", allow_duplicate=True),
        Input({"type": "load-more-btn", "year": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )

    # ------------------------------------------------------------------ #
    # Milestone click / Ver Detalle / Year chip → timeline-context-store  #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("timeline-context-store", "data"),
        Input({"type": "timeline-milestone", "index": ALL}, "n_clicks"),
        Input({"type": "milestone-detail-btn", "index": ALL}, "n_clicks"),
        Input("selected-year-store", "data"),
        State("milestones-data-store", "data"),
        State("timeline-context-store", "data"),
        prevent_initial_call=True,
    )
    def select_milestone(
        milestone_clicks, detail_clicks, selected_year, milestones_data, current_context
    ):
        """Updates the context store when a milestone icon, Ver Detalle, or year chip is clicked."""
        if not ctx.triggered_id or not milestones_data:
            return no_update

        triggered = ctx.triggered_id

        # Year chip: find career milestone for the selected year
        if triggered == "selected-year-store":
            if not selected_year:
                return no_update
            for m in milestones_data:
                m_year = m.get("group_year") or str(m.get("date", ""))[:4]
                if m.get("type") == "career" and m_year == str(selected_year):
                    return {"type": "career", "payload": m["payload"]}
            return no_update

        if isinstance(triggered, dict) and triggered.get("type") in (
            "timeline-milestone",
            "milestone-detail-btn",
        ):
            # Guard: Dash 4 fires ALL-pattern callbacks when components are dynamically
            # added to the DOM (n_clicks=0). Only process genuine user clicks.
            trigger_value = ctx.triggered[0].get("value", 0) if ctx.triggered else 0
            if not trigger_value:
                return no_update
            milestone_id = triggered["index"]
            # Toggle: if this milestone is already the active context, clear it → dashboard
            if (
                current_context
                and current_context.get("payload", {}) == next(
                    (item.get("payload") for item in milestones_data if item.get("id") == milestone_id),
                    None,
                )
            ):
                return None
            # Find the milestone by ID in the list
            m = next(
                (item for item in milestones_data if item.get("id") == milestone_id),
                None,
            )
            if m:
                return {"type": m["type"], "payload": m["payload"]}

        return no_update

    # ------------------------------------------------------------------ #
    # milestones-data-store → Initial career overview (no card selected) #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("stage-content", "children", allow_duplicate=True),
        Input("milestones-data-store", "data"),
        prevent_initial_call=True,
    )
    def render_initial_stage(milestones_data):
        """
        Shows the Career Overview as the default stage when milestones first load
        and no card has been selected yet.
        """
        if milestones_data is None:
            return no_update
        try:
            player_id   = getattr(current_user, "player_id", None)
            user_role   = getattr(current_user, "role", "player") if current_user else "player"
            if not player_id:
                return no_update
            from utils.player_index import get_player_index
            pi          = get_player_index()
            player_info = pi.get_player_info(player_id)
            player_name = player_info.get("canonical_name", "") if player_info else ""
            if not player_name:
                return no_update
            return render_career_overview(player_name, player_id, user_role)
        except Exception as e:
            logger.warning(f"render_initial_stage error: {e}")
            return no_update

    # ------------------------------------------------------------------ #
    # timeline-context-store → Stage content                              #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("stage-content", "children"),
        Input("timeline-context-store", "data"),
        prevent_initial_call=True,
    )
    def update_stage(context):
        """Dispatches rendering to the appropriate stage helper based on card type."""
        if not context:
            # Card was closed — show career overview again
            try:
                player_id   = getattr(current_user, "player_id", None)
                user_role   = getattr(current_user, "role", "player") if current_user else "player"
                if player_id:
                    from utils.player_index import get_player_index
                    pi          = get_player_index()
                    player_info = pi.get_player_info(player_id)
                    player_name = player_info.get("canonical_name", "") if player_info else ""
                    if player_name:
                        return render_player_dashboard(player_name, player_id, user_role)
            except Exception:
                pass
            return no_update

        user_role = (
            getattr(current_user, "role", "player") if current_user else "player"
        )
        m_type  = context.get("type")
        payload = context.get("payload", {})

        try:
            if m_type == "post-match":
                return render_post_match(payload)
            elif m_type == "pre-match":
                # Resolve logged-in player's position for rival analysis
                pos_group = ""
                position_main = ""
                current_role_hint = ""
                try:
                    player_id   = getattr(current_user, "player_id", None)
                    if player_id:
                        from utils.player_index import get_player_index
                        from utils.app_context import get_hong_kong_data_manager as _get_dm
                        from models.db_models import Player, MatchHistory
                        from utils.db_engine import SessionFactory
                        pi          = get_player_index()
                        player_info = pi.get_player_info(player_id)
                        player_name = player_info.get("canonical_name", "") if player_info else ""
                        with SessionFactory() as session:
                            player_obj = session.get(Player, player_id)
                            position_main = str(getattr(player_obj, "position_main", "") or "").strip()
                            recent_matches = (
                                session.query(MatchHistory)
                                .filter(MatchHistory.player_id == player_id)
                                .order_by(MatchHistory.date.desc())
                                .limit(8)
                                .all()
                            )
                            weighted = {}
                            for idx, match in enumerate(recent_matches):
                                raw_pos = str(getattr(match, "position", "") or "").strip().upper()
                                mapped = {
                                    "ED": "RW", "EI": "LW", "ID": "RM", "II": "LM",
                                    "MCO": "AMF", "CMF": "CM", "DMF": "DM",
                                }.get(raw_pos, raw_pos)
                                if not mapped:
                                    continue
                                minutes = int(getattr(match, "minutes_played", 0) or 0)
                                weight = max(minutes, 1) + max(0, 8 - idx)
                                weighted[mapped] = weighted.get(mapped, 0) + weight
                            if weighted:
                                current_role_hint = max(weighted.items(), key=lambda item: item[1])[0]
                        if player_name:
                            pos_group = _get_position_group(player_name, _get_dm())
                except Exception:
                    pass
                return render_pre_match(
                    payload,
                    player_pos_group=pos_group,
                    player_position_main=position_main,
                    player_current_role=current_role_hint,
                )
            elif m_type == "career":
                return render_career_insights(payload, user_role)
            else:
                return dbc.Alert(
                    f"Tipo de contexto desconocido: {m_type}", color="warning"
                )
        except Exception as e:
            logger.error(f"update_stage error: {e}")
            return dbc.Alert("Error al renderizar el escenario.", color="danger")

    @app.callback(
        Output("stage-shell", "className"),
        Input("timeline-context-store", "data"),
        prevent_initial_call=False,
    )
    def update_stage_shell_class(context):
        """Keeps the persistent stage shell while changing the glass modifier by active context."""
        base = "glass-card stage-shell"
        if not context:
            return f"{base} glass-career"

        m_type = context.get("type")
        if m_type == "pre-match":
            return f"{base} glass-prematch"
        if m_type == "post-match":
            payload = context.get("payload", {}) or {}
            rating = payload.get("rating") or ((payload.get("player_stats") or {}).get("performance_stats", {}) or {}).get("rating")
            try:
                rating = float(rating) if rating is not None else None
            except (TypeError, ValueError):
                rating = None
            modifier = "glass-danger" if (rating is not None and rating < 6.0) else "glass-success"
            return f"{base} {modifier}"
        return f"{base} glass-career"

    # ------------------------------------------------------------------ #
    # Phase 3: Clientside expand/collapse (Optimized for instant feel)   #
    # Toggles is-expanded class on .timeline-event and .season-group-container.
    # ------------------------------------------------------------------ #
    app.clientside_callback(
        """
        function(n_clicks_list, expand_store) {
            var triggered_id = dash_clientside.callback_context.triggered_id;
            if (!triggered_id || triggered_id.type !== 'milestone-header') {
                return window.dash_clientside.no_update;
            }
            var mid = triggered_id.index;
            var open_ids = new Set(expand_store || []);

            // Flexible selector for dictionary IDs
            var selector = '[id*="index"][id*="' + mid + '"][id*="type"][id*="milestone-header"]';
            var headerEl = document.querySelector(selector);
            if (!headerEl) return window.dash_clientside.no_update;
            
            var eventContainer = headerEl.closest('.timeline-event');
            if (!eventContainer) return window.dash_clientside.no_update;

            var willOpen = !eventContainer.classList.contains('is-expanded');
            
            // Handle Accordion for Season Groups
            var seasonContainer = eventContainer.closest('.season-group-container');
            if (seasonContainer && seasonContainer.getAttribute('data-career-id') === mid) {
                if (willOpen) {
                    document.querySelectorAll('.season-group-container.is-expanded').forEach(function(el) {
                        el.classList.remove('is-expanded');
                        var cid = el.getAttribute('data-career-id');
                        if (cid) open_ids.delete(cid);
                        el.querySelectorAll('.timeline-event.is-expanded').forEach(function(e) { e.classList.remove('is-expanded'); });
                    });
                    seasonContainer.classList.add('is-expanded');
                    eventContainer.classList.add('is-expanded');
                    open_ids.add(mid);
                } else {
                    seasonContainer.classList.remove('is-expanded');
                    eventContainer.classList.remove('is-expanded');
                    open_ids.delete(mid);
                }
            } else {
                if (willOpen) {
                    eventContainer.classList.add('is-expanded');
                    open_ids.add(mid);
                } else {
                    eventContainer.classList.remove('is-expanded');
                    open_ids.delete(mid);
                }
            }

            // Background store sync
            window.dash_clientside.set_props('timeline-expand-store', {data: Array.from(open_ids)});
            
            return window.dash_clientside.no_update;
        }
        """,
        Output("timeline-pagination-store", "data", allow_duplicate=True),
        Input({"type": "milestone-header", "index": ALL}, "n_clicks"),
        State("timeline-expand-store", "data"),
        prevent_initial_call=True,
    )

    # ------------------------------------------------------------------ #
    # Phase 3: Consolidates Intersection Observer & Lucide Init          #
    # Registers an IntersectionObserver on .season-section divs.          #
    # Updates active-year-store, pill active class, and scrolls pill.     #
    # ------------------------------------------------------------------ #
    app.clientside_callback(
        """
        function(children) {
            // 1. Re-init Lucide icons
            setTimeout(function() {
                if (window.lucide) { lucide.createIcons(); }
            }, 150);

            // 2. Setup IntersectionObserver for scroll sync
            setTimeout(function() {
                if (window._seasonObserver) {
                    window._seasonObserver.disconnect();
                }
                var container = document.querySelector('.milestone-list-container');
                var sections = document.querySelectorAll('.season-section');
                if (!sections || !sections.length) return;

                window._seasonObserver = new IntersectionObserver(function(entries) {
                    var topYear = null;
                    var topPos = Infinity;
                    entries.forEach(function(entry) {
                        if (entry.isIntersecting) {
                            var top = Math.abs(entry.boundingClientRect.top);
                            if (top < topPos) {
                                topPos = top;
                                topYear = entry.target.getAttribute('data-year');
                            }
                        }
                    });
                    if (!topYear) return;
                    
                    window.dash_clientside.set_props('active-year-store', {data: topYear});
                    
                    var pills = document.querySelectorAll('#year-navigator-pills button');
                    pills.forEach(function(pill) {
                        var pillYear = pill.textContent.trim();
                        if (pillYear === topYear) {
                            pill.classList.add('active');
                            pill.scrollIntoView({behavior: 'smooth', inline: 'center', block: 'nearest'});
                        } else {
                            pill.classList.remove('active');
                        }
                    });
                }, {threshold: 0.2, root: container});

                sections.forEach(function(s) {
                    window._seasonObserver.observe(s);
                });
            }, 400);
            return window.dash_clientside.no_update;
        }
        """,
        Output("active-year-store", "data"),
        Input("timeline-milestones", "children"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(children) {
            setTimeout(function() {
                if (window.lucide) { lucide.createIcons(); }
            }, 150);
            return null;
        }
        """,
        Output("stage-lucide-refresh-dummy", "data"),
        Input("stage-content", "children"),
        prevent_initial_call=True,
    )


    # ------------------------------------------------------------------ #
    # Phase 3: Action Node click → Stage gallery (task 6.1)               #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("stage-content", "children", allow_duplicate=True),
        Output("gallery-close-btn", "style"),
        Input({"type": "action-node", "index": ALL}, "n_clicks"),
        Input("gallery-close-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def update_stage_from_action_node(node_clicks, close_clicks):
        """Opens image gallery in Stage when an Action Node is clicked; close button resets."""
        if not ctx.triggered_id:
            return no_update, no_update

        # Close button resets stage to skeleton loader and hides itself
        if ctx.triggered_id == "gallery-close-btn":
            from utils.skeleton_components import create_skeleton_stage

            return create_skeleton_stage(), {"display": "none"}

        triggered = ctx.triggered_id
        if not isinstance(triggered, dict) or triggered.get("type") != "action-node":
            return no_update, no_update

        # Ensure it was an actual click (not initial render)
        if not any(node_clicks):
            return no_update, no_update

        milestone_id = triggered["index"]
        path = get_cached_image_path(milestone_id)
        return render_image_gallery(path), {
            "display": "inline-flex",
            "alignItems": "center",
        }

    # ------------------------------------------------------------------ #
    # Clientside sliding panel navigation                                  #
    # ------------------------------------------------------------------ #
    app.clientside_callback(
        """
        function(detail_clicks, back_clicks) {
            var triggered = dash_clientside.callback_context.triggered;
            if (!triggered || triggered.length === 0) {
                return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            }
            var prop_id = triggered[0].prop_id || "";

            if (prop_id.includes("milestone-detail-btn")) {
                return ["portal-viewport show-stage", {"panel": "stage"}];
            }
            if (prop_id === "portal-back-btn.n_clicks") {
                return ["portal-viewport", {"panel": "timeline"}];
            }
            return [window.dash_clientside.no_update, window.dash_clientside.no_update];
        }
        """,
        Output("portal-viewport", "className"),
        Output("portal-panel-state", "data"),
        Input({"type": "milestone-detail-btn", "index": ALL}, "n_clicks"),
        Input("portal-back-btn", "n_clicks"),
        prevent_initial_call=True,
    )

    # ------------------------------------------------------------------ #
    # task 5.2 + 5.3: Card expand/collapse — accordion via card-expand-   #
    # store. One card open at a time; detail panels show/hide clientside. #
    # ------------------------------------------------------------------ #
    app.clientside_callback(
        """
        function(n_clicks_list, card_expand_store) {
            var triggered_id = dash_clientside.callback_context.triggered_id;
            if (!triggered_id || triggered_id.type !== 'card-header') {
                return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            }
            var mid = triggered_id.index;
            var store = card_expand_store || {};
            var isOpen = !!store[mid];

            // Accordion: close all, then open the clicked one (unless it was already open)
            var newStore = {};
            if (!isOpen) {
                newStore[mid] = true;
            }

            // Map new store to panel styles for all card-detail-panel outputs
            var header_inputs = dash_clientside.callback_context.inputs_list[0];
            var styles = header_inputs.map(function(inp) {
                return newStore[inp.id.index]
                    ? {display: 'block'}
                    : {display: 'none'};
            });

            return [newStore, styles];
        }
        """,
        Output("card-expand-store", "data"),
        Output({"type": "card-detail-panel", "index": ALL}, "style"),
        Input({"type": "card-header", "index": ALL}, "n_clicks"),
        State("card-expand-store", "data"),
        prevent_initial_call=True,
    )

    # ------------------------------------------------------------------ #
    # Back button visibility from portal-panel-state                      #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("portal-back-button", "style"),
        Input("portal-panel-state", "data"),
        prevent_initial_call=False,
    )
    def toggle_back_button_visibility(panel_state):
        """Shows the back button when the stage panel is active (mobile only via CSS)."""
        if panel_state and panel_state.get("panel") == "stage":
            return {"display": "flex", "alignItems": "center"}
        return {"display": "none"}

    # ------------------------------------------------------------------ #
    # Action Node pill click → Card Studio (new) or gallery open (already generated) #
    # Task 8.1: Route to Card Studio via run_card_design_agent; "View" path unchanged #
    # ------------------------------------------------------------------------------ #
    @app.callback(
        Output("stage-content", "children", allow_duplicate=True),
        Output("timeline-pagination-store", "data", allow_duplicate=True),
        Output("card-editor-state", "data", allow_duplicate=True),
        Input({"type": "action-node-pill", "index": ALL}, "n_clicks"),
        State("milestones-data-store", "data"),
        State("timeline-pagination-store", "data"),
        prevent_initial_call=True,
    )
    def handle_action_node_pill(n_clicks_list, milestones_data, pagination_store):
        """Open Card Studio on first click; show gallery if already generated."""
        if not ctx.triggered_id or not any(n_clicks_list or []):
            return no_update, no_update, no_update
        triggered = ctx.triggered_id
        if (
            not isinstance(triggered, dict)
            or triggered.get("type") != "action-node-pill"
        ):
            return no_update, no_update, no_update

        milestone_id = triggered["index"]
        if not milestones_data:
            return no_update, no_update, no_update
        m = next(
            (item for item in milestones_data if item.get("id") == milestone_id), None
        )
        if not m:
            return no_update, no_update, no_update

        store = pagination_store or {}
        generated = dict(store.get("generated", {}))
        is_generated = generated.get(milestone_id, False)
        m_type = m.get("type")
        payload = m.get("payload", {})

        # Already generated → show gallery from new player_cards dir (with cache fallback)
        if is_generated:
            path = get_cached_image_path(milestone_id)
            return render_image_gallery(path), no_update, no_update

        # Only handle card-type milestones
        if m_type not in ("pre-match", "post-match"):
            return no_update, no_update, no_update

        card_type = m_type

        # Load saved draft if it exists
        try:
            from flask_login import current_user as _cu

            player_id = str(_cu.id) if _cu and _cu.is_authenticated else "unknown"
        except Exception:
            player_id = "unknown"

        from pathlib import Path as _Path
        import json as _json

        draft_path = (
            _Path("data/player_cards") / player_id / milestone_id / "card_editor.json"
        )
        saved_draft = None
        if draft_path.exists():
            try:
                saved_draft = _json.loads(draft_path.read_text("utf-8"))
            except Exception:
                saved_draft = None

        from utils.image_processing import get_player_album
        album = get_player_album(player_id)

        # Render Studio Layout IMMEDIATELY
        try:
            from layouts.components.card_editor import (
                create_pre_game_card_studio,
                create_performance_card_studio,
            )

            match_context = {
                "home_team": payload.get("home_team"),
                "away_team": payload.get("away_team"),
                "competition": payload.get("competition"),
                "date": payload.get("date"),
                "score": payload.get("score"),
            }

            if saved_draft:
                editor_state = saved_draft
                editor_state["needs_ai"] = False
                editor_state["editor_active"] = True
            else:
                editor_state = {
                    "milestone_id": milestone_id,
                    "card_type": card_type,
                    "template": "A",
                    "format": "1:1",
                    "ai_proposal": {},
                    "layout_modifiers": {},
                    "selected_photo_idx": None,
                    "needs_ai": True,  # TRIGGER FOR ASYNC AI
                    "last_saved": None,
                    "editor_active": True,  # Guard: tells render_editor_updates the studio is mounted
                }

            from callbacks.card_editor_callbacks import _build_preview_layout

            # Pass empty/placeholder state initially
            initial_preview = _build_preview_layout(editor_state, {"album": album}, milestones_data)

            if card_type == "pre-match":
                studio = create_pre_game_card_studio(milestone_id, match_context, [], initial_preview=initial_preview, album=album)
            else:
                studio = create_performance_card_studio(milestone_id, match_context, [], initial_preview=initial_preview, album=album)

            return studio, no_update, editor_state
        except Exception as exc:
            logger.error(f"handle_action_node_pill studio render error: {exc}")
            return (
                dbc.Alert("Error opening the Card Studio.", color="danger"),
                no_update,
                no_update,
            )

    # ------------------------------------------------------------------ #
    # AI Insight card click → Stage deep-dive (Task 7.1)                 #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("stage-content", "children", allow_duplicate=True),
        Output("stage-context-snapshot", "data", allow_duplicate=True),
        Input({"type": "ai-insight-card", "index": ALL}, "n_clicks"),
        State("milestones-data-store", "data"),
        prevent_initial_call=True,
    )
    def handle_ai_insight_click(n_clicks_list, milestones_data):
        """Opens Stage deep-dive panel when an AI Insight card is clicked."""
        if not ctx.triggered_id or not any(n_clicks_list or []):
            return no_update, no_update
        triggered = ctx.triggered_id
        if (
            not isinstance(triggered, dict)
            or triggered.get("type") != "ai-insight-card"
        ):
            return no_update, no_update

        milestone_id = triggered["index"]
        if not milestones_data:
            return no_update, no_update
        m = next(
            (item for item in milestones_data if item.get("id") == milestone_id), None
        )
        if not m:
            return no_update, no_update

        payload = m.get("payload", {})
        title = payload.get("title", "AI Insight")
        detail = payload.get("detail", "")
        summary = payload.get("summary", "")

        stage_content = html.Div(
            [
                html.Div(
                    [
                        html.I(
                            **{
                                "data-lucide": "cpu",
                                "className": "lucide-inline-icon me-2",
                            }
                        ),
                        html.Span(title, className="fw-bold"),
                    ],
                    className="d-flex align-items-center mb-3",
                    style={"color": "var(--accent-cyan, #00D4FF)"},
                ),
                html.Div(
                    detail or summary,
                    className="portal-text-muted small",
                    style={"lineHeight": "1.6"},
                ),
            ]
        )
        snapshot = {"type": "ai-insight", "title": title, "detail": detail}
        return stage_content, snapshot


def _serialize_milestones(milestones: list) -> list:
    """Converts datetime objects to ISO strings and adds unique IDs for Phase 3."""
    result = []
    for m in milestones:
        entry = dict(m)
        date_obj = entry.get("date")
        if hasattr(date_obj, "isoformat"):
            entry["date"] = date_obj.isoformat()

        # Generate Unique ID (Task 7.1)
        # Format: {type}-{date/season}
        m_type = entry.get("type", "unknown")
        date_str = entry["date"][:10] if isinstance(entry["date"], str) else "no-date"
        if m_type == "career":
            date_str = entry.get("payload", {}).get("season", date_str)
        entry["id"] = f"{m_type}-{date_str}"

        payload = dict(entry.get("payload", {}))
        if hasattr(payload.get("date"), "isoformat"):
            payload["date"] = payload["date"].isoformat()

        # Handle nested matches serialization
        if "matches" in payload:
            serialized_matches = []
            for match in payload["matches"]:
                m_copy = dict(match)
                if hasattr(m_copy.get("date"), "isoformat"):
                    m_copy["date"] = m_copy["date"].isoformat()
                serialized_matches.append(m_copy)
            payload["matches"] = serialized_matches

        entry["payload"] = payload
        result.append(entry)
    return result


def _get_player_sync_status(player_id: str) -> dict:
    """
    Returns a dict with sync state for the given player_id.

    States:
      'no_data'    — player exists but has no season stats and no TM id (just registered)
      'no_history' — TM id found but match-level history not yet fetched
      'ready'      — has season stats or match history (can render the portal)
    """
    try:
        from utils.db_engine import SessionFactory
        from models.db_models import Player, MatchHistory, PlayerSeasonStat
        from sqlalchemy import func, select

        session = SessionFactory()
        try:
            player = session.get(Player, player_id)
            if player is None:
                return {"state": "ready"}

            season_count = session.execute(
                select(func.count()).where(PlayerSeasonStat.player_id == player_id)
            ).scalar()

            match_count = session.execute(
                select(func.count()).where(MatchHistory.player_id == player_id)
            ).scalar()

            # Nothing at all — truly fresh registration, still being linked
            if season_count == 0 and match_count == 0 and not player.tm_id:
                return {"state": "no_data", "name": player.name}

            # TM id found but individual match history not yet fetched
            if player.tm_id and match_count == 0:
                return {"state": "no_history", "name": player.name}

            # Has league stats but no TM link → portal works but no match-level detail
            if season_count > 0 and match_count == 0 and not player.tm_id:
                return {"state": "no_tm_link", "name": player.name}

            return {"state": "ready"}
        finally:
            session.close()
    except Exception:
        return {"state": "ready"}
