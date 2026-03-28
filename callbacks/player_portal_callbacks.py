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

import html as _html_lib

logger = logging.getLogger(__name__)

_COMPETITION_LOGO_MAP = {
    "HK Premier League": "/assets/competition_logos/hong_kong_premier_league.png",
    "HKFA Cup": "/assets/competition_logos/hong_kong_fa_cup.png",
    "Sapling Cup": "/assets/competition_logos/hong_kong_sapling_cup___15__25.png",
    "Senior Shield": "/assets/competition_logos/hong_kong_senior_challenge_shield.png",
    "AFC Champions League Two": "/assets/competition_logos/afc_champions_league_two.png",
}

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

# Display-layer normalization for Chinese competition names already persisted in
# fixtures.json (mirrors fixture_manager.COMPETITION_MAPPING + BOC alias).
_COMP_DISPLAY_MAP = {
    "中銀人壽香港超級聯賽": "HK Premier League",
    "香港超級聯賽": "HK Premier League",
    "BOC Life Hong Kong Premier League": "HK Premier League",
    "Hong Kong Premier League": "HK Premier League",  # English alias in cached fixtures
    "足總盃": "HKFA Cup",
    "Hong Kong FA Cup": "HKFA Cup",
    "HKFA Cup": "HKFA Cup",
    "賽馬會菁英盃": "Sapling Cup",
    "菁英盃": "Sapling Cup",
    "Hong Kong Sapling Cup": "Sapling Cup",  # TM English name (with date suffix)
    "聯賽盃": "League Cup",
    "高級組銀牌": "Senior Shield",
    "銀牌": "Senior Shield",
    "Hong Kong Senior Challenge Shield": "Senior Shield",
}


def _normalize_comp(raw: str) -> str:
    """Normalize a competition name to its English display form.
    Handles exact matches first, then substring matching (longest key first)."""
    if not raw:
        return raw
    if raw in _COMP_DISPLAY_MAP:
        return _COMP_DISPLAY_MAP[raw]
    for key in sorted(_COMP_DISPLAY_MAP, key=len, reverse=True):
        if key in raw:
            return _COMP_DISPLAY_MAP[key]
    return raw


def _competition_logo_url(competition: str):
    """Return local web path for competition logo, or None if not mapped."""
    return _COMPETITION_LOGO_MAP.get(_normalize_comp(competition))


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


def _competition_logo_img(competition: str):
    """Return a small competition logo img element, or text abbreviation if no asset available."""
    comp = _normalize_comp(competition)
    logo = _COMPETITION_LOGO_MAP.get(comp)
    if not logo:
        if comp:
            return html.Span(
                comp[:4].upper(),
                className="small fw-semibold portal-text-muted",
                style={"fontSize": "0.55rem"},
                title=comp,
            )
        return None
    return html.Img(
        src=logo,
        className="competition-logo-img",
        style={"width": "22px", "height": "22px", "objectFit": "contain"},
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
}

