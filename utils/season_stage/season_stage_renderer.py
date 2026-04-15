# ABOUTME: Main renderer for the season-stage surface, orchestrating season context, role profile, and UI sections.
# ABOUTME: Replaces the placeholder season stage with a season-first, modular renderer outside the legacy stage_helpers file.

from __future__ import annotations

import logging
from typing import Dict

from dash import html

from utils.intelligence.overlay_surface import choose_primary_overlay_candidate
from utils.season_stage.season_components import (
    render_season_intelligence_debug,
    render_season_competition_split,
    render_season_header,
    render_season_performance,
    render_season_role_profile,
)
from utils.season_stage.season_context import build_season_stage_context
from utils.season_stage.season_profile import build_season_profile_context
from utils.cache import cache

_PROFILE_CTX_CACHE_TTL = 3600  # 1 hour — matches figure cache TTL
logger = logging.getLogger(__name__)


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
        try:
            cache.set(
                f"season-profile-ctx:v1:{player_name}:{season}",
                profile_context,
                timeout=_PROFILE_CTX_CACHE_TTL,
            )
        except Exception as exc:
            logger.debug("Season stage profile cache skipped: %s", exc)

    intelligence_payload = dict(payload.get("season_intelligence") or {})

    overlay_surface = dict((intelligence_payload or {}).get("overlay_surface") or {})
    dismissed_overlay_keys = {
        str(key).strip()
        for key in list(payload.get("_dismissed_overlay_keys") or [])
        if str(key).strip()
    }
    visible_overlay_candidate = dict(overlay_surface.get("primary_candidate") or {})
    if dismissed_overlay_keys:
        visible_candidates = [
            dict(candidate)
            for candidate in list(overlay_surface.get("candidates") or [])
            if str(candidate.get("signal_id") or "") not in dismissed_overlay_keys
            and str(candidate.get("evidence_key") or "") not in dismissed_overlay_keys
            and str(candidate.get("title") or "") not in dismissed_overlay_keys
        ]
        visible_overlay_candidate = dict(choose_primary_overlay_candidate(visible_candidates) or {})

    debug_meta = dict((intelligence_payload or {}).get("debug") or {})
    debug_meta["mode"] = str((intelligence_payload or {}).get("mode") or "fallback")
    debug_node = render_season_intelligence_debug(debug_meta)
    context["season_intelligence"] = intelligence_payload or {}
    log_message = (
        "Season stage render mode=%s non_blocking=%s refresh_requested=%s "
        "served_from=%s"
    )
    log_args = [
        (intelligence_payload or {}).get("mode") or "fallback",
        (intelligence_payload or {}).get("non_blocking", True),
        bool((intelligence_payload or {}).get("background_refresh_required")),
        debug_meta.get("served_from") or {},
    ]
    fallback_reason = debug_meta.get("fallback_reason") or ""
    if fallback_reason:
        log_message += " fallback_reason=%s"
        log_args.append(fallback_reason)
    runtime_meta = debug_meta.get("runtime") or {}
    if runtime_meta:
        log_message += " persistence_enabled=%s derived_writes_enabled=%s"
        log_args.extend(
            [
                bool(runtime_meta.get("persistence_enabled")),
                bool(runtime_meta.get("derived_writes_enabled")),
            ]
        )
    logger.info(log_message, *log_args)

    return html.Div(
        [
            debug_node,
            None,
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
