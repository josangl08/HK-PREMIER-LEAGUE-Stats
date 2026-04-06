# ABOUTME: Expandable Next Game Card component for the Player Portal timeline.
# ABOUTME: Renders pre-match milestones with a closed header (competition/date/teams) and expandable panel (stadium/streaming/AI win prob/H2H).

from typing import Dict, Any, Optional
from pathlib import Path

from dash import html
import dash_bootstrap_components as dbc
from utils.performance_helpers import get_streaming_label


# Badge color per competition — distinct from type colors (primary/success/warning).
_COMP_COLOR_MAP = {
    "HK Premier League": "info",
    "HKFA Cup": "danger",
    "Sapling Cup": "dark",
    "Senior Shield": "secondary",
    "League Cup": "light",
    "AFC Champions League Two": "secondary",
}

_COMP_LOGO_MAP = {
    "HK Premier League": "/assets/competition_logos/hong_kong_premier_league.png",
    "HKFA Cup": "/assets/competition_logos/hong_kong_fa_cup.png",
    "Sapling Cup": "/assets/competition_logos/hong_kong_sapling_cup___15__25.png",
    "Senior Shield": "/assets/competition_logos/hong_kong_senior_challenge_shield.png",
    "AFC Champions League Two": "/assets/competition_logos/afc_champions_league_two.png",
}

_COMP_DISPLAY_MAP = {
    "中銀人壽香港超級聯賽": "HK Premier League",
    "香港超級聯賽": "HK Premier League",
    "BOC Life Hong Kong Premier League": "HK Premier League",
    "Hong Kong Premier League": "HK Premier League",
    "足總盃": "HKFA Cup",
    "賽馬會菁英盃": "Sapling Cup",
    "菁英盃": "Sapling Cup",
    "聯賽盃": "League Cup",
    "高級組銀牌": "Senior Shield",
    "銀牌": "Senior Shield",
}


def _normalize_comp(raw: str) -> str:
    if not raw:
        return raw
    if raw in _COMP_DISPLAY_MAP:
        return _COMP_DISPLAY_MAP[raw]
    for key in sorted(_COMP_DISPLAY_MAP, key=len, reverse=True):
        if key in raw:
            return _COMP_DISPLAY_MAP[key]
    return raw


def _lucide(name: str) -> html.I:
    """Returns a Lucide icon element."""
    return html.I(**{"data-lucide": name, "className": "lucide-inline-icon me-1"})


def _team_logo_block(team_name: str, logo_url: Optional[str]) -> html.Div:
    """Renders a team block: logo image (or placeholder) + name."""
    
    resolved_logo = None
    
    # 1. Intentar resolver localmente por nombre
    if team_name:
        normalized = team_name.lower().replace(" ", "_").replace("-", "_").replace(".", "")
        # Caso especial para North District
        if "north" in normalized:
            normalized = "north_dt"
            
        local_file = f"{normalized}.png"
        # Ruta física para comprobación
        assets_path = Path(__file__).parent.parent.parent / "assets" / "team_logos" / local_file
        if assets_path.exists():
            resolved_logo = f"/assets/team_logos/{local_file}"

    # 2. Si no hay local, usar la URL de la DB
    if not resolved_logo and logo_url:
        resolved_logo = logo_url

    if resolved_logo:
        logo = html.Img(
            src=resolved_logo,
            className="next-game-card__team-logo",
            alt=team_name,
            style={"width": "36px", "height": "36px", "objectFit": "contain"},
        )
    else:
        logo = html.Div(
            html.Span(team_name[:2].upper(), className="fw-bold small"),
            className="next-game-card__team-logo-placeholder rounded-circle d-flex align-items-center justify-content-center",
            style={
                "width": "36px",
                "height": "36px",
                "background": "var(--background-secondary, #2a2a3e)",
                "color": "var(--text-secondary, #aaa)",
            },
        )
    return html.Div(
        [logo, html.Small(team_name, className="text-truncate mt-1", style={"maxWidth": "80px"})],
        className="d-flex flex-column align-items-center gap-1",
        style={"maxWidth": "90px"},
    )


