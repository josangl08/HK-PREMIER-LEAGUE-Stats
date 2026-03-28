# ABOUTME: Expandable Past Game Card component for the Player Portal timeline.
# ABOUTME: Renders post-match milestones with a closed header (competition/date/result/teams) and expandable panel (stadium/player stats or absence reason).

from typing import Dict, Any, Optional

from dash import html
import dash_bootstrap_components as dbc


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

_ABSENCE_LABELS = {
    "not_summoned": ("secondary", "No convocado"),
    "injured": ("warning", "Lesion"),
    "suspended": ("danger", "Sancion"),
    "unknown": ("light", "Ausencia (razon desconocida)"),
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


def _result_badge(result: str) -> dbc.Badge:
    """Maps W/D/L/- result code to a coloured badge."""
    color_map = {"W": "success", "D": "secondary", "L": "danger"}
    color = color_map.get(result.upper(), "light")
    return dbc.Badge(result.upper(), color=color, className="small me-1")


def render_past_game_card(
    milestone_payload: Dict[str, Any],
    milestone_id: str,
) -> html.Div:
    """
    Renders a Past Game (post-match) card with closed and expandable states.

    Closed state: competition badge + logo (top-right), date, result (W/D/L + score),
                  team names, expand arrow (bottom-right).
    Expanded panel: stadium name + player-level stats OR absence reason.
    """
    home_team = milestone_payload.get("home_team", "Home")
    away_team = milestone_payload.get("away_team", "Away")
    competition_raw = milestone_payload.get("competition", "")
    competition = _normalize_comp(competition_raw)
    kickoff_display = milestone_payload.get("kickoff_display", "")
    stadium = milestone_payload.get("stadium")

    # Player stats and absence
    player_stats = milestone_payload.get("player_stats") or {}
    perf = player_stats.get("performance_stats", {})
    minutes = int(milestone_payload.get("minutes_played", 0) or 0)
    if minutes == 0:
        minutes = int(perf.get("Minutes", 0) or 0)
    goals = int(milestone_payload.get("goals", 0) or 0)
    assists = int(milestone_payload.get("assists", 0) or 0)
    absence_reason = milestone_payload.get("absence_reason")
    confirmation_status = milestone_payload.get("confirmation_status", "")

    result_code = milestone_payload.get("result", "")

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

    # Competition badge (no logo — logo is in the corner)
    comp_badge = (
        dbc.Badge(competition, color=comp_color, className="small")
        if competition
        else None
    )

    status_badge = (
        dbc.Badge(
            confirmation_status,
            color="success" if confirmation_status == "Confirmed" else "secondary",
            className="small ms-1",
        )
        if confirmation_status
        else None
    )

    # ── Closed header ──────────────────────────────────────────────────────
    header_content = html.Div(
        [
            # Top row: competition + date + logo top-right
            html.Div(
                [
                    html.Div(
                        [
                            comp_badge,
                            html.Small(kickoff_display, className="portal-text-muted me-2"),
                            status_badge,
                        ],
                        className="d-flex align-items-center flex-wrap gap-1 flex-grow-1",
                    ),
                    comp_logo_el,
                ],
                className="d-flex align-items-start justify-content-between mb-1",
            ),
            # Teams + result
            html.Div(
                [
                    html.Small(home_team, className="text-truncate fw-semibold", style={"maxWidth": "90px"}),
                    html.Div(
                        [
                            _result_badge(result_code) if result_code else None,
                            html.Small("vs", className="portal-text-muted mx-1"),
                        ],
                        className="d-flex align-items-center mx-2 flex-shrink-0",
                    ),
                    html.Small(away_team, className="text-truncate", style={"maxWidth": "90px"}),
                ],
                className="d-flex align-items-center",
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
        className="past-game-card__header px-2 py-1",
    )

    # ── Expandable detail panel ────────────────────────────────────────────
    detail_rows = []

    if stadium:
        detail_rows.append(
            html.Div(
                [_lucide("map-pin"), html.Small(stadium, className="portal-text-muted")],
                className="d-flex align-items-center gap-1 mb-2",
            )
        )

    if minutes > 0:
        rating = perf.get("Rating") or perf.get("rating")
        detail_rows.append(
            html.Div(
                [
                    html.Small(
                        [_lucide("timer"), f"{minutes}'"],
                        className="portal-text-muted me-3",
                    ),
                    html.Small(
                        [_lucide("crosshair"), f"{goals} gol{'es' if goals != 1 else ''}"],
                        className="portal-text-muted me-3",
                    ),
                    html.Small(
                        [_lucide("trending-up"), f"{assists} asist."],
                        className="portal-text-muted me-3",
                    ),
                ],
                className="d-flex flex-wrap align-items-center gap-1 mb-1",
            )
        )
        if rating:
            detail_rows.append(
                html.Div(
                    [_lucide("star"), html.Small(f"Rating: {rating}", className="portal-text-muted")],
                    className="d-flex align-items-center gap-1",
                )
            )
    else:
        # Task 8.2: Enhanced absence badge with descriptive text
        if isinstance(absence_reason, dict):
            category = absence_reason.get("category", "unknown")
            text = absence_reason.get("text")
            badge_color, label = _ABSENCE_LABELS.get(category, ("light", category))
            display_text = f"Absence: {text}" if text else f"Absence: {label}"
        else:
            reason = absence_reason or "unknown"
            badge_color, label = _ABSENCE_LABELS.get(reason, ("light", reason))
            display_text = f"Absence: {label}"

        detail_rows.append(
            html.Div(
                [
                    _lucide("user-x"),
                    dbc.Badge(
                        display_text, 
                        color=badge_color, 
                        pill=True, 
                        className="small border border-white border-opacity-10 shadow-sm"
                    ),
                ],
                className="d-flex align-items-center gap-2",
            )
        )

    detail_panel = html.Div(
        detail_rows if detail_rows else [
            html.Small("Sin detalles disponibles.", className="portal-text-muted fst-italic")
        ],
        id={"type": "card-detail-panel", "index": milestone_id},
        className="past-game-card__detail pt-2 px-2 border-top border-secondary",
        style={"display": "none"},  # toggled by clientside card-expand callback
    )

    return html.Div(
        [header_content, detail_panel],
        className="past-game-card py-1",
    )
