# ABOUTME: Agent Portal view layout — dark-themed, matches HKFA design system.
# ABOUTME: Includes roster management (add/remove players) and batch content generation.

from dash import html, dcc
import dash_bootstrap_components as dbc
from flask_login import current_user

# ── Design tokens (HKFA dark theme) ──────────────────────────────────────────
_BG_PRIMARY    = "#18181A"
_BG_SECONDARY  = "#232326"
_BG_TERTIARY   = "#2C2C2E"
_BORDER        = "#3A3A3C"
_ACCENT        = "#93312a"
_ACCENT_LIGHT  = "#b84040"
_TEXT          = "#FFFFFF"
_TEXT_MUTED    = "#A7A7A7"

_CARD_STYLE = {
    "backgroundColor": _BG_SECONDARY,
    "border": f"1px solid {_BORDER}",
    "borderRadius": "12px",
}
_CARD_HEADER_STYLE = {
    "backgroundColor": _BG_TERTIARY,
    "borderBottom": f"1px solid {_BORDER}",
    "color": _TEXT,
}
_INPUT_STYLE = {
    "backgroundColor": _BG_TERTIARY,
    "border": f"1px solid {_BORDER}",
    "color": _TEXT,
    "borderRadius": "6px",
}
_ROSTER_BOX_STYLE = {
    "backgroundColor": _BG_PRIMARY,
    "border": f"1px solid {_BORDER}",
    "borderRadius": "8px",
    "minHeight": "120px",
    "maxHeight": "320px",
    "overflowY": "auto",
    "padding": "8px",
}


