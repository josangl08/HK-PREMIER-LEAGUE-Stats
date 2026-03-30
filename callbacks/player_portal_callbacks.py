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
    get_cached_image_path,
    render_image_gallery,
)
from utils.performance_helpers import get_streaming_label
from utils.app_context import get_hong_kong_data_manager
from utils.competition_helpers import normalize_competition, get_competition_logo

import html as _html_lib

logger = logging.getLogger(__name__)

# Static team color palette — sourced from official club identity (primary, secondary)
_TEAM_COLORS = {
    "kitchee": {"colour1": "#E31837", "colour2": "#003087"},
    "kitchee sc": {"colour1": "#E31837", "colour2": "#003087"},
    "eastern": {"colour1": "#004EA2", "colour2": "#FFD700"},
    "eastern aa": {"colour1": "#004EA2", "colour2": "#FFD700"},
    "eastern sc": {"colour1": "#004EA2", "colour2": "#FFD700"},
    "lee man": {"colour1": "#C8102E", "colour2": "#1a1a2e"},
    "lee man fc": {"colour1": "#C8102E", "colour2": "#1a1a2e"},
    "southern district": {"colour1": "#0057A8", "colour2": "#E31837"},
    "southern": {"colour1": "#0057A8", "colour2": "#E31837"},
    "rangers": {"colour1": "#0057A8", "colour2": "#ffffff"},
    "hk rangers": {"colour1": "#0057A8", "colour2": "#ffffff"},
    "tai po": {"colour1": "#003087", "colour2": "#FFB612"},
    "north district": {"colour1": "#F58220", "colour2": "#1a1a2e"},
    "hong kong football club": {"colour1": "#E41B17", "colour2": "#ffffff"},
    "hkfc": {"colour1": "#E41B17", "colour2": "#ffffff"},
    "kowloon city": {"colour1": "#6A0DAD", "colour2": "#1a1a2e"},
}


def _get_team_colors(team_name: str) -> dict:
    """Returns team color dict {colour1, colour2} for a given team name, or empty dict."""
    if not team_name:
        return {}
    key = team_name.lower().strip()
    return _TEAM_COLORS.get(key, {})


# Badge color per competition — must be distinct from the TYPE accent colors:
#   pre-match=primary (blue), post-match=success (green), career=warning (yellow).
# Allowed: danger, info, secondary, dark, light.
_COMPETITION_COLOR_MAP = {
    "HK Premier League": "info",  # teal/cyan
    "HKFA Cup": "danger",  # red
    "Sapling Cup": "dark",  # near-black
    "Senior Shield": "secondary",  # muted grey
    "League Cup": "light",  # light (white-ish)
    "AFC Champions League Two": "secondary",  # grey
}


def _normalize_comp(raw: str) -> str:
    """Normalize a competition name using central helper."""
    return normalize_competition(raw)


def _competition_logo_url(competition: str):
    """Return local web path for competition logo, or None if not mapped."""
    return get_competition_logo(competition)


def _competition_color(competition: str) -> str:
    """Return Bootstrap badge color for a competition name."""
    return _COMPETITION_COLOR_MAP.get(_normalize_comp(competition), "primary")


def _comp_badge(competition: str) -> "dbc.Badge | None":
    """Return a colored Badge with the competition name (logo shown separately in right column)."""
    comp = _normalize_comp(competition)
    if not comp:
        return None
    color = _competition_color(comp)
    return dbc.Badge(comp, color=color, className="small")


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
    if m_type == "post-match":
        status = milestone.get("confirmation_status") or milestone.get(
            "payload", {}
        ).get("confirmation_status", "")
        return "glass-success" if status == "Confirmed" else "glass-prematch"
    return _GLASS_CLASS_MAP.get(m_type, "glass-career")


def _lucide(name: str) -> html.I:
    """Returns a Lucide icon element."""
    return html.I(**{"data-lucide": name, "className": "lucide-inline-icon me-1"})


