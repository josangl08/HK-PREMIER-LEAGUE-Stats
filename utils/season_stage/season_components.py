# ABOUTME: Dash component builders for the season-stage surface, including snapshot, profile block, competition split, and UMAP modal.
# ABOUTME: Keeps season-stage UI composition modular and independent from data assembly helpers.

from __future__ import annotations

from typing import Any, Dict, List

import dash_bootstrap_components as dbc
from dash import dcc, html

from data.competition_registry import get_competition_display_name, get_competition_logo
from utils.chart_helpers import HKFATheme
from utils.season_stage.season_figures import (
    build_season_comparison_figure,
    build_season_quadrant_figure,
    build_season_umap_evidence_figure,
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


def _section_title(icon: str, title: str, subtitle: str = "", class_name: str = "mb-3") -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.I(className=f"bi {icon} me-2", style={"color": HKFATheme.ACCENT_GOLD}),
                    html.Span(title, style={"fontWeight": "700", "fontSize": "1.02rem", "color": HKFATheme.TEXT_PRIMARY}),
                ],
                className="d-flex align-items-center mb-1",
            ),
            html.Div(subtitle, className="season-stage-section-subtitle") if subtitle else None,
        ],
        className=class_name,
    )


def _pulse_card(label: str, value: Any, icon: str, modifier: str = "") -> html.Div:
    class_name = "season-stage-kpi"
    if modifier:
        class_name = f"{class_name} {modifier}"
    return html.Div(
        [
            html.Div(
                [
                    html.I(className=f"bi {icon} me-2", style={"fontSize": "1rem", "color": HKFATheme.ACCENT_GOLD}),
                    html.Span(label, className="season-stage-kpi__label season-stage-kpi__label--full"),
                ],
                className="season-stage-kpi__top",
            ),
            html.Div(str(value), className="season-stage-kpi__value"),
        ],
        className=class_name,
    )


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


def _delta_card(label: str, value: Any, delta_text: str, icon: str, accent: str) -> html.Div:
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

    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(
                    [
                        icon_node,
                        html.Span(
                            label,
                            style={"color": "rgb(201, 210, 222)", "fontSize": "0.8rem", "fontWeight": "400"},
                        ),
                    ],
                    className="mb-2",
                ),
                html.Div(
                    str(value),
                    style={"color": "rgb(244, 248, 252)", "fontSize": "1.55rem", "fontWeight": "800", "lineHeight": "1.05"},
                ),
                html.Div(
                    delta_text,
                    style={"color": delta_color, "fontSize": "0.86rem", "fontWeight": "400", "marginTop": "8px"},
                ),
            ]
            ,
            style={"padding": "14px 14px 12px"}
        ),
        className="border-0 prematch-float-card prematch-clean-card prematch-stat-card",
        style={
            "position": "relative",
            "width": "150px",
            "minWidth": "150px",
            "maxWidth": "150px",
            "height": "100%",
            "minHeight": "150px",
            "maxHeight": "150px",
            "marginBottom": "0",
            "padding": "0",
            "boxSizing": "border-box",
            "overflow": "hidden",
            "display": "block",
        },
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