def create_agent_view_layout():
    """
    Agent Portal layout — dark HKFA theme, roster management + batch generation.
    """
    # Agent profile info
    agent_name  = getattr(current_user, 'username', 'Agente')
    agent_profile = getattr(current_user, 'agent_profile', {}) or {}
    full_name   = agent_profile.get('full_name') or agent_name
    agency      = agent_profile.get('agency', '')

    subtitle = f"{full_name} · {agency}" if agency else full_name

    return html.Div([
        dbc.Container([

            # ── HEADER ────────────────────────────────────────────────────────
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Div([
                            html.I(className="bi bi-person-badge-fill me-3",
                                   style={"fontSize": "2rem", "color": _ACCENT_LIGHT}),
                            html.Div([
                                html.H2("Portal del Agente",
                                        className="mb-0",
                                        style={"color": _TEXT, "fontWeight": "700"}),
                                html.P(subtitle,
                                       className="mb-0",
                                       style={"color": _TEXT_MUTED, "fontSize": "0.9rem"}),
                            ])
                        ], className="d-flex align-items-center"),
                    ], style={
                        "background": f"linear-gradient(135deg, {_BG_SECONDARY} 0%, #2a1a18 100%)",
                        "border": f"1px solid {_BORDER}",
                        "borderLeft": f"4px solid {_ACCENT}",
                        "borderRadius": "12px",
                        "padding": "1.5rem",
                    })
                ], width=12)
            ], className="mb-4"),

            # ── MAIN ROW ──────────────────────────────────────────────────────
            dbc.Row([

                # LEFT — Roster Management (5 cols)
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="bi bi-people-fill me-2",
                                   style={"color": _ACCENT_LIGHT}),
                            html.Span("Gestión de Roster", style={"color": _TEXT, "fontWeight": "600"}),
                        ], style=_CARD_HEADER_STYLE),

                        dbc.CardBody([

                            # ── Add player ────────────────────────────────────
                            html.P("Añadir jugador al roster:",
                                   className="mb-2",
                                   style={"color": _TEXT_MUTED, "fontSize": "0.85rem",
                                          "fontWeight": "600", "textTransform": "uppercase",
                                          "letterSpacing": "0.5px"}),

                            dbc.InputGroup([
                                dcc.Dropdown(
                                    id="agent-add-player-dropdown",
                                    placeholder="Buscar jugador...",
                                    searchable=True,
                                    clearable=True,
                                    # options populated by callback from player-names-store
                                    style={
                                        "flex": "1",
                                        "--Dash-background-color": _BG_TERTIARY,
                                        "color": _TEXT,
                                    },
                                    className="dash-dropdown-dark flex-grow-1",
                                ),
                                dbc.Button(
                                    [html.I(className="bi bi-plus-lg me-1"), "Añadir"],
                                    id="agent-add-player-btn",
                                    color="danger",
                                    size="sm",
                                    style={"backgroundColor": _ACCENT,
                                           "borderColor": _ACCENT,
                                           "whiteSpace": "nowrap"},
                                    n_clicks=0,
                                ),
                            ], className="mb-2"),

                            # Feedback
                            html.Div(id="agent-roster-feedback", className="mb-3"),

                            html.Hr(style={"borderColor": _BORDER, "margin": "0.75rem 0"}),

                            # ── Roster list ───────────────────────────────────
                            html.P(id="agent-roster-count",
                                   style={"color": _TEXT_MUTED, "fontSize": "0.8rem",
                                          "fontWeight": "600", "textTransform": "uppercase",
                                          "letterSpacing": "0.5px"},
                                   className="mb-2"),

                            html.Div(
                                id="agent-roster-list",
                                style=_ROSTER_BOX_STYLE,
                                children=[
                                    html.P("Tu roster está vacío. Añade jugadores usando el buscador.",
                                           className="text-center py-3",
                                           style={"color": _TEXT_MUTED, "fontSize": "0.85rem"})
                                ]
                            ),

                        ], style={"backgroundColor": _BG_SECONDARY}),
                    ], style=_CARD_STYLE, className="mb-4 h-100"),
                ], width=12, lg=5),

                # RIGHT — Content Generation (7 cols)
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="bi bi-image me-2",
                                   style={"color": _ACCENT_LIGHT}),
                            html.Span("Generar Contenido", style={"color": _TEXT, "fontWeight": "600"}),
                        ], style=_CARD_HEADER_STYLE),

                        dbc.CardBody([

                            # ── Player checklist ──────────────────────────────
                            html.P("Selecciona jugadores para procesar:",
                                   className="mb-2",
                                   style={"color": _TEXT_MUTED, "fontSize": "0.85rem",
                                          "fontWeight": "600", "textTransform": "uppercase",
                                          "letterSpacing": "0.5px"}),

                            html.Div(
                                id="agent-roster-container",
                                style={**_ROSTER_BOX_STYLE, "maxHeight": "200px"},
                                children=[
                                    dcc.Checklist(
                                        id="agent-player-selection",
                                        options=[],
                                        value=[],
                                        labelStyle={
                                            "display": "flex",
                                            "alignItems": "center",
                                            "marginBottom": "6px",
                                            "color": _TEXT,
                                            "cursor": "pointer",
                                        },
                                        inputStyle={"marginRight": "8px", "accentColor": _ACCENT},
                                    )
                                ]
                            ),

                            dbc.ButtonGroup([
                                dbc.Button("Seleccionar todos",
                                           id="agent-select-all-btn",
                                           size="sm", color="link",
                                           style={"color": _ACCENT_LIGHT, "fontSize": "0.8rem"}),
                                dbc.Button("Limpiar",
                                           id="agent-clear-btn",
                                           size="sm", color="link",
                                           style={"color": _TEXT_MUTED, "fontSize": "0.8rem"}),
                            ], className="mb-3 mt-1"),

                            html.Hr(style={"borderColor": _BORDER, "margin": "0.5rem 0 1rem 0"}),

                            # ── Export format ─────────────────────────────────
                            html.P("Formato de exportación:",
                                   className="mb-2",
                                   style={"color": _TEXT_MUTED, "fontSize": "0.85rem",
                                          "fontWeight": "600", "textTransform": "uppercase",
                                          "letterSpacing": "0.5px"}),

                            dcc.RadioItems(
                                id="agent-batch-format",
                                options=[
                                    {"label": " Solo Cards (PNG)", "value": "png"},
                                    {"label": " Solo Dossiers (PDF)", "value": "pdf"},
                                    {"label": " Pack Completo (PNG + PDF)", "value": "both"},
                                ],
                                value="png",
                                labelStyle={
                                    "display": "block",
                                    "color": _TEXT,
                                    "fontSize": "0.9rem",
                                    "marginBottom": "6px",
                                    "cursor": "pointer",
                                },
                                inputStyle={"marginRight": "8px", "accentColor": _ACCENT},
                                className="mb-3",
                            ),

                            dbc.Button(
                                [html.I(className="bi bi-file-earmark-zip-fill me-2"),
                                 "Generar y Descargar ZIP"],
                                id="agent-batch-download-btn",
                                className="w-100",
                                n_clicks=0,
                                style={
                                    "backgroundColor": _ACCENT,
                                    "borderColor": _ACCENT,
                                    "color": _TEXT,
                                    "fontWeight": "600",
                                    "borderRadius": "8px",
                                    "padding": "0.6rem 1rem",
                                }
                            ),
                            dcc.Download(id="agent-batch-download"),

                        ], style={"backgroundColor": _BG_SECONDARY}),
                    ], style=_CARD_STYLE),
                ], width=12, lg=7),
            ], className="g-3"),

        ], fluid=True, className="py-4"),
    ], style={"backgroundColor": _BG_PRIMARY, "minHeight": "100vh"})


__all__ = ["create_agent_view_layout"]