def _team_pill(name: str, logo_url, reverse: bool = False) -> html.Div:
    """Small team block: logo + name (or name + logo when reverse=True)."""
    if logo_url:
        badge = html.Img(
            src=logo_url,
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

        return [
            dbc.Badge(
                f"Season {season}",
                color="warning",
                className="small fw-semibold text-dark mb-1",
            ),
            html.Div(
                [
                    html.Small(
                        [_lucide("activity"), f"MP: {pj}"],
                        className="portal-text-muted me-2",
                    ),
                    html.Small(
                        [_lucide("crosshair"), f"G: {goals}"],
                        className="portal-text-muted me-2",
                    ),
                    html.Small(
                        [_lucide("trending-up"), f"A: {assists}"],
                        className="portal-text-muted me-2",
                    ),
                    html.Small(
                        [_lucide("timer"), f"Min: {minutes}"],
                        className="portal-text-muted",
                    ),
                ],
                className="d-flex flex-wrap gap-1",
            ),
        ]

    if m_type == "pre-match":
        competition = _normalize_comp(payload.get("competition", ""))
        kickoff = payload.get("kickoff_display", date_str)
        home = payload.get("home_team", "Home")
        away = payload.get("away_team", "Away")
        home_logo = payload.get("home_logo")
        away_logo = payload.get("away_logo")
        badge = _comp_badge(competition)
        return [
            html.Div(badge, className="card-row--competition") if badge else None,
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

            # Core Stats Row
            stat_parts = [
                html.Small(
                    [_lucide("timer"), f"{minutes}'"],
                    className="portal-text-muted me-3",
                ),
                html.Small(
                    [_lucide("crosshair"), f"{goals}G"],
                    className="portal-text-muted me-3",
                ),
                html.Small(
                    [_lucide("trending-up"), f"{assists}A"],
                    className="portal-text-muted",
                ),
            ]
            if own_goals > 0:
                stat_parts.append(
                    html.Small(
                        [_lucide("alert-triangle"), f"{own_goals} OG"],
                        className="text-danger ms-3",
                    )
                )

            rows.append(
                html.Div(
                    stat_parts, className="d-flex flex-wrap align-items-center mb-2"
                )
            )

            # Cards and Substitution Line
            detail_parts = []
            if yellow > 0:
                detail_parts.append(
                    dbc.Badge(
                        f"{yellow} Yellow",
                        color="warning",
                        className="me-2 small text-dark",
                    )
                )
            if red > 0:
                detail_parts.append(
                    dbc.Badge(f"{red} Red", color="danger", className="me-2 small")
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
            comp = m.get("competition", "Other")
            if comp not in comp_agg:
                comp_agg[comp] = {"pj": 0, "goals": 0, "assists": 0}
            comp_agg[comp]["pj"] += 1
            comp_agg[comp]["goals"] += int(m.get("goals", 0) or 0)
            comp_agg[comp]["assists"] += int(m.get("assists", 0) or 0)

        rows.append(
            html.Small(
                "Competition breakdown",
                className="portal-text-muted text-uppercase fw-bold d-block mb-1",
                style={"fontSize": "0.65rem"},
            )
        )
        for comp, stats in comp_agg.items():
            rows.append(
                html.Div(
                    [
                        html.Small(
                            comp,
                            className="text-truncate fw-semibold flex-grow-1",
                            style={"maxWidth": "130px"},
                        ),
                        html.Div(
                            [
                                html.Small(
                                    [_lucide("hash"), f"{stats['pj']}MP"],
                                    className="portal-text-muted me-2",
                                ),
                                html.Small(
                                    [_lucide("crosshair"), f"{stats['goals']}G"],
                                    className="portal-text-muted me-2",
                                ),
                                html.Small(
                                    [_lucide("trending-up"), f"{stats['assists']}A"],
                                    className="portal-text-muted",
                                ),
                            ],
                            className="d-flex align-items-center flex-shrink-0",
                        ),
                    ],
                    className="d-flex align-items-center justify-content-between border-bottom border-secondary py-1",
                )
            )
    else:
        rows.append(
            html.Small(
                "No match data available.", className="portal-text-muted fst-italic"
            )
        )

    return html.Div(rows, className="pb-1 pt-1")


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
    circle_cls = f"event-circle event-circle-{color}"
    if cached_image:
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
    # ETL → milestones-data-store                                         #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("milestones-data-store", "data"),
        Input("url", "pathname"),
        prevent_initial_call=False,
    )
    def update_timeline(pathname):
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
                return None

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
        prevent_initial_call=False,
    )
    def render_timeline_milestones(milestones_data):
        """
        Renders milestone items grouped by season in .season-section divs.
        Career milestones act as season headers; match groups visibility
        is controlled by the is-expanded class on the season-group-container.
        """
        if not milestones_data:
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

                matches_group = html.Div(
                    match_items,
                    id={"type": "season-matches-group", "index": career_id} if career_id else None,
                    className="season-matches-group",
                )
                
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
        prevent_initial_call=True,
    )
    def select_milestone(
        milestone_clicks, detail_clicks, selected_year, milestones_data
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
            milestone_id = triggered["index"]
            # Find the milestone by ID in the list
            m = next(
                (item for item in milestones_data if item.get("id") == milestone_id),
                None,
            )
            if m:
                return {"type": m["type"], "payload": m["payload"]}

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
        """Dispatches rendering to the appropriate stage helper."""
        if not context:
            return no_update

        user_role = (
            getattr(current_user, "role", "player") if current_user else "player"
        )
        m_type = context.get("type")
        payload = context.get("payload", {})

        try:
            if m_type == "post-match":
                return render_post_match(payload)
            elif m_type == "pre-match":
                return render_pre_match(payload)
            elif m_type == "career":
                return render_career_insights(payload, user_role)
            else:
                return dbc.Alert(
                    f"Tipo de contexto desconocido: {m_type}", color="warning"
                )
        except Exception as e:
            logger.error(f"update_stage error: {e}")
            return dbc.Alert("Error al renderizar el escenario.", color="danger")

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

        # Show spinner while agent runs (synchronous call — Dash 4 doesn't block here noticeably)
        try:
            from layouts.components.card_editor import create_card_studio_spinner
            from utils.card_design_agent import run_card_design_agent

            _team_colors = _get_team_colors(payload.get("home_team", ""))
            proposals = run_card_design_agent(
                match_payload=payload,
                player_profile={},
                team_colors=_team_colors,
                player_history=[],
                has_player_photo=False,
                card_type=card_type,
            )
            ai_notice = None
        except Exception as exc:
            logger.error(f"handle_action_node_pill agent error: {exc}")
            from utils.card_design_agent import _deterministic_fallback

            proposals = _deterministic_fallback(
                {
                    "match_payload": payload,
                    "team_colors": _get_team_colors(payload.get("home_team", "")),
                    "has_player_photo": False,
                    "card_type": card_type,
                }
            )
            ai_notice = "IA no disponible — propuesta básica cargada."

        # Build initial editor state (draft overrides AI proposal if exists)
        first_proposal = proposals[0] if proposals else {}
        if saved_draft:
            editor_state = saved_draft
        else:
            editor_state = {
                "milestone_id": milestone_id,
                "card_type": card_type,
                "template": (first_proposal.get("design") or {}).get("template", "A"),
                "format": "1:1",
                "ai_proposal": first_proposal,
                "elements": (first_proposal.get("design") or {}).get("elements") or {},
                "selected_photo_idx": None,
                "last_saved": None,
            }

        # Render the appropriate Card Studio layout
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

            from callbacks.card_editor_callbacks import _build_preview_layout

            initial_preview = _build_preview_layout(editor_state, {})

            if card_type == "pre-match":
                studio = create_pre_game_card_studio(
                    milestone_id,
                    match_context,
                    proposals,
                    initial_preview=initial_preview,
                )
            else:
                studio = create_performance_card_studio(
                    milestone_id,
                    match_context,
                    proposals,
                    initial_preview=initial_preview,
                )

            children = [studio]
            if ai_notice:
                children.insert(
                    0, dbc.Alert(ai_notice, color="warning", className="small mb-2")
                )
            result = html.Div(children)
        except Exception as exc:
            logger.error(f"handle_action_node_pill studio render error: {exc}")
            return (
                dbc.Alert("Error abriendo el Card Studio.", color="danger"),
                no_update,
                no_update,
            )

        return result, no_update, editor_state

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
            ],
            className="glass-card p-3",
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
