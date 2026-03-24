# ABOUTME: Callbacks for the Player Portal Phase 2 SPA navigation architecture.
# ABOUTME: Handles Timeline population, milestone selection, Stage rendering, sliding panel navigation, and year-scroll navigation.

import logging
from dash import Input, Output, State, callback, html, no_update, ALL, ctx, dcc
import dash_bootstrap_components as dbc
from flask_login import current_user

from data.aggregators.timeline_aggregator import TimelineAggregator
from utils.stage_helpers import render_post_match, render_pre_match, render_career_insights
from utils.app_context import get_hong_kong_data_manager

logger = logging.getLogger(__name__)

_ICON_MAP = {
    "pre-match": "bi-calendar-plus",
    "post-match": "bi-bar-chart-fill",
    "career":     "bi-trophy-fill",
}

_COLOR_MAP = {
    "pre-match": "primary",
    "post-match": "success",
    "career":     "warning",
}

_GLASS_CLASS_MAP = {
    "pre-match": "glass-prematch",
    "career":    "glass-career",
}


def _get_glass_class(milestone: dict) -> str:
    """Returns the glass context modifier class for a milestone."""
    m_type = milestone.get("type", "career")
    if m_type == "post-match":
        status = milestone.get("confirmation_status") or milestone.get("payload", {}).get("confirmation_status", "")
        return "glass-success" if status == "Confirmed" else "glass-prematch"
    return _GLASS_CLASS_MAP.get(m_type, "glass-career")


def _build_collapse_content(m_type: str, payload: dict, matches: list) -> html.Div:
    """Builds the type-specific collapse content for a milestone card."""
    if m_type == "career":
        if not matches:
            return html.Div(
                html.Small("Sin partidos registrados.", className="text-muted fst-italic"),
                className="px-3 pb-2",
            )
        rows = []
        for m in matches:
            goals = m.get("goals", 0)
            rows.append(html.Div(
                [
                    html.Small(m.get("date", ""), className="text-muted", style={"minWidth": "80px"}),
                    html.Small(
                        m.get("opponent", "Rival"),
                        className="flex-grow-1 text-truncate px-2 small",
                    ),
                    html.Small(f"{m.get('minutes_played', 0)}'", className="text-muted", style={"minWidth": "32px"}),
                    html.Small(
                        f"⚽{goals}" if goals else "",
                        className="text-warning fw-bold",
                        style={"minWidth": "28px"},
                    ),
                ],
                className="d-flex align-items-center border-bottom border-secondary py-1",
            ))
        return html.Div(rows, className="px-3 pb-2 pt-1")

    if m_type == "pre-match":
        details = []
        if payload.get("kickoff_display"):
            details.append(html.Small([html.I(className="bi bi-clock me-1"), payload["kickoff_display"]], className="text-muted me-3"))
        if payload.get("stadium"):
            details.append(html.Small([html.I(className="bi bi-geo-alt me-1"), payload["stadium"]], className="text-muted me-3"))
        if payload.get("competition"):
            details.append(html.Small([html.I(className="bi bi-trophy me-1"), payload["competition"]], className="text-muted"))
        return html.Div(details or [html.Small("Sin detalles.", className="text-muted fst-italic")],
                        className="d-flex flex-wrap gap-2 px-3 pb-2 pt-1")

    # post-match
    stats = payload.get("player_stats", {})
    perf = stats.get("performance_stats", {})
    minutes = perf.get("Minutes", payload.get("minutes_played", "—"))
    goals = perf.get("Goals", 0)
    assists = perf.get("Assists", 0)
    status = payload.get("confirmation_status", "")
    badge_color = "success" if status == "Confirmed" else "secondary"
    return html.Div(
        [
            html.Span(status, className=f"badge bg-{badge_color} me-2 small") if status else None,
            html.Small([html.I(className="bi bi-stopwatch me-1"), f"{minutes}'"], className="text-muted me-3"),
            html.Small([html.I(className="bi bi-bullseye me-1"), f"{goals} goles"], className="text-muted me-3"),
            html.Small([html.I(className="bi bi-arrow-up-right me-1"), f"{assists} asist."], className="text-muted"),
        ],
        className="d-flex flex-wrap align-items-center gap-2 px-3 pb-2 pt-1",
    )


