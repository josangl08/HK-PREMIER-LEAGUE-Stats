# ABOUTME: Dash component builders for the season-stage surface: snapshot, profile block, competition split, and role profile.
# ABOUTME: Keeps season-stage UI composition modular and independent from data assembly helpers.

from __future__ import annotations

from typing import Any, Dict, List
import json

import dash_bootstrap_components as dbc
from dash import dcc, html

from data.competition_registry import get_competition_display_name, get_competition_logo
from layouts.components.shared import (
    create_stage_metric_card,
    create_stage_section_title,
)
from utils.chart_helpers import HKFATheme
from utils.season_stage.season_figures import (
    build_season_comparison_figure,
    build_season_quadrant_figure,
)
from utils.stage_helpers import _resolve_team_logo


COMPETITION_PALETTE = [
    "#ff6b6b",
    "#ffd166",
    "#06d6a0",
    "#118ab2",
    "#8338ec",
    "#fb5607",
    "#3a86ff",
    "#ff006e",
]

COMPARISON_METRIC_COLORS = [
    "#ef5350",
    "#ff8f3a",
    "#ffb300",
    "#2f5d8a",
    "#3c7db8",
    "#18c7c0",
    "#68d391",
    "#b794f4",
]

def _format_delta_value(current: float, previous: float) -> tuple[str, str]:
    delta = current - previous
    direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
    symbol = "↑" if delta > 0 else "↓" if delta < 0 else "→"
    if abs(delta) < 0.01:
        direction = "flat"
        symbol = "→"
    if float(current).is_integer() and float(previous).is_integer():
        return f"{symbol} {delta:+.0f}", direction
    return f"{symbol} {delta:+.2f}", direction

def _build_delta_metric_card(label: str, value: Any, delta_text: str, icon: str, accent: str) -> html.Div:
    delta_color = "#d6dde6"
    if str(delta_text).startswith("↑"):
        delta_color = "#52dc8e"
    elif str(delta_text).startswith("↓"):
        delta_color = "#ff6b6b"
    elif str(delta_text).startswith("→"):
        delta_color = "#ffab52"

    icon_node: Any
    if label == "Goals":
        icon_node = html.Img(
            src="/assets/icons/soccer-ball.svg",
            style={"width": "20px", "height": "20px", "objectFit": "contain", "marginRight": "8px"},
        )
    else:
        icon_node = html.I(
            className=f"bi {icon}",
            style={"color": accent, "fontSize": "1rem", "marginRight": "8px"},
        )
    return create_stage_metric_card(
        label=label,
        value=str(value),
        subtext=delta_text,
        icon=icon_node,
        accent=accent,
        subtext_color=delta_color,
        class_name="pp-stage-metric-card--delta",
        size="170px",
    )


def _format_metric_display(value: float) -> str:
    if abs(value) >= 1000 and float(value).is_integer():
        return f"{int(value):,}"
    if float(value).is_integer():
        return f"{int(value)}"
    if abs(value) >= 100:
        return f"{value:.1f}"
    return f"{value:.2f}"