_COLOR_MAP = {
    "pre-match": "primary",
    "post-match": "success",
    "career": "warning",
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
        pj = len(matches)
        goals = sum(int(m.get("goals", 0) or 0) for m in matches)
        assists = sum(int(m.get("assists", 0) or 0) for m in matches)
        minutes = sum(int(m.get("minutes_played", 0) or 0) for m in matches)
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
                            platform_label,
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
                            get_streaming_label(None, None),
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
        # Prefer per-match TM stats; fall back to session player_stats
        minutes = int(payload.get("minutes_played", 0) or 0)
        goals = int(payload.get("goals", 0) or 0)
        assists = int(payload.get("assists", 0) or 0)
        if minutes == 0:
            player_stats = payload.get("player_stats") or {}
            perf = player_stats.get("performance_stats", {})
            minutes = int(perf.get("Minutes", 0) or 0)
            goals = int(perf.get("Goals", 0) or 0)
            assists = int(perf.get("Assists", 0) or 0)
        absence_reason = payload.get("absence_reason")

        if minutes > 0:
            player_stats = payload.get("player_stats") or {}
            perf = player_stats.get("performance_stats", {})
            rating = perf.get("Rating") or perf.get("rating")
            stat_parts = [
                html.Small(
                    [_lucide("timer"), f"{minutes}'"],
                    className="portal-text-muted me-2",
                ),
                html.Small(
                    [_lucide("crosshair"), f"{goals}G"],
                    className="portal-text-muted me-2",
                ),
                html.Small(
                    [_lucide("trending-up"), f"{assists}A"],
                    className="portal-text-muted",
                ),
            ]
            if rating:
                stat_parts.append(
                    html.Small(f" ⭐ {rating}", className="portal-text-muted ms-2")
                )
            rows.append(
                html.Div(
                    stat_parts, className="d-flex flex-wrap align-items-center gap-1"
                )
            )
        else:
            # Keys cover both raw slugs (from old data) and mapped strings (current pipeline)
            _ABSENCE_LABELS = {
                "not_summoned": ("secondary", "Not Summoned"),
                "Not Summoned": ("secondary", "Not Summoned"),
                "injured": ("warning", "Injury"),
                "Absence: Injury": ("warning", "Injury"),
                "suspended": ("danger", "Suspension"),
                "Absence: Suspension": ("danger", "Suspension"),
                "unknown": ("light", "Unknown absence"),
                "Absence: Unknown": ("light", "Unknown absence"),
            }
            reason = absence_reason or "unknown"
            badge_color, label = _ABSENCE_LABELS.get(reason, ("secondary", reason or "Not Played"))
            rows.append(
                html.Div(
                    [
                        _lucide("user-x"),
                        dbc.Badge(label, color=badge_color, className="small"),
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
    milestone: dict, initial_open: bool = False, generated_set: set = None, hidden: bool = False
) -> html.Div:
    """Renders a single timeline milestone as a Lucide-icon circle + connector + glass card.

    Structure: .timeline-event > [.event-node | .event-connector-h | .event-card.glass-card]
    The event-circle (inside event-node) carries the Lucide icon and doubles as the
    Action Node trigger for the image gallery (id=action-node kept for callback compat).
    """
    milestone_id = milestone.get("id", "unknown")
    m_type = milestone.get("type", "career")

    # AI-Insight milestones use a distinct card layout
    if m_type == "ai-insight":
        from layouts.components.ai_insight_card import render_ai_insight_card

        payload = milestone.get("payload", {})
        year_cls_val = milestone.get("group_year", "")
        year_cls = f" year-{year_cls_val}" if year_cls_val else ""
        hidden_cls = " timeline-item-hidden" if hidden else ""
        hidden_style = {"display": "none"} if hidden else {}
        return html.Div(
            render_ai_insight_card(payload, milestone_id),
            className=f"timeline-event mb-2{year_cls}{hidden_cls}",
            style=hidden_style,
        )
    lucide_icon = _ICON_MAP.get(m_type, "circle")
    payload = milestone.get("payload", {})
    matches = payload.get("matches", [])
    # Timeline accent color is TYPE-based (circle, line, button border).
    # Competition color is only for the badge text — set in _comp_badge / _comp_badge.
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

    # ── Header: type-specific collapsed state ─────────────────────────────
    header_label_content = _build_header_label(
        m_type, milestone, payload, matches, date_str
    )

    if m_type in ("pre-match", "post-match"):
        # ── CSS Grid: 2 columns × 2 rows ──────────────────────────────────
        # | label_content (col 1, rows 1-2) | comp_logo (col 2, row 1) |
        # |                                 | arrow btn (col 2, row 2) |
        # No right/bottom padding on container → arrow is flush to corner.
        comp_logo_el = _competition_logo_img(payload.get("competition", ""))
        logo_cell = (
            html.Div(
                comp_logo_el,
                className="competition-logo-container",
                style={
                    "display": "flex",
                    "alignItems": "flex-start",
                    "justifyContent": "flex-end",
                    "padding": "4px 4px 0 0",
                    "gridColumn": "2",
                    "gridRow": "1",
                },
            )
            if comp_logo_el
            else html.Div(style={"gridColumn": "2", "gridRow": "1"})
        )  # explicit placement avoids grid auto-placement ambiguity

        detail_btn = html.Div(
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
            style={"cursor": "pointer", "gridColumn": "2", "gridRow": "2"},
        )
        header_row = html.Div(
            [
                html.Div(
                    header_label_content,
                    id={"type": "timeline-milestone-text", "index": milestone_id},
                    style={"cursor": "pointer", "gridRow": "1 / 3"},  # spans both rows
                ),
                logo_cell,  # col 2, row 1 → top-right
                detail_btn,  # col 2, row 2 → bottom-right, flush to corner
            ],
            id={"type": "milestone-header", "index": milestone_id},
            className="milestone-header",
            style={
                "display": "grid",
                "gridTemplateColumns": "1fr auto",
                "gridTemplateRows": "1fr auto",
                "minHeight": "76px",
                "padding": "8px 0 0 8px",  # no right/bottom → arrow flush to corner
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
            className="d-flex align-items-center gap-2 py-2 px-2",
            n_clicks=0,
            style={"cursor": "pointer"},
        )

    # Hidden span for select_milestone callback compat
    milestone_trigger = html.Span(
        id={"type": "timeline-milestone", "index": milestone_id},
        n_clicks=0,
        style={"display": "none"},
    )

    # ── Body: expanded detail, toggled by clientside expand-store ─────────
    body_style = {"display": "block"} if initial_open else {"display": "none"}
    milestone_body = html.Div(
        _build_collapse_content(m_type, payload, matches, milestone_id=milestone_id),
        id={"type": "milestone-body", "index": milestone_id},
        style=body_style,
    )

    year_cls_val = milestone.get("group_year") or year_str
    year_cls = f" year-{year_cls_val}" if year_cls_val else ""
    # Action Node pill for pre/post-match only
    action_node_pill = None
    if m_type in ("pre-match", "post-match"):
        is_generated = bool(generated_set and milestone_id in generated_set)
        action_node_pill = _render_action_node_pill(m_type, milestone_id, is_generated)

    event_card = html.Div(
        [header_row, milestone_body],
        className=f"event-card event-card-{color} glass-card {glass_cls}",
    )

    # Wrap card + action node pill in a vertical column so the pill sits
    # below the card (not lateral/to-the-right).
    if action_node_pill:
        right_col = html.Div(
            [event_card, action_node_pill],
            className="event-card-column",
        )
    else:
        right_col = event_card

    hidden_cls = " timeline-item-hidden" if hidden else ""
    hidden_style = {"display": "none"} if hidden else {}
    return html.Div(
        className=f"timeline-event mb-2{year_cls}{hidden_cls}",
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
        Renders milestone items grouped by year in .season-section divs.
        Career milestones act as season headers; pre/post-match cards are wrapped
        in a season-matches-group div whose visibility mirrors the career card state.
        Pre-expands the most recent season's career milestone.
        Supports 5+10 pagination per season via timeline-pagination-store.
        """
        if not milestones_data:
            return no_update, no_update

        from collections import defaultdict

        groups = defaultdict(list)
        for m in milestones_data:
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

            # Separate career anchor from match milestones (ai-insight included in match group)
            career_m = next(
                (m for m in year_milestones if m.get("type") == "career"), None
            )
            match_milestones = [m for m in year_milestones if m.get("type") != "career"]

            items = []

            # Career milestone as season header (body pre-open for most recent year)
            if career_m:
                items.append(
                    _render_milestone_item(career_m, initial_open=is_recent)
                )
                career_id = career_m.get("id")
            else:
                career_id = None

            # Render ALL match milestones; first 5 visible, rest hidden.
            # A clientside Load More callback reveals 10 more on click (no server roundtrip).
            if match_milestones:
                match_items = [
                    _render_milestone_item(m, initial_open=False, hidden=(i >= 5))
                    for i, m in enumerate(match_milestones)
                ]
                if len(match_milestones) > 5:
                    match_items.append(
                        html.Div(
                            [
                                html.Div(className="load-more-axis-spacer"),  # aligns with event-node
                                html.Div(
                                    html.Button(
                                        [
                                            html.I(
                                                **{
                                                    "data-lucide": "chevrons-down",
                                                    "className": "lucide-inline-icon me-1",
                                                }
                                            ),
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

                group_style = {"display": "block"} if is_recent else {"display": "none"}
                if career_id:
                    items.append(
                        html.Div(
                            match_items,
                            id={"type": "season-matches-group", "index": career_id},
                            style=group_style,
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
        Output("timeline-pagination-store", "data"),
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
    # Phase 3: Clientside expand/collapse (task 3.1)                      #
    # Toggles milestone-body display; syncs with timeline-expand-store.   #
    # ------------------------------------------------------------------ #
    app.clientside_callback(
        """
        function(n_clicks_list, expand_store) {
            var triggered_id = dash_clientside.callback_context.triggered_id;
            if (!triggered_id || triggered_id.type !== 'milestone-header') {
                return [
                    window.dash_clientside.no_update,
                    window.dash_clientside.no_update,
                    window.dash_clientside.no_update,
                    window.dash_clientside.no_update
                ];
            }
            var mid = triggered_id.index;
            var open_ids = new Set(expand_store || []);

            // Accordion: when opening a career milestone (one that has a season-matches-group),
            // close all other career milestones first so only one season is open at a time.
            var group_outputs = dash_clientside.callback_context.outputs_list[2];
            var career_ids = new Set();
            if (group_outputs && group_outputs.length > 0) {
                group_outputs.forEach(function(out) { career_ids.add(out.id.index); });
            }
            if (career_ids.has(mid) && !open_ids.has(mid)) {
                career_ids.forEach(function(cid) { if (cid !== mid) open_ids.delete(cid); });
            }

            if (open_ids.has(mid)) {
                open_ids.delete(mid);
            } else {
                open_ids.add(mid);
            }
            var open_ids_array = Array.from(open_ids);

            // milestone-body styles (all milestone types)
            var header_inputs = dash_clientside.callback_context.inputs_list[0];
            var body_styles = header_inputs.map(function(inp) {
                return open_ids.has(inp.id.index) ? {display: 'block'} : {display: 'none'};
            });

            // season-matches-group styles (career milestone IDs control group visibility)
            var group_styles = [];
            if (group_outputs && group_outputs.length > 0) {
                group_styles = group_outputs.map(function(out) {
                    return open_ids.has(out.id.index) ? {display: 'block'} : {display: 'none'};
                });
            }

            // detail-btn rotation: rotate 90deg when expanded, back to 0deg when collapsed
            var btn_styles = header_inputs.map(function(inp) {
                var isOpen = open_ids.has(inp.id.index);
                return {transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)',
                        transition: 'transform 0.3s ease'};
            });

            return [open_ids_array, body_styles, group_styles, btn_styles];
        }
        """,
        Output("timeline-expand-store", "data", allow_duplicate=True),
        Output({"type": "milestone-body", "index": ALL}, "style"),
        Output({"type": "season-matches-group", "index": ALL}, "style"),
        Output({"type": "milestone-detail-btn", "index": ALL}, "style"),
        Input({"type": "milestone-header", "index": ALL}, "n_clicks"),
        State("timeline-expand-store", "data"),
        prevent_initial_call=True,
    )

    # ------------------------------------------------------------------ #
    # Phase 3: Intersection Observer scroll sync (tasks 3.2 + 3.3 + 4.2) #
    # Registers an IntersectionObserver on .season-section divs.          #
    # Updates active-year-store, pill active class, and scrolls pill.     #
    # ------------------------------------------------------------------ #
    app.clientside_callback(
        """
        function(children) {
            setTimeout(function() {
                if (window._seasonObserver) {
                    window._seasonObserver.disconnect();
                }
                var container = document.querySelector('.milestone-list-container');
                var sections = document.querySelectorAll('.season-section');
                if (!sections.length) return;

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
                    // Update Dash store (task 3.2)
                    window.dash_clientside.set_props('active-year-store', {data: topYear});
                    // Toggle active class on pills (task 3.3)
                    var pills = document.querySelectorAll('#year-navigator-pills button');
                    pills.forEach(function(pill) {
                        var pillYear = pill.textContent.trim();
                        if (pillYear === topYear) {
                            pill.classList.add('active');
                            // Scroll pill into center view (task 4.2)
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
    # Phase 3: Init Lucide icons after timeline renders                   #
    # ------------------------------------------------------------------ #
    app.clientside_callback(
        """
        function(children) {
            setTimeout(function() {
                if (window.lucide) { lucide.createIcons(); }
            }, 150);
            return window.dash_clientside.no_update;
        }
        """,
        Output("active-year-store", "data", allow_duplicate=True),
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
    # Action Node pill click → card generation or gallery open            #
    # Tasks 6.3 + 6.4: route to generate/view; transition label via store #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("stage-content", "children", allow_duplicate=True),
        Output("timeline-pagination-store", "data", allow_duplicate=True),
        Input({"type": "action-node-pill", "index": ALL}, "n_clicks"),
        State("milestones-data-store", "data"),
        State("timeline-pagination-store", "data"),
        prevent_initial_call=True,
    )
    def handle_action_node_pill(n_clicks_list, milestones_data, pagination_store):
        """Generate or view social card from action node pill below each match card."""
        if not ctx.triggered_id or not any(n_clicks_list or []):
            return no_update, no_update
        triggered = ctx.triggered_id
        if (
            not isinstance(triggered, dict)
            or triggered.get("type") != "action-node-pill"
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

        store = pagination_store or {}
        generated = dict(store.get("generated", {}))
        is_generated = generated.get(milestone_id, False)
        m_type = m.get("type")
        payload = m.get("payload", {})

        if is_generated:
            path = get_cached_image_path(milestone_id)
            return render_image_gallery(path), no_update

        # Generate card
        try:
            if m_type == "pre-match":
                from layouts.prematch_card import create_prematch_card

                result = create_prematch_card(payload)
            elif m_type == "post-match":
                result = render_post_match(payload)
            else:
                return no_update, no_update
        except Exception as e:
            logger.error(f"handle_action_node_pill generation error: {e}")
            return dbc.Alert("Error generating card.", color="danger"), no_update

        generated[milestone_id] = True
        new_store = {**store, "generated": generated}
        return result, new_store

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
        entry["payload"] = payload
        result.append(entry)
    return result
