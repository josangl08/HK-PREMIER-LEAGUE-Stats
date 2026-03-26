# ABOUTME: Season Summary Card component for the Player Portal timeline.
# ABOUTME: Renders career milestones as seasonal anchors with aggregated stats per season and competition.

from typing import Dict, Any, List, Optional
from dash import html
import dash_bootstrap_components as dbc


def _lucide(name: str) -> html.I:
    """Returns a Lucide icon element."""
    return html.I(**{"data-lucide": name, "className": "lucide-inline-icon me-1"})


def _stat_col(label: str, value: Any, is_main: bool = False) -> dbc.Col:
    """Renders a single stat column with label and value."""
    return dbc.Col(
        [
            html.Small(label, className="portal-text-muted d-block text-uppercase small", style={"fontSize": "0.65rem"}),
            html.Span(str(value), className=f"fw-bold {'h4 mb-0' if is_main else 'h6 mb-0'}"),
        ],
        xs=3,
        className="text-center",
    )


def render_season_card(season_data: Dict[str, Any]) -> dbc.Card:
    """
    Renders a Season Card with club logo, season label, total stats row, and per-competition rows.

    Args:
        season_data: Dict with {season, club, club_logo, pj, goals, assists, minutes, by_competition: [...]}.
    """
    season = season_data.get("season", "Unknown Season")
    club = season_data.get("club", "Unknown Club")
    club_logo = season_data.get("club_logo")
    pj = season_data.get("pj", 0)
    goals = season_data.get("goals", 0)
    assists = season_data.get("assists", 0)
    minutes = season_data.get("minutes", 0)
    by_competition = season_data.get("by_competition", [])

    # Header with Club Logo and Season
    header = html.Div(
        [
            html.Div(
                [
                    html.Img(src=club_logo, style={"width": "40px", "height": "40px", "objectFit": "contain"}) if club_logo else 
                    html.Div(club[:2].upper() if club else "??", className="rounded-circle bg-secondary d-flex align-items-center justify-content-center text-white fw-bold", style={"width": "40px", "height": "40px"}),
                    html.Div(
                        [
                            html.H5(season, className="mb-0 fw-bold"),
                            html.Small(club, className="portal-text-muted"),
                        ],
                        className="ms-3"
                    )
                ],
                className="d-flex align-items-center"
            ),
            dbc.Badge("Season Summary", color="info", className="ms-auto small text-uppercase")
        ],
        className="d-flex align-items-center mb-4"
    )

    # Main Stats Row
    stats_row = dbc.Row(
        [
            _stat_col("Played", pj, is_main=True),
            _stat_col("Goals", goals, is_main=True),
            _stat_col("Assists", assists, is_main=True),
            _stat_col("Minutes", minutes, is_main=True),
        ],
        className="g-0 mb-4 py-3 rounded",
        style={"background": "rgba(var(--portal-accent-rgb, 0, 123, 255), 0.1)"}
    )

    # Competition Breakdown
    comp_rows = []
    if by_competition:
        comp_rows.append(html.Small("Competition Breakdown", className="portal-text-muted d-block mb-2 text-uppercase fw-bold", style={"fontSize": "0.7rem"}))
        for comp in by_competition:
            comp_name = comp.get("competition", "Unknown")
            c_pj = comp.get("pj", 0)
            c_goals = comp.get("goals", 0)
            c_assists = comp.get("assists", 0)
            
            comp_rows.append(
                html.Div(
                    [
                        html.Span(comp_name, className="small fw-bold text-truncate", style={"maxWidth": "150px"}),
                        html.Div(
                            [
                                html.Small(f"{c_pj} PJ", className="me-2"),
                                html.Small(f"{c_goals} G", className="me-2 text-primary"),
                                html.Small(f"{c_assists} A", className="text-success"),
                            ],
                            className="ms-auto"
                        )
                    ],
                    className="d-flex align-items-center mb-1 pb-1 border-bottom border-light last-child-no-border"
                )
            )

    return dbc.Card(
        dbc.CardBody(
            [
                header,
                stats_row,
                html.Div(comp_rows) if comp_rows else None
            ]
        ),
        className="season-card mb-4 border-0 shadow-sm",
        style={
            "borderRadius": "12px",
            "background": "var(--card-bg, #fff)",
            "borderLeft": "4px solid var(--info)"
        }
    )
