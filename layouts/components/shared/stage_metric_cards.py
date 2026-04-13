# ABOUTME: Shared stage metric card components used by season, pre-match, and career surfaces.
# ABOUTME: Keeps metric card structure consistent while letting each surface supply metric-specific content and accents.

from __future__ import annotations

from typing import Any

from dash import html

from layouts.components.shared.stage_card_shell import create_stage_card_shell


def create_stage_metric_card(
    label: str,
    value: str,
    subtext: str = "",
    icon: str | Any = "bi-dot",
    accent: str = "#ffffff",
    subtext_color: str = "#d6dde6",
    class_name: str = "",
    size: str = "150px",
    height: str = "130px",
) -> html.Div:
    icon_node: Any
    if isinstance(icon, str):
        icon_node = html.I(
            className=f"bi {icon}",
            style={"color": accent, "fontSize": "1rem", "marginRight": "8px"},
        )
    else:
        icon_node = icon

    card = create_stage_card_shell(
        [
            html.Div(
                [
                    icon_node,
                    html.Span(label, className="pp-stage-metric-card__label"),
                ],
                className="pp-stage-metric-card__top",
            ),
            html.Div(value, className="pp-stage-metric-card__value"),
            html.Div(subtext, className="pp-stage-metric-card__subtext", style={"color": subtext_color}) if subtext else None,
        ],
        variant="clean",
        padding="md",
        class_name=f"prematch-stat-card pp-stage-metric-card {class_name}".strip(),
        style={
            "width": size,
            "minWidth": size,
            "maxWidth": size,
            "height": height,
            "minHeight": height,
            "maxHeight": height,
            "overflow": "hidden",
            "display": "block",
            "boxSizing": "border-box",
        },
    )

    return html.Div(
        card,
        className="pp-stage-metric-card-shell",
        style={
            "flex": f"1 1 {size}",
            "minWidth": size,
            "maxWidth": size,
            "height": height,
        },
    )