def _season_performance_metric_specs(pos_group: str) -> List[tuple[str, str, str]]:
    base = [
        ("Matches Played", "Matches played", "bi-calendar-check"),
        ("Minutes Played", "Minutes played", "bi-stopwatch"),
        ("Goals", "Goals", "bi-bullseye"),
        ("Assists", "Assists", "bi-activity"),
    ]
    by_pos = {
        "Forward": [
            ("Expected Goals /90", "xG per 90", "bi-crosshair2"),
            ("Shots /90", "Shots per 90", "bi-bullseye"),
            ("Touches In Box /90", "Touches in box per 90", "bi-bounding-box"),
            ("Shot Accuracy", "Shots on target, %", "bi-percent"),
            ("Goal Conversion", "Goal conversion, %", "bi-graph-up-arrow"),
        ],
        "Winger": [
            ("Expected Assists /90", "xA per 90", "bi-stars"),
            ("Expected Goals /90", "xG per 90", "bi-crosshair2"),
            ("Dribbles /90", "Dribbles per 90", "bi-lightning-charge"),
            ("Crosses /90", "Crosses per 90", "bi-bezier"),
            ("Progressive Runs /90", "Progressive runs per 90", "bi-arrow-up-right-circle"),
        ],
        "Midfielder": [
            ("Expected Assists /90", "xA per 90", "bi-stars"),
            ("Key Passes /90", "Key passes per 90", "bi-diagram-3"),
            ("Progressive Passes /90", "Progressive passes per 90", "bi-arrow-up-right-circle"),
            ("Pass Accuracy", "Accurate passes, %", "bi-percent"),
            ("Interceptions /90", "Interceptions per 90", "bi-shield"),
        ],
        "Defender": [
            ("Interceptions /90", "Interceptions per 90", "bi-shield"),
            ("Defensive Duel Win %", "Defensive duels won, %", "bi-percent"),
            ("Aerial %", "Aerial duels won, %", "bi-percent"),
            ("Progressive Passes /90", "Progressive passes per 90", "bi-arrow-up-right-circle"),
            ("Pass Accuracy", "Accurate passes, %", "bi-percent"),
        ],
        "Goalkeeper": [
            ("Clean Sheets", "Clean sheets", "bi-lock"),
            ("Save Rate", "Save rate, %", "bi-hand-index-thumb"),
            ("Prevented Goals /90", "Prevented goals per 90", "bi-shield-check"),
            ("Long Pass Accuracy", "Accurate long passes, %", "bi-percent"),
            ("Exits /90", "Exits per 90", "bi-door-open"),
            ("Pass Accuracy", "Accurate passes, %", "bi-percent"),
        ],
    }
    return base + by_pos.get(pos_group, by_pos["Midfielder"])


import math

def _build_season_performance_metrics(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    current_row = context.get("season_row")
    prev_row = (context.get("previous_season") or {}).get("row")
    if current_row is None:
        return []

    # Use a global logarithmic scale to ensure absolute value mapping across ALL metrics.
    # log10(val + 1) preserves order: 1800 > 30 > 10 > 3 > 0.55
    # and ensures that small values are visible while large values don't dwarf them completely.
    def global_log_scale(val: float) -> float:
        v = abs(float(val or 0.0))
        # log10(2501) approx 3.4. We use 2500 as the global reference ceiling (full bar).
        ceiling_log = 3.398  # math.log10(2500 + 1)
        return min(1.0, math.log10(v + 1) / ceiling_log)

    metrics: List[Dict[str, Any]] = []
    for idx, (label, key, icon) in enumerate(_season_performance_metric_specs(context.get("pos_group", "Midfielder"))):
        if key not in current_row.index:
            continue
        current_value = float(current_row.get(key) or 0)
        previous_value = float(prev_row.get(key) or 0) if prev_row is not None and key in prev_row.index else 0.0
        
        delta_text, direction = _format_delta_value(current_value, previous_value)
        metrics.append(
            {
                "label": label,
                "key": key,
                "icon": icon,
                "current_value": current_value,
                "previous_value": previous_value,
                "current_display": _format_metric_display(current_value),
                "previous_display": _format_metric_display(previous_value),
                "delta_text": delta_text,
                "direction": direction,
                "current_scaled": global_log_scale(current_value),
                "previous_scaled": global_log_scale(previous_value),
                "color": COMPARISON_METRIC_COLORS[idx % len(COMPARISON_METRIC_COLORS)],
            }
        )
    return metrics


def render_season_header(context: Dict[str, Any]) -> html.Div:
    profile = context.get("profile_context") or {}
    season_team = context.get("season_team") or "Season Club"
    player_name = context.get("player_name", "Player")
    season = context.get("season")
    pos_group = context.get("pos_group", "Player")
    team_logo = _resolve_team_logo(season_team)
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(f"Season {season}", className="season-stage-eyebrow"),
                            html.Div(
                                [
                                    html.Img(src=team_logo, className="season-stage-hero__crest") if team_logo else None,
                                    html.H4(
                                        season_team,
                                        className="mb-1 season-stage-hero__title",
                                        style={"color": HKFATheme.TEXT_PRIMARY, "fontWeight": "800"},
                                    ),
                                ],
                                className="season-stage-hero__club",
                            ),
                            html.Div(
                                [
                                    html.Span(player_name, className="season-stage-hero__meta-primary"),
                                    html.Span("·", className="season-stage-hero__meta-dot"),
                                    html.Span(pos_group, className="season-stage-hero__meta-secondary season-stage-hero__meta-chip"),
                                    html.Span(
                                        profile.get("archetype_label", f"{pos_group} Profile"),
                                        className="season-stage-hero__meta-chip season-stage-hero__meta-chip--cluster",
                                    ),
                                ],
                                className="season-stage-hero__meta",
                            ),
                        ],
                        className="season-stage-hero__copy",
                    ),
                ],
                className="d-flex justify-content-between align-items-start flex-wrap gap-3 season-stage-hero__top",
            ),
            html.Div(
                f"This season places {player_name} inside a {profile.get('archetype_label', 'defined')} role profile in the league, with the selected campaign acting as the unit of analysis rather than a career aggregate.",
                className="season-stage-intro-copy",
            ),
        ],
        className="season-stage-hero mb-4",
    )


