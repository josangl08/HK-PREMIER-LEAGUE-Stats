# ABOUTME: Callbacks for the Player Portal 'Career Stage' architecture.
# ABOUTME: Handles Timeline population, milestone selection, Stage rendering, and Decision Nodes injection.

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


def _render_milestone_item(milestone: dict, index: int) -> html.Div:
    """Renders a single timeline milestone as a glass card with expand/collapse inline summary."""
    m_type = milestone.get("type", "career")
    icon_cls = _ICON_MAP.get(m_type, "bi-circle")
    color = _COLOR_MAP.get(m_type, "secondary")
    glass_cls = _get_glass_class(milestone)
    payload = milestone.get("payload", {})
    matches = payload.get("matches", [])
    summary = payload.get("summary", {})
    opponent = payload.get("opponent", "")

    date_str = ""
    if milestone.get("date"):
        try:
            from datetime import datetime
            if isinstance(milestone["date"], str):
                dt = datetime.fromisoformat(milestone["date"].replace('Z', '+00:00'))
            else:
                dt = milestone["date"]
            date_str = dt.strftime("%d/%m/%Y")
        except Exception:
            date_str = str(milestone["date"])[:10]

    # Career summary text (e.g. "15 Goles · 4 Asist.")
    summary_text = None
    if m_type == "career" and summary:
        g = summary.get("goals", 0)
        a = summary.get("assists", 0)
        summary_text = html.Small(f"{g} Goles · {a} Asist.", className="text-warning extra-small fw-bold d-block")

    # Inline expand/collapse summary (task 5.2) — shown on chevron click, no stage dispatch
    inline_summary_items = [
        html.Small(milestone.get("label", ""), className="fw-semibold d-block"),
        html.Small(date_str, className="text-muted"),
    ]
    if opponent:
        inline_summary_items.append(
            html.Span(opponent, className=f"badge bg-{color} ms-1 small")
        )
    if m_type == "career" and summary:
        inline_summary_items.append(summary_text)

    inline_collapse = dbc.Collapse(
        html.Div(inline_summary_items, className="px-2 pb-2 pt-1 small"),
        id={"type": "milestone-inline-collapse", "index": index},
        is_open=False,
    )

    # Match history sub-list (career type)
    has_matches = m_type == "career" and len(matches) > 0
    match_rows = []
    if has_matches:
        for m in matches:
            match_rows.append(html.Div([
                html.Small(m.get("date", ""), className="text-muted", style={"width": "75px"}),
                html.Small(m.get("opponent", "Rival"), className="fw-normal flex-grow-1 text-truncate px-2"),
                html.Small(f"{m.get('minutes_played', 0)}'", className="text-muted text-end", style={"width": "40px"}),
            ], className="d-flex border-bottom py-1 align-items-center"))

    match_history_collapse = dbc.Collapse(
        html.Div(match_rows, className="ps-4 pe-2 pb-2 rounded-bottom"),
        id={"type": "match-history-collapse", "index": index},
        is_open=False,
    ) if has_matches else None

    toggle_icon = html.I(
        className="bi bi-chevron-down ms-auto small text-muted",
        id={"type": "milestone-inline-toggle", "index": index},
        style={"cursor": "pointer", "padding": "4px"},
        n_clicks=0,
    )

    history_toggle = html.I(
        className="bi bi-list-ul ms-1 small text-muted",
        id={"type": "match-history-toggle", "index": index},
        style={"cursor": "pointer", "padding": "4px"},
        n_clicks=0,
    ) if has_matches else None

    return html.Div([
        html.Div([
            html.Div([
                html.Span(
                    html.I(className=f"bi {icon_cls}"),
                    className=f"badge rounded-pill bg-{color} me-2",
                    id={"type": "timeline-milestone", "index": index},
                    n_clicks=0,
                    style={"cursor": "pointer"},
                ),
                html.Div([
                    html.Span(milestone.get("label", ""), className="small fw-semibold",
                              id={"type": "timeline-milestone-label", "index": index}),
                    html.Small(date_str, className="text-muted d-block"),
                ], id={"type": "timeline-milestone-text", "index": index}, style={"cursor": "pointer"}),
            ], className="d-flex align-items-center flex-grow-1"),
            html.Div([
                history_toggle,
                toggle_icon,
            ], className="d-flex align-items-center"),
        ], className="d-flex align-items-center py-2 px-2"),
        inline_collapse,
        match_history_collapse,
    ], className=f"glass-card {glass_cls} mb-2")