def _build_season_performance_metrics(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    current_row = context.get("season_row")
    prev_row = (context.get("previous_season") or {}).get("row")
    if current_row is None:
        return []

    metrics: List[Dict[str, Any]] = []
    for idx, (label, key, icon) in enumerate(_season_performance_metric_specs(context.get("pos_group", "Midfielder"))):
        if key not in current_row.index:
            continue
        current_value = float(current_row.get(key) or 0)
        previous_value = float(prev_row.get(key) or 0) if prev_row is not None and key in prev_row.index else 0.0
        max_value = max(abs(current_value), abs(previous_value), 1e-6)
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
                "current_scaled": current_value / max_value,
                "previous_scaled": previous_value / max_value,
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


def render_season_performance(context: Dict[str, Any]) -> html.Div:
    prev = context.get("previous_season") or {}
    current_row = context.get("season_row")
    prev_row = prev.get("row")
    if current_row is None or prev_row is None:
        return html.Div(
            [
                _section_title("bi-speedometer2", "Season Performance", "Selected season metrics with previous-season comparison."),
                html.Div("Previous-season comparison is not available for this player yet.", className="text-muted small"),
            ]
        )
    metrics = _build_season_performance_metrics(context)
    if not metrics:
        return html.Div(
            [
                _section_title("bi-speedometer2", "Season Performance", "Selected season metrics with previous-season comparison."),
                html.Div("Season performance metrics are not available.", className="text-muted small"),
            ]
        )
    return html.Div(
        [
            _section_title("bi-speedometer2", "Season Performance", "Selected season metrics with previous-season comparison."),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                _delta_card(
                                    metric["label"],
                                    metric["current_display"],
                                    metric["delta_text"],
                                    metric["icon"],
                                    metric["color"],
                                ),
                                className="season-stage-performance-card-shell",
                                style={
                                    "flex": "1 1 150px",
                                    "minWidth": "150px",
                                    "maxWidth": "150px",
                                    "height": "150px",
                                },
                            )
                            for metric in metrics
                        ],
                        className="season-stage-kpi-grid season-stage-kpi-grid--performance",
                        style={
                            "display": "flex",
                            "gap": "12px",
                            "flexWrap": "wrap",
                            "alignItems": "stretch",
                        },
                    ),
                    html.Div(
                        dcc.Graph(
                            figure=build_season_comparison_figure(
                                metrics,
                                prev.get("season") or "Previous",
                                context.get("season") or "Selected",
                            ),
                            config={"displayModeBar": False, "responsive": True},
                            className="w-100 season-comparison-panel",
                            responsive=True,
                            style={"width": "100%", "minWidth": "0", "marginBottom": "0", "display": "block"},
                        ),
                        className="season-stage-panel season-stage-panel--performance-chart",
                    ),
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
            _section_title(
                "bi-diagram-3",
                "Role Profile in the League",
                "How this season's role sits inside the league cohort.",
                class_name="season-role-profile__title",
            ),
            html.Div(
                [
                    dcc.Graph(
                        figure=build_season_quadrant_figure(profile_context),
                        config={"displayModeBar": False, "responsive": True},
                        className="w-100 season-quadrant-panel",
                        responsive=True,
                        style={"width": "100%", "minWidth": "0"},
                    ),
                    html.Div(profile_context.get("archetype_label", "Season Profile"), className="season-role-badge season-role-badge--large"),
                    html.Div(clarity.get("copy", ""), className="season-role-copy"),
                    html.Div(
                        [
                            html.Div(clarity.get("label", "Profile read"), className="season-profile-clarity"),
                            html.Div(f"Nearest profiles: {nearest_line}", className="season-profile-neighbors"),
                        ],
                        className="season-role-profile__summary",
                    ),
                ],
                className="season-role-profile-card",
            ),
            dbc.Button(
                "View Full Profile Map",
                id="season-profile-map-open",
                color="link",
                className="season-profile-cta px-0 mt-2",
                n_clicks=0,
            ),
            render_season_umap_modal(profile_context),
        ],
    )


def render_season_competition_split(split_rows: List[Dict[str, Any]], is_current_season: bool = False) -> html.Div:
    body: List[Any] = [_section_title("bi-trophy", "Competition Split")]
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


def render_season_umap_modal(profile_context: Dict[str, Any]) -> dbc.Modal:
    explainer = html.Div(
        [
            html.Div("Nearby points suggest similar statistical profiles for this season.", className="season-umap-explainer"),
            html.Div("Cluster colors indicate broader role families rather than exact football positions.", className="season-umap-explainer"),
            html.Div("The highlighted point marks the selected season profile and the same archetype used in the badge and quadrant block.", className="season-umap-explainer"),
        ],
        className="mb-3",
    )
    return dbc.Modal(
        [
            dbc.ModalHeader(
                dbc.ModalTitle(f"Full Profile Map · {profile_context.get('archetype_label', 'Season Profile')}"),
                close_button=True,
            ),
            dbc.ModalBody(
                [
                    explainer,
                    dcc.Graph(
                        figure=build_season_umap_evidence_figure(profile_context),
                        config={"displayModeBar": False, "responsive": True},
                    ),
                ],
                className="career-evidence-modal-body",
            ),
            dbc.ModalFooter(
                dbc.Button("Close", id="season-profile-map-close", color="secondary", n_clicks=0)
            ),
        ],
        id="season-profile-map-modal",
        is_open=False,
        centered=True,
        size="xl",
        scrollable=True,
        className="career-evidence-modal season-umap-modal",
        fade=False,
    )