def render_worth_noticing_block(
    curated_insight: Dict[str, Any] | None,
    debug_meta: Dict[str, Any] | None = None,
) -> html.Div | None:
    """Render the compact inline Worth Noticing surface when a curated insight exists."""
    if not curated_insight:
        return None

    debug_meta = debug_meta or {}
    badge_label = str(curated_insight.get("type") or "context")
    anchor = str(curated_insight.get("anchor") or "")
    served_from = str((debug_meta.get("served_from") or {}).get("overlay") or "")
    confidence = curated_insight.get("confidence")
    evidence = dict(curated_insight.get("evidence") or {})

    anchor_label_map = {
        "season_profile_context": "Role profile",
        "recent_form_context": "Recent form",
        "competition_split_context": "Competition split",
        "previous_season_context": "Season comparison",
        "season_performance_context": "Season output",
    }
    anchor_label = anchor_label_map.get(
        anchor,
        anchor.replace("_", " ") if anchor else "Season intelligence",
    )
    status_label = {
        "artifact": "Still the clearest signal",
        "session_memory": "Held for continuity",
        "inline": "New this visit",
    }.get(served_from, "Contextual signal")

    meta_bits = [badge_label.replace("_", " "), anchor_label]
    if confidence is not None:
        meta_bits.append(f"confidence {float(confidence):.2f}")

    evidence_summary = ""
    if evidence.get("metric"):
        evidence_summary = f"Focus: {evidence.get('metric')}"
    elif evidence.get("competition"):
        evidence_summary = f"Focus: {evidence.get('competition')}"
    elif evidence.get("current_pos_group") and evidence.get("previous_pos_group"):
        evidence_summary = (
            f"Focus: {evidence.get('previous_pos_group')} -> {evidence.get('current_pos_group')}"
        )
    elif anchor:
        evidence_summary = f"Focus: {anchor_label}"

    tooltip_bits = [status_label]
    if anchor_label:
        tooltip_bits.append(anchor_label)
    if evidence_summary and evidence_summary != f"Focus: {anchor_label}":
        tooltip_bits.append(evidence_summary)
    meta_tooltip = " | ".join(bit for bit in tooltip_bits if bit)

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Span("Worth Noticing", className="season-worth-noticing__eyebrow"),
                            html.H5(
                                str(curated_insight.get("title") or "Worth Noticing"),
                                className="season-worth-noticing__title mb-0",
                            ),
                        ],
                        className="season-worth-noticing__heading",
                    ),
                    html.Div(
                        " · ".join(meta_bits),
                        className="season-worth-noticing__meta",
                        title=meta_tooltip,
                    ),
                    html.Button(
                        "×",
                        id={
                            "type": "stage-overlay-prominent-dismiss",
                            "signal_id": str(curated_insight.get("signal_id") or ""),
                            "evidence_key": str(curated_insight.get("evidence_key") or curated_insight.get("signal_id") or ""),
                            "title": str(curated_insight.get("title") or ""),
                            "body": str(curated_insight.get("body") or ""),
                            "anchor": anchor,
                            "tier": "prominent",
                        },
                        n_clicks=0,
                        className="season-worth-noticing__dismiss",
                        title="Cerrar",
                    ),
                ],
                className="season-worth-noticing__top",
            ),
            html.P(
                str(curated_insight.get("body") or ""),
                className="season-worth-noticing__body mb-0",
            ),
        ],
        className="season-stage-panel season-worth-noticing season-worth-noticing--full-width",
        **{
            "data-signal-id": str(curated_insight.get("signal_id") or ""),
            "data-overlay-source": served_from or "unknown",
        },
    )


