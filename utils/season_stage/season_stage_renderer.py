# ABOUTME: Main renderer for the season-stage surface, orchestrating season context, role profile, and UI sections.
# ABOUTME: Replaces the placeholder season stage with a season-first, modular renderer outside the legacy stage_helpers file.

from __future__ import annotations

from typing import Dict

from dash import html

from utils.season_stage.season_components import (
    render_season_competition_split,
    render_season_header,
    render_season_performance,
    render_season_role_profile,
)
from utils.season_stage.season_context import build_season_stage_context
from utils.season_stage.season_profile import build_season_profile_context


def render_season_stage(payload: Dict) -> html.Div:
    context = build_season_stage_context(payload)
    context["profile_context"] = build_season_profile_context(
        context.get("season_df"),
        context.get("player_name", "Player"),
        context.get("pos_group", "Midfielder"),
        context.get("season", ""),
    )

    return html.Div(
        [
            html.Div(
                [
                    render_season_header(context),
                    html.Div(
                        render_season_competition_split(
                            context.get("competition_split") or [],
                            is_current_season=bool(context.get("is_current_season")),
                        ),
                        className="season-stage-competition-surface",
                    ),
                ],
                className="season-stage-grid season-stage-grid--top",
            ),
            render_season_performance(context),
            render_season_role_profile(context.get("profile_context") or {}),
        ],
        className="stage-view stage-view--season season-stage-stack pb-2",
    )
