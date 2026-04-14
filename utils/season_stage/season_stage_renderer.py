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
from utils.cache import cache

_PROFILE_CTX_CACHE_TTL = 3600  # 1 hour — matches figure cache TTL


def render_season_stage(payload: Dict) -> html.Div:
    context = build_season_stage_context(payload)
    player_name = context.get("player_name", "Player")
    season = context.get("season", "")

    profile_context = build_season_profile_context(
        context.get("season_df"),
        player_name,
        context.get("pos_group", "Midfielder"),
        season,
    )
    context["profile_context"] = profile_context

    # Cache profile_context so the lazy UMAP modal callback can retrieve it without
    # re-running build_season_profile_context or touching the database again.
    if player_name and season:
        cache.set(
            f"season-profile-ctx:v1:{player_name}:{season}",
            profile_context,
            timeout=_PROFILE_CTX_CACHE_TTL,
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