def render_season_intelligence_debug(debug_meta: Dict[str, Any] | None) -> html.Div:
    """Render a hidden debug hook so developers can inspect season intelligence mode and refresh state."""
    debug_meta = debug_meta or {}
    mode = str(debug_meta.get("mode") or "unknown")
    refresh_requested = bool(debug_meta.get("background_refresh_requested"))
    fallback_reason = str(debug_meta.get("fallback_reason") or "")
    served_from = debug_meta.get("served_from") or {}
    summary = {
        "mode": mode,
        "refresh_requested": refresh_requested,
        "fallback_reason": fallback_reason,
        "served_from": served_from,
    }
    return html.Div(
        json.dumps(summary, sort_keys=True),
        className="season-stage-intelligence-debug visually-hidden",
        **{
            "data-mode": mode,
            "data-refresh-requested": str(refresh_requested).lower(),
            "data-fallback-reason": fallback_reason,
        },
    )


def render_season_performance(context: Dict[str, Any]) -> html.Div:
    prev = context.get("previous_season") or {}
    current_row = context.get("season_row")
    prev_row = prev.get("row")
    if current_row is None or prev_row is None:
        return html.Div(
            [
                create_stage_section_title("Season Performance", "Selected season metrics with previous-season comparison.", icon="bi-speedometer2"),
                html.Div("Previous-season comparison is not available for this player yet.", className="text-muted small"),
            ]
        )
    metrics = _build_season_performance_metrics(context)
    if not metrics:
        return html.Div(
            [
                create_stage_section_title("Season Performance", "Selected season metrics with previous-season comparison.", icon="bi-speedometer2"),
                html.Div("Season performance metrics are not available.", className="text-muted small"),
            ]
        )
    return html.Div(
        [
            create_stage_section_title("Season Performance", "Selected season metrics with previous-season comparison.", icon="bi-speedometer2"),
            html.Div(
                [
                    html.Div(
                        [
                            _build_delta_metric_card(
                                metric["label"],
                                metric["current_display"],
                                metric["delta_text"],
                                metric["icon"],
                                metric["color"],
                            )
                            for metric in metrics
                        ],
                        className="season-stage-kpi-grid season-stage-kpi-grid--performance",
                    ),
                    html.Div(
                        dcc.Graph(
                            figure=build_season_comparison_figure(
                                metrics,
                                prev.get("season") or "Previous",
                                context.get("season") or "Selected",
                            ),
                            config={"displayModeBar": False, "responsive": True},
                            className="w-100",
                            responsive=True,
                            style={"width": "100%", "minWidth": "0", "marginBottom": "0", "display": "block"},
                        ),
                        className="season-stage-performance-chart-wrap",
                    )
                ],
                className="season-stage-grid season-stage-grid--performance",
            ),
        ]
    )