def _render_pill(milestone: dict, index: int) -> dbc.Button:
    """Renders a pill button for the mobile carousel."""
    m_type = milestone.get("type", "career")
    icon_cls = _ICON_MAP.get(m_type, "bi-circle")
    color = _COLOR_MAP.get(m_type, "secondary")
    return dbc.Button(
        [html.I(className=f"bi {icon_cls} me-1"), milestone.get("label", "")[:20]],
        id={"type": "timeline-pill", "index": index},
        color=color,
        outline=True,
        size="sm",
        className="flex-shrink-0 rounded-pill",
        n_clicks=0,
    )


def register_player_portal_callbacks(app):
    """Registers all Player Portal callbacks."""

    # ------------------------------------------------------------------ #
    # ETL → milestones-data-store + mobile pills                          #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("milestones-data-store", "data"),
        Output("timeline-pills-mobile", "children"),
        Input("url", "pathname"),
        prevent_initial_call=False,
    )
    def update_timeline(pathname):
        """Fetches timeline milestones and stores serialized data; builds mobile pills."""
        if pathname != "/player-portal":
            return no_update, no_update

        try:
            player_id = getattr(current_user, "player_id", None)
            if not player_id:
                return None, html.Div("Sin datos de jugador vinculados.", className="text-muted small p-2")

            aggregator = TimelineAggregator(data_manager=get_hong_kong_data_manager())
            milestones = aggregator.get_player_timeline(player_id)

            if not milestones:
                return None, html.Div("No hay hitos disponibles.", className="text-muted small p-2")

            pills = [_render_pill(m, i) for i, m in enumerate(milestones)]
            return _serialize_milestones(milestones), pills

        except Exception as e:
            logger.error(f"update_timeline error: {e}")
            err = dbc.Alert("Error cargando el timeline.", color="danger", className="small")
            return None, err

    # ------------------------------------------------------------------ #
    # milestones-data-store + selected-year → timeline-milestones         #
    # (task 5.1 glass wrapping + task 4.3 year filtering)                 #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("timeline-milestones", "children"),
        Input("milestones-data-store", "data"),
        Input("selected-year-store", "data"),
        prevent_initial_call=False,
    )
    def render_timeline_milestones(milestones_data, selected_year):
        """Renders glass-card milestone items, optionally filtered by selected year."""
        if not milestones_data:
            return no_update

        filtered = milestones_data
        if selected_year:
            filtered = [
                m for m in milestones_data
                if str(m.get("date", ""))[:4] == str(selected_year)
            ]
            if not filtered:
                return html.Div(f"No hay hitos para {selected_year}.", className="text-muted small p-2")

        items = [_render_milestone_item(m, i) for i, m in enumerate(filtered)]
        return items

    # ------------------------------------------------------------------ #
    # task 4.1  milestones-data-store → year-navigator chips              #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("year-navigator", "children"),
        Input("milestones-data-store", "data"),
        prevent_initial_call=True,
    )
    def update_year_navigator(milestones_data):
        """Builds year chip buttons from available milestone years."""
        if not milestones_data:
            return []

        years = sorted(
            {str(m.get("date", ""))[:4] for m in milestones_data if m.get("date")},
            reverse=True,
        )
        if not years:
            return []

        chips = []
        for year in years:
            chips.append(
                dbc.Button(
                    year,
                    id={"type": "year-chip", "year": year},
                    color="secondary",
                    outline=True,
                    size="sm",
                    className="me-1 rounded-pill year-chip",
                    n_clicks=0,
                    style={"display": "inline-block"},
                )
            )
        return chips

    # ------------------------------------------------------------------ #
    # task 4.2  Clientside auto-scroll to current-year chip               #
    # ------------------------------------------------------------------ #
    app.clientside_callback(
        """
        function(children) {
            if (!children || children.length === 0) return null;
            setTimeout(function() {
                var bar = document.getElementById('year-navigator');
                if (!bar) return;
                var currentYear = new Date().getFullYear().toString();
                var buttons = bar.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                    if (buttons[i].textContent.trim() === currentYear) {
                        buttons[i].scrollIntoView({behavior: 'smooth', inline: 'center', block: 'nearest'});
                        break;
                    }
                }
            }, 100);
            return null;
        }
        """,
        Output("year-nav-scroll-dummy", "data"),
        Input("year-navigator", "children"),
        prevent_initial_call=True,
    )

    # ------------------------------------------------------------------ #
    # task 4.3  Year chip click → selected-year-store                     #
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
            return None if year == current_year else year
        return no_update

    # ------------------------------------------------------------------ #
    # 5.2  Milestone click → update timeline-context-store                #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("timeline-context-store", "data"),
        Input({"type": "timeline-milestone", "index": ALL}, "n_clicks"),
        Input({"type": "timeline-pill", "index": ALL}, "n_clicks"),
        State("milestones-data-store", "data"),
        prevent_initial_call=True,
    )
    def select_milestone(milestone_clicks, pill_clicks, milestones_data):
        """Updates the context store when a milestone is clicked."""
        if not ctx.triggered_id or not milestones_data:
            return no_update

        triggered = ctx.triggered_id
        if isinstance(triggered, dict) and triggered.get("type") in ("timeline-milestone", "timeline-pill"):
            index = triggered["index"]
            if 0 <= index < len(milestones_data):
                m = milestones_data[index]
                return {"type": m["type"], "payload": m["payload"]}

        return no_update

    # ------------------------------------------------------------------ #
    # 5.3  timeline-context-store → Stage content                         #
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
    # task 5.2  Inline milestone expand/collapse toggle                   #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output({"type": "milestone-inline-collapse", "index": ALL}, "is_open"),
        Input({"type": "milestone-inline-toggle", "index": ALL}, "n_clicks"),
        State({"type": "milestone-inline-collapse", "index": ALL}, "is_open"),
        prevent_initial_call=True,
    )
    def toggle_milestone_inline(n_clicks_list, is_open_list):
        """Toggles inline summary collapse for milestone cards without stage dispatch."""
        if not ctx.triggered_id:
            return no_update
        triggered_index = ctx.triggered_id.get("index")
        result = list(is_open_list)
        for i, (nc, current_open) in enumerate(zip(n_clicks_list, is_open_list)):
            if i == triggered_index and nc:
                result[i] = not current_open
        return result

    # ------------------------------------------------------------------ #
    # Match-history expand/collapse toggle (career milestones)            #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output({"type": "match-history-collapse", "index": ALL}, "is_open"),
        Input({"type": "match-history-toggle", "index": ALL}, "n_clicks"),
        State({"type": "match-history-collapse", "index": ALL}, "is_open"),
        prevent_initial_call=True,
    )
    def toggle_match_history(n_clicks_list, is_open_list):
        """Toggles the visibility of the match-history sub-list for the triggered milestone."""
        if not ctx.triggered_id:
            return no_update

        triggered_index = ctx.triggered_id.get("index")
        result = list(is_open_list)
        for i, (nc, current_open) in enumerate(zip(n_clicks_list, is_open_list)):
            if i == triggered_index and nc:
                result[i] = not current_open
        return result


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
