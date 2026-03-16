# ABOUTME: Pre-match Card layout component for the Player Panel.
# ABOUTME: Displays the next HKFA fixture: team logos, kickoff time (HKT), stadium, streaming link.

from pathlib import Path
from dash import html, dcc
import dash_bootstrap_components as dbc

_ASSETS_LOGOS = Path(__file__).parent.parent / "assets" / "team_logos"

_CARD_STYLE = {
    "background": "linear-gradient(135deg, #1a1a1c 0%, #2a1a18 100%)",
    "border": "1px solid #3A3A3C",
    "borderRadius": "12px",
    "padding": "1.5rem",
}

_COMPETITION_BADGE_STYLE = {
    "backgroundColor": "#93312a",
    "borderRadius": "4px",
    "padding": "2px 10px",
    "fontSize": "0.7rem",
    "fontWeight": "700",
    "letterSpacing": "1px",
    "color": "white",
    "display": "inline-block",
    "textTransform": "uppercase",
}


def _logo_or_initial(team_name: str, logo_url: str | None) -> html.Div:
    """Return an Img from local assets if the file exists, else a styled initial badge."""
    if logo_url:
        slug = logo_url.split("/")[-1]  # e.g. kitchee.png
        local_path = _ASSETS_LOGOS / slug
        if local_path.exists():
            return html.Img(
                src=logo_url,
                style={"width": "64px", "height": "64px", "objectFit": "contain"},
                title=team_name,
            )

    # Fallback: initial letter badge
    initial = (team_name or "?")[0].upper()
    return html.Div(
        initial,
        style={
            "width": "64px", "height": "64px",
            "borderRadius": "50%",
            "backgroundColor": "#93312a",
            "color": "white",
            "fontSize": "1.8rem",
            "fontWeight": "bold",
            "display": "flex", "alignItems": "center", "justifyContent": "center",
        },
        title=team_name,
    )


def create_prematch_card(fixture: dict | None) -> html.Div:
    """
    Render the Pre-match Card.

    Args:
        fixture: dict from FixtureManager.get_next_fixture(), or None.

    Returns:
        html.Div with the card content (or a no-fixture placeholder).
    """
    if not fixture:
        return html.Div(
            dbc.Card(
                dbc.CardBody([
                    html.I(className="bi bi-calendar-x fs-2 text-muted mb-2 d-block text-center"),
                    html.P(
                        "No hay próximo partido disponible",
                        className="text-muted text-center mb-0 small"
                    ),
                ]),
                style=_CARD_STYLE,
            ),
            className="mb-3",
        )

    home = fixture.get("home_team", "")
    away = fixture.get("away_team", "")
    competition = fixture.get("competition", "")
    kickoff = fixture.get("kickoff_display", "")
    stadium = fixture.get("stadium")
    streaming_url = fixture.get("streaming_url")
    home_logo = fixture.get("home_logo_url")
    away_logo = fixture.get("away_logo_url")

    streaming_btn = html.A(
        [html.I(className="bi bi-play-circle-fill me-2"), "Ver en directo"],
        href=streaming_url,
        target="_blank",
        rel="noopener noreferrer",
        className="btn btn-sm btn-outline-danger mt-3 w-100",
    ) if streaming_url else None

    return html.Div(
        dbc.Card(
            dbc.CardBody([
                # Competition badge
                html.Div(
                    html.Span(competition, style=_COMPETITION_BADGE_STYLE),
                    className="text-center mb-3"
                ),

                # Logos + VS row
                html.Div([
                    html.Div([
                        _logo_or_initial(home, home_logo),
                        html.Small(home, className="text-white-50 d-block text-center mt-1",
                                   style={"fontSize": "0.65rem", "maxWidth": "80px"}),
                    ], className="text-center"),

                    html.Div("VS", className="text-white fw-bold fs-4 mx-3 align-self-center"),

                    html.Div([
                        _logo_or_initial(away, away_logo),
                        html.Small(away, className="text-white-50 d-block text-center mt-1",
                                   style={"fontSize": "0.65rem", "maxWidth": "80px"}),
                    ], className="text-center"),
                ], className="d-flex justify-content-center align-items-center mb-3"),

                # Kickoff info
                html.Div([
                    html.I(className="bi bi-clock me-1 text-muted"),
                    html.Span(kickoff, className="text-white small"),
                ], className="text-center mb-1"),

                # Stadium
                html.Div([
                    html.I(className="bi bi-geo-alt me-1 text-muted"),
                    html.Span(stadium or "Estadio por confirmar", className="text-white-50 small"),
                ], className="text-center mb-2") if stadium is not None else None,

                # Action buttons
                streaming_btn,
                dbc.Button(
                    [html.I(className="bi bi-download me-2"), "Descargar Card"],
                    id="prematch-dl-btn",
                    color="outline-light",
                    size="sm",
                    className="mt-2 w-100",
                    style={"fontSize": "0.75rem", "borderStyle": "dashed"}
                ) if not not fixture else None,
            ]),
            style=_CARD_STYLE,
        ),
        dcc.Download(id="prematch-card-download"),
    ], className="mb-3")