def render_season_role_profile(profile_context: Dict[str, Any]) -> html.Div:
    clarity = profile_context.get("profile_clarity") or {}
    nearest = profile_context.get("nearest_profiles") or []
    nearest_line = " · ".join(item["name"] for item in nearest) if nearest else "No close profiles detected."
    return html.Div(
        className="season-role-profile-section",
        children=[
            create_stage_section_title(
                "Role Profile in the League",
                "How this season's role sits inside the league cohort.",
                icon="bi-diagram-3",
                class_name="season-role-profile__title",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(profile_context.get("archetype_label", "Season Profile"), className="season-role-badge season-role-badge--large"),
                            html.Div(clarity.get("copy", ""), className="season-role-copy"),
                        ],
                        className="season-role-profile__meta",
                    ),
                    dcc.Graph(
                        figure=build_season_quadrant_figure(profile_context),
                        config={"displayModeBar": False, "responsive": True},
                        className="w-100 season-role-profile__graph",
                        responsive=True,
                        style={"width": "100%", "minWidth": "0", "marginBottom": "0", "display": "block"},
                    ),
                    html.Div(
                        [
                            html.Div(clarity.get("label", "Profile read"), className="season-profile-clarity"),
                            html.Div(f"Nearest profiles: {nearest_line}", className="season-profile-neighbors"),
                        ],
                        className="season-role-profile__summary",
                    ),
                ],
                className="season-role-profile-content",
            ),
            dbc.Button(
                "View Full Profile Map",
                id="season-profile-map-open",
                color="link",
                className="season-profile-cta px-0 mt-2",
                n_clicks=0,
            ),
            # Modal lives in the persistent portal layout (player_portal.py) to avoid
            # being recreated on every stage-content rewrite — do NOT add it here.
        ],
    )


def render_season_competition_split(split_rows: List[Dict[str, Any]], is_current_season: bool = False) -> html.Div:
    body: List[Any] = [create_stage_section_title("Competition Split", icon="bi-trophy")]
    if not split_rows:
        body.append(html.Div("Competition breakdown is not available yet.", className="text-muted small"))
        return html.Div(body)

    color_by_comp = {
        row["competition"]: COMPETITION_PALETTE[idx % len(COMPETITION_PALETTE)]
        for idx, row in enumerate(split_rows)
    }
    metrics = [
        ("Minutes", "minutes_played"),
        ("Matches", "matches_played"),
        ("Goals", "goals"),
        ("Assists", "assists"),
        ("Yellow Cards", "yellow_cards"),
        ("Red Cards", "red_cards"),
    ]

    body.append(
        html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            [
                                html.Span(
                                    className="season-competition-legend__swatch",
                                    style={"background": color_by_comp[row["competition"]]},
                                ),
                                html.Img(
                                    src=get_competition_logo(row["competition"]),
                                    style={"width": "18px", "height": "18px", "objectFit": "contain"},
                                ) if get_competition_logo(row["competition"]) else None,
                                html.Span(get_competition_display_name(row["competition"], long_form=False)),
                            ],
                            className="season-competition-legend__item",
                            style={
                                "background": f"{color_by_comp[row['competition']]}22",
                                "borderColor": f"{color_by_comp[row['competition']]}66",
                                "boxShadow": f"inset 0 1px 0 {color_by_comp[row['competition']]}1A",
                            },
                            title=f"{row['matches_played']} MP · {row['minutes_played']:,} MIN · {row['goals']} G · {row['assists']} A",
                        )
                        for row in split_rows
                    ],
                    className="season-competition-legend",
                ),
            ]
        )
    )

    for label, key in metrics:
        total = sum(float(row.get(key, 0) or 0) for row in split_rows)
        segments = []
        for row in split_rows:
            value = float(row.get(key, 0) or 0)
            width_pct = (value / total * 100.0) if total > 0 else 0
            segments.append(
                html.Div(
                    className="season-competition-bar__segment",
                    style={
                        "flex": f"0 0 {width_pct:.4f}%",
                        "width": f"{width_pct:.4f}%",
                        "background": color_by_comp[row["competition"]],
                        "minWidth": "8px" if value > 0 else "0",
                        "height": "100%",
                    },
                    title=f"{get_competition_display_name(row['competition'], long_form=False)} · {int(value) if float(value).is_integer() else value:g}",
                )
            )

        display_total = f"{int(total):,}" if float(total).is_integer() else f"{total:.2f}"
        body.append(
            html.Div(
                [
                    html.Div(label, className="season-competition-metric__label"),
                    html.Div(
                        [
                            html.Div(segments, className="season-competition-bar"),
                            html.Div(display_total, className="season-competition-metric__value"),
                        ],
                        className="season-competition-metric__track",
                    ),
                ],
                className="season-competition-metric",
            )
        )
    return html.Div(body)