def _render_milestone_item(milestone: dict, index: int) -> html.Div:
    """Renders a single timeline milestone as a glass card.

    Level 1 header (always visible): icon · label · date · Ver Detalle · chevron
    Collapse: type-specific content (match list, fixture details, or match stats)
    """
    m_type = milestone.get("type", "career")
    icon_cls = _ICON_MAP.get(m_type, "bi-circle")
    color = _COLOR_MAP.get(m_type, "secondary")
    glass_cls = _get_glass_class(milestone)
    payload = milestone.get("payload", {})
    matches = payload.get("matches", [])

    date_str = ""
    year_str = ""
    if milestone.get("date"):
        try:
            from datetime import datetime
            if isinstance(milestone["date"], str):
                dt = datetime.fromisoformat(milestone["date"].replace('Z', '+00:00'))
            else:
                dt = milestone["date"]
            date_str = dt.strftime("%d/%m/%Y")
            year_str = str(dt.year)
        except Exception:
            date_str = str(milestone["date"])[:10]
            year_str = str(milestone["date"])[:4]

    # ── Level 1 header (always visible) ─────────────────────────────────
    header_row = html.Div(
        [
            html.Span(
                html.I(className=f"bi {icon_cls}"),
                className=f"badge rounded-pill bg-{color} me-2 flex-shrink-0",
                id={"type": "timeline-milestone", "index": index},
                n_clicks=0,
                style={"cursor": "pointer"},
            ),
            html.Div(
                [
                    html.Span(milestone.get("label", ""), className="small fw-semibold"),
                    html.Small(date_str, className="text-muted d-block"),
                ],
                className="flex-grow-1",
                id={"type": "timeline-milestone-text", "index": index},
                style={"cursor": "pointer"},
            ),
            dbc.Button(
                [html.I(className="bi bi-arrow-right-circle me-1"), "Ver Detalle"],
                id={"type": "milestone-detail-btn", "index": index},
                color=color,
                outline=True,
                size="sm",
                className="flex-shrink-0 me-1",
                n_clicks=0,
            ),
            html.I(
                className="bi bi-chevron-down flex-shrink-0 small text-muted milestone-expand-icon",
                id={"type": "milestone-toggle", "index": index},
                style={"cursor": "pointer", "padding": "4px"},
                n_clicks=0,
            ),
        ],
        className="d-flex align-items-center gap-1 py-2 px-2",
    )

    # ── Single collapse per card ─────────────────────────────────────────
    milestone_collapse = dbc.Collapse(
        _build_collapse_content(m_type, payload, matches),
        id={"type": "milestone-collapse", "index": index},
        is_open=False,
    )

    year_cls = f" year-{year_str}" if year_str else ""
    return html.Div(
        [header_row, milestone_collapse],
        className=f"glass-card {glass_cls} mb-2{year_cls}",
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
    # (task 7.1 — migrated to year-navigator-pills ID)                   #
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
            {str(m.get("date", ""))[:4] for m in milestones_data if m.get("date")},
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
    # milestones-data-store → timeline-milestones (continuous, no filter) #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("timeline-milestones", "children"),
        Input("milestones-data-store", "data"),
        prevent_initial_call=False,
    )
    def render_timeline_milestones(milestones_data):
        """Renders all glass-card milestone items continuously (no year filter)."""
        if not milestones_data:
            return no_update

        return [_render_milestone_item(m, i) for i, m in enumerate(milestones_data)]

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
    def select_milestone(milestone_clicks, detail_clicks, selected_year, milestones_data):
        """Updates the context store when a milestone icon, Ver Detalle, or year chip is clicked."""
        if not ctx.triggered_id or not milestones_data:
            return no_update

        triggered = ctx.triggered_id

        # Year chip: find career milestone for the selected year
        if triggered == "selected-year-store":
            if not selected_year:
                return no_update
            for m in milestones_data:
                if m.get("type") == "career" and str(m.get("date", ""))[:4] == str(selected_year):
                    return {"type": "career", "payload": m["payload"]}
            return no_update

        if isinstance(triggered, dict) and triggered.get("type") in (
            "timeline-milestone",
            "milestone-detail-btn",
        ):
            index = triggered["index"]
            if 0 <= index < len(milestones_data):
                m = milestones_data[index]
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

        user_role = getattr(current_user, "role", "player") if current_user else "player"
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
                return dbc.Alert(f"Tipo de contexto desconocido: {m_type}", color="warning")
        except Exception as e:
            logger.error(f"update_stage error: {e}")
            return dbc.Alert("Error al renderizar el escenario.", color="danger")

    # ------------------------------------------------------------------ #
    # Milestone expand/collapse toggle — manual + year-chip auto-expand   #
    # (all milestones have milestone-collapse, so index maps 1:1)         #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output({"type": "milestone-collapse", "index": ALL}, "is_open"),
        Input({"type": "milestone-toggle", "index": ALL}, "n_clicks"),
        Input("selected-year-store", "data"),
        State({"type": "milestone-collapse", "index": ALL}, "is_open"),
        State("milestones-data-store", "data"),
        prevent_initial_call=True,
    )
    def toggle_milestone(n_clicks_list, selected_year, is_open_list, milestones_data):
        """Toggles Level 2 collapse; year chip auto-expands the matching career card."""
        if not ctx.triggered_id:
            return no_update

        triggered = ctx.triggered_id

        # Year chip: open matching career card (multi-expand — don't close others)
        if triggered == "selected-year-store":
            if not selected_year or not milestones_data:
                return no_update
            result = list(is_open_list)
            for i, m in enumerate(milestones_data):
                if i < len(result):
                    year = str(m.get("date", ""))[:4]
                    if m.get("type") == "career" and year == str(selected_year):
                        result[i] = True
            return result

        # Manual toggle
        if isinstance(triggered, dict) and triggered.get("type") == "milestone-toggle":
            triggered_index = triggered["index"]
            result = list(is_open_list)
            if triggered_index < len(result):
                result[triggered_index] = not result[triggered_index]
            return result

        return no_update

    # ------------------------------------------------------------------ #
    # tasks 6.1 + 6.2  Clientside sliding panel navigation               #
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
    # task 6.3  Back button visibility from portal-panel-state            #
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


def _serialize_milestones(milestones: list) -> list:
    """Converts datetime objects to ISO strings for JSON serialization."""
    result = []
    for m in milestones:
        entry = dict(m)
        if hasattr(entry.get("date"), "isoformat"):
            entry["date"] = entry["date"].isoformat()
        payload = dict(entry.get("payload", {}))
        if hasattr(payload.get("date"), "isoformat"):
            payload["date"] = payload["date"].isoformat()
        entry["payload"] = payload
        result.append(entry)
    return result