def render_next_game_card(
    milestone_payload: Dict[str, Any],
    milestone_id: str,
    h2h: Optional[Dict[str, Any]] = None,
) -> html.Div:
    """
    Renders a Next Game (pre-match) card with closed and expandable states.

    Closed state: competition badge + logo (top-right), date/time, team logos/names,
                  expand arrow (bottom-right).
    Expanded panel: stadium, streaming link (if available), AI win prob bar, H2H.
    """
    home_team = milestone_payload.get("home_team", "Home")
    away_team = milestone_payload.get("away_team", "Away")
    home_logo = milestone_payload.get("home_logo")
    away_logo = milestone_payload.get("away_logo")
    competition_raw = milestone_payload.get("competition", "")
    competition = _normalize_comp(competition_raw)
    kickoff_display = milestone_payload.get("kickoff_display", "")
    stadium = milestone_payload.get("stadium")
    streaming_url = milestone_payload.get("streaming_url")
    streaming_platform = milestone_payload.get("streaming_platform")

    comp_color = _COMP_COLOR_MAP.get(competition, "primary")
    comp_logo = _COMP_LOGO_MAP.get(competition)

    # Competition logo for top-right corner (text fallback when no logo asset)
    comp_logo_el = (
        html.Img(
            src=comp_logo,
            style={"width": "22px", "height": "22px", "objectFit": "contain"},
            title=competition,
        )
        if comp_logo
        else (
            html.Span(
                competition[:4].upper(),
                className="small fw-semibold portal-text-muted",
                style={"fontSize": "0.55rem"},
                title=competition,
            )
            if competition
            else html.Span()
        )
    )

    # Competition badge (left side, no logo — logo is in the corner)
    comp_badge = (
        dbc.Badge(competition, color=comp_color, className="small")
        if competition
        else None
    )

    # Status badges for LIVE or Pending
    status = milestone_payload.get("confirmation_status")
    hkfa_status = milestone_payload.get("hkfa_status")
    has_var = milestone_payload.get("has_var", False)
    
    status_badge = None
    if status == "LIVE":
        status_badge = dbc.Badge("LIVE", color="danger", className="small ms-1 animate-glass-pulse")
    elif status == "Pending Update":
        status_badge = dbc.Badge("Awaiting Statistics", color="warning", className="small ms-1 text-dark")
    elif hkfa_status == "Delay" or hkfa_status == "Delayed":
        status_badge = dbc.Badge("DELAYED", color="warning", className="small ms-1 animate-glass-pulse text-dark")

    var_badge = dbc.Badge("VAR", color="dark", className="small ms-1", style={"opacity": 0.8}) if has_var else None

    # ── Closed header ──────────────────────────────────────────────────────
    header_content = html.Div(
        [
            # Top row: competition badge + kickoff + logo top-right
            html.Div(
                [
                    html.Div(
                        [
                            comp_badge,
                            var_badge,
                            status_badge,
                            html.Small(
                                [_lucide("clock"), kickoff_display] if kickoff_display else "",
                                className="portal-text-muted ms-1",
                            ),
                        ],
                        className="d-flex align-items-center flex-wrap gap-1 flex-grow-1",
                    ),
                    comp_logo_el,
                ],
                className="d-flex align-items-start justify-content-between mb-2",
            ),
            # Team row: home logo | VS | away logo
            html.Div(
                [
                    _team_logo_block(home_team, home_logo),
                    html.Span("VS", className="fw-bold text-muted mx-2 small"),
                    _team_logo_block(away_team, away_logo),
                ],
                className="d-flex align-items-center justify-content-center gap-2",
            ),
            # Bottom row: expand arrow in bottom-right corner
            html.Div(
                html.I(**{"data-lucide": "chevron-down", "className": "lucide-inline-icon"}),
                className="d-flex justify-content-end mt-1",
                style={"paddingBottom": 0, "paddingRight": 0},
            ),
        ],
        id={"type": "card-header", "index": milestone_id},
        n_clicks=0,
        style={"cursor": "pointer"},
        className="next-game-card__header px-2 py-1",
    )

    # ── Expandable detail panel ────────────────────────────────────────────
    detail_rows = []

    if stadium:
        detail_rows.append(
            html.Div(
                [_lucide("map-pin"), html.Small(stadium, className="portal-text-muted")],
                className="d-flex align-items-center gap-1 mb-1",
            )
        )

    platform_label = get_streaming_label(streaming_url, streaming_platform)
    broadcast_type = milestone_payload.get("broadcast_type")
    ticket_prices = milestone_payload.get("ticket_prices")
    
    if streaming_url:
        # Create a stylized on.cc logo if the platform is on.cc
        is_on_cc = "on.cc" in platform_label.lower() or "on.cc" in (streaming_url or "").lower()
        
        if is_on_cc:
            logo_content = html.Span([
                html.Span("on.", style={"color": "#fff", "fontWeight": "900"}),
                html.Span("cc", style={"color": "#ffee00", "fontWeight": "900"}),
            ], className="px-2 py-0 rounded", style={"background": "#e60012", "fontSize": "0.75rem", "letterSpacing": "-0.5px"})
        else:
            logo_content = html.Span(platform_label, className="small fw-bold text-uppercase")

        # Lock icon for PPV
        lock_icon = _lucide("lock") if broadcast_type == "PPV" else None
        
        detail_rows.append(
            html.Div(
                [
                    _lucide("tv"),
                    html.A(
                        [logo_content, lock_icon] if lock_icon else logo_content,
                        href=streaming_url,
                        target="_blank",
                        rel="noopener noreferrer",
                        className="d-inline-flex align-items-center gap-1 text-decoration-none",
                        title=f"Watch on {platform_label} {'(Pay-Per-View)' if broadcast_type == 'PPV' else '(Free)'}"
                    ),
                    dbc.Badge("PPV", color="warning", className="ms-2 text-dark", style={"fontSize": "0.6rem"}) if broadcast_type == "PPV" else None,
                    dbc.Badge("FREE", color="success", className="ms-2", style={"fontSize": "0.6rem"}) if broadcast_type == "Free" else None,
                ],
                className="d-flex align-items-center gap-1 mb-2",
            )
        )
    else:
        detail_rows.append(
            html.Div(
                [
                    _lucide("tv-off"),
                    html.Small(platform_label, className="portal-text-muted"),
                ],
                className="d-flex align-items-center gap-1 mb-2",
            )
        )

    # Ticket Prices Row
    if ticket_prices:
        detail_rows.append(
            html.Div(
                [
                    _lucide("ticket"),
                    html.Small(f"Tickets: {ticket_prices}", className="portal-text-muted fw-semibold"),
                ],
                className="d-flex align-items-center gap-1 mb-2",
            )
        )

    # AI win probability (stub at 50% if not available)
    win_prob = milestone_payload.get("win_probability", 50)
    win_prob_label = (
        f"{win_prob}% win probability"
        if milestone_payload.get("win_probability") is not None
        else "Win probability: pending"
    )
    detail_rows.append(
        html.Div(
            [
                html.Small(
                    [_lucide("bar-chart-2"), win_prob_label],
                    className="portal-text-muted d-block mb-1",
                ),
                dbc.Progress(
                    value=win_prob,
                    max=100,
                    color="success" if win_prob >= 50 else "warning",
                    className="mb-1",
                    style={"height": "6px"},
                ),
            ],
            className="mb-2",
        )
    )

    # H2H record
    if h2h:
        h2h_text = (
            f"Ultimos {h2h.get('matches_found', 0)} enfrentamientos: "
            f"{h2h.get('wins', 0)}W - {h2h.get('draws', 0)}D - {h2h.get('losses', 0)}L"
        )
    else:
        h2h_text = "H2H: sin datos"
    detail_rows.append(
        html.Div(
            [_lucide("shield"), html.Small(h2h_text, className="portal-text-muted")],
            className="d-flex align-items-center gap-1",
        )
    )

    detail_panel = html.Div(
        detail_rows,
        id={"type": "card-detail-panel", "index": milestone_id},
        className="next-game-card__detail pt-2 px-2 border-top border-secondary",
        style={"display": "none"},  # toggled by clientside card-expand callback
    )

    return html.Div(
        [header_content, detail_panel],
        className="next-game-card py-1",
    )
