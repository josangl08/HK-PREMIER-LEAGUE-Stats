# ABOUTME: Shared stage section title component for season, pre-match, and career blocks.
# ABOUTME: Uses career-stage typography with a simple icon treatment and explicit spacing control.

from __future__ import annotations

from dash import html

from utils.chart_helpers import HKFATheme


def create_stage_section_title(
    title: str,
    subtitle: str = "",
    icon: str = "bi-circle",
    accent: str | None = None,
    class_name: str = "",
) -> html.Div:
    resolved_accent = accent or HKFATheme.ACCENT_GOLD
    return html.Div(
        [
            html.Div(
                [
                    html.I(className=f"bi {icon} me-2", style={"color": resolved_accent}),
                    html.Span(title, className="pp-stage-title__text"),
                ],
                className="pp-stage-title__row",
            ),
            html.Div(subtitle, className="pp-stage-title__subtitle") if subtitle else None,
        ],
        className=f"pp-stage-title {class_name}".strip(),
    )
