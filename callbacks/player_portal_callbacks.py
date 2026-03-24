# ABOUTME: Callbacks for the Player Portal Phase 3 interactive timeline with client-side expand/collapse and scroll-sync.
# ABOUTME: Handles Timeline population, milestone selection, Stage rendering, sliding panels, year-scroll, and Action Node gallery.

import logging
from dash import Input, Output, State, callback, html, no_update, ALL, ctx, dcc
import dash_bootstrap_components as dbc
from flask_login import current_user

from data.aggregators.timeline_aggregator import TimelineAggregator
from utils.stage_helpers import (
    render_post_match,
    render_pre_match,
    render_career_insights,
    get_cached_image_path,
    render_image_gallery,
)
from utils.app_context import get_hong_kong_data_manager

logger = logging.getLogger(__name__)

_ICON_MAP = {
    "pre-match": "calendar-plus",
    "post-match": "bar-chart-2",
    "career":    "trophy",
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


def _lucide(name: str) -> html.I:
    """Returns a Lucide icon element."""
    return html.I(**{"data-lucide": name, "className": "lucide-inline-icon me-1"})


def _build_collapse_content(m_type: str, payload: dict, matches: list) -> html.Div:
    """Builds the type-specific collapse content for a milestone card."""
    if m_type == "career":
        if not matches:
            return html.Div(
                html.Small("Sin partidos registrados.", className="portal-text-muted fst-italic"),
                className="px-3 pb-2",
            )
        rows = []
        for m in matches:
            goals = m.get("goals", 0)
            rows.append(html.Div(
                [
                    html.Small(m.get("date", ""), className="portal-text-muted", style={"minWidth": "80px"}),
                    html.Small(
                        m.get("opponent", "Rival"),
                        className="flex-grow-1 text-truncate px-2 small",
                    ),
                    html.Small(f"{m.get('minutes_played', 0)}'", className="portal-text-muted", style={"minWidth": "32px"}),
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
            details.append(html.Small([_lucide("clock"), payload["kickoff_display"]], className="portal-text-muted me-3"))
        if payload.get("stadium"):
            details.append(html.Small([_lucide("map-pin"), payload["stadium"]], className="portal-text-muted me-3"))
        if payload.get("competition"):
            details.append(html.Small([_lucide("trophy"), payload["competition"]], className="portal-text-muted"))
        return html.Div(details or [html.Small("Sin detalles.", className="portal-text-muted fst-italic")],
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
            html.Small([_lucide("timer"), f"{minutes}'"], className="portal-text-muted me-3"),
            html.Small([_lucide("crosshair"), f"{goals} goles"], className="portal-text-muted me-3"),
            html.Small([_lucide("trending-up"), f"{assists} asist."], className="portal-text-muted"),
        ],
        className="d-flex flex-wrap align-items-center gap-2 px-3 pb-2 pt-1",
    )


def _render_milestone_item(milestone: dict, initial_open: bool = False) -> html.Div:
    """Renders a single timeline milestone as a Lucide-icon circle + connector + glass card.

    Structure: .timeline-event > [.event-node | .event-connector-h | .event-card.glass-card]
    The event-circle (inside event-node) carries the Lucide icon and doubles as the
    Action Node trigger for the image gallery (id=action-node kept for callback compat).
    """
    milestone_id = milestone.get("id", "unknown")
    m_type = milestone.get("type", "career")
    lucide_icon = _ICON_MAP.get(m_type, "circle")
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

    # ── Level 1 header: label + colored arrow (single action button) ──────
    header_row = html.Div(
        [
            html.Div(
                [
                    html.Span(milestone.get("label", ""), className="small fw-semibold"),
                    html.Small(date_str, className="portal-text-muted d-block"),
                ],
                className="flex-grow-1",
                id={"type": "timeline-milestone-text", "index": milestone_id},
                style={"cursor": "pointer"},
            ),
            # Colored arrow: opens detail stage panel (no duplicate chevron)
            html.Div(
                html.I(**{"data-lucide": "arrow-right-circle", "className": "lucide-detail-icon"}),
                id={"type": "milestone-detail-btn", "index": milestone_id},
                className=f"event-detail-btn event-detail-btn-{color} flex-shrink-0",
                n_clicks=0,
                title="Ver Detalle",
                style={"cursor": "pointer"},
            ),
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

    # ── Body: toggled by clientside expand-store (Phase 3) ───────────────
    body_style = {"display": "block"} if initial_open else {"display": "none"}
    milestone_body = html.Div(
        _build_collapse_content(m_type, payload, matches),
        id={"type": "milestone-body", "index": milestone_id},
        style=body_style,
    )

    year_cls = f" year-{year_str}" if year_str else ""
    return html.Div(
        className=f"timeline-event mb-2{year_cls}",
        children=[
            # Left axis: circle only — ::before draws line, ::after draws horizontal connector
            html.Div(
                className=f"event-node event-node-{color}",
                children=[event_circle, milestone_trigger],
            ),
            # Right: glass card — ::before draws horizontal connector stub
            # margin-left + margin-top create space for the visible L-connector
            html.Div(
                [header_row, milestone_body],
                className=f"event-card event-card-{color} glass-card {glass_cls}",
            ),
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
    # milestones-data-store → timeline-milestones (grouped by season)     #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("timeline-milestones", "children"),
        Output("timeline-expand-store", "data"),
        Input("milestones-data-store", "data"),
        prevent_initial_call=False,
    )
    def render_timeline_milestones(milestones_data):
        """
        Renders milestone items grouped by season in .season-section divs.
        Pre-expands the most recent season and pre-populates timeline-expand-store.
        """
        if not milestones_data:
            return no_update, no_update

        from collections import defaultdict
        groups = defaultdict(list)
        for m in milestones_data:
            year = str(m.get("date", ""))[:4] or "unknown"
            groups[year].append(m)

        sorted_years = sorted(groups.keys(), reverse=True)
        most_recent_year = sorted_years[0] if sorted_years else None

        # Pre-populate expand-store with IDs from the most recent season
        expand_ids = [m["id"] for m in groups[most_recent_year] if m.get("id")] if most_recent_year else []

        sections = []
        for year in sorted_years:
            is_recent = year == most_recent_year
            sections.append(
                html.Div(
                    id=f"season-{year}",
                    className="season-section",
                    **{"data-year": year},
                    children=[_render_milestone_item(m, initial_open=is_recent) for m in groups[year]],
                )
            )
        return sections, expand_ids

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
            milestone_id = triggered["index"]
            # Find the milestone by ID in the list
            m = next((item for item in milestones_data if item.get("id") == milestone_id), None)
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
    # Phase 3: Clientside expand/collapse (task 3.1)                      #
    # Toggles milestone-body display; syncs with timeline-expand-store.   #
    # ------------------------------------------------------------------ #
    app.clientside_callback(
        """
        function(n_clicks_list, expand_store) {
            var triggered_id = dash_clientside.callback_context.triggered_id;
            if (!triggered_id || triggered_id.type !== 'milestone-header') {
                return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            }
            var mid = triggered_id.index;
            var open_ids = new Set(expand_store || []);
            if (open_ids.has(mid)) {
                open_ids.delete(mid);
            } else {
                open_ids.add(mid);
            }
            var open_ids_array = Array.from(open_ids);
            var header_inputs = dash_clientside.callback_context.inputs_list[0];
            var styles = header_inputs.map(function(inp) {
                return open_ids.has(inp.id.index) ? {display: 'block'} : {display: 'none'};
            });
            return [open_ids_array, styles];
        }
        """,
        Output("timeline-expand-store", "data", allow_duplicate=True),
        Output({"type": "milestone-body", "index": ALL}, "style"),
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
        return render_image_gallery(path), {"display": "inline-flex", "alignItems": "center"}

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
