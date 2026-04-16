# ABOUTME: Callbacks for the Player Portal Phase 3 interactive timeline with client-side expand/collapse and scroll-sync.
# ABOUTME: Handles Timeline population, stage rendering, and non-disruptive card viewing via card-viewer-modal for finalized assets.

import logging
import json
import re
import time
from difflib import SequenceMatcher
from typing import Any
from pathlib import Path
from dash import Input, Output, State, callback, html, no_update, ALL, ctx, dcc, ClientsideFunction
import dash_bootstrap_components as dbc
from flask_login import current_user

from data.aggregators.timeline_aggregator import TimelineAggregator
from data.aggregators.hong_kong_aggregator import get_h2h_record
from data.managers.transfermarkt_runtime_manager import TransfermarktRuntimeManager
from utils.ai_services.evidence_router import normalize_evidence_key, resolve_career_surface_evidence_key
from utils.intelligence.runtime_config import get_intelligence_runtime_config
from utils.intelligence.discovery_overlay_mapper import build_overlay_candidates_from_analysis
from utils.intelligence.overlay_surface import (
    PRESENTATION_CONTEXTUAL,
    PRESENTATION_CRITICAL,
    PRESENTATION_MICRO,
    PRESENTATION_PROMINENT,
    build_overlay_inbox_entry,
    resolve_stage_overlay_surface,
)
from utils.stage_helpers import (
    _build_postmatch_overlay_surface,
    _build_prematch_overlay_surface,
    render_post_match,
    render_pre_match,
    render_career_insights,
    render_career_overview,
    render_player_dashboard,
    render_career_evidence_view,
    _build_career_kpi_trend_view,
    get_cached_image_path,
    render_image_gallery,
    _get_position_group,
    _resolve_team_logo,
    _resolve_team_jersey,
)
from utils.season_stage import render_season_stage
# Pre-warm lazy sklearn / UMAP imports so they're never first-initialized inside a
# running callback.  The season_stage __init__ wraps render_season_stage in a lazy
# function to avoid circular imports at package load time; importing the concrete
# renderer here forces sklearn.cluster._kmeans and umap to initialize before any
# callback thread is spawned, preventing _ModuleLock deadlocks on concurrent calls.
from utils.season_stage.season_stage_renderer import render_season_stage as _  # noqa: F811
from utils.season_stage.season_figures import build_season_umap_evidence_figure
from utils.performance_helpers import get_streaming_label
from utils.app_context import get_hong_kong_data_manager
from data.competition_registry import (
    get_competition_display_name,
    get_competition_logo,
    normalize_competition,
)
from data.team_branding_registry import get_team_colors as get_registered_team_colors
from utils.runtime_storage import resolve_player_cards_path

import html as _html_lib

logger = logging.getLogger(__name__)

_CAREER_HISTORY_RESET_VERSION = "career_history_reset_v2"
_PLAYER_INSIGHT_RESET_VERSION = "player_insight_reset_v1"
_PLAYER_IDS_REQUIRING_INSIGHT_RESET = {"211580"}

_MATCH_POSITION_MAP = {
    "CEN": "CB",
    "ED": "RW",
    "EI": "LW",
    "ID": "RM",
    "II": "LM",
    "MCO": "AMF",
    "CMF": "CM",
    "DMF": "DM",
}


def _career_visible_overlay_queue(resolved_surface: dict | None) -> list[dict]:
    """Return the visible non-critical career queue ordered primary-first."""
    surface = resolved_surface or {}
    primary_candidate = dict(surface.get("primary_candidate") or {})
    deferred_candidates = [
        dict(candidate)
        for candidate in list(surface.get("deferred_candidates") or [])
    ]
    visible_tiers = {PRESENTATION_PROMINENT, PRESENTATION_CONTEXTUAL, PRESENTATION_MICRO}

    queue: list[dict] = []
    if str(primary_candidate.get("presentation_tier") or "") in visible_tiers:
        queue.append(primary_candidate)

    for candidate in deferred_candidates:
        if str(candidate.get("presentation_tier") or "") in visible_tiers:
            queue.append(candidate)

    return queue


def _is_career_dashboard_overlay_context(timeline_context: dict | None) -> bool:
    context_type = str((timeline_context or {}).get("type") or "")
    return not timeline_context or context_type in ("ai-insight", "career-overview")


def _active_overlay_stage_name(timeline_context: dict | None) -> str:
    if _is_career_dashboard_overlay_context(timeline_context):
        return "career"

    context_type = str((timeline_context or {}).get("type") or "").strip().lower()
    if context_type == "career":
        return "season"
    if context_type == "pre-match":
        return "prematch"
    if context_type == "post-match":
        return "postmatch"
    return ""


def _dismissed_overlay_keys(session_state: dict | None, *, stage: str, player_id: str = "") -> set[str]:
    """Collect dismissed overlay identifiers from persisted inbox history."""
    dismissed: set[str] = set()
    for entry in list((session_state or {}).get("history") or []):
        if str(entry.get("stage") or "").strip().lower() != stage:
            continue
        cta_context = dict(entry.get("cta_context") or {})
        entry_player_id = str(cta_context.get("player_id") or entry.get("player_id") or "").strip()
        if player_id and entry_player_id and entry_player_id != str(player_id).strip():
            continue
        signal_id = str(cta_context.get("signal_id") or "").strip()
        novelty_key = str(cta_context.get("novelty_key") or "").strip()
        evidence_key = str(cta_context.get("evidence_key") or "").strip()
        title = str(entry.get("title") or "").strip()
        if signal_id:
            dismissed.add(signal_id)
        if novelty_key:
            dismissed.add(novelty_key)
        if evidence_key:
            dismissed.add(evidence_key)
        if title:
            dismissed.add(title)
    return dismissed


def _build_active_stage_inbox_entries(context: dict | None) -> list[dict]:
    """Keep inbox sourced from persisted history only; active stage queues live outside the inbox."""
    return []


def _dedupe_inbox_entries(entries: list[dict]) -> list[dict]:
    """Keep inbox ordering stable while deduplicating equivalent entries."""
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[dict] = []
    for entry in entries:
        signature = (
            str(entry.get("stage") or ""),
            str(entry.get("tier") or ""),
            str(entry.get("title") or ""),
            str(entry.get("body") or ""),
        )
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(entry)
    return deduped


def _upsert_stage_history_entry(
    history: list[dict],
    entry: dict,
    *,
    stage: str,
    player_id: str = "",
) -> list[dict]:
    """Upsert a stage history entry using stable identity keys for the active player."""
    stage_name = str(stage or "").strip().lower()
    active_player_id = str(player_id or "").strip()
    entry_cta = dict(entry.get("cta_context") or {})
    entry_signal_id = str(entry_cta.get("signal_id") or "").strip()
    entry_novelty_key = str(entry_cta.get("novelty_key") or "").strip()
    entry_title = str(entry.get("title") or "").strip()

    updated_history = list(history or [])
    duplicate_index = next(
        (
            idx
            for idx, existing in enumerate(updated_history)
            if str(existing.get("stage") or "").strip().lower() == stage_name
            and str((existing.get("cta_context") or {}).get("player_id") or existing.get("player_id") or "").strip() == active_player_id
            and (
                (
                    entry_novelty_key
                    and str((existing.get("cta_context") or {}).get("novelty_key") or "").strip() == entry_novelty_key
                )
                or (
                    entry_signal_id
                    and str((existing.get("cta_context") or {}).get("signal_id") or "").strip() == entry_signal_id
                )
                or (
                    entry_title
                    and str(existing.get("title") or "").strip() == entry_title
                )
            )
        ),
        None,
    )
    if duplicate_index is None:
        updated_history.append(entry)
    else:
        updated_history[duplicate_index] = entry
    return updated_history


def _compact_stage_history_entries(
    history: list[dict],
    *,
    stage: str,
    player_id: str = "",
) -> list[dict]:
    """Compact stored history so stale variants of the same insight do not accumulate."""
    stage_name = str(stage or "").strip().lower()
    active_player_id = str(player_id or "").strip()
    untouched: list[dict] = []
    compacted: dict[tuple[str, str, str, str], dict] = {}

    for entry in list(history or []):
        entry_stage = str(entry.get("stage") or "").strip().lower()
        entry_player_id = str((entry.get("cta_context") or {}).get("player_id") or entry.get("player_id") or "").strip()
        if entry_stage != stage_name or (active_player_id and entry_player_id != active_player_id):
            untouched.append(entry)
            continue

        cta_context = dict(entry.get("cta_context") or {})
        novelty_key = str(cta_context.get("novelty_key") or "").strip()
        signal_id = str(cta_context.get("signal_id") or "").strip()
        title = str(entry.get("title") or "").strip()
        dedupe_key = (
            entry_stage,
            entry_player_id,
            novelty_key or signal_id,
            title if not (novelty_key or signal_id) else "",
        )
        current = compacted.get(dedupe_key)
        if current is None or str(entry.get("timestamp") or "") >= str(current.get("timestamp") or ""):
            compacted[dedupe_key] = entry

    compacted_entries = sorted(compacted.values(), key=lambda item: str(item.get("timestamp") or ""))
    if stage_name == "career" and active_player_id:
        similarity_compacted: list[dict] = []
        for entry in compacted_entries:
            entry_text = (
                f"{str(entry.get('title') or '').strip().lower()} "
                f"{str(entry.get('body') or '').strip().lower()}"
            ).strip()
            merge_index = next(
                (
                    idx
                    for idx, existing in enumerate(similarity_compacted)
                    if SequenceMatcher(
                        None,
                        entry_text,
                        (
                            f"{str(existing.get('title') or '').strip().lower()} "
                            f"{str(existing.get('body') or '').strip().lower()}"
                        ).strip(),
                    ).ratio() >= 0.72
                ),
                None,
            )
            if merge_index is None:
                similarity_compacted.append(entry)
            elif str(entry.get("timestamp") or "") >= str(similarity_compacted[merge_index].get("timestamp") or ""):
                similarity_compacted[merge_index] = entry
        compacted_entries = similarity_compacted

    return untouched + compacted_entries


def _reset_career_history_for_player_if_needed(
    session_state: dict | None,
    *,
    player_id: str,
) -> dict:
    """One-time reset of stale career history for a player in local browser state."""
    active_player_id = str(player_id or "").strip()
    if not active_player_id:
        return dict(session_state or {})

    normalized_state = dict(session_state or {})
    reset_versions = dict(normalized_state.get("career_history_reset_versions") or {})
    if reset_versions.get(active_player_id) == _CAREER_HISTORY_RESET_VERSION:
        return normalized_state

    history = list(normalized_state.get("history") or [])
    filtered_history = [
        entry
        for entry in history
        if not (
            str(entry.get("stage") or "").strip().lower() == "career"
            and str((entry.get("cta_context") or {}).get("player_id") or entry.get("player_id") or "").strip() == active_player_id
        )
    ]
    normalized_state["history"] = filtered_history
    normalized_state["t1_dismissed_this_session"] = False
    reset_versions[active_player_id] = _CAREER_HISTORY_RESET_VERSION
    normalized_state["career_history_reset_versions"] = reset_versions
    return normalized_state


def _filter_history_entries_for_active_player(entries: list[dict], timeline_context: dict | None) -> list[dict]:
    """Keep player-scoped history isolated to the active player."""
    active_player_id = str(
        ((timeline_context or {}).get("payload") or {}).get("player_id")
        or getattr(current_user, "player_id", "")
        or ""
    ).strip()
    if not active_player_id:
        return list(entries or [])

    player_scoped_stages = {"career", "season", "prematch", "postmatch", "pre-match", "post-match"}
    filtered: list[dict] = []
    for entry in list(entries or []):
        stage_name = str(entry.get("stage") or "").strip().lower()
        if stage_name not in player_scoped_stages:
            filtered.append(entry)
            continue
        cta_context = dict(entry.get("cta_context") or {})
        entry_player_id = str(cta_context.get("player_id") or entry.get("player_id") or "").strip()
        if not entry_player_id:
            continue
        if entry_player_id == active_player_id:
            filtered.append(entry)
    return filtered


def _reset_player_insight_history_if_needed(
    session_state: dict | None,
    *,
    player_id: str,
) -> dict:
    """One-time reset of locally stored insight history for selected players."""
    active_player_id = str(player_id or "").strip()
    if not active_player_id:
        return dict(session_state or {})
    if active_player_id not in _PLAYER_IDS_REQUIRING_INSIGHT_RESET:
        return dict(session_state or {})

    normalized_state = dict(session_state or {})
    reset_versions = dict(normalized_state.get("player_insight_reset_versions") or {})
    if reset_versions.get(active_player_id) == _PLAYER_INSIGHT_RESET_VERSION:
        return normalized_state

    history = list(normalized_state.get("history") or [])
    player_scoped_stages = {"career", "season", "prematch", "postmatch", "pre-match", "post-match"}
    normalized_state["history"] = [
        entry
        for entry in history
        if not (
            str(entry.get("stage") or "").strip().lower() in player_scoped_stages
            and str((entry.get("cta_context") or {}).get("player_id") or entry.get("player_id") or "").strip() == active_player_id
        )
    ]
    normalized_state["t1_dismissed_this_session"] = False
    reset_versions[active_player_id] = _PLAYER_INSIGHT_RESET_VERSION
    normalized_state["player_insight_reset_versions"] = reset_versions
    return normalized_state


def collect_insight_inbox_entries(session_state: dict | None, timeline_context: dict | None) -> list[dict]:
    """Combine persisted history with active-stage overlay entries for the shared inbox."""
    history = _filter_history_entries_for_active_player(
        list((session_state or {}).get("history", [])),
        timeline_context,
    )
    active_stage_entries = _build_active_stage_inbox_entries(timeline_context)
    return _dedupe_inbox_entries(history + active_stage_entries)


