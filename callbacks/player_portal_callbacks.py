# ABOUTME: Callbacks for the Player Portal 'Career Stage' architecture.
# ABOUTME: Handles Timeline population, milestone selection, Stage rendering, and Decision Nodes injection.

import logging
from dash import Input, Output, State, callback, html, no_update, ALL, ctx, dcc
import dash_bootstrap_components as dbc
from flask_login import current_user

from data.aggregators.timeline_aggregator import TimelineAggregator
from utils.stage_helpers import render_post_match, render_pre_match, render_career_insights

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


def _render_milestone_item(milestone: dict, index: int) -> dbc.ListGroupItem:
    """Renders a single timeline milestone as a clickable list item."""
    m_type = milestone.get("type", "career")
    icon_cls = _ICON_MAP.get(m_type, "bi-circle")
    color = _COLOR_MAP.get(m_type, "secondary")
    date_str = ""
    if milestone.get("date"):
        try:
            date_str = milestone["date"].strftime("%d/%m/%Y")
        except Exception:
            date_str = str(milestone["date"])[:10]

    return dbc.ListGroupItem(
        html.Div([
            html.Div([
                html.Span(
                    html.I(className=f"bi {icon_cls}"),
                    className=f"badge rounded-pill bg-{color} me-2",
                ),
                html.Span(milestone.get("label", ""), className="small fw-semibold"),
            ], className="d-flex align-items-center"),
            html.Small(date_str, className="text-muted ms-4"),
        ]),
        id={"type": "timeline-milestone", "index": index},
        action=True,
        className="border-0 py-2 px-2",
        style={"cursor": "pointer", "borderRadius": "8px"},
        n_clicks=0,
    )


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
    # 5.1  Populate Timeline from ETL aggregator                          #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("timeline-milestones", "children"),
        Output("timeline-pills-mobile", "children"),
        Input("url", "pathname"),
        prevent_initial_call=False,
    )
    def update_timeline(pathname):
        """Builds the timeline milestone list for the authenticated player."""
        if pathname != "/player-portal":
            return no_update, no_update

        try:
            player_id = getattr(current_user, "player_id", None)
            if not player_id:
                empty = html.Div("Sin datos de jugador vinculados.", className="text-muted small p-2")
                return empty, empty

            aggregator = TimelineAggregator()
            milestones = aggregator.get_player_timeline(player_id)

            if not milestones:
                empty = html.Div("No hay hitos disponibles.", className="text-muted small p-2")
                return empty, empty

            items = [_render_milestone_item(m, i) for i, m in enumerate(milestones)]
            pills = [_render_pill(m, i) for i, m in enumerate(milestones)]

            # Store milestone data in a hidden div for retrieval on click
            store = dcc.Store(id="milestones-data-store", data=_serialize_milestones(milestones))

            return [store, dbc.ListGroup(items, flush=True)], pills

        except Exception as e:
            logger.error(f"update_timeline error: {e}")
            err = dbc.Alert("Error cargando el timeline.", color="danger", className="small")
            return err, err

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