def render_insight_inbox_entries(entries: list[dict]) -> list[Any]:
    """Render stage-aware shared inbox entries into Offcanvas children."""
    from datetime import datetime as _dt, timezone as _tz

    if not entries:
        return [html.P("Sin insights guardados aún.", className="text-muted small p-2")]

    items = []
    for entry in reversed(entries):
        tier = entry.get("tier", PRESENTATION_CONTEXTUAL)
        stage_name = str(entry.get("stage") or "career")
        title = entry.get("title", "—")
        body = entry.get("body", "")
        cta_context = entry.get("cta_context") or {}
        focus_metric = str(cta_context.get("focus_metric", "") or "")
        timestamp_raw = entry.get("timestamp", "")
        tier_class = {
            PRESENTATION_CRITICAL: "insight-inbox-item--critical",
            PRESENTATION_PROMINENT: "insight-inbox-item--prominent",
            PRESENTATION_CONTEXTUAL: "insight-inbox-item--contextual",
        }.get(tier, "insight-inbox-item--micro")
        tier_label = str(tier or PRESENTATION_CONTEXTUAL).upper()
        stage_label = stage_name.upper()

        body_short = (body[:117] + "…") if len(body) > 120 else body

        ts_display = ""
        if timestamp_raw:
            try:
                ts = _dt.fromisoformat(timestamp_raw)
                now = _dt.now(_tz.utc).replace(tzinfo=None)
                diff = now - ts
                minutes = int(diff.total_seconds() // 60)
                if minutes < 1:
                    ts_display = "Ahora"
                elif minutes < 60:
                    ts_display = f"Hace {minutes} min"
                else:
                    ts_display = f"Hace {minutes // 60} h"
            except Exception:
                ts_display = ""

        actions: list[Any] = []
        if stage_name == "career":
            evidence_key = resolve_career_surface_evidence_key(
                cta_context.get("evidence_key", "career_arc"),
                label=title,
            )
            actions.append(
                dbc.Button(
                    "See evidence",
                    id={
                        "type": "career-evidence-trigger",
                        "key": evidence_key,
                        "source": "inbox",
                        "index": f"inbox:{timestamp_raw or title}",
                        "focus_metric": focus_metric,
                    },
                    color="link",
                    className="insight-inbox-item__cta px-0 mt-2",
                    n_clicks=0,
                )
            )
        else:
            actions.append(
                html.Div(
                    f"Visible in {stage_name.replace('-', ' ')} stage",
                    className="insight-inbox-item__cta mt-2",
                )
            )

        items.append(
            html.Div(
                [
                    html.Div([
                        html.Span(tier_label, style={
                            "fontSize": "0.6rem", "fontWeight": "700",
                            "textTransform": "uppercase", "letterSpacing": "0.06em",
                            "opacity": "0.7",
                        }),
                        html.Span(" · ", style={"opacity": "0.45", "margin": "0 6px"}),
                        html.Span(stage_label, style={
                            "fontSize": "0.6rem", "fontWeight": "700",
                            "textTransform": "uppercase", "letterSpacing": "0.06em",
                            "opacity": "0.62",
                        }),
                        html.Span(ts_display, className="insight-inbox-timestamp ms-auto"),
                    ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}),
                    html.Div(title, style={"fontSize": "0.8rem", "fontWeight": "700", "marginBottom": "4px"}),
                    html.Div(body_short, style={"fontSize": "0.75rem", "opacity": "0.75", "lineHeight": "1.4"}),
                    *actions,
                ],
                className=f"insight-inbox-item {tier_class}",
            )
        )

    return items


def _get_active_player_identity():
    """Returns `(player_id, player_name, user_role)` for the logged-in portal user."""
    player_id = getattr(current_user, "player_id", None)
    user_role = getattr(current_user, "role", "player") if current_user else "player"
    player_name = ""
    if player_id:
        from utils.player_index import get_player_index

        pi = get_player_index()
        player_info = pi.get_player_info(player_id)
        player_name = player_info.get("canonical_name", "") if player_info else ""
    return player_id, player_name, user_role


def _display_match_position(position: Any) -> str:
    raw = str(position or "").strip().upper()
    return _MATCH_POSITION_MAP.get(raw, raw or "N/A")


def _render_default_stage_content(ai_payload=None, pre_fetched_data=None):
    """Renders the default dashboard stage inside the persistent shell.
    Pass pre_fetched_data to skip the DB fetch (progressive loading phases 2 and 3)."""
    try:
        from utils.domain_ai.career_dashboard_ai import normalize_career_dashboard_brief_payload

        player_id, player_name, user_role = _get_active_player_identity()
        normalized_ai_payload = normalize_career_dashboard_brief_payload(ai_payload)
        if player_id and player_name:
            if not normalized_ai_payload:
                try:
                    return render_player_dashboard(
                        player_name, player_id, user_role,
                        synthesize_with_ai=False,
                        pre_fetched_data=pre_fetched_data,
                    )
                except TypeError:
                    return render_player_dashboard(player_name, player_id, user_role)
            try:
                return render_player_dashboard(
                    player_name,
                    player_id,
                    user_role,
                    ai_payload=normalized_ai_payload,
                    synthesize_with_ai=False,
                    pre_fetched_data=pre_fetched_data,
                )
            except TypeError:
                return render_player_dashboard(player_name, player_id, user_role)
        logger.warning("default stage render skipped: missing player identity id=%s name=%s", player_id, player_name)
        return no_update
    except Exception as exc:
        logger.exception("default stage render error: %s", exc)
        return dbc.Alert(
            "Error al cargar el stage del jugador.",
            color="danger",
            className="m-3",
        )


def _render_stage_content_for_context(context):
    """Dispatches a context dict to the correct stage renderer."""
    return _render_stage_content_for_context_with_session(context, None)


def _build_prematch_render_payload(payload: dict) -> tuple[dict, str, str, str]:
    """Enrich the prematch payload with the logged-in player's role context."""
    enriched_payload = dict(payload or {})
    player_name = ""
    pos_group = ""
    position_main = ""
    current_role_hint = ""
    player_id = str(enriched_payload.get("player_id") or "")
    try:
        player_id = str(getattr(current_user, "player_id", None) or player_id or "").strip()
        if player_id:
            from utils.player_index import get_player_index
            from utils.app_context import get_hong_kong_data_manager as _get_dm
            from models.db_models import Player, MatchHistory
            from utils.db_engine import SessionFactory

            pi = get_player_index()
            player_info = pi.get_player_info(player_id)
            player_name = player_info.get("canonical_name", "") if player_info else ""
            with SessionFactory() as session:
                player_obj = session.get(Player, player_id)
                position_main = str(getattr(player_obj, "position_main", "") or "").strip()
                recent_matches = (
                    session.query(MatchHistory)
                    .filter(MatchHistory.player_id == player_id)
                    .order_by(MatchHistory.date.desc())
                    .limit(8)
                    .all()
                )
                weighted = {}
                for idx, match in enumerate(recent_matches):
                    raw_pos = str(getattr(match, "position", "") or "").strip().upper()
                    mapped = {
                        "ED": "RW", "EI": "LW", "ID": "RM", "II": "LM",
                        "MCO": "AMF", "CMF": "CM", "DMF": "DM",
                    }.get(raw_pos, raw_pos)
                    if not mapped:
                        continue
                    minutes = int(getattr(match, "minutes_played", 0) or 0)
                    weight = max(minutes, 1) + max(0, 8 - idx)
                    weighted[mapped] = weighted.get(mapped, 0) + weight
                if weighted:
                    current_role_hint = max(weighted.items(), key=lambda item: item[1])[0]
            if player_name:
                pos_group = _get_position_group(player_name, _get_dm())
    except Exception:
        pass

    fixture_id = str(
        enriched_payload.get("fixture_id")
        or enriched_payload.get("match_id")
        or ""
    ).strip()
    if not fixture_id:
        fixture_bits = [
            str(enriched_payload.get("home_team") or "").strip().lower().replace(" ", "-"),
            "vs",
            str(enriched_payload.get("away_team") or enriched_payload.get("opponent") or "").strip().lower().replace(" ", "-"),
            str(enriched_payload.get("date") or enriched_payload.get("kickoff_display") or "").strip().lower().replace(" ", "-"),
        ]
        fixture_id = "-".join([bit for bit in fixture_bits if bit]).strip("-")

    enriched_payload["player_id"] = player_id
    enriched_payload["fixture_id"] = fixture_id
    enriched_payload["player_name"] = player_name
    enriched_payload["player_pos_group"] = pos_group
    enriched_payload["player_position_main"] = position_main
    enriched_payload["player_current_role"] = current_role_hint
    return enriched_payload, pos_group, position_main, current_role_hint


def _prematch_analysis_request_key(payload: dict) -> str:
    """Build a stable key for one prematch analysis request."""
    return "|".join(
        [
            str(payload.get("player_id") or ""),
            str(payload.get("fixture_id") or ""),
            str(payload.get("opponent") or ""),
            str(payload.get("kickoff_display") or payload.get("date") or ""),
            str(payload.get("player_name") or ""),
            str(payload.get("player_current_role") or ""),
        ]
    )


def _build_postmatch_render_payload(payload: dict) -> dict:
    """Enrich postmatch payloads with canonical scope keys before orchestration."""
    enriched_payload = dict(payload or {})

    player_id = str(
        enriched_payload.get("player_id")
        or getattr(current_user, "player_id", "")
        or ""
    ).strip()
    match_id = str(
        enriched_payload.get("match_id")
        or enriched_payload.get("fixture_id")
        or ""
    ).strip()
    if not match_id:
        match_bits = [
            str(enriched_payload.get("home_team") or "").strip().lower().replace(" ", "-"),
            "vs",
            str(enriched_payload.get("away_team") or enriched_payload.get("opponent") or "").strip().lower().replace(" ", "-"),
            str(enriched_payload.get("date") or enriched_payload.get("kickoff_display") or "").strip().lower().replace(" ", "-"),
        ]
        match_id = "-".join([bit for bit in match_bits if bit]).strip("-")

    enriched_payload["player_id"] = player_id
    enriched_payload["match_id"] = match_id
    return enriched_payload


def _career_analysis_request_key(portal_data: dict) -> str:
    """Build a stable key for one career analysis request."""
    return "|".join(
        [
            str(portal_data.get("player_id") or ""),
            str(portal_data.get("player_name") or ""),
            str((portal_data.get("career_phase") or {}).get("current_season") or ""),
        ]
    )


def _season_analysis_request_key(payload: dict) -> str:
    """Build a stable key for one season analysis request."""
    return "|".join(
        [
            str(payload.get("player_id") or ""),
            str(payload.get("player_name") or ""),
            str(payload.get("season") or ""),
            str(payload.get("team") or payload.get("season_team") or ""),
        ]
    )


def _postmatch_analysis_request_key(payload: dict) -> str:
    """Build a stable key for one postmatch analysis request."""
    return "|".join(
        [
            str(payload.get("player_id") or ""),
            str(payload.get("match_id") or payload.get("fixture_id") or ""),
            str(payload.get("opponent") or ""),
            str(payload.get("kickoff_display") or payload.get("date") or ""),
            str(payload.get("result") or ""),
        ]
    )


def _resolve_active_overlay_surface(
    timeline_context: dict | None,
    portal_data: dict | None,
    career_stage_analysis: dict | None,
    season_stage_analysis: dict | None,
    prematch_stage_analysis: dict | None,
    postmatch_stage_analysis: dict | None,
) -> tuple[str, dict, str, str]:
    """Resolve the active stage overlay surface for the shared overlay runtime."""
    stage_name = _active_overlay_stage_name(timeline_context)
    if not stage_name:
        return "", {}, "", ""

    if stage_name == "career":
        active_player_id = str((portal_data or {}).get("player_id") or "").strip()
        player_name = str(
            (portal_data or {}).get("player_name")
            or ((timeline_context or {}).get("payload") or {}).get("player_name")
            or getattr(current_user, "player_name", None)
            or ""
        )
        analysis_bundle = dict(career_stage_analysis or {})
        analysis_payload = dict(analysis_bundle.get("analysis") or {})
        raw_candidates = list(
            (analysis_bundle.get("overlay_candidates") or {}).get("candidates")
            or (build_overlay_candidates_from_analysis(analysis_payload) or {}).get("candidates")
            or []
        )
        return (
            stage_name,
            resolve_stage_overlay_surface(stage_name, {"candidates": raw_candidates}),
            active_player_id,
            player_name,
        )

    context_payload = dict((timeline_context or {}).get("payload") or {})
    active_player_id = str(
        context_payload.get("player_id")
        or (portal_data or {}).get("player_id")
        or getattr(current_user, "player_id", "")
        or ""
    ).strip()
    player_name = str(
        context_payload.get("player_name")
        or (portal_data or {}).get("player_name")
        or getattr(current_user, "player_name", None)
        or ""
    )

    try:
        if stage_name == "season":
            request_key = _season_analysis_request_key(context_payload)
            cached = dict(season_stage_analysis or {})
            intelligence = (
                dict(cached.get("intelligence") or {})
                if str(cached.get("request_key") or "") == request_key
                else {}
            )
            return stage_name, dict((intelligence or {}).get("overlay_surface") or {}), active_player_id, player_name

        if stage_name == "prematch":
            from utils.agents.prematch_intelligence_orchestrator import orchestrate_prematch_intelligence

            payload, _, _, _ = _build_prematch_render_payload(context_payload)
            request_key = _prematch_analysis_request_key(payload)
            cached = dict(prematch_stage_analysis or {})
            intelligence = (
                dict(cached.get("intelligence") or {})
                if str(cached.get("request_key") or "") == request_key
                else orchestrate_prematch_intelligence(payload)
            )
            return stage_name, dict((intelligence or {}).get("overlay_surface") or {}), active_player_id, player_name

        if stage_name == "postmatch":
            from utils.agents.postmatch_intelligence_orchestrator import orchestrate_postmatch_intelligence

            payload = _build_postmatch_render_payload(context_payload)
            request_key = _postmatch_analysis_request_key(payload)
            cached = dict(postmatch_stage_analysis or {})
            intelligence = (
                dict(cached.get("intelligence") or {})
                if str(cached.get("request_key") or "") == request_key
                else orchestrate_postmatch_intelligence(payload)
            )
            return stage_name, dict((intelligence or {}).get("overlay_surface") or {}), active_player_id, player_name
    except Exception as exc:
        logger.debug("active overlay surface resolution error stage=%s error=%s", stage_name, exc)

    return stage_name, {}, active_player_id, player_name


def _render_stage_content_for_context_with_session(
    context,
    session_state,
    season_stage_analysis=None,
    prematch_stage_analysis=None,
    postmatch_stage_analysis=None,
):
    """Dispatches a context dict to the correct stage renderer with overlay-session awareness."""
    if not context:
        return _render_default_stage_content()

    user_role = getattr(current_user, "role", "player") if current_user else "player"
    m_type = context.get("type")
    payload = dict(context.get("payload", {}) or {})

    if m_type == "post-match":
        payload = _build_postmatch_render_payload(payload)
        analysis_bundle = dict(postmatch_stage_analysis or {})
        request_key = _postmatch_analysis_request_key(payload)
        if request_key == str(analysis_bundle.get("request_key") or ""):
            intelligence_bundle = dict(analysis_bundle.get("intelligence") or {})
            payload["postmatch_stage_analysis"] = dict(intelligence_bundle.get("stage_analysis") or analysis_bundle.get("analysis") or {})
            payload["postmatch_intelligence"] = intelligence_bundle
        payload["_postmatch_ai_pending"] = bool(not payload.get("postmatch_stage_analysis"))
        try:
            return render_post_match(payload, milestone_id=context.get("id", ""))
        except TypeError:
            return render_post_match(payload)

    if m_type == "pre-match":
        payload, pos_group, position_main, current_role_hint = _build_prematch_render_payload(payload)
        analysis_bundle = dict(prematch_stage_analysis or {})
        request_key = _prematch_analysis_request_key(payload)
        llm_enabled = bool(get_intelligence_runtime_config().get("prematch_agent_llm_enabled", False))
        if request_key == str(analysis_bundle.get("request_key") or ""):
            intelligence_bundle = dict(analysis_bundle.get("intelligence") or {})
            payload["prematch_stage_analysis"] = dict(intelligence_bundle.get("stage_analysis") or analysis_bundle.get("analysis") or {})
            payload["prematch_intelligence"] = intelligence_bundle
        payload["_prematch_ai_pending"] = bool(llm_enabled and not payload.get("prematch_stage_analysis"))
        return render_pre_match(
            payload,
            player_pos_group=pos_group,
            player_position_main=position_main,
            player_current_role=current_role_hint,
        )

    if m_type == "career":
        payload["_dismissed_overlay_keys"] = sorted(_dismissed_overlay_keys(session_state, stage="season"))
        analysis_bundle = dict(season_stage_analysis or {})
        request_key = _season_analysis_request_key(payload)
        if request_key == str(analysis_bundle.get("request_key") or ""):
            payload["season_intelligence"] = dict(analysis_bundle.get("intelligence") or {})
        return render_season_stage(payload)

    return dbc.Alert(f"Tipo de contexto desconocido: {m_type}", color="warning")


def _get_career_parent_context(milestones_data, milestone) -> dict | None:
    """Returns the season-level career context for a non-career milestone."""
    if not milestone:
        return None
    milestone_year = milestone.get("group_year") or str(milestone.get("date", ""))[:4]
    fallback_career = next(
        (
            item for item in (milestones_data or [])
            if item.get("type") == "career"
            and (item.get("group_year") or str(item.get("date", ""))[:4]) == milestone_year
        ),
        None,
    )
    if not fallback_career:
        return None
    return {
        "id": fallback_career.get("id"),
        "type": "career",
        "payload": fallback_career["payload"],
    }


def _get_expand_ids_for_context(context) -> list[str]:
    """Returns the timeline card ids that should remain expanded for a context."""
    if not context:
        return []

    context_id = context.get("id")
    context_type = context.get("type")
    parent = context.get("parent") or {}
    parent_id = parent.get("id")

    if context_type == "career":
        return [context_id] if context_id else []

    expand_ids = []
    if parent_id:
        expand_ids.append(parent_id)
    if context_id:
        expand_ids.append(context_id)
    return expand_ids


def _get_default_expand_ids(milestones_data) -> list[str]:
    """Returns the default expanded ids when the timeline first loads."""
    if not milestones_data:
        return []

    # Timeline should enter in a fully collapsed state.
    return []


def _render_season_team_assets(team_name: str):
    """Top-right team assets for career cards: crest + home kit + away kit."""
    if not team_name:
        return None

    crest = _resolve_team_logo(team_name)
    home_jersey = _resolve_team_jersey(team_name, "home")
    away_jersey = _resolve_team_jersey(team_name, "away")

    items = []
    if crest:
        items.append(
            html.Img(
                src=crest,
                title=team_name,
                id={"type": "season-team-asset", "src": crest, "label": team_name},
                style={"width": "34px", "height": "34px", "objectFit": "contain", "display": "block", "cursor": "zoom-in"},
            )
        )
    if home_jersey:
        items.append(
            html.Img(
                src=home_jersey,
                title=f"{team_name} home kit",
                id={"type": "season-team-asset", "src": home_jersey, "label": f"{team_name} home kit"},
                style={"width": "40px", "height": "40px", "objectFit": "contain", "display": "block", "marginLeft": "2px", "marginTop": "-2px", "cursor": "zoom-in"},
            )
        )
    if away_jersey:
        items.append(
            html.Img(
                src=away_jersey,
                title=f"{team_name} away kit",
                id={"type": "season-team-asset", "src": away_jersey, "label": f"{team_name} away kit"},
                style={"width": "40px", "height": "40px", "objectFit": "contain", "display": "block", "marginLeft": "-4px", "marginTop": "-2px", "cursor": "zoom-in"},
            )
        )

    if not items:
        return None

    return html.Div(
        items,
        className="season-team-assets",
        style={
            "display": "flex",
            "alignItems": "flex-start",
            "justifyContent": "flex-end",
            "gap": "0px",
            "marginTop": "0px",
            "width": "100%",
        },
    )


def _get_player_current_team_name(player_id: str) -> str:
    """DB fallback for career header assets when serialized payload lacks season_team."""
    if not player_id:
        return ""
    try:
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        from utils.db_engine import SessionFactory
        from models.db_models import Player

        session = SessionFactory()
        try:
            stmt = (
                select(Player)
                .options(joinedload(Player.current_team))
                .where(Player.id == player_id)
            )
            player = session.execute(stmt).unique().scalar_one_or_none()
            if player and player.current_team:
                return player.current_team.name or ""
            return ""
        finally:
            session.close()
    except Exception:
        return ""

def _get_team_colors(team_name: str) -> dict:
    """Returns team color dict {badge, kit_home, kit_away, colour1, colour2} for a given team name."""
    return get_registered_team_colors(team_name)


# Hex color palettes per competition — sourced from official branding
_COMPETITION_COLOR_MAP = {
    "HK Premier League": ["#ac0c34", "#1c1c1c", "#b40c34"],
    "Sapling Cup": ["#153465", "#c1cf31", "#78ac46"],
    "Senior Shield": ["#050505", "#b8b8b8", "#444444"],
    "HKFA Cup": ["#bb9d5e", "#bcbcbc", "#bcbcc4"],
    "AFC Cup": ["#c6bcb6", "#318cd6", "#191c1a", "#61af69", "#eb8b3e"],
    "AFC Champions League Two": ["#111112", "#cec9c1", "#218ec2", "#f7a240", "#959b9e"],
    "AFC Champions League": ["#111112", "#cec9c1", "#218ec2", "#f7a240", "#959b9e"],
}


def _normalize_comp(raw: str) -> str:
    """Normalize a competition name using central helper."""
    return normalize_competition(raw)


def _competition_logo_url(competition: str):
    """Return local web path for competition logo, or None if not mapped."""
    return get_competition_logo(competition)


def _competition_color(competition: str) -> str:
    """Return primary hex color for a competition name."""
    palette = _COMPETITION_COLOR_MAP.get(_normalize_comp(competition), ["#0d6efd"])
    return palette[0]


def _comp_badge(competition: str) -> "html.Span | None":
    """Return a styled Span badge with the competition name."""
    comp = _normalize_comp(competition)
    comp_label = get_competition_display_name(competition, long_form=False)
    if not comp:
        return None
    bg_color = _competition_color(comp)
    # Determine text color based on background brightness (simplified)
    # For now, white text for dark/vibrant backgrounds, black for very light ones
    text_color = "#ffffff"
    light_bgs = [
        "#cec9c1", "#bcbcbc", "#d1dee6", "#ededec", "#e1e3e5", 
        "#c6bcb6", "#bb9d5e", "#d0d0d5", "#f7e4e7"
    ]
    if bg_color.lower() in [c.lower() for c in light_bgs]:
        text_color = "#18181a"

    return html.Span(
        comp_label,
        className="small px-2 py-0 rounded-1 fw-semibold",
        style={
            "backgroundColor": bg_color,
            "color": text_color,
            "fontSize": "0.7rem",
            "display": "inline-block",
            "lineHeight": "1.4",
        }
    )


def _competition_logo_img(competition: str, logo_url: str = None):
    """Return a small competition logo img element, or text abbreviation if no asset available."""
    comp = _normalize_comp(competition)
    comp_label = get_competition_display_name(competition, long_form=False)
    # Prefer explicit logo_url if provided (e.g. from DB/TM), fallback to local mapping
    logo = logo_url if logo_url else get_competition_logo(competition)

    if not logo:
        if comp_label:
            return html.Span(
                comp_label[:4].upper(),
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
                title=comp_label,
            )
        return None

    return html.Img(
        src=logo,
        id="image-overlay",
        className="competition-logo-img",
        style={"width": "40px", "height": "40px", "objectFit": "contain"},
        title=comp_label,
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


def _get_timeline_priority(milestone: dict) -> tuple[int, Any]:
    """Sorts timeline milestones within a season so future next-game cards stay above live/pending items."""
    from datetime import datetime

    payload = milestone.get("payload", {}) or {}
    m_type = milestone.get("type", "career")
    status = str(payload.get("confirmation_status") or milestone.get("confirmation_status") or "")
    date_value = milestone.get("date")
    parsed_date = None
    if isinstance(date_value, str):
        try:
            parsed_date = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
        except ValueError:
            parsed_date = None
    elif hasattr(date_value, "timestamp"):
        parsed_date = date_value

    timestamp = parsed_date.timestamp() if parsed_date is not None else 0.0

    if m_type == "pre-match" and status == "Scheduled":
        return (0, timestamp)
    if m_type == "pre-match" and status == "LIVE":
        return (1, timestamp)
    if m_type == "pre-match" and status == "Pending Update":
        return (2, -timestamp)
    if m_type == "post-match":
        return (3, -timestamp)
    return (4, -timestamp)


def _log_timeline_snapshot(player_id: str, milestones: list[dict], source: str) -> None:
    """Logs a compact snapshot of timeline ordering and statuses for portal debugging."""
    try:
        summary = []
        for milestone in milestones or []:
            payload = milestone.get("payload", {}) or {}
            summary.append(
                {
                    "id": milestone.get("id"),
                    "type": milestone.get("type"),
                    "group_year": milestone.get("group_year"),
                    "status": payload.get("confirmation_status") or milestone.get("confirmation_status"),
                    "label": milestone.get("label"),
                    "date": str(milestone.get("date") or ""),
                }
            )
        logger.debug("[TIMELINE_%s] player_id=%s milestones=%s", source, player_id or "unknown", summary)
    except Exception as exc:
        logger.debug("timeline snapshot log error: %s", exc)


def _get_glass_class(milestone: dict) -> str:
    """Returns the glass context modifier class for a milestone."""
    m_type = milestone.get("type", "career")
    status = milestone.get("confirmation_status") or milestone.get(
        "payload", {}
    ).get("confirmation_status", "")
    
    if status == "LIVE":
        return "glass-live"
    if status == "Pending Update":
        return "glass-success"
        
    if m_type == "post-match":
        return "glass-success" if status == "Confirmed" else "glass-prematch"
    return _GLASS_CLASS_MAP.get(m_type, "glass-career")


def _lucide(name: str) -> html.I:
    """Returns a Lucide icon element."""
    return html.I(**{"data-lucide": name, "className": "lucide-inline-icon me-1"})


def _bi(icon_name: str, class_name: str = "me-1", style: dict | None = None) -> html.I:
    """Returns a Bootstrap icon element for first-paint stable UI icons."""
    return html.I(className=f"bi bi-{icon_name} {class_name}".strip(), style=style or {})


def _format_match_result(result: Any, penalties: Any = None) -> str:
    """Formats a result and appends '(p)' or '(ET)' for knockout outcomes."""
    raw_result = str(result or "").strip()
    if not raw_result:
        return "- : -"

    penalties_resolved = bool(penalties)
    extra_time_resolved = False
    lowered_result = raw_result.lower()

    if "pen" in lowered_result:
        penalties_resolved = True
        raw_result = re.sub(
            r"\s*(?:on\s*pens?\.?|pens?\.?)\s*$",
            "",
            raw_result,
            flags=re.IGNORECASE,
        ).strip()
    elif "aet" in lowered_result or re.search(r"\bet\b", lowered_result) or "extra time" in lowered_result:
        extra_time_resolved = True
        raw_result = re.sub(
            r"\s*(?:a\.?e\.?t\.?|after\s+extra\s+time|extra\s+time|\bet\b)\s*$",
            "",
            raw_result,
            flags=re.IGNORECASE,
        ).strip()

    if penalties_resolved:
        return f"{raw_result} (p)"
    if extra_time_resolved:
        return f"{raw_result} (ET)"
    return raw_result


def _normalize_timeline_team_name(team_name: Any) -> str:
    """Normalizes team labels for timeline cards only."""
    normalized = str(team_name or "").strip()
    if not normalized:
        return "?"

    lowered = normalized.lower()
    if lowered in {"resources capital", "resources capital fc", "rcfc"}:
        return "RCFC"

    normalized = re.sub(r"\(\d+\.\)", "", normalized).strip()
    normalized = re.sub(r"\bDistrict\b", "Dt.", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bDist\.?\b", "Dt.", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"Dt\.\.+", "Dt.", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = re.sub(r"\s+\.", ".", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _card_icon(color: str, size: str = "14px", class_name: str = "me-1") -> html.I:
    """Returns a vertical rectangle icon for disciplinary cards."""
    return html.I(
        **{"data-lucide": "rectangle-vertical"},
        className=class_name,
        style={"width": size, "height": size, "color": color, "opacity": "0.95", "lineHeight": "1"},
    )


def _team_pill(name: str, logo_url, reverse: bool = False) -> html.Div:
    """Small team block: outer name + inner crest (or mirrored when reverse=True)."""
    display_name = _normalize_timeline_team_name(name)
    resolved_logo = None
    
    # 1. Intentar resolver localmente por nombre
    if name:
        # Normalización: minúsculas, guiones/espacios a _, quitar puntos
        normalized = name.lower().replace(" ", "_").replace("-", "_").replace(".", "")
        # Caso especial para North District
        if "north" in normalized:
            normalized = "north_dt"
            
        local_file = f"{normalized}.png"
        # Ruta física para comprobación (ajustada relativa a este archivo)
        from pathlib import Path
        root_dir = Path(__file__).parent.parent
        assets_path = root_dir / "assets" / "team_logos" / local_file
        if assets_path.exists():
            resolved_logo = f"/assets/team_logos/{local_file}"

    # 2. Si no hay local, usar la URL proporcionada
    if not resolved_logo and logo_url:
        resolved_logo = logo_url

    if resolved_logo:
        badge = html.Img(
            src=resolved_logo,
            style={
                "width": "28px",
                "height": "28px",
                "objectFit": "contain",
                "borderRadius": "50%",
                "flexShrink": "0",
            },
            alt=name or "Team crest",
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
        display_name,
        className="small text-truncate me-2" if reverse else "small text-truncate ms-2",
        style={"maxWidth": "84px"},
    )
    children = [badge, label] if reverse else [label, badge]
    justify = "justify-content-end" if reverse else "justify-content-start"
    return html.Div(children, className=f"d-flex align-items-center {justify}", style={"minWidth": "0", "gap": "6px"})


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
        yellow = stats.get("yellow_cards", sum(int(m.get("yellow_cards", 0) or 0) for m in matches))
        red = stats.get("red_cards", sum(int(m.get("red_cards", 0) or 0) for m in matches))

        return [
            dbc.Badge(
                f"Season {season}",
                color="warning",
                className="small fw-semibold text-dark mb-1",
            ),
            html.Div(
                [
                    html.Div([
                        html.Span(
                            html.I(className="bi bi-calendar-check", style={"fontSize": "20px", "lineHeight": "1"}),
                            className="me-1 d-inline-flex align-items-center justify-content-center",
                            style={"width": "20px", "height": "20px", "flexShrink": "0"},
                        ),
                        html.Span(str(pj)),
                    ], className="portal-text-muted d-flex align-items-center justify-content-start", style={"whiteSpace": "nowrap"}),
                    html.Div([
                        html.Span(
                            html.I(className="bi bi-stopwatch", style={"fontSize": "20px", "lineHeight": "1"}),
                            className="me-1 d-inline-flex align-items-center justify-content-center",
                            style={"width": "20px", "height": "20px", "flexShrink": "0"},
                        ),
                        html.Span(str(minutes)),
                    ], className="portal-text-muted d-flex align-items-center justify-content-start", style={"whiteSpace": "nowrap"}),
                    html.Div([
                        html.Span(
                            html.Img(src="/assets/icons/soccer-ball.svg", style={"width": "20px", "height": "20px", "opacity": "0.85", "display": "block"}),
                            className="me-1 d-inline-flex align-items-center justify-content-center",
                            style={"width": "20px", "height": "20px", "flexShrink": "0"},
                        ),
                        html.Span(str(goals)),
                    ], className="portal-text-muted d-flex align-items-center justify-content-start", style={"whiteSpace": "nowrap"}),
                    html.Div([
                        html.Span(
                            html.I(**{"data-lucide": "sport-shoe"}, style={"width": "20px", "height": "20px", "opacity": "0.9", "lineHeight": "1"}),
                            className="me-1 d-inline-flex align-items-center justify-content-center",
                            style={"width": "20px", "height": "20px", "flexShrink": "0"},
                        ),
                        html.Span(str(assists)),
                    ], className="portal-text-muted d-flex align-items-center justify-content-start", style={"whiteSpace": "nowrap"}),
                    html.Div([
                        html.Span(
                            _card_icon("#f4c351", size="20px"),
                            className="me-1 d-inline-flex align-items-center justify-content-center",
                            style={"width": "20px", "height": "20px", "flexShrink": "0"},
                        ),
                        html.Span(str(yellow)),
                    ], className="portal-text-muted d-flex align-items-center justify-content-start", style={"whiteSpace": "nowrap"}),
                    html.Div([
                        html.Span(
                            _card_icon("#ef6b6b", size="20px"),
                            className="me-1 d-inline-flex align-items-center justify-content-center",
                            style={"width": "20px", "height": "20px", "flexShrink": "0"},
                        ),
                        html.Span(str(red)),
                    ], className="portal-text-muted d-flex align-items-center justify-content-start", style={"whiteSpace": "nowrap"}),
                ],
                className="season-stats-grid",
                style={
                    "justifyContent": "start",
                    "marginLeft": "16px",
                    "marginTop": "12px",
                    "width": "100%",
                }
            ),
        ]

    if m_type == "pre-match":
        competition = _normalize_comp(payload.get("competition", ""))
        kickoff = payload.get("kickoff_display", date_str)
        home = payload.get("home_team", "Home")
        away = payload.get("away_team", "Away")
        home_logo = payload.get("home_logo")
        away_logo = payload.get("away_logo")
        status = payload.get("confirmation_status")
        badge = _comp_badge(competition)
        
        status_pill = None
        if status == "LIVE":
            status_pill = dbc.Badge(
                "LIVE",
                className="ms-2 animate-glass-pulse live-status-badge",
            )
        elif status == "Pending Update":
            status_pill = dbc.Badge(
                "Awaiting Stats",
                className="ms-2 pending-update-badge",
            )
            
        return [
            html.Div([
                html.Div(badge, className="card-row--competition") if badge else None,
                status_pill
            ], className="d-flex align-items-center mb-1") if (badge or status_pill) else None,
            html.Div(
                [
                    _team_pill(home, home_logo),
                    html.Span("vs", className="portal-text-muted mx-2 small"),
                    _team_pill(away, away_logo, reverse=True),
                ],
                className="d-flex align-items-center justify-content-center gap-1 card-row--teams",
            ),
            html.Div(
                [_bi("clock"), html.Small(kickoff, className="ms-1")],
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
    penalties = payload.get("penalties")

    badge = _comp_badge(competition)

    # Row 2: home logo | home name | result | away name | away logo
    score_el = html.Span(
        _format_match_result(result, penalties),
        className="fw-bold small mx-1",
        style={"color": "var(--text-primary, #fff)", "whiteSpace": "nowrap"},
    )
    match_row = html.Div(
        [
            _team_pill(home, home_logo),
            score_el,
            _team_pill(away, away_logo, reverse=True),
        ],
        className="d-flex align-items-center justify-content-center gap-1 card-row--teams",
    )

    return [
        html.Div(badge, className="card-row--competition") if badge else None,
        match_row,
        html.Div(
            [_bi("clock"), html.Small(kickoff, className="ms-1")],
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
        user_team = payload.get("player_team", "") or payload.get("team_name", "") or payload.get("team", "") or ""
        team_a = home
        team_b = away
        user_team_norm = str(user_team or "").strip().lower()
        if user_team_norm:
            if user_team_norm == str(away or "").strip().lower():
                team_a, team_b = away, home
            elif user_team_norm == str(home or "").strip().lower():
                team_a, team_b = home, away
        h2h = None
        if team_a and team_b:
            try:
                h2h = get_h2h_record(team_a, team_b, last_n=None)
            except Exception:
                pass

        rows = []
        status = payload.get("confirmation_status")
        if status == "LIVE":
            rows.append(
                html.Div(
                    [
                        _bi("broadcast"),
                        html.Small("Match in progress. Performance data will be available after official confirmation.", 
                                   className="fw-bold live-status-text"),
                    ],
                    className="d-flex align-items-center gap-1 mb-2 live-status-panel rounded p-1",
                )
            )
        elif status == "Pending Update":
            rows.append(
                html.Div(
                    [
                        _bi("clock-history"),
                        html.Small("Finished. Awaiting official statistics update from Transfermarkt.", 
                                   className="text-warning fw-bold"),
                    ],
                    className="d-flex align-items-center gap-1 mb-2 border border-warning border-opacity-25 rounded p-1",
                    style={"backgroundColor": "rgba(255, 193, 7, 0.05)"}
                )
            )

        stadium = payload.get("stadium")
        streaming_url = payload.get("streaming_url")
        streaming_platform = payload.get("streaming_platform")
        if stadium:
            rows.append(
                html.Div(
                    [
                        _bi("geo-alt"),
                        html.Small(stadium, className="portal-text-muted"),
                    ],
                    className="d-flex align-items-center gap-1 mb-1",
                )
            )
        if streaming_url and "facebook.com" not in str(streaming_url).lower():
            platform_label = get_streaming_label(streaming_url, streaming_platform)
            rows.append(
                html.Div(
                    [
                        _bi("tv"),
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
        elif not streaming_url:
            rows.append(
                html.Div(
                    [
                        _bi("tv"),
                        html.Small(
                            "No Streaming",
                            className="portal-text-muted",
                        ),
                    ],
                    className="d-flex align-items-center gap-1 mb-1",
                )
            )
        if h2h and h2h.get("matches_found", 0) > 0:
            matches_found = max(int(h2h.get("matches_found", 0) or 0), 1)
            wins = int(h2h.get("wins", 0) or 0)
            draws = int(h2h.get("draws", 0) or 0)
            losses = int(h2h.get("losses", 0) or 0)
            h2h_txt = f"H2H: {wins}W - {draws}D - {losses}L"
            rows.append(
                html.Div(
                    [
                        html.Small(
                            [_bi("shield"), h2h_txt],
                            className="portal-text-muted d-block mb-1",
                        ),
                        html.Div(
                            [
                                html.Div(style={
                                    "width": f"{(wins / matches_found) * 100:.2f}%",
                                    "background": "#76d289",
                                    "height": "100%",
                                }),
                                html.Div(style={
                                    "width": f"{(draws / matches_found) * 100:.2f}%",
                                    "background": "#f4c351",
                                    "height": "100%",
                                }),
                                html.Div(style={
                                    "width": f"{(losses / matches_found) * 100:.2f}%",
                                    "background": "#ef6b6b",
                                    "height": "100%",
                                }),
                            ],
                            style={
                                "display": "flex",
                                "height": "6px",
                                "borderRadius": "999px",
                                "overflow": "hidden",
                                "background": "rgba(255,255,255,0.08)",
                            },
                            className="mb-1",
                        ),
                    ],
                    className="mb-1",
                )
            )
        else:
            rows.append(
                html.Div(
                    [_bi("shield"), html.Small("H2H: sin datos", className="portal-text-muted")],
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
                        _bi("geo-alt"),
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
        position = _display_match_position(payload.get("position", "N/A"))
        sub_in = payload.get("subbed_in")
        sub_out = payload.get("subbed_out")

        absence_reason = payload.get("absence_reason")

        if minutes > 0:
            # Position Line
            rows.append(
                html.Div(
                    [
                        _bi("person"),
                        html.Small("Pos:", className="portal-text-muted fw-semibold me-2"),
                        html.Span(position, className="portal-position-chip"),
                    ],
                    className="d-flex align-items-center mb-2",
                )
            )

            # Core Stats Row - Unificado con Season Cards
            stat_parts = [
                html.Div([
                    html.I(className="bi bi-stopwatch me-1", style={"fontSize": "0.85rem"}),
                    html.Span(f"{minutes}'"),
                ], className="portal-text-muted d-flex align-items-center justify-content-start", style={"flex": "1 1 0", "minWidth": "0"}),
                
                html.Div([
                    html.Img(src="/assets/icons/soccer-ball.svg", style={"width": "14px", "height": "14px", "opacity": "0.85"}, className="me-1"),
                    html.Span(f"{goals}G"),
                ], className="portal-text-muted d-flex align-items-center justify-content-center", style={"flex": "1 1 0", "minWidth": "0"}),

                html.Div([
                    _bi("activity", style={"fontSize": "0.85rem", "opacity": "0.85"}),
                    html.Span(f"{assists}A"),
                ], className="portal-text-muted d-flex align-items-center justify-content-center", style={"flex": "1 1 0", "minWidth": "0"}),
            ]
            if own_goals > 0:
                stat_parts.append(
                    html.Small(
                        [html.I(className="bi bi-exclamation-triangle me-1"), f"{own_goals} OG"],
                        className="text-danger ms-3",
                    )
                )

            rows.append(
                html.Div(
                    stat_parts, className="d-flex align-items-center mb-2", style={"width": "100%", "gap": "8px"}
                )
            )

            # Cards and Substitution Line - Unificado
            detail_parts = []
            if yellow > 0:
                detail_parts.append(
                    html.Div([
                        _card_icon("#f4c351"),
                        html.Span(f"{yellow} Yellow"),
                    ], className="portal-text-muted d-flex align-items-center me-3", style={"fontSize": "0.8rem"})
                )
            if red > 0:
                detail_parts.append(
                    html.Div([
                        _card_icon("#ef6b6b"),
                        html.Span(f"{red} Red"),
                    ], className="portal-text-muted d-flex align-items-center", style={"fontSize": "0.8rem"})
                )

            sub_info = []
            if sub_in is not None:
                sub_info.append(
                    html.Small(
                        [_bi("box-arrow-in-right"), f"In: {sub_in}'"],
                        className="text-success me-2",
                    )
                )
            if sub_out is not None:
                sub_info.append(
                    html.Small(
                        [_bi("box-arrow-right"), f"Out: {sub_out}'"],
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
                "No jugado": ("danger", "Did Not Play"),
                "No jugo": ("danger", "Did Not Play"),
                "Not played": ("danger", "Did Not Play"),
                "not_played": ("danger", "Did Not Play"),
            }
            reason_raw = absence_reason or "No jugado"
            badge_info = _ABSENCE_LABELS.get(reason_raw, ("danger", "Did Not Play"))

            rows.append(
                html.Div(
                    [
                        _bi("person-x"),
                        dbc.Badge(
                            badge_info[1], color=badge_info[0], className="small text-white"
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
            # ONLY count as a played match if minutes > 0
            mins = int(m.get("minutes_played", 0) or 0)
            if mins <= 0:
                continue

            comp = _normalize_comp(m.get("competition", "Other")) or "Other"
            if comp not in comp_agg:
                comp_agg[comp] = {"pj": 0, "goals": 0, "assists": 0, "minutes": 0, "yellow": 0, "red": 0}
            
            comp_agg[comp]["pj"] += 1
            comp_agg[comp]["goals"] += int(m.get("goals", 0) or 0)
            comp_agg[comp]["assists"] += int(m.get("assists", 0) or 0)
            comp_agg[comp]["minutes"] += mins
            comp_agg[comp]["yellow"] += int(m.get("yellow_cards", 0) or 0)
            comp_agg[comp]["red"] += int(m.get("red_cards", 0) or 0)

        rows.append(
            html.Small(
                "Competition breakdown",
                className="portal-text-muted text-uppercase fw-bold d-block mb-2",
                style={"fontSize": "0.6rem", "letterSpacing": "0.05em"},
            )
        )
        for comp, stats in sorted(comp_agg.items(), key=lambda item: (-item[1]["pj"], item[0])):
            # Competition Logo with Tooltip
            logo_el = _competition_logo_img(comp)
            
            # Ajustamos el tamaño para el breakdown (un poco más pequeño que en el header)
            if hasattr(logo_el, "style"):
                logo_el.style.update({
                    "width": "32px", 
                    "height": "32px"
                })

            logo_container = html.Div(
                logo_el,
                title=comp,
                className="me-2 flex-shrink-0"
            )

            rows.append(
                html.Div(
                    [
                        logo_container,
                        html.Div(
                            [
                                # MP
                                html.Div([
                                    html.I(className="bi bi-calendar-check me-1", style={"fontSize": "0.86rem", "opacity": "0.95", "color": "#e4ecf4"}),
                                    html.Span(str(stats['pj']), style={"color": "#e4ecf4", "fontWeight": "600"}),
                                ], className="portal-text-muted d-flex align-items-center justify-content-center", style={"fontSize": "0.8rem", "color": "#e4ecf4", "flex": "1 1 0", "minWidth": "0", "whiteSpace": "nowrap"}),
                                
                                # Min
                                html.Div([
                                    html.I(className="bi bi-stopwatch me-1", style={"fontSize": "0.86rem", "opacity": "0.95", "color": "#e4ecf4"}),
                                    html.Span(str(stats['minutes']), style={"color": "#e4ecf4", "fontWeight": "600"}),
                                ], className="portal-text-muted d-flex align-items-center justify-content-center", style={"fontSize": "0.8rem", "color": "#e4ecf4", "flex": "1.2 1 0", "minWidth": "0", "whiteSpace": "nowrap"}),

                                # Goals
                                html.Div([
                                    html.Img(src="/assets/icons/soccer-ball.svg", style={"width": "15px", "height": "17px", "opacity": "0.95"}, className="me-1"),
                                    html.Span(str(stats['goals']), style={"color": "#e4ecf4", "fontWeight": "600"}),
                                ], className="portal-text-muted d-flex align-items-center justify-content-center", style={"fontSize": "0.8rem", "color": "#e4ecf4", "flex": "1 1 0", "minWidth": "0", "whiteSpace": "nowrap"}),

                                # Assists
                                html.Div([
                                    html.I(**{"data-lucide": "sport-shoe"}, style={"width": "15px", "height": "15px", "opacity": "0.95", "color": "#e4ecf4"}, className="me-1"),
                                    html.Span(str(stats['assists']), style={"color": "#e4ecf4", "fontWeight": "600"}),
                                ], className="portal-text-muted d-flex align-items-center justify-content-center", style={"fontSize": "0.8rem", "color": "#e4ecf4", "flex": "1 1 0", "minWidth": "0", "whiteSpace": "nowrap"}),

                                html.Div(
                                    [
                                        # Yellow
                                        html.Div([
                                            _card_icon("#f4c351", size="13px"),
                                            html.Span(str(stats['yellow']), style={"color": "#e4ecf4", "fontWeight": "600"}),
                                        ], className="portal-text-muted d-flex align-items-center justify-content-center", style={"fontSize": "0.8rem", "color": "#e4ecf4", "whiteSpace": "nowrap"}),

                                        # Red
                                        html.Div([
                                            _card_icon("#ef6b6b", size="13px"),
                                            html.Span(str(stats['red']), style={"color": "#e4ecf4", "fontWeight": "600"}),
                                        ], className="portal-text-muted d-flex align-items-center justify-content-center", style={"fontSize": "0.8rem", "color": "#e4ecf4", "whiteSpace": "nowrap"}),
                                    ],
                                    className="d-flex align-items-center justify-content-center",
                                    style={"flex": "1.45 1 0", "minWidth": "0", "gap": "4px"},
                                ),
                            ],
                            className="d-flex align-items-center flex-grow-1",
                            style={"gap": "6px", "width": "100%"},
                        ),
                    ],
                    className="d-flex align-items-center border-bottom border-secondary border-opacity-25 py-2",
                )
            )
    else:
        rows.append(
            html.Small(
                "No match data available.", className="portal-text-muted fst-italic"
            )
        )

    return html.Div(rows, className="pb-1 pt-1 px-2")


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
    # Special case: LIVE status uses 'danger' color.
    status = payload.get("confirmation_status")
    if status == "LIVE":
        color = "live"
    elif status == "Pending Update":
        color = "success"
    else:
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
    status = payload.get("confirmation_status")
    
    circle_cls = f"event-circle event-circle-{color}"
    if cached_image or status == "LIVE":
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
            # Career card: arrow anchored bottom-right like pre/post-match
            season_team_name = (
                payload.get("season_team")
                or payload.get("team_name")
                or payload.get("team")
                or _get_player_current_team_name(payload.get("player_id") or payload.get("player"))
            )
            season_team_assets = _render_season_team_assets(
                season_team_name
            )
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
                style={
                    "cursor": "pointer",
                    "gridColumn": "2",
                    "gridRow": "2",
                    "justifySelf": "end",
                    "alignSelf": "end",
                },
            )
            right_action_stack = html.Div(
                [
                    html.Div(
                        season_team_assets,
                        className="season-team-assets-wrap",
                        style={
                            "marginTop": "2px",
                            "minHeight": "30px",
                            "display": "flex",
                            "alignItems": "flex-start",
                            "justifyContent": "flex-end",
                            "width": "100%",
                        },
                    ),
                    detail_btn,
                ],
                className="career-right-stack",
                style={
                    "display": "flex",
                    "flexDirection": "column",
                    "alignItems": "flex-end",
                    "justifyContent": "space-between",
                    "gridColumn": "2",
                    "gridRow": "1 / 3",
                    "minWidth": "108px",
                    "width": "108px",
                    "maxWidth": "108px",
                    "flexShrink": "0",
                    "minHeight": "74px",
                    "height": "100%",
                },
            )
            header_row = html.Div(
                [
                    html.Div(
                        header_label_content,
                        id={"type": "timeline-milestone-text", "index": milestone_id},
                        className="career-header-main",
                        style={"cursor": "pointer", "gridRow": "1 / 3", "minWidth": "0"},
                    ),
                    right_action_stack,
                ],
                id={"type": "milestone-header", "index": milestone_id},
                className="milestone-header milestone-header--career",
                style={
                    "display": "grid",
                    "gridTemplateColumns": "minmax(0, 1fr) 108px",
                    "gridTemplateRows": "1fr auto",
                    "minHeight": "80px",
                    "padding": "5px 0 0 0",
                    "cursor": "pointer",
                    "columnGap": "8px",
                },
                n_clicks=0,
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

    @app.callback(
        Output("timeline-context-store", "data", allow_duplicate=True),
        Output("selected-year-store", "data", allow_duplicate=True),
        Output("timeline-expand-store", "data", allow_duplicate=True),
        Input("url", "pathname"),
        prevent_initial_call="initial_duplicate",
    )
    def reset_portal_navigation_state(pathname):
        """Ensures the portal mounts with a clean collapsed navigation state."""
        if pathname != "/player-portal":
            return no_update, no_update, no_update
        return None, None, []

    @app.callback(
        Output("season-asset-modal", "is_open"),
        Output("season-asset-modal-image", "src"),
        Output("season-asset-modal-title", "children"),
        Input({"type": "season-team-asset", "src": ALL, "label": ALL}, "n_clicks"),
        Input("season-asset-modal", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_season_asset_modal(asset_clicks, modal_open):
        triggered = ctx.triggered_id
        if isinstance(triggered, dict) and triggered.get("type") == "season-team-asset":
            if not any((click or 0) > 0 for click in (asset_clicks or [])):
                return False, no_update, no_update
            return True, triggered.get("src"), triggered.get("label", "")
        return False, no_update, no_update

    # ------------------------------------------------------------------ #
    # Sync-status banner + interval enable/disable                        #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("sync-status-banner", "children"),
        Output("sync-status-banner", "style"),
        Output("sync-poll-interval", "disabled"),
        Input("url", "pathname"),
        Input("sync-poll-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_sync_banner(pathname, _n):
        """Checks player sync status and shows a subtle informational banner."""
        hidden = {"display": "none"}
        if pathname != "/player-portal":
            return no_update, hidden, True

        player_id = getattr(current_user, "player_id", None)
        if not player_id:
            return no_update, hidden, True

        status = _get_player_sync_status(player_id)
        state = status.get("state", "ready")
        tm_runtime = TransfermarktRuntimeManager().get_status()
        tm_mode = tm_runtime.mode or "NORMAL"

        if state == "ready" and tm_mode == "NORMAL":
            return None, hidden, True

        if tm_mode == "BLOCKED" and state in {"ready", "no_history"}:
            content = [
                html.I(className="bi bi-shield-exclamation me-2", style={"fontSize": "0.8rem", "opacity": "0.65"}),
                html.Span(
                    "Your recent match details may be delayed while Transfermarkt refresh is temporarily blocked."
                    if state == "no_history"
                    else "Recent rival and season updates may be delayed."
                ),
            ]
            return content, {"display": "flex"}, True

        if tm_mode == "ASSISTED_ACTIVE" and state == "ready":
            content = [
                html.I(className="bi bi-arrow-repeat me-2", style={"fontSize": "0.8rem", "opacity": "0.65"}),
                html.Span("Recent rival data is being refreshed."),
            ]
            return content, {"display": "flex"}, True

        if tm_mode == "ASSISTED_ACTIVE" and state == "no_history":
            content = [
                html.I(className="bi bi-arrow-repeat me-2", style={"fontSize": "0.8rem", "opacity": "0.65"}),
                html.Span("Your recent match details are being refreshed."),
            ]
            return content, {"display": "flex"}, False

        if tm_mode in {"DEGRADED", "RECOVERING"} and state == "ready":
            content = [
                html.I(className="bi bi-info-circle me-2", style={"fontSize": "0.8rem", "opacity": "0.6"}),
                html.Span("Some recent opponent updates may still be catching up."),
            ]
            return content, {"display": "flex"}, True

        if state == "no_data":
            content = [
                html.Span(className="sync-dot sync-dot--pending"),
                html.Span("Setting up your profile — your stats will appear shortly."),
            ]
        elif state == "no_history":
            content = [
                html.Span(className="sync-dot sync-dot--loading"),
                html.Span("Loading your match history — this may take a moment."),
            ]
        else:  # no_tm_link
            content = [
                html.I(className="bi bi-info-circle me-2", style={"fontSize": "0.8rem", "opacity": "0.6"}),
                html.Span("League stats available. Individual match detail will be added once your profile is linked."),
            ]

        banner_style = {"display": "flex"}
        # no_tm_link is a static state — no background process will resolve it, stop polling
        interval_disabled = (state == "no_tm_link")
        return content, banner_style, interval_disabled

    # ------------------------------------------------------------------ #
    # ETL → milestones-data-store                                         #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("milestones-data-store", "data"),
        Input("url", "pathname"),
        Input("sync-poll-interval", "n_intervals"),
        State("milestones-data-store", "data"),
        prevent_initial_call=False,
    )
    def update_timeline(pathname, _n, current_data):
        """Fetches timeline milestones and stores serialized data."""
        if pathname != "/player-portal":
            return no_update

        try:
            player_id = getattr(current_user, "player_id", None)
            if not player_id:
                return None

            aggregator = TimelineAggregator(data_manager=get_hong_kong_data_manager())
            milestones = aggregator.get_player_timeline(player_id)
            _log_timeline_snapshot(player_id, milestones, "RAW")

            if not milestones:
                return no_update if current_data == [] else []

            serialized = _serialize_milestones(milestones)
            _log_timeline_snapshot(player_id, serialized, "SERIALIZED")
            if serialized == current_data:
                return no_update
            return serialized

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
        ClientsideFunction(namespace="playerPortal", function_name="scrollYearNavigator"),
        Output("year-nav-scroll-dummy", "data"),
        Input("year-navigator-pills", "children"),
        Input("selected-year-store", "data"),
        prevent_initial_call=True,
    )

    # ------------------------------------------------------------------ #
    # Clientside: scroll milestone list to selected year section          #
    # ------------------------------------------------------------------ #
    app.clientside_callback(
        ClientsideFunction(namespace="playerPortal", function_name="scrollTimelineToYear"),
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
            # Guard: Dash 4 fires ALL-pattern callbacks when components are dynamically
            # added to the DOM (n_clicks=0). Only process genuine user clicks.
            trigger_value = ctx.triggered[0].get("value", 0) if ctx.triggered else 0
            if not trigger_value:
                return no_update
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
        Input("timeline-pagination-store", "data"),
        prevent_initial_call=True,
    )
    def render_timeline_milestones(milestones_data, pagination_store):
        """
        Renders milestone items grouped by season in .season-section divs.
        Career milestones act as season headers; match groups visibility
        is controlled by the is-expanded class on the season-group-container.
        """
        if not milestones_data:
            # Show contextual empty state based on sync status
            player_id = getattr(current_user, "player_id", None)
            if player_id:
                status = _get_player_sync_status(player_id)
                state = status.get("state", "ready")
                if state == "no_data":
                    empty_msg = html.Div([
                        html.Span(className="sync-dot sync-dot--pending me-2"),
                        html.Span("Your profile is being set up. Match history will appear here shortly.", className="portal-text-muted small"),
                    ], className="d-flex align-items-center px-3 py-4")
                    return [empty_msg], []
                elif state == "no_history":
                    empty_msg = html.Div([
                        html.Span(className="sync-dot sync-dot--loading me-2"),
                        html.Span("Loading your match history — check back in a moment.", className="portal-text-muted small"),
                    ], className="d-flex align-items-center px-3 py-4")
                    return [empty_msg], []
            return no_update, no_update

        from collections import defaultdict

        groups = defaultdict(list)
        for m in milestones_data:
            # group_year now contains season strings like "2025-26"
            year = m.get("group_year") or str(m.get("date", ""))[:4] or "unknown"
            groups[year].append(m)

        sorted_years = sorted(groups.keys(), reverse=True)
        expand_ids = _get_default_expand_ids(milestones_data)
        expand_ids_set = set(expand_ids)
        
        # PERSISTENCE: Build generated set from store + disk check
        generated_set = set((pagination_store or {}).get("generated", {}).keys())
        u_id = str(current_user.id) if current_user and current_user.is_authenticated else None
        
        # Cross-reference with disk for session persistence
        if u_id:
            from utils.stage_helpers import get_cached_image_path
            for m in milestones_data:
                mid = m.get("id")
                if mid and mid not in generated_set:
                    # PROACTIVE DISK CHECK: uses robust logic (metadata, standard names, etc)
                    cached_path = get_cached_image_path(mid, player_id=u_id)
                    if cached_path:
                        generated_set.add(mid)
                        logger.debug(f"Persistence found generated card for {mid} at {cached_path}")

        sections = []
        for year in sorted_years:
            year_milestones = groups[year]

            # Separate career anchor from match milestones
            career_m = next(
                (m for m in year_milestones if m.get("type") == "career"), None
            )
            match_milestones = [m for m in year_milestones if m.get("type") != "career"]
            match_milestones = sorted(
                match_milestones,
                key=_get_timeline_priority,
            )
            try:
                logger.debug(
                    "[TIMELINE_RENDER_ORDER] player_id=%s year=%s order=%s",
                    getattr(current_user, "player_id", None) or "unknown",
                    year,
                    [
                        {
                            "id": m.get("id"),
                            "type": m.get("type"),
                            "status": (m.get("payload") or {}).get("confirmation_status"),
                            "label": m.get("label"),
                            "date": str(m.get("date") or ""),
                            "priority": _get_timeline_priority(m),
                        }
                        for m in match_milestones
                    ],
                )
            except Exception as exc:
                logger.debug("timeline render order log error: %s", exc)

            items = []

            # Career milestone as season header
            if career_m:
                career_item = _render_milestone_item(
                    career_m,
                    initial_open=career_m.get("id") in expand_ids_set,
                    generated_set=generated_set,
                )
                career_id = career_m.get("id")
            else:
                career_item = None
                career_id = None

            # Render ALL match milestones; first 5 visible, rest hidden.
            if match_milestones:
                match_items = [
                    _render_milestone_item(
                        m,
                        initial_open=m.get("id") in expand_ids_set,
                        generated_set=generated_set,
                        hidden=(i >= 5),
                    )
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

                matches_group_kwargs = {"className": "season-matches-group"}
                if career_id:
                    matches_group_kwargs["id"] = {"type": "season-matches-group", "index": career_id}
                matches_group = html.Div(match_items, **matches_group_kwargs)

                if career_item:
                    # Wrap career + matches in a container that controls match visibility via is-expanded class
                    expanded_cls = " is-expanded" if career_id in expand_ids_set else ""
                    items.append(
                        html.Div(
                            [career_item, matches_group],
                            className=f"season-group-container{expanded_cls}",
                            **{"data-career-id": career_id}
                        )
                    )
                else:
                    items.extend(match_items)
            elif career_item:
                # Career-only section (no match milestones yet) — still render the career card
                items.append(career_item)

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
        ClientsideFunction(namespace="playerPortal", function_name="loadMoreMilestones"),
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
        Input({"type": "milestone-header", "index": ALL}, "n_clicks"),
        State("milestones-data-store", "data"),
        State("timeline-context-store", "data"),
        prevent_initial_call=True,
    )
    def select_milestone(
        milestone_clicks, detail_clicks, header_clicks, milestones_data, current_context
    ):
        """Updates the context store when a milestone icon or detail CTA is clicked."""
        if not ctx.triggered_id or not milestones_data:
            return no_update

        triggered = ctx.triggered_id

        if isinstance(triggered, dict) and triggered.get("type") in (
            "timeline-milestone",
            "milestone-detail-btn",
            "milestone-header",
        ):
            # Guard: Dash 4 fires ALL-pattern callbacks when components are dynamically
            # added to the DOM (n_clicks=0). Only process genuine user clicks.
            trigger_value = ctx.triggered[0].get("value", 0) if ctx.triggered else 0
            if not trigger_value:
                return no_update
            milestone_id = triggered["index"]
            milestone = next(
                (item for item in milestones_data if item.get("id") == milestone_id),
                None,
            )
            # Toggle: if this milestone is already the active context, clear it → dashboard
            if current_context and current_context.get("id") == milestone_id:
                return current_context.get("parent") or None
            # Find the milestone by ID in the list
            m = milestone
            if m:
                context = {"id": m.get("id"), "type": m["type"], "payload": m["payload"]}
                if m.get("type") != "career":
                    parent = _get_career_parent_context(milestones_data, m)
                    if parent:
                        context["parent"] = parent
                return context

        return no_update

    @app.callback(
        Output("timeline-context-store", "data", allow_duplicate=True),
        Input({"type": "milestone-header", "index": ALL}, "n_clicks"),
        State("timeline-expand-store", "data"),
        State("milestones-data-store", "data"),
        State("timeline-context-store", "data"),
        prevent_initial_call=True,
    )
    def sync_context_on_header_toggle(header_clicks, expand_store, milestones_data, current_context):
        """Clears or restores stage context when a currently open timeline header is collapsed."""
        if not ctx.triggered_id or not milestones_data:
            return no_update

        triggered = ctx.triggered_id
        if not isinstance(triggered, dict) or triggered.get("type") != "milestone-header":
            return no_update

        trigger_value = ctx.triggered[0].get("value", 0) if ctx.triggered else 0
        if not trigger_value:
            return no_update

        milestone_id = triggered.get("index")
        if not milestone_id:
            return no_update

        open_ids = set(expand_store or [])
        is_currently_open = milestone_id in open_ids
        if not is_currently_open:
            return no_update

        milestone = next(
            (item for item in (milestones_data or []) if item.get("id") == milestone_id),
            None,
        )
        if not milestone:
            return no_update

        milestone_type = milestone.get("type")
        active_id = (current_context or {}).get("id")
        active_parent_id = ((current_context or {}).get("parent") or {}).get("id")

        if milestone_type == "career":
            if active_id == milestone_id or active_parent_id == milestone_id:
                return None
            return no_update

        if active_id == milestone_id:
            return (current_context or {}).get("parent") or None

        return no_update

    # ------------------------------------------------------------------ #
    # Progressive loading: 3-phase cascade                               #
    #   Phase 1 (UI):    layout initial content = create_skeleton_stage  #
    #                    + create_skeleton_timeline — no callback needed  #
    #   Phase 2 (amber): portal-data-store → deterministic render        #
    #   Phase 3 (purple): portal-render-complete-store → AI synthesis    #
    # ------------------------------------------------------------------ #

    # Phase 1 — ETL: fetch all dashboard data once into portal-data-store
    # (The layout already provides create_skeleton_stage / create_skeleton_timeline
    #  as initial HTML — no callback needed for Phase 1.)
    @app.callback(
        Output("portal-data-store", "data"),
        Input("milestones-data-store", "data"),
        prevent_initial_call=True,
    )
    def populate_portal_data_store(milestones_data):
        """ETL phase: fetches all dashboard data once. Feeds both phase 2 render and phase 3 AI synthesis."""
        if milestones_data is None:
            return no_update
        try:
            from utils.career_intelligence import get_career_phase_data, get_career_signals, get_development_priorities
            from utils.stage_helpers import _fetch_dashboard_data, _serialize_dashboard_data

            player_id, player_name, user_role = _get_active_player_identity()
            if not player_id or not player_name:
                return no_update

            data = _fetch_dashboard_data(player_name, player_id)
            career_phase_data = get_career_phase_data(data, data.get("history_df"))
            career_signals = get_career_signals(data, data.get("history_df"), career_phase_data or {})
            development_priorities = get_development_priorities(data.get("percentiles_data") or {})
            return {
                "player_id": player_id,
                "player_name": player_name,
                "user_role": user_role,
                "data": _serialize_dashboard_data(data),
                "career_phase": career_phase_data,
                "signals": career_signals,
                "priorities": development_priorities,
            }
        except Exception as exc:
            logger.error(f"populate_portal_data_store error: {exc}")
            return no_update

    # Phase 2 — deterministic render with real data (no AI)
    # Emits portal-render-complete-store to signal phase 3 can start.
    @app.callback(
        Output("stage-content", "children", allow_duplicate=True),
        Output("portal-render-complete-store", "data"),
        Input("portal-data-store", "data"),
        State("timeline-context-store", "data"),
        prevent_initial_call=True,
    )
    def render_stage_with_data(portal_data, timeline_context):
        """Phase 2 (data/amber): renders full dashboard with deterministic data, no AI.
        Skips render if a card is open (timeline_context set) to avoid overwriting it."""
        if not portal_data:
            return no_update, no_update
        if timeline_context:
            # Card is open — don't overwrite stage, but still signal phase 3 to proceed
            return no_update, {"player_id": portal_data.get("player_id"), "skipped": True}
        try:
            from utils.stage_helpers import _deserialize_dashboard_data
            data = _deserialize_dashboard_data(portal_data["data"])
            content = _render_default_stage_content(ai_payload=None, pre_fetched_data=data)
            return content, {"player_id": portal_data.get("player_id"), "skipped": False}
        except Exception as exc:
            logger.error(f"render_stage_with_data error: {exc}")
            return no_update, no_update

    # Phase 3a — AI synthesis (starts AFTER phase 2 render completes, not in parallel)
    # Using portal-render-complete-store as input ensures sequential execution.
    @app.callback(
        Output("career-dashboard-brief-store", "data"),
        Input("portal-render-complete-store", "data"),
        State("portal-data-store", "data"),
        prevent_initial_call=True,
    )
    def build_career_dashboard_ai_brief(render_signal, portal_data):
        """Phase 3a: synthesizes AI overrides using pre-fetched data — no second DB fetch.
        Runs strictly after phase 2 render to avoid parallel career_dashboard_ai calls."""
        if not render_signal or not portal_data or bool((render_signal or {}).get("skipped")):
            return no_update
        runtime_config = get_intelligence_runtime_config()
        if not bool(runtime_config.get("career_dashboard_ai_enabled", True)):
            logger.info("Career dashboard AI skipped reason=disabled")
            return no_update
        try:
            from utils.career_intelligence import (
                DashboardInsightItem,
                CareerDashboardBrief,
            )
            from utils.domain_ai import synthesize_career_dashboard_ai_payload
            from utils.domain_ai.career_dashboard_ai import normalize_career_dashboard_brief_payload
            from utils.stage_helpers import _deserialize_dashboard_data

            data = _deserialize_dashboard_data(portal_data["data"])
            synthesized = synthesize_career_dashboard_ai_payload(
                CareerDashboardBrief,
                DashboardInsightItem,
                data,
                portal_data.get("career_phase") or {},
                portal_data.get("signals") or {},
                portal_data.get("priorities") or [],
            )
            normalized = normalize_career_dashboard_brief_payload(synthesized)
            return normalized or no_update
        except Exception as exc:
            logger.debug(f"build_career_dashboard_ai_brief error: {exc}")
            return no_update

    @app.callback(
        Output("career-stage-analysis-store", "data"),
        Input("portal-render-complete-store", "data"),
        State("portal-data-store", "data"),
        State("career-stage-analysis-store", "data"),
        prevent_initial_call=True,
    )
    def build_career_stage_analysis_after_render(render_signal, portal_data, current_analysis_store):
        """Build shared career stage analysis after the deterministic dashboard render completes."""
        if not render_signal or not portal_data or bool((render_signal or {}).get("skipped")):
            return no_update
        try:
            from utils.career_stage.career_intelligence import orchestrate_career_intelligence
            from utils.stage_helpers import _deserialize_dashboard_data

            data = _deserialize_dashboard_data(portal_data["data"])
            player_payload = dict(data.get("player") or {})
            if not player_payload.get("player_id"):
                player_payload["player_id"] = str(portal_data.get("player_id") or "")
            if not player_payload.get("player_name"):
                player_payload["player_name"] = str(portal_data.get("player_name") or "")
            data["player"] = player_payload
            data.setdefault("player_name", str(portal_data.get("player_name") or ""))
            request_key = _career_analysis_request_key(portal_data)
            runtime_config = get_intelligence_runtime_config()
            persistence_enabled = bool(runtime_config.get("persistence_enabled"))
            store_reuse_enabled = bool(runtime_config.get("stage_analysis_store_reuse_enabled", True))
            existing_store = dict(current_analysis_store or {})
            if (
                persistence_enabled
                and store_reuse_enabled
                and str(existing_store.get("request_key") or "") == request_key
                and existing_store.get("analysis")
            ):
                logger.info(
                    "Career stage analysis reuse request_key=%s analysis_source=%s llm_enabled=%s model_profile=%s persistence_enabled=%s store_reuse_enabled=%s",
                    request_key,
                    str(((existing_store.get("analysis") or {}).get("debug") or {}).get("analysis_source") or "unknown"),
                    bool(runtime_config.get("career_agent_llm_enabled")),
                    str(runtime_config.get("career_agent_model_profile") or "flash"),
                    persistence_enabled,
                    store_reuse_enabled,
                )
                return no_update
            from utils.agents.career_intelligence_orchestrator import orchestrate_career_intelligence

            orchestration = orchestrate_career_intelligence(
                data,
                force_refresh=not persistence_enabled,
            )
            analysis_payload = dict(orchestration.get("stage_analysis") or {})
            debug_payload = dict(orchestration.get("debug") or {})
            served_from = dict(debug_payload.get("served_from") or {})
            logger.info(
                "Career stage analysis built request_key=%s analysis_source=%s llm_enabled=%s model_profile=%s persistence_enabled=%s store_reuse_enabled=%s served_from=%s refresh_plan=%s",
                request_key,
                str(((analysis_payload or {}).get("debug") or {}).get("analysis_source") or "unknown"),
                bool(runtime_config.get("career_agent_llm_enabled")),
                str(runtime_config.get("career_agent_model_profile") or "flash"),
                persistence_enabled,
                store_reuse_enabled,
                served_from,
                list(orchestration.get("refresh_plan") or []),
            )
            return {
                "request_key": request_key,
                "analysis": analysis_payload,
                "overlay_candidates": dict(orchestration.get("overlay_candidates") or {}),
                "overlay_surface": dict(orchestration.get("overlay_surface") or {}),
                "debug": debug_payload,
            } if analysis_payload else no_update
        except Exception as exc:
            logger.info("build_career_stage_analysis_after_render error: %s", exc)
            return no_update

    # Phase 3b — re-render with AI copy (no DB fetch: data from State)
    @app.callback(
        Output("stage-content", "children", allow_duplicate=True),
        Input("career-dashboard-brief-store", "data"),
        State("timeline-context-store", "data"),
        State("portal-data-store", "data"),
        prevent_initial_call=True,
    )
    def refresh_default_stage_with_ai(career_dashboard_brief, timeline_context, portal_data):
        """Phase 3b (AI/purple): re-renders dashboard with AI copy — no ETL (data from portal-data-store)."""
        if not career_dashboard_brief:
            return no_update
        if timeline_context:
            return no_update
        try:
            from utils.stage_helpers import _deserialize_dashboard_data
            pre_fetched = _deserialize_dashboard_data(portal_data["data"]) if portal_data else None
            return _render_default_stage_content(
                ai_payload=career_dashboard_brief,
                pre_fetched_data=pre_fetched,
            )
        except Exception as exc:
            logger.error(f"refresh_default_stage_with_ai error: {exc}")
            return _render_default_stage_content(ai_payload=career_dashboard_brief)

    @app.callback(
        Output("stage-background-dispatch-store", "data"),
        Input("portal-render-complete-store", "data"),
        State("portal-data-store", "data"),
        State("milestones-data-store", "data"),
        prevent_initial_call=True,
    )
    def dispatch_stage_reevaluations_after_portal_entry(render_signal, portal_data, milestones_data):
        """Prewarm eligible stage runtimes after app entry without waiting for stage-local callbacks."""
        if not render_signal or not portal_data or bool((render_signal or {}).get("skipped")):
            return no_update
        try:
            from utils.intelligence.background_dispatch import dispatch_background_stage_reevaluations

            summary = dispatch_background_stage_reevaluations(portal_data, milestones_data)
            logger.info(
                "Portal background stage dispatch summary=%s",
                {
                    stage_name: {
                        "eligible": bool(stage_summary.get("eligible")),
                        "dispatched": bool(stage_summary.get("dispatched")),
                        "refresh_plan": list(stage_summary.get("refresh_plan") or []),
                        "reevaluation_reason": str((stage_summary.get("reevaluation") or {}).get("reason") or ""),
                    }
                    for stage_name, stage_summary in dict(summary or {}).items()
                },
            )
            return json.loads(json.dumps(summary, default=str))
        except Exception as exc:
            logger.warning("portal background stage dispatch error: %s", exc)
            return no_update

    # ------------------------------------------------------------------ #
    # timeline-context-store → Stage content                              #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("stage-content", "children"),
        Input("timeline-context-store", "data"),
        State("insight-session-state", "data"),
        State("season-stage-analysis-store", "data"),
        State("prematch-stage-analysis-store", "data"),
        State("postmatch-stage-analysis-store", "data"),
        prevent_initial_call=True,
    )
    def update_stage(context, session_state, season_stage_analysis, prematch_stage_analysis, postmatch_stage_analysis):
        """Dispatches rendering to the appropriate stage helper based on card type."""
        try:
            return _render_stage_content_for_context_with_session(
                context,
                session_state,
                season_stage_analysis,
                prematch_stage_analysis,
                postmatch_stage_analysis,
            )
        except Exception as e:
            logger.error(f"update_stage error: {e}")
            return dbc.Alert("Error al renderizar el escenario.", color="danger")

    @app.callback(
        Output("season-stage-analysis-store", "data"),
        Input("stage-content", "children"),
        State("timeline-context-store", "data"),
        State("season-stage-analysis-store", "data"),
        prevent_initial_call=True,
    )
    def build_season_stage_analysis_after_render(_, context, current_analysis_store):
        """Compute season intelligence after the stage is visible, avoiding repeated stage-entry orchestration."""
        if not context or str(context.get("type") or "") != "career":
            return no_update
        try:
            from utils.agents.intelligence_orchestrator import orchestrate_season_intelligence

            payload = dict(context.get("payload") or {})
            request_key = _season_analysis_request_key(payload)
            runtime_config = get_intelligence_runtime_config()
            persistence_enabled = bool(runtime_config.get("persistence_enabled"))
            store_reuse_enabled = bool(runtime_config.get("stage_analysis_store_reuse_enabled", True))
            store = dict(current_analysis_store or {})
            if (
                store_reuse_enabled
                and str(store.get("request_key") or "") == request_key
                and store.get("intelligence")
            ):
                logger.info(
                    "Season stage analysis reuse request_key=%s persistence_enabled=%s store_reuse_enabled=%s",
                    request_key,
                    persistence_enabled,
                    store_reuse_enabled,
                )
                return no_update
            intelligence = orchestrate_season_intelligence(payload)
            logger.info(
                "Season stage analysis built request_key=%s analysis_source=%s persistence_enabled=%s store_reuse_enabled=%s served_from=%s refresh_plan=%s",
                request_key,
                str((((intelligence or {}).get("stage_analysis") or {}).get("debug") or {}).get("analysis_source") or "unknown"),
                persistence_enabled,
                store_reuse_enabled,
                dict((intelligence or {}).get("debug") or {}).get("served_from") or {},
                list(dict((intelligence or {}).get("debug") or {}).get("refresh_plan") or []),
            )
            return {
                "request_key": request_key,
                "analysis": dict((intelligence or {}).get("stage_analysis") or {}),
                "intelligence": intelligence,
            }
        except Exception as exc:
            logger.debug("season stage analysis async build error: %s", exc)
            return no_update

    @app.callback(
        Output("stage-content", "children", allow_duplicate=True),
        Input("season-stage-analysis-store", "data"),
        State("timeline-context-store", "data"),
        State("insight-session-state", "data"),
        State("prematch-stage-analysis-store", "data"),
        State("postmatch-stage-analysis-store", "data"),
        prevent_initial_call=True,
    )
    def refresh_season_stage_after_analysis(
        season_stage_analysis,
        timeline_context,
        session_state,
        prematch_stage_analysis,
        postmatch_stage_analysis,
    ):
        """Refresh the visible season stage once the async intelligence bundle is ready."""
        if not timeline_context or str(timeline_context.get("type") or "") != "career":
            return no_update
        if not season_stage_analysis:
            return no_update
        return _render_stage_content_for_context_with_session(
            timeline_context,
            session_state,
            season_stage_analysis,
            prematch_stage_analysis,
            postmatch_stage_analysis,
        )

    @app.callback(
        Output("prematch-stage-analysis-store", "data"),
        Input("stage-content", "children"),
        State("timeline-context-store", "data"),
        State("prematch-stage-analysis-store", "data"),
        prevent_initial_call=True,
    )
    def build_prematch_stage_analysis_after_render(_, context, current_analysis_store):
        """Compute prematch AI analysis after the stage is already visible, avoiding first-render blocking."""
        if not context or str(context.get("type") or "") != "pre-match":
            return no_update
        try:
            from utils.agents.prematch_intelligence_orchestrator import orchestrate_prematch_intelligence

            payload, _, _, _ = _build_prematch_render_payload(dict(context.get("payload") or {}))
            request_key = _prematch_analysis_request_key(payload)
            runtime_config = get_intelligence_runtime_config()
            persistence_enabled = bool(runtime_config.get("persistence_enabled"))
            store_reuse_enabled = bool(runtime_config.get("stage_analysis_store_reuse_enabled", True))
            store = dict(current_analysis_store or {})
            if (
                persistence_enabled
                and store_reuse_enabled
                and str(store.get("request_key") or "") == request_key
                and store.get("analysis")
            ):
                logger.info(
                    "Prematch stage analysis reuse request_key=%s analysis_source=%s llm_enabled=%s model_profile=%s persistence_enabled=%s store_reuse_enabled=%s",
                    request_key,
                    str(((store.get("analysis") or {}).get("debug") or {}).get("analysis_source") or "unknown"),
                    bool(runtime_config.get("prematch_agent_llm_enabled")),
                    str(runtime_config.get("prematch_agent_model_profile") or "flash"),
                    persistence_enabled,
                    store_reuse_enabled,
                )
                return no_update
            intelligence = orchestrate_prematch_intelligence(
                payload,
                force_refresh=not persistence_enabled,
            )
            logger.info(
                "Prematch stage analysis built request_key=%s analysis_source=%s llm_enabled=%s model_profile=%s persistence_enabled=%s store_reuse_enabled=%s",
                request_key,
                str((((intelligence or {}).get("stage_analysis") or {}).get("debug") or {}).get("analysis_source") or "unknown"),
                bool(runtime_config.get("prematch_agent_llm_enabled")),
                str(runtime_config.get("prematch_agent_model_profile") or "flash"),
                persistence_enabled,
                store_reuse_enabled,
            )
            return {
                "request_key": request_key,
                "analysis": dict((intelligence or {}).get("stage_analysis") or {}),
                "intelligence": intelligence,
            }
        except Exception as exc:
            logger.debug("prematch stage analysis async build error: %s", exc)
            return no_update

    @app.callback(
        Output("stage-content", "children", allow_duplicate=True),
        Input("prematch-stage-analysis-store", "data"),
        State("timeline-context-store", "data"),
        State("insight-session-state", "data"),
        prevent_initial_call=True,
    )
    def refresh_prematch_stage_after_analysis(prematch_stage_analysis, timeline_context, session_state):
        """Refresh the visible prematch stage once the async AI analysis is ready."""
        if not timeline_context or str(timeline_context.get("type") or "") != "pre-match":
            return no_update
        if not prematch_stage_analysis:
            return no_update
        return _render_stage_content_for_context_with_session(
            timeline_context,
            session_state,
            None,
            prematch_stage_analysis,
        )

    @app.callback(
        Output("postmatch-stage-analysis-store", "data"),
        Input("stage-content", "children"),
        State("timeline-context-store", "data"),
        State("postmatch-stage-analysis-store", "data"),
        prevent_initial_call=True,
    )
    def build_postmatch_stage_analysis_after_render(_, context, current_analysis_store):
        """Compute postmatch AI analysis after the stage is already visible, avoiding first-render blocking."""
        if not context or str(context.get("type") or "") != "post-match":
            return no_update
        try:
            from utils.agents.postmatch_intelligence_orchestrator import orchestrate_postmatch_intelligence

            payload = _build_postmatch_render_payload(dict(context.get("payload") or {}))
            request_key = _postmatch_analysis_request_key(payload)
            runtime_config = get_intelligence_runtime_config()
            persistence_enabled = bool(runtime_config.get("persistence_enabled"))
            store_reuse_enabled = bool(runtime_config.get("stage_analysis_store_reuse_enabled", True))
            store = dict(current_analysis_store or {})
            if (
                persistence_enabled
                and store_reuse_enabled
                and str(store.get("request_key") or "") == request_key
                and store.get("analysis")
            ):
                logger.info(
                    "Postmatch stage analysis reuse request_key=%s analysis_source=%s persistence_enabled=%s store_reuse_enabled=%s",
                    request_key,
                    str(((store.get("analysis") or {}).get("debug") or {}).get("analysis_source") or "unknown"),
                    persistence_enabled,
                    store_reuse_enabled,
                )
                return no_update
            intelligence = orchestrate_postmatch_intelligence(
                payload,
                force_refresh=not persistence_enabled,
            )
            logger.info(
                "Postmatch stage analysis built request_key=%s analysis_source=%s persistence_enabled=%s store_reuse_enabled=%s",
                request_key,
                str((((intelligence or {}).get("stage_analysis") or {}).get("debug") or {}).get("analysis_source") or "unknown"),
                persistence_enabled,
                store_reuse_enabled,
            )
            return {
                "request_key": request_key,
                "analysis": dict((intelligence or {}).get("stage_analysis") or {}),
                "intelligence": intelligence,
            }
        except Exception as exc:
            logger.debug("postmatch stage analysis async build error: %s", exc)
            return no_update

    @app.callback(
        Output("stage-content", "children", allow_duplicate=True),
        Input("postmatch-stage-analysis-store", "data"),
        State("timeline-context-store", "data"),
        State("insight-session-state", "data"),
        State("prematch-stage-analysis-store", "data"),
        prevent_initial_call=True,
    )
    def refresh_postmatch_stage_after_analysis(postmatch_stage_analysis, timeline_context, session_state, prematch_stage_analysis):
        """Refresh the visible postmatch stage once the async AI analysis is ready."""
        if not timeline_context or str(timeline_context.get("type") or "") != "post-match":
            return no_update
        if not postmatch_stage_analysis:
            return no_update
        return _render_stage_content_for_context_with_session(
            timeline_context,
            session_state,
            prematch_stage_analysis,
            postmatch_stage_analysis,
        )

    # ------------------------------------------------------------------ #
    # timeline-context-store → season-umap-context-store + modal header  #
    # Populated whenever a career (season) stage becomes active so the    #
    # lazy UMAP callback knows which profile_context to fetch.            #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("season-umap-context-store", "data"),
        Output("season-umap-modal-title", "children"),
        Output("season-umap-modal-explainer", "children"),
        Input("timeline-context-store", "data"),
        prevent_initial_call=True,
    )
    def sync_umap_context_store(context):
        if not context or context.get("type") != "career":
            return no_update, no_update, no_update
        payload = context.get("payload", {})
        player_name = str(payload.get("player_name") or "")
        season = str(payload.get("season") or "")
        if not player_name or not season:
            return no_update, no_update, no_update

        # Try to get archetype labels from the cached profile_context
        from utils.cache import cache as _cache
        profile_context = _cache.get(f"season-profile-ctx:v1:{player_name}:{season}") or {}
        archetype = profile_context.get("archetype_label", "Season Profile")
        cluster_archetype = profile_context.get("cluster_archetype_label", archetype)

        title = f"Full Profile Map · {archetype}"
        explainer = html.Div([
            html.Div([
                html.Span("Stage role:", className="season-umap-label-pair__key"),
                html.Span(archetype, className="season-umap-label-pair__value"),
            ], className="season-umap-label-pair"),
            html.Div([
                html.Span("Cluster role:", className="season-umap-label-pair__key"),
                html.Span(cluster_archetype, className="season-umap-label-pair__value"),
            ], className="season-umap-label-pair"),
            html.Div("Nearby points suggest similar statistical profiles for this season.", className="season-umap-explainer"),
            html.Div("Cluster colors indicate broader role families rather than exact football positions.", className="season-umap-explainer"),
            html.Div("The highlighted point marks the selected season profile.", className="season-umap-explainer"),
        ])
        return {"player_name": player_name, "season": season}, title, explainer

    # ------------------------------------------------------------------ #
    # season-profile-map-modal open → season-umap-graph figure            #
    # Runs fit_umap only when the user actually opens the modal.          #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("season-umap-graph", "figure"),
        Input("season-profile-map-modal", "is_open"),
        State("season-umap-context-store", "data"),
        prevent_initial_call=True,
    )
    def render_season_umap_on_modal_open(is_open, keys):
        if not is_open or not keys:
            return no_update
        player_name = keys.get("player_name", "")
        season = keys.get("season", "")
        if not player_name or not season:
            return no_update
        from utils.cache import cache as _cache
        profile_context = _cache.get(f"season-profile-ctx:v1:{player_name}:{season}")
        if profile_context is None:
            logger.warning(f"render_season_umap_on_modal_open: no cached profile_context for {player_name}/{season}")
            return no_update
        return build_season_umap_evidence_figure(profile_context)

    @app.callback(
        Output("stage-shell", "className"),
        Input("timeline-context-store", "data"),
        prevent_initial_call=False,
    )
    def update_stage_shell_class(context):
        """Keeps the persistent stage shell while changing the glass modifier by active context."""
        base = "glass-card stage-shell"
        if not context:
            return f"{base} stage-shell--career"

        m_type = context.get("type")
        if m_type == "pre-match":
            return f"{base} glass-prematch"
        if m_type == "post-match":
            # TASK 4.5: Consistently use glass-success for all post-match stages
            # to maintain semantic category (Post-Match = Green), similar to Pre-Match = Blue.
            return f"{base} glass-success"
        return f"{base} stage-shell--career"

    @app.callback(
        Output("timeline-expand-store", "data", allow_duplicate=True),
        Input("timeline-context-store", "data"),
        prevent_initial_call=True,
    )
    def sync_timeline_expand_store(context):
        """Keeps timeline expansion aligned with the active stage context."""
        return _get_expand_ids_for_context(context)

    app.clientside_callback(
        ClientsideFunction(namespace="playerPortal", function_name="toggleTimelineExpand"),
        Output("timeline-expand-store", "data", allow_duplicate=True),
        Input({"type": "milestone-header", "index": ALL}, "n_clicks"),
        State("timeline-expand-store", "data"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        ClientsideFunction(namespace="playerPortal", function_name="syncTimelineExpandedClasses"),
        Output("timeline-expand-visual-sync-dummy", "data"),
        Input("timeline-expand-store", "data"),
        Input("timeline-milestones", "children"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        ClientsideFunction(namespace="playerPortal", function_name="observeSeasonSections"),
        Output("timeline-season-observer-dummy", "data"),
        Input("timeline-milestones", "children"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        ClientsideFunction(namespace="playerPortal", function_name="refreshStageLucide"),
        Output("stage-lucide-refresh-dummy", "data"),
        Input("stage-content", "children"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        ClientsideFunction(namespace="playerPortal", function_name="scrollPrematchH2H"),
        Output("prematch-h2h-scroll-dummy", "data"),
        Input("prematch-h2h-today-btn", "n_clicks"),
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
        State("timeline-context-store", "data"),
        prevent_initial_call=True,
    )
    def update_stage_from_action_node(node_clicks, close_clicks, active_context):
        """Opens image gallery in Stage when an Action Node is clicked; close button resets."""
        if not ctx.triggered_id:
            return no_update, no_update

        # Close button restores the active stage context and hides itself
        if ctx.triggered_id == "gallery-close-btn":
            restored = _render_stage_content_for_context(active_context)
            return restored, {"display": "none"}

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
        ClientsideFunction(namespace="playerPortal", function_name="togglePortalViewport"),
        Output("portal-viewport", "className"),
        Output("portal-panel-state", "data"),
        Input({"type": "milestone-detail-btn", "index": ALL}, "n_clicks"),
        Input({"type": "action-node-pill", "index": ALL}, "n_clicks"),
        Input("portal-back-btn", "n_clicks"),
        prevent_initial_call=True,
    )

    # ------------------------------------------------------------------ #
    # task 5.2 + 5.3: Card expand/collapse — accordion via card-expand-   #
    # store. One card open at a time; detail panels show/hide clientside. #
    # ------------------------------------------------------------------ #
    app.clientside_callback(
        ClientsideFunction(namespace="playerPortal", function_name="toggleCardDetailPanels"),
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
        Output("gallery-close-btn", "style", allow_duplicate=True),
        Output("player-photos-store", "data", allow_duplicate=True),
        Output("card-viewer-modal", "is_open", allow_duplicate=True),
        Output("card-viewer-modal-content", "children", allow_duplicate=True),
        Input({"type": "action-node-pill", "index": ALL}, "n_clicks"),
        State("milestones-data-store", "data"),
        State("timeline-pagination-store", "data"),
        prevent_initial_call=True,
    )
    def handle_action_node_pill(n_clicks_list, milestones_data, pagination_store):
        """Open Card Studio on first click; show modal viewer if already generated."""
        if not ctx.triggered_id or not any(n_clicks_list or []):
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update
        triggered = ctx.triggered_id
        if (
            not isinstance(triggered, dict)
            or triggered.get("type") != "action-node-pill"
        ):
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update

        milestone_id = triggered["index"]
        if not milestones_data:
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update
        m = next(
            (item for item in milestones_data if item.get("id") == milestone_id), None
        )
        if not m:
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update

        # Identify current player
        try:
            from flask_login import current_user as _cu
            player_id = str(_cu.id) if _cu and _cu.is_authenticated else "unknown"
        except Exception:
            player_id = "unknown"

        store = pagination_store or {}
        generated = dict(store.get("generated", {}))
        is_generated = generated.get(milestone_id, False)
        cached_path = None
        
        # PERSISTENCE CHECK: if not in store, check disk for finalized card using robust logic
        if player_id != "unknown":
            from utils.stage_helpers import get_cached_image_path
            cached_path = get_cached_image_path(milestone_id, player_id=player_id)
            if cached_path:
                is_generated = True

        m_type = m.get("type")
        payload = m.get("payload", {})

        # Already generated → show card in MODAL without changing stage
        if is_generated:
            if cached_path and Path(cached_path).exists():
                import base64 as _b64
                with open(cached_path, "rb") as f:
                    ext = Path(cached_path).suffix.lower().replace(".", "")
                    mime = f"image/{ext}" if ext != "jpg" else "image/jpeg"
                    encoded = _b64.b64encode(f.read()).decode()
                    src = f"data:{mime};base64,{encoded}"
                
                modal_content = html.Img(src=src, className="img-fluid rounded", style={"maxHeight": "80vh", "boxShadow": "0 20px 40px rgba(0,0,0,0.5)"})
                return no_update, no_update, no_update, no_update, no_update, True, modal_content
            
            # If we thought it was generated but can't find path, don't open editor if we are in 'Past' mode
            # unless the user explicitly wants to generate a NEW one (handled below).
            # For now, if path is missing, we allow falling through to editor as a fallback.

        # Only handle card-type milestones
        if m_type not in ("pre-match", "post-match"):
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update

        card_type = m_type
        import json as _json

        draft_path = resolve_player_cards_path(player_id, milestone_id, "card_editor.json")
        saved_draft = None
        if draft_path and draft_path.exists():
            try:
                saved_draft = _json.loads(draft_path.read_text("utf-8"))
            except Exception:
                saved_draft = None

        from utils.image_processing import get_player_album
        album = get_player_album(player_id)

        # Render Studio Layout IMMEDIATELY
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
                "venue": payload.get("venue") or payload.get("stadium"),
                "score": payload.get("score") or payload.get("result"),
                "result": payload.get("result"),
                "rating": payload.get("rating"),
                "started": payload.get("started"),
            }

            if saved_draft:
                editor_state = saved_draft
                # Always clear transient generation flags so loading a draft
                # never auto-triggers the AI agent.
                editor_state["needs_ai"] = False
                editor_state["needs_background_refresh"] = False
                editor_state["generating"] = False
                editor_state["editor_active"] = True
            else:
                # Default photo selection (first available)
                default_photo_idx = album[0].get("idx") if album else None
                
                editor_state = {
                    "milestone_id": milestone_id,
                    "card_type": card_type,
                    "template": "A",
                    "format": "9:16", # DEFAULT FORMAT
                    "ai_proposal": {},
                    "layout_modifiers": {},
                    "selected_photo_idx": default_photo_idx, # AUTO-SELECT PHOTO
                    "needs_ai": True,   # Active for One-Shot flow
                    "generating": False,
                    "progress": {"phase": "Listo para diseñar", "pct": 0},
                    "last_saved": None,
                    "editor_active": True,
                }

            # Restore design history and last card from persistent metadata
            from callbacks.card_editor_callbacks import _build_preview_layout, _get_card_metadata
            meta = _get_card_metadata(str(player_id), str(milestone_id))
            existing_designs = meta.get("designs", [])
            last_card = meta.get("final_card") or (existing_designs[-1].get("path") if existing_designs and isinstance(existing_designs[-1], dict) else (existing_designs[-1] if existing_designs else None))
            editor_state["design_history"] = existing_designs
            if not editor_state.get("generated_card_path") and last_card:
                editor_state["generated_card_path"] = last_card
            if not editor_state.get("caption"):
                editor_state["caption"] = meta.get("final_caption", "")

            # Pre-render the initial preview (blueprint) so it's visible immediately
            initial_preview = _build_preview_layout(editor_state, {"album": album}, milestones_data)

            if card_type == "pre-match":
                studio = create_pre_game_card_studio(
                    milestone_id, match_context, album=album, selected_idx=editor_state.get("selected_photo_idx"), initial_preview=initial_preview
                )
            else:
                studio = create_performance_card_studio(
                    milestone_id, match_context, album=album, selected_idx=editor_state.get("selected_photo_idx"), initial_preview=initial_preview
                )

            # Populate store with THIS player's photos — prevents cross-player data bleed
            photos_store = {"album": album, "player_id": player_id}
            return studio, no_update, editor_state, {"display": "none"}, photos_store, False, None
        except Exception as exc:
            logger.error(f"handle_action_node_pill studio render error: {exc}")
            return (
                dbc.Alert("Error opening the Card Studio.", color="danger"),
                no_update,
                no_update,
                {"display": "none"},
                no_update,
                False,
                None,
            )

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
            ]
        )
        snapshot = {"type": "ai-insight", "title": title, "detail": detail}
        return stage_content, snapshot


def _serialize_milestones(milestones: list) -> list:
    """Converts datetime objects to ISO strings and adds unique IDs for Phase 3."""
    def _slug(value: object) -> str:
        raw = str(value or "").lower()
        raw = re.sub(r"\(\d+\.\)", "", raw)
        raw = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
        return raw or "na"

    result = []
    for m in milestones:
        entry = dict(m)
        date_obj = entry.get("date")
        if hasattr(date_obj, "isoformat"):
            entry["date"] = date_obj.isoformat()

        # Generate stable unique IDs per milestone.
        m_type = entry.get("type", "unknown")
        date_str = entry["date"][:10] if isinstance(entry["date"], str) else "no-date"
        payload = dict(entry.get("payload", {}))
        if hasattr(payload.get("date"), "isoformat"):
            payload["date"] = payload["date"].isoformat()

        if m_type == "career":
            season_key = payload.get("season", date_str)
            entry["id"] = f"career-{_slug(season_key)}"
        elif m_type in {"pre-match", "post-match"}:
            home_key = _slug(payload.get("home_team"))
            away_key = _slug(payload.get("away_team"))
            comp_key = _slug(payload.get("competition"))
            entry["id"] = f"{m_type}-{date_str}-{home_key}-vs-{away_key}-{comp_key}"
        elif m_type == "injury":
            entry["id"] = f"injury-{date_str}-{_slug(payload.get('type'))}"
        elif m_type == "ai-insight":
            entry["id"] = f"ai-insight-{date_str}-{_slug(payload.get('title') or entry.get('label'))}"
        else:
            entry["id"] = f"{m_type}-{date_str}-{_slug(entry.get('label'))}"

        # Ensure intelligence metrics are properly typed for JS (Task 3.2)
        if "rating" in payload and payload["rating"] is not None:
            try:
                payload["rating"] = float(payload["rating"])
            except (ValueError, TypeError):
                pass

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


def _get_player_sync_status(player_id: str) -> dict:
    """
    Returns a dict with sync state for the given player_id.

    States:
      'no_data'    — player exists but has no season stats and no TM id (just registered)
      'no_history' — TM id found but match-level history not yet fetched
      'ready'      — has season stats or match history (can render the portal)
    """
    try:
        from utils.db_engine import SessionFactory
        from models.db_models import Player, MatchHistory, PlayerSeasonStat
        from sqlalchemy import func, select

        session = SessionFactory()
        try:
            player = session.get(Player, player_id)
            if player is None:
                return {"state": "ready"}

            season_count = session.execute(
                select(func.count()).where(PlayerSeasonStat.player_id == player_id)
            ).scalar()

            match_count = session.execute(
                select(func.count()).where(MatchHistory.player_id == player_id)
            ).scalar()

            # Nothing at all — truly fresh registration, still being linked
            if season_count == 0 and match_count == 0 and not player.tm_id:
                return {"state": "no_data", "name": player.name}

            # TM id found but individual match history not yet fetched
            if player.tm_id and match_count == 0:
                return {"state": "no_history", "name": player.name}

            # Has league stats but no TM link → portal works but no match-level detail
            if season_count > 0 and match_count == 0 and not player.tm_id:
                return {"state": "no_tm_link", "name": player.name}

            return {"state": "ready"}
        finally:
            session.close()
    except Exception:
        return {"state": "ready"}


# ══════════════════════════════════════════════════════════════════════════════
# Career Intelligence Overlay Callbacks (T1 / T2 / IntersectionObserver)
# ══════════════════════════════════════════════════════════════════════════════

def register_career_intelligence_callbacks(app):
    """Registers T1/T2 overlay and IntersectionObserver bridge callbacks."""
    import json
    from datetime import date, timedelta
    from dash import Input, Output, State, callback, ctx, no_update, ALL
    from dash import clientside_callback
    from flask_login import current_user

    from utils.intelligence.overlay_surface import (
        PRESENTATION_CONTEXTUAL,
        PRESENTATION_CRITICAL,
        build_overlay_inbox_entry,
        resolve_stage_overlay_surface,
    )
    from layouts.components.ai_overlay import render_contextual_overlay, render_critical_overlay

    # ── Shared career overlay runtime ───────────────────────────────────────

    @app.callback(
        Output("stage-overlay-primary-store", "data"),
        Output("stage-overlay-queue-store", "data"),
        Output("insight-session-state", "data"),
        Input("timeline-context-store", "data"),
        Input("portal-data-store", "data"),
        Input("career-stage-analysis-store", "data"),
        Input("season-stage-analysis-store", "data"),
        Input("prematch-stage-analysis-store", "data"),
        Input("postmatch-stage-analysis-store", "data"),
        State("insight-session-state", "data"),
        prevent_initial_call=False,
    )
    def evaluate_career_signals(
        timeline_context,
        portal_data,
        career_stage_analysis,
        season_stage_analysis,
        prematch_stage_analysis,
        postmatch_stage_analysis,
        session_state,
    ):
        """
        Runs the shared overlay evaluator for the active surface.
        """
        try:
            active_stage = _active_overlay_stage_name(timeline_context)
            if not active_stage:
                return None, [], no_update

            if not portal_data:
                logger.info("Stage overlay skipped portal_data_missing stage=%s", active_stage)
                return None, [], no_update

            stage_name, resolved_surface, active_player_id, player_name = _resolve_active_overlay_surface(
                timeline_context,
                portal_data,
                career_stage_analysis,
                season_stage_analysis,
                prematch_stage_analysis,
                postmatch_stage_analysis,
            )
            if not stage_name:
                return None, [], no_update

            normalized_session_state = _reset_career_history_for_player_if_needed(
                session_state,
                player_id=active_player_id,
            )
            normalized_session_state = _reset_player_insight_history_if_needed(
                normalized_session_state,
                player_id=active_player_id,
            )
            normalized_session_state["history"] = _compact_stage_history_entries(
                list(normalized_session_state.get("history") or []),
                stage=stage_name,
                player_id=active_player_id,
            )
            current_season = str(
                ((timeline_context or {}).get("payload") or {}).get("season")
                or (portal_data.get("career_phase") or {}).get("current_season")
                or ""
            )
            today = date.today().isoformat()

            if not list(resolved_surface.get("candidates") or []):
                logger.info(
                    "Stage overlay evaluated player=%s season=%s stage=%s discoveries=0",
                    player_name,
                    current_season,
                    stage_name,
                )
                return None, [], {
                    **normalized_session_state,
                    "season_at_eval": current_season,
                    "eval_date": today,
                }

            logger.info(
                "Stage overlay resolved candidates player=%s stage=%s details=%s",
                player_name,
                stage_name,
                [
                    {
                        "signal_id": str(candidate.get("signal_id") or ""),
                        "novelty_key": str(candidate.get("novelty_key") or ""),
                        "tier": str(candidate.get("presentation_tier") or ""),
                        "priority": candidate.get("priority"),
                        "confidence": candidate.get("confidence"),
                    }
                    for candidate in list(resolved_surface.get("candidates") or [])
                ],
            )
            dismissed_keys = _dismissed_overlay_keys(
                normalized_session_state,
                stage=stage_name,
                player_id=active_player_id,
            )
            if dismissed_keys:
                logger.info(
                    "Stage overlay suppressing dismissed entries stage=%s count=%s",
                    stage_name,
                    len(dismissed_keys),
                )
                filtered_candidates = [
                    candidate
                    for candidate in list(resolved_surface.get("candidates") or [])
                    if str(candidate.get("signal_id") or "") not in dismissed_keys
                    and str(candidate.get("novelty_key") or "") not in dismissed_keys
                ]
                logger.info(
                    "Stage overlay filtered candidates player=%s stage=%s details=%s",
                    player_name,
                    stage_name,
                    [
                        {
                            "signal_id": str(candidate.get("signal_id") or ""),
                            "novelty_key": str(candidate.get("novelty_key") or ""),
                            "tier": str(candidate.get("presentation_tier") or ""),
                        }
                        for candidate in filtered_candidates
                    ],
                )
                resolved_surface = resolve_stage_overlay_surface(
                    stage_name,
                    {"candidates": [candidate.get("raw_candidate") or candidate for candidate in filtered_candidates]},
                )
            primary_overlay = None
            contextual_queue = []
            primary_candidate = dict(resolved_surface.get("primary_candidate") or {})
            if primary_candidate and primary_candidate.get("presentation_tier") == PRESENTATION_CRITICAL:
                primary_overlay = primary_candidate
            contextual_queue = _career_visible_overlay_queue(resolved_surface)

            logger.info(
                "Stage overlay evaluated player=%s season=%s stage=%s candidates=%s primary_tier=%s queue=%s",
                player_name,
                current_season,
                stage_name,
                len(list(resolved_surface.get("candidates") or [])),
                str(primary_candidate.get("presentation_tier") or "none"),
                len(contextual_queue),
            )

            new_session_state = {
                **normalized_session_state,
                "season_at_eval": current_season,
                "eval_date": today,
                "t1_dismissed_this_session": False,
            }
            return primary_overlay, contextual_queue, new_session_state

        except Exception as exc:
            logger.exception("Career overlay evaluation error: %s", exc)
            return None, [], no_update

    @app.callback(
        Output("portal-overlay-store", "data"),
        Input("insight-inbox-btn", "n_clicks"),
        Input({"type": "career-evidence-trigger", "key": ALL, "source": ALL, "index": ALL, "focus_metric": ALL}, "n_clicks"),
        Input({"type": "stage-overlay-critical-btn", "action": ALL, "stage": ALL, "signal_id": ALL, "evidence_key": ALL}, "n_clicks"),
        Input({"type": "stage-overlay-contextual-cta", "index": ALL, "stage": ALL, "signal_id": ALL, "evidence_key": ALL}, "n_clicks"),
        Input("career-evidence-modal-close", "n_clicks"),
        State("portal-overlay-store", "data"),
        prevent_initial_call=True,
    )
    def update_portal_overlay_state(_, __, ___, ____, _____, overlay_state):
        """Uses a single overlay state so inbox and evidence modal cannot coexist."""
        triggered_id = ctx.triggered_id
        current = overlay_state or {"type": "none"}
        trigger_value = ctx.triggered[0].get("value", 0) if ctx.triggered else 0

        # Dash can fire callbacks when dynamic components mount with n_clicks=0.
        # Ignore any non-user interaction here so overlays don't auto-open on load.
        if not trigger_value:
            return no_update

        if triggered_id == "career-evidence-modal-close":
            return {"type": "none"}

        if triggered_id == "insight-inbox-btn":
            return {"type": "none"} if current.get("type") == "inbox" else {"type": "inbox"}

        if not isinstance(triggered_id, dict):
            return no_update

        if triggered_id.get("type") == "career-evidence-trigger":
            return {
                "type": "evidence",
                "evidence_key": resolve_career_surface_evidence_key(triggered_id.get("key", "career_arc")),
                "focus_metric": str(triggered_id.get("focus_metric", "") or ""),
                "source": triggered_id.get("source", "dashboard"),
                "nonce": ctx.triggered[0]["value"],
            }
        if triggered_id.get("type") == "stage-overlay-critical-btn" and triggered_id.get("action") == "cta":
            if str(triggered_id.get("stage") or "").strip().lower() != "career":
                return no_update
            return {
                "type": "evidence",
                "evidence_key": resolve_career_surface_evidence_key(triggered_id.get("evidence_key", "career_arc")),
                "focus_metric": "",
                "source": "overlay-critical",
                "nonce": ctx.triggered[0]["value"],
            }
        if triggered_id.get("type") == "stage-overlay-contextual-cta":
            if str(triggered_id.get("stage") or "").strip().lower() != "career":
                return no_update
            return {
                "type": "evidence",
                "evidence_key": resolve_career_surface_evidence_key(triggered_id.get("evidence_key", "career_arc")),
                "focus_metric": "",
                "source": "overlay-contextual",
                "nonce": ctx.triggered[0]["value"],
            }
        return no_update

    @app.callback(
        Output("career-evidence-modal-title", "children"),
        Output("career-evidence-modal-body", "children"),
        Output("career-evidence-modal", "is_open"),
        Output("insight-inbox-offcanvas", "is_open"),
        Input("portal-overlay-store", "data"),
        prevent_initial_call=False,
    )
    def render_portal_overlay_state(overlay_state):
        """Renders either the inbox or the evidence modal from one shared overlay state."""
        state = overlay_state or {"type": "none"}
        overlay_type = state.get("type", "none")

        if overlay_type == "inbox":
            return no_update, no_update, False, True

        if overlay_type != "evidence":
            return no_update, no_update, False, False

        player_id, player_name, _ = _get_active_player_identity()
        if not player_id or not player_name:
            return "Evidence", html.P("Player evidence is not available.", className="text-muted small mb-0"), True, False

        try:
            payload = render_career_evidence_view(
                state.get("evidence_key", "career_arc"),
                player_name,
                player_id,
                focus_metric=str(state.get("focus_metric", "") or ""),
            )
            return payload["title"], payload["content"], True, False
        except Exception as exc:
            logger.warning(f"career evidence modal error: {exc}")
            return "Evidence", html.P("Detailed evidence is not available right now.", className="text-muted small mb-0"), True, False

    @app.callback(
        Output("career-kpi-trend-modal-title", "children"),
        Output("career-kpi-trend-modal-body", "children"),
        Output("career-kpi-trend-modal", "is_open"),
        Input({"type": "career-kpi-trigger", "metric_key": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def render_career_kpi_trend_modal(_):
        triggered_id = ctx.triggered_id
        trigger_value = ctx.triggered[0].get("value", 0) if ctx.triggered else 0
        if not isinstance(triggered_id, dict) or triggered_id.get("type") != "career-kpi-trigger" or not trigger_value:
            return no_update, no_update, no_update

        player_id, player_name, _ = _get_active_player_identity()
        if not player_id or not player_name:
            return "KPI Trend", html.P("Player KPI history is not available.", className="text-muted small mb-0"), True

        try:
            payload = _build_career_kpi_trend_view(player_name, player_id, triggered_id.get("metric_key", "matches"))
            return payload["title"], payload["content"], True
        except Exception as exc:
            logger.warning(f"career kpi trend modal error: {exc}")
            return "KPI Trend", html.P("Trend detail is not available right now.", className="text-muted small mb-0"), True

    @app.callback(
        Output("season-profile-map-modal", "is_open"),
        Input("season-profile-map-open", "n_clicks"),
        Input("season-profile-map-close", "n_clicks"),
        State("season-profile-map-modal", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_season_profile_map_modal(open_clicks, close_clicks, is_open):
        trigger_value = ctx.triggered[0].get("value", 0) if ctx.triggered else 0
        if not trigger_value:
            return no_update
        return not bool(is_open)

    # ── 7.2 T1 render/dismiss callback ──────────────────────────────────────

    @app.callback(
        Output("stage-overlay-critical-container", "children"),
        Output("stage-overlay-critical-container", "style"),
        Output("insight-session-state", "data", allow_duplicate=True),
        Output("season-overlay-dismissed-signal", "data", allow_duplicate=True),
        Input("stage-overlay-primary-store", "data"),
        Input({"type": "stage-overlay-critical-btn", "action": ALL, "stage": ALL, "signal_id": ALL, "evidence_key": ALL}, "n_clicks"),
        State("timeline-context-store", "data"),
        State("insight-session-state", "data"),
        prevent_initial_call=True,
    )
    def render_critical_overlay_callback(primary_data, btn_clicks, timeline_context, session_state):
        """
        Renders the T1 overlay when the store is populated.
        Dismiss/CTA click → hide overlay + update session state.
        CTA navigation is handled by a clientside callback.
        """
        triggered_id = ctx.triggered_id
        active_stage = _active_overlay_stage_name(timeline_context)

        if not active_stage:
            return None, {"display": "none"}, no_update, no_update

        if isinstance(triggered_id, dict) and triggered_id.get("type") == "stage-overlay-critical-btn":
            if triggered_id.get("action") != "dismiss":
                return no_update, no_update, no_update, no_update
            updated_state = dict(session_state or {})
            updated_state["t1_dismissed_this_session"] = True
            # Append to history so Insight Inbox can display it
            if primary_data:
                from datetime import datetime as _dt
                signal_stage = str((primary_data or {}).get("stage") or active_stage or "").strip().lower()
                player_id = str(getattr(current_user, "player_id", "") or "")
                history = list(updated_state.get("history", []))
                entry = build_overlay_inbox_entry(primary_data, surfaced=True)
                entry["timestamp"] = _dt.utcnow().isoformat()
                entry["player_id"] = player_id
                if signal_stage == "career":
                    entry["cta_context"]["evidence_key"] = resolve_career_surface_evidence_key(
                        primary_data.get("evidence_key", "career_arc"),
                        label=primary_data.get("title", ""),
                    )
                entry["cta_context"]["novelty_key"] = str(primary_data.get("novelty_key") or "")
                entry["cta_context"]["player_id"] = player_id
                updated_state["history"] = _upsert_stage_history_entry(
                    history,
                    entry,
                    stage=signal_stage,
                    player_id=player_id,
                )
            logger.info(
                "Stage critical overlay dismissed stage=%s signal_id=%s",
                str((primary_data or {}).get("stage") or active_stage or ""),
                str((primary_data or {}).get("signal_id") or ""),
            )
            return None, {"display": "none"}, updated_state, int(time.time() * 1000)

        if not primary_data:
            logger.info("Stage critical overlay hidden stage=%s reason=no_signal", active_stage)
            return None, {"display": "none"}, no_update, no_update

        logger.info(
            "Stage critical overlay rendered stage=%s signal_id=%s",
            str((primary_data or {}).get("stage") or active_stage or ""),
            str((primary_data or {}).get("signal_id") or ""),
        )
        return render_critical_overlay(primary_data), {"display": "block"}, no_update, no_update

    # ── 7.3 T2 queue management callback ────────────────────────────────────

    @app.callback(
        Output("stage-overlay-contextual-container", "children"),
        Output("stage-overlay-queue-store", "data", allow_duplicate=True),
        Output("insight-session-state", "data", allow_duplicate=True),
        Output("season-overlay-dismissed-signal", "data", allow_duplicate=True),
        Input("stage-overlay-queue-store", "data"),
        Input({"type": "stage-overlay-contextual-dismiss", "index": ALL}, "n_clicks"),
        State("timeline-context-store", "data"),
        State("insight-session-state", "data"),
        prevent_initial_call=True,
    )
    def render_contextual_overlays(queue, dismiss_clicks_list, timeline_context, session_state):
        """
        Renders the next non-critical overlay card from the queue.
        Dismiss [×] click removes that card, appends it to history, and surfaces the next queued signal.
        """
        triggered_id = ctx.triggered_id
        active_stage = _active_overlay_stage_name(timeline_context)

        queue = list(queue or [])
        updated_session = no_update
        dismissed_signal = no_update

        if not active_stage:
            return [], queue, no_update, no_update

        # Handle dismiss click
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "stage-overlay-contextual-dismiss":
            idx = triggered_id.get("index", 0)
            if idx < len(queue):
                dismissed = queue.pop(idx)
                # Append dismissed signal to insight history
                from datetime import datetime as _dt
                signal_stage = str((dismissed or {}).get("stage") or active_stage or "").strip().lower()
                player_id = str(getattr(current_user, "player_id", "") or "")
                updated_session = dict(session_state or {})
                history = list(updated_session.get("history", []))
                entry = build_overlay_inbox_entry(dismissed, surfaced=True)
                entry["timestamp"] = _dt.utcnow().isoformat()
                entry["player_id"] = player_id
                if signal_stage == "career":
                    entry["cta_context"]["evidence_key"] = resolve_career_surface_evidence_key(
                        dismissed.get("evidence_key", "career_arc"),
                        label=dismissed.get("title", ""),
                    )
                entry["cta_context"]["novelty_key"] = str(dismissed.get("novelty_key") or "")
                entry["cta_context"]["player_id"] = player_id
                updated_session["history"] = _upsert_stage_history_entry(
                    history,
                    entry,
                    stage=signal_stage,
                    player_id=player_id,
                )
                dismissed_signal = int(time.time() * 1000)
                logger.info(
                    "Stage non_critical overlay dismissed stage=%s signal_id=%s remaining=%s",
                    signal_stage,
                    str(dismissed.get("signal_id") or ""),
                    len(queue),
                )

        if not queue:
            logger.info("Stage non_critical overlay hidden stage=%s reason=queue_empty", active_stage)
            return [], queue, updated_session, dismissed_signal

        # Render only the next queued card so the stage shows one visible
        # non-critical overlay at a time, aligned with the shared dismiss flow.
        visible = queue[:1]
        cards = []
        for i, sig_data in enumerate(visible):
            cards.append(render_contextual_overlay(sig_data, signal_index=i))

        logger.info(
            "Stage non_critical overlay rendered stage=%s signal_id=%s visible=%s queued=%s",
            str((visible[0] or {}).get("stage") or active_stage or ""),
            str((visible[0] or {}).get("signal_id") or ""),
            len(visible),
            len(queue),
        )

        return cards, queue, updated_session, dismissed_signal

    # ── 7.4 T2 career-context gate ──────────────────────────────────────────

    @app.callback(
        Output("stage-overlay-contextual-container", "style"),
        Input("timeline-context-store", "data"),
        Input("stage-overlay-primary-store", "data"),
        Input("insight-session-state", "data"),
        prevent_initial_call=True,
    )
    def gate_contextual_overlay_by_context(context, primary_data, session_state):
        """Hide contextual overlays outside the dashboard/career layer and while a critical alert is active."""
        if _active_overlay_stage_name(context):
            dismissed = bool((session_state or {}).get("t1_dismissed_this_session"))
            if primary_data and not dismissed:
                return {"display": "none"}
            return {"display": "block"}
        return {"display": "none"}

    # ── 13.3 Insight Inbox: Offcanvas toggle + badge count ──────────────────

    @app.callback(
        Output("insight-inbox-count", "children"),
        Output("insight-inbox-count", "style"),
        Input("insight-session-state", "data"),
        Input("timeline-context-store", "data"),
        prevent_initial_call=True,
    )
    def update_insight_inbox_badge(session_state, timeline_context):
        """Updates the inbox badge count independently from overlay open state."""
        entries = collect_insight_inbox_entries(session_state, timeline_context)
        count = len(entries)
        badge_text = str(count) if count > 0 else ""
        badge_style = {} if count > 0 else {"display": "none"}
        return badge_text, badge_style

    # ── 13.5 Insight Inbox: body render callback ─────────────────────────────

    @app.callback(
        Output("insight-inbox-body", "children"),
        Input("insight-session-state", "data"),
        Input("timeline-context-store", "data"),
    )
    def render_insight_inbox_body(session_state, timeline_context):
        """Renders dismissed insight history as inbox items in the Offcanvas."""
        entries = collect_insight_inbox_entries(session_state, timeline_context)
        return render_insight_inbox_entries(entries)

    @app.callback(
        Output("insight-session-state", "data", allow_duplicate=True),
        Output("season-overlay-dismissed-signal", "data", allow_duplicate=True),
        Input(
            {
                "type": "stage-overlay-prominent-dismiss",
                "signal_id": ALL,
                "evidence_key": ALL,
                "title": ALL,
                "body": ALL,
                "anchor": ALL,
                "tier": ALL,
            },
            "n_clicks",
        ),
        State("insight-session-state", "data"),
        prevent_initial_call=True,
    )
    def dismiss_season_prominent_overlay(_, session_state):
        """Dismiss the visible season prominent surface and archive it to inbox history."""
        trigger_value = ctx.triggered[0].get("value", 0) if ctx.triggered else 0
        triggered_id = ctx.triggered_id
        if not trigger_value or not isinstance(triggered_id, dict):
            return no_update, no_update

        updated_state = dict(session_state or {})
        history = list(updated_state.get("history", []))
        signal_id = str(triggered_id.get("signal_id") or "").strip()
        evidence_key = str(triggered_id.get("evidence_key") or "").strip()
        title = str(triggered_id.get("title") or "").strip()

        duplicate = next(
            (
                entry
                for entry in history
                if str(entry.get("stage") or "").strip().lower() == "season"
                and (
                    str((entry.get("cta_context") or {}).get("signal_id") or "").strip() == signal_id
                    or str((entry.get("cta_context") or {}).get("evidence_key") or "").strip() == evidence_key
                    or str(entry.get("title") or "").strip() == title
                )
            ),
            None,
        )
        if duplicate is None:
            from datetime import datetime as _dt

            history.append(
                {
                    "stage": "season",
                    "player_id": str(getattr(current_user, "player_id", "") or ""),
                    "tier": str(triggered_id.get("tier") or "prominent"),
                    "title": title,
                    "body": str(triggered_id.get("body") or ""),
                    "timestamp": _dt.utcnow().isoformat(),
                    "anchor": str(triggered_id.get("anchor") or ""),
                    "cta_context": {
                        "signal_id": signal_id,
                        "evidence_key": evidence_key,
                        "player_id": str(getattr(current_user, "player_id", "") or ""),
                    },
                    "surfaced": True,
                }
            )
        updated_state["history"] = history
        logger.info("Season prominent overlay dismissed signal_id=%s", signal_id)
        return updated_state, int(time.time() * 1000)

    @app.callback(
        Output("stage-content", "children", allow_duplicate=True),
        Input("season-overlay-dismissed-signal", "data"),
        State("insight-session-state", "data"),
        State("timeline-context-store", "data"),
        State("season-stage-analysis-store", "data"),
        prevent_initial_call=True,
    )
    def refresh_stage_after_overlay_session_change(_, session_state, timeline_context, season_stage_analysis):
        """Refresh the active season stage only when a season overlay is actually dismissed.
        Decoupled from insight-session-state to avoid re-renders on every overlay dispatch."""
        if not timeline_context or str(timeline_context.get("type") or "") != "career":
            return no_update
        return _render_stage_content_for_context_with_session(
            timeline_context,
            session_state,
            season_stage_analysis,
            None,
            None,
        )

    # ── Loading Color System: pre-flight clientside callbacks ────────────────
    # These fire before the server callbacks (no network round-trip) so the
    # stage-shell data-loading-type attribute is set while data-dash-is-loading
    # becomes true, giving the dot the correct color immediately.

    # Milestone/card clicks → data (amber)
    app.clientside_callback(
        """function() {
            var el = document.getElementById('stage-shell');
            if (el) el.dataset.loadingType = 'data';
            return window.dash_clientside.no_update;
        }""",
        Output("stage-loading-type-sync-dummy", "data"),
        Input({"type": "timeline-milestone", "index": ALL}, "n_clicks"),
        Input({"type": "milestone-detail-btn", "index": ALL}, "n_clicks"),
        Input({"type": "milestone-header", "index": ALL}, "n_clicks"),
        Input({"type": "action-node", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )

    # AI insight card clicks → ai (purple)
    app.clientside_callback(
        """function() {
            var el = document.getElementById('stage-shell');
            if (el) el.dataset.loadingType = 'ai';
            return window.dash_clientside.no_update;
        }""",
        Output("stage-loading-type-sync-dummy", "data", allow_duplicate=True),
        Input({"type": "ai-insight-card", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )

    # career-dashboard-brief-store update → ai (purple; AI results rendering)
    app.clientside_callback(
        """function() {
            var el = document.getElementById('stage-shell');
            if (el) el.dataset.loadingType = 'ai';
            return window.dash_clientside.no_update;
        }""",
        Output("stage-loading-type-sync-dummy", "data", allow_duplicate=True),
        Input("career-dashboard-brief-store", "data"),
        prevent_initial_call=True,
    )

    # Phase 2 pre-flight: portal-data-store ready → data (amber)
    app.clientside_callback(
        """function() {
            var el = document.getElementById('stage-shell');
            if (el) el.dataset.loadingType = 'data';
            return window.dash_clientside.no_update;
        }""",
        Output("stage-loading-type-sync-dummy", "data", allow_duplicate=True),
        Input("portal-data-store", "data"),
        prevent_initial_call=True,
    )

    # Bug B fix: reset data-loading-type after stage-content finishes loading.
    # Without this, the color from the previous action persists and the next
    # untagged load (e.g. player change) shows the wrong color instead of blue.
    app.clientside_callback(
        """function() {
            var el = document.getElementById('stage-shell');
            if (el) el.dataset.loadingType = '';
            return window.dash_clientside.no_update;
        }""",
        Output("stage-loading-type-sync-dummy", "data", allow_duplicate=True),
        Input("stage-content", "children"),
        prevent_initial_call=True,
    )

    # Bug A fix: set data-timeline-loading-type before render_timeline_milestones fires.
    # null/undefined store → first load (interface building) → blue (ui).
    # existing data → data refresh from polling or pagination → amber (data).
    app.clientside_callback(
        """function(data) {
            var el = document.getElementById('timeline-milestones');
            if (el) el.dataset.timelineLoadingType = (data === null || data === undefined) ? 'ui' : 'data';
            return window.dash_clientside.no_update;
        }""",
        Output("stage-loading-type-sync-dummy", "data", allow_duplicate=True),
        Input("milestones-data-store", "data"),
        prevent_initial_call="initial_duplicate",
    )
