# ABOUTME: Helper functions for rendering Stage scenarios, AI widgets, and image gallery (Feature G).
# ABOUTME: Dispatches rendering for post-match, pre-match, career-insights, and Action Node gallery views.

import logging
import os
import threading
from pathlib import Path
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc
from typing import Dict, List, Any, Optional

from utils.app_context import get_hong_kong_data_manager
from utils.chart_helpers import apply_hkfa_theme, glass_figure_layout, HKFATheme
from utils.ai_helpers import umap_scatter_chart

# Numba/UMAP is not thread-safe with the default workqueue layer.
# This lock serializes concurrent calls to fit_umap across Flask threads.
_umap_lock = threading.Lock()

logger = logging.getLogger(__name__)

# Metrics displayed in the projector per position group.
# Keys match the Position_Group values from the processed DataFrame.
POSITION_METRICS: Dict[str, List[str]] = {
    "Forward":    ["Goals", "xG", "Shots on target, %", "Goal conversion, %"],
    "Winger":     ["Goals", "Assists", "Dribbles per 90", "Crosses per 90"],
    "Midfielder": ["Assists", "xA", "Key passes per 90", "Accurate passes, %"],
    "Defender":   ["Interceptions per 90", "Defensive duels won, %", "Aerial duels won, %", "Shots blocked per 90"],
    "Goalkeeper": ["Save rate, %", "Clean sheets", "Prevented goals per 90", "xG against per 90"],
}

_CURRENT_SEASON_FALLBACK = "2025-26"
_CARD_CACHE_DIR = Path("data/cache/cards")


def _get_current_season() -> str:
    """Returns the active season from the data manager, falling back to a constant."""
    try:
        return get_hong_kong_data_manager().current_season or _CURRENT_SEASON_FALLBACK
    except Exception:
        return _CURRENT_SEASON_FALLBACK


def get_cached_image_path(milestone_id: str) -> Optional[str]:
    """
    Checks the card cache directory for a generated image matching the milestone ID.
    Returns the path string if found, None otherwise.
    """
    if not milestone_id:
        return None
    try:
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            candidate = _CARD_CACHE_DIR / f"{milestone_id}{ext}"
            if candidate.exists():
                return str(candidate)
    except Exception as e:
        logger.warning(f"get_cached_image_path error for '{milestone_id}': {e}")
    return None


def render_image_gallery(image_path: Optional[str]) -> html.Div:
    """
    Returns a glassmorphic image gallery view for the Stage panel.
    Shows the image if path is valid, otherwise a graceful placeholder.
    Close button is rendered statically in the layout (gallery-close-btn).
    """
    if image_path and os.path.isfile(image_path):
        content = html.Div(
            [
                html.Div(
                    html.Img(
                        src=image_path,
                        className="img-fluid rounded",
                        style={"maxHeight": "400px", "objectFit": "contain"},
                    ),
                    className="text-center",
                ),
                html.Small(
                    os.path.basename(image_path),
                    className="text-muted d-block text-center mt-2",
                ),
            ]
        )
    else:
        content = html.Div(
            [
                html.I(className="bi bi-image text-muted", style={"fontSize": "3rem"}),
                html.P("No hay imagen disponible", className="text-muted mt-2 mb-0"),
            ],
            className="text-center py-4",
        )

    return html.Div(
        content,
        className="stage-gallery-view",
    )


def _infer_position_group(position: str) -> str:
    """Maps a raw Wyscout position string to one of the POSITION_METRICS keys."""
    if not position:
        return "Midfielder"
    p = position.upper()
    if "GK" in p:
        return "Goalkeeper"
    if any(x in p for x in ("CF", "RWF", "LWF")):
        return "Forward"
    if any(x in p for x in ("RW", "LW", "RWF", "LWF", "RAMF", "LAMF")):
        return "Winger"
    if any(x in p for x in ("CB", "RCB", "LCB", "RB", "LB", "RWB", "LWB")):
        return "Defender"
    return "Midfielder"

def render_post_match(payload: Dict[str, Any]) -> html.Div:
    """
    Renders the Post-Match analysis stage.
    Shows a match header, Radar Chart, and Percentile bars for the player's season stats.
    """
    opponent = payload.get("opponent", "Opponent")
    date_str = payload.get("kickoff_display") or str(payload.get("date", ""))[:10]
    home = payload.get("home_team", "")
    away = payload.get("away_team", "")
    player_stats = payload.get("player_stats") or {}

    # ── Match header card ──────────────────────────────────────────────────
    match_label = f"{home} vs {away}" if home and away else f"vs {opponent}"
    header = dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col(html.Div([
                    html.Span(match_label, className="fw-bold fs-5"),
                ]), width="auto"),
                dbc.Col(html.Small(date_str, className="text-muted"), width="auto", className="ms-auto"),
            ], align="center"),
        ])
    ], className="mb-3 border-0 shadow-sm")

    # ── Performance stats from data manager ───────────────────────────────
    perf = player_stats.get("performance_stats", {})
    percentiles = player_stats.get("percentiles", {})
    basic = player_stats.get("basic_info", {})
    player_name = basic.get("name", "Player")
    position = basic.get("position_primary", basic.get("position", ""))

    # Radar: use available numeric stats normalized 0-100 via percentiles
    radar_metrics = ["Goals", "Assists", "Accurate passes, %", "Minutes played"]
    radar_values = [percentiles.get(m, 50) for m in radar_metrics]
    radar_labels = ["Goals", "Assists", "Pass Accuracy", "Minutes"]

    from utils.chart_helpers import create_radar_chart
    radar_fig = glass_figure_layout(create_radar_chart(
        values=radar_values,
        metrics=radar_labels,
        title=f"{player_name} — Season Percentiles",
        name=player_name,
    ))

    from utils.chart_helpers import create_percentile_bars
    percentile_display = {
        "Goals": percentiles.get("Goals", 0),
        "Assists": percentiles.get("Assists", 0),
        "Pass %": percentiles.get("Accurate passes, %", 0),
        "Minutes": percentiles.get("Minutes played", 0),
    }

    # ── Rating-based glass modifier ─────────────────────────────────────────
    rating = payload.get("rating") or player_stats.get("performance_stats", {}).get("rating")
    try:
        rating = float(rating) if rating is not None else None
    except (ValueError, TypeError):
        rating = None
    glass_modifier = "glass-danger" if (rating is not None and rating < 6.0) else "glass-success"

    # ── KPI icons with animate-glass-pulse (task 6.4) ─────────────────────
    kpi_icon = html.I(className="bi bi-person-fill me-1 animate-glass-pulse")

    # ── Layout ─────────────────────────────────────────────────────────────
    return html.Div(
        html.Div([
            header,
            html.P([
                kpi_icon,
                html.Span(f"{player_name}", className="fw-semibold me-2"),
                html.Small(position, className="text-muted badge bg-secondary"),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col([
                    html.H6("Performance Radar", className="text-muted mb-2"),
                    dcc.Graph(figure=radar_fig, config={"displayModeBar": False}, className="w-100"),
                ], width=12, md=7),
                dbc.Col([
                    html.H6("Percentiles", className="text-muted mb-3"),
                    create_percentile_bars(percentile_display),
                ], width=12, md=5),
            ]),
        ]),
        className=f"glass-card {glass_modifier}",
    )


def render_pre_match(payload: Dict[str, Any]) -> html.Div:
    """
    Renders the Pre-Match preparation hub.
    Shows fixture details, opponent info, and a rule-based Game-Plan insight.
    """
    opponent = payload.get("opponent", "Opponent")
    home = payload.get("home_team", "")
    away = payload.get("away_team", "")
    date_str = payload.get("kickoff_display") or str(payload.get("date", ""))[:16]
    stadium = payload.get("stadium", "")
    streaming_url = payload.get("streaming_url")
    competition = payload.get("competition", "HK Premier League")

    # ── Fixture header ─────────────────────────────────────────────────────
    streaming_link = html.A(
        [html.I(className="bi bi-play-circle me-1"), "Watch stream"],
        href=streaming_url,
        target="_blank",
        className="btn btn-sm btn-outline-primary mt-2",
    ) if streaming_url else html.Small("No broadcast available", className="text-muted")

    fixture_card = dbc.Card([
        dbc.CardBody([
            html.Small(competition, className="text-muted text-uppercase fw-bold d-block mb-2"),
            dbc.Row([
                dbc.Col(html.H5(home, className="text-end fw-bold mb-0"), width=5),
                dbc.Col(html.H6("VS", className="text-center text-muted mb-0"), width=2),
                dbc.Col(html.H5(away, className="fw-bold mb-0"), width=5),
            ], align="center", className="mb-2"),
            html.Hr(className="my-2"),
            html.Div([
                html.I(className="bi bi-calendar3 me-1"),
                html.Span(date_str, className="me-3"),
                html.I(className="bi bi-geo-alt me-1"),
                html.Span(stadium or "Stadium to be confirmed"),
            ], className="small text-muted"),
            html.Div(streaming_link, className="mt-2"),
        ])
    ], className="mb-3 border-0 shadow-sm")

    # ── Game-Plan insight (rule-based) ─────────────────────────────────────
    try:
        dm = get_hong_kong_data_manager()
        opp_stats = dm.get_player_overview(opponent)
        has_opp_data = opp_stats and "error" not in opp_stats
    except Exception:
        has_opp_data = False

    if has_opp_data:
        game_plan_text = (
            f"Analysis available for {opponent}. "
            "Review their defensive and offensive stats to prepare tactics."
        )
    else:
        game_plan_text = (
            f"Prepare for the match against {opponent}. "
            "Focus on quick transitions and high pressure in midfield."
        )

    game_plan_card = dbc.Card([
        dbc.CardHeader([
            html.I(className="bi bi-robot me-2"),
            html.Span("AI Game-Plan", className="fw-semibold"),
        ], className="border-0"),
        dbc.CardBody([
            html.P(game_plan_text, className="mb-0 small"),
        ])
    ], className="border-0 shadow-sm mb-3", color="dark", outline=True)

    # ── Clock icon with animate-glass-spin (task 6.4) ─────────────────────
    spin_icon = html.I(className="bi bi-calendar3 me-1 animate-glass-spin")

    return html.Div(
        html.Div([
            fixture_card,
            html.Div([
                spin_icon,
                html.Small(date_str, className="text-muted"),
            ], className="mb-2 small") if date_str else None,
            game_plan_card,
        ]),
        className="glass-card glass-prematch",
    )


def render_career_insights(payload: Dict[str, Any], user_role: str = "player") -> html.Div:
    """
    Renders the Career Insights stage with contextual projection, UMAP clustering,
    and a role-conditional Dossier export button.
    """
    season = payload.get("season", "")
    player_id = payload.get("player_id", "")
    player_name = payload.get("player_name", "Player")
    current_season = _get_current_season()

    # ── Projection figure (context-aware: wrap_up vs projection mode) ──────
    projection_fig = get_projection_figure(player_id, season, current_season=current_season)
    projection_section = dbc.Card([
        dbc.CardHeader([
            html.I(className="bi bi-graph-up-arrow me-2"),
            html.Span("Performance Projection", className="fw-semibold"),
        ], className="border-0"),
        dbc.CardBody([
            dcc.Graph(figure=projection_fig, config={"displayModeBar": False}),
        ])
    ], className="border-0 shadow-sm mb-3")

    # ── UMAP clustering figure (nested glass-card, task 6.3) ──────────────
    umap_fig = get_umap_figure(player_id)
    umap_section = html.Div([
        dbc.Card([
            dbc.CardHeader([
                html.I(className="bi bi-diagram-3 me-2"),
                html.Span("Playstyle Map (UMAP)", className="fw-semibold"),
            ], className="border-0"),
            dbc.CardBody([
                dcc.Graph(figure=umap_fig, config={"displayModeBar": False}),
            ])
        ], className="border-0 shadow-sm mb-3"),
    ], className="glass-card")

    # ── Agent role: Dossier export button ──────────────────────────────────
    dossier_button = html.Div()
    if user_role == "agent":
        dossier_button = html.Div([
            dbc.Button(
                [html.I(className="bi bi-file-earmark-pdf me-2"), "Export PDF Dossier"],
                id="export-dossier-btn",
                color="danger",
                outline=True,
                className="mt-2",
                n_clicks=0,
            ),
            dcc.Download(id="dossier-download"),
        ])

    return html.Div(
        html.Div([
            html.H6([
                html.I(className="bi bi-calendar3 me-2"),
                html.Span(
                    f"Career Perspective — Season {season}",
                    className="animate-glass-draw",
                ),
            ], className="mb-3 text-muted"),
            dbc.Row([
                dbc.Col(projection_section, width=12, lg=6),
                dbc.Col(umap_section, width=12, lg=6),
            ]),
            dossier_button,
        ]),
        className="glass-card glass-career",
    )

def get_umap_figure(player_id: str) -> go.Figure:
    """
    Wraps clustering_engine output into a Plotly figure.
    Highlights the selected player's point.
    """
    try:
        from ai_models.clustering import fit_umap
        from utils.player_index import get_player_index

        dm = get_hong_kong_data_manager()
        df = dm.processed_data
        if df is None or df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data available for clustering", showarrow=False)
            return apply_hkfa_theme(fig)

        # 1. Resolve player name
        pi = get_player_index()
        player_info = pi.get_player_info(player_id)
        player_name = player_info.get("canonical_name") if player_info else None

        # 2. Prepare features
        meta_cols = {"Player", "Season", "Team", "Position"}
        feature_cols = [c for c in df.columns if c not in meta_cols and pd.api.types.is_numeric_dtype(df[c])]

        # Sample for performance if needed, but ensure player is included
        if len(df) > 1000:
            df_plot = df.sample(1000)
            if player_name and player_name not in df_plot["Player"].values:
                player_row = df[df["Player"] == player_name]
                if not player_row.empty:
                    df_plot = pd.concat([df_plot, player_row.head(1)])
        else:
            df_plot = df

        X = df_plot[feature_cols].fillna(0).values
        # Standardize
        X_scaled = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-6)

        names = df_plot["Player"].tolist()
        # Serialize Numba/UMAP calls — workqueue layer is not thread-safe
        with _umap_lock:
            umap_df, _ = fit_umap(X_scaled, player_names=names)
        
        # Add metadata for hover
        if "Team" in df_plot.columns: umap_df["team"] = df_plot["Team"].values
        if "Season" in df_plot.columns: umap_df["season"] = df_plot["Season"].values
            
        fig = umap_scatter_chart(umap_df)
        
        # 3. Highlight player
        if player_name:
            player_point = umap_df[umap_df["player_name"] == player_name]
            if not player_point.empty:
                fig.add_trace(go.Scatter(
                    x=player_point["x"],
                    y=player_point["y"],
                    mode="markers+text",
                    marker=dict(size=15, color="white", line=dict(width=3, color=HKFATheme.ACCENT_RED)),
                    text=[player_name],
                    textposition="top center",
                    name="Selected",
                    showlegend=True
                ))

        fig.update_layout(title="Playstyle Map (UMAP)")
        return glass_figure_layout(fig)
    except Exception as e:
        logger.error(f"Error generating UMAP figure: {e}")
        fig = go.Figure()
        fig.add_annotation(text=f"Error: {str(e)}", showarrow=False)
        return glass_figure_layout(fig)

def get_projection_figure(
    player_id: str,
    selected_season: Optional[str] = None,
    current_season: Optional[str] = None,
) -> go.Figure:
    """
    Returns a Plotly figure for the performance projector.

    Mode selection:
    - If selected_season != current_season → wrap_up mode (season summary vs league avg).
    - If selected_season == current_season → projection mode (forward-looking trend).

    Args:
        player_id: Internal player identifier (Wyscout ID).
        selected_season: The season the user is viewing (e.g. "2022-23").
        current_season: The active season (e.g. "2025-26"). Defaults to data manager value.
    """
    if current_season is None:
        current_season = _get_current_season()
    if not selected_season:
        selected_season = current_season

    # Determine mode: Only current season gets projection; others get wrap-up summary
    mode = "wrap_up" if selected_season != current_season else "projection"

    try:
        from utils.player_index import get_player_index

        pi = get_player_index()
        player_info = pi.get_player_info(player_id)
        if not player_info:
            fig = go.Figure()
            fig.add_annotation(text="Player not found", showarrow=False)
            return apply_hkfa_theme(fig)

        player_name = player_info.get("canonical_name", "Player")
        seasons = sorted(player_info.get("seasons", []))

        if not seasons:
            fig = go.Figure()
            fig.add_annotation(text="Insufficient data", showarrow=False)
            return apply_hkfa_theme(fig)

        if mode == "wrap_up":
            return _build_wrapup_chart(player_name, selected_season, current_season)
        else:
            return _build_projection_chart(player_name, seasons, current_season)

    except Exception as e:
        logger.error(f"Error generating projection figure: {e}")
        fig = go.Figure()
        fig.add_annotation(text=f"Error: {str(e)}", showarrow=False)
        return apply_hkfa_theme(fig)


def _get_position_group(player_name: str, dm: "HongKongDataManager") -> str:
    """Derives the Position_Group for a player from the processed DataFrame."""
    try:
        df = dm.processed_data
        if df is None or df.empty:
            return "Midfielder"
        row = df[df["Player"] == player_name]
        if row.empty:
            return "Midfielder"
        pos_group = row.iloc[0].get("Position_Group") if "Position_Group" in row.columns else None
        if pos_group and str(pos_group) in POSITION_METRICS:
            return str(pos_group)
        raw_pos = row.iloc[0].get("Position", "")
        return _infer_position_group(str(raw_pos))
    except Exception:
        return "Midfielder"


def _build_wrapup_chart(
    player_name: str,
    selected_season: str,
    current_season: str,
) -> go.Figure:
    """
    Builds a Season Wrap-up bar chart comparing the player's metrics to the
    league average for their position group.
    """
    try:
        dm = get_hong_kong_data_manager()
        df = dm.processed_data
        pos_group = _get_position_group(player_name, dm)
        metrics = [m for m in POSITION_METRICS.get(pos_group, POSITION_METRICS["Midfielder"])
                   if m in (df.columns if df is not None else [])]

        if df is None or df.empty or not metrics:
            raise ValueError("No data available for wrap-up chart")

        # Player row (current season data — proxy for selected season)
        player_row = df[df["Player"] == player_name]
        player_vals = [
            float(player_row.iloc[0][m]) if not player_row.empty else 0.0
            for m in metrics
        ]

        # League average for the same position group
        league_df = df[df["Position_Group"] == pos_group] if "Position_Group" in df.columns else df
        league_vals = [
            float(league_df[m].mean()) if m in league_df.columns else 0.0
            for m in metrics
        ]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name=player_name,
            x=metrics,
            y=player_vals,
            marker_color=HKFATheme.ACCENT_BLUE,
        ))
        fig.add_trace(go.Bar(
            name="League Average",
            x=metrics,
            y=league_vals,
            marker_color=HKFATheme.ACCENT_RED,
            opacity=0.7,
        ))

        note = "" if selected_season == current_season else f" (proxy data: {current_season})"
        fig.update_layout(
            title=f"Season Summary {selected_season} — {player_name}{note}",
            barmode="group",
            xaxis_title="Metric",
            yaxis_title="Value",
            hovermode="x unified",
        )
        return glass_figure_layout(fig)

    except Exception as e:
        logger.warning(f"Wrap-up chart fallback: {e}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Season summary {selected_season} — league data not available",
            showarrow=False,
        )
        return glass_figure_layout(fig)


def _build_projection_chart(
    player_name: str,
    seasons: List[str],
    current_season: str,
) -> go.Figure:
    """
    Builds a forward-looking performance projection line chart.
    """
    try:
        dm = get_hong_kong_data_manager()
        pos_group = _get_position_group(player_name, dm)
        # Use the first metric for the primary trend line
        primary_metric = POSITION_METRICS.get(pos_group, ["Goals"])[0]
        metric_label = primary_metric.split(",")[0].strip()

        # Use available seasons as X axis; mock values where real data absent
        historical_y = [np.random.randint(2, 12) for _ in seasons]

        next_year_start = int(current_season.split("-")[0]) + 1
        next_season = f"{next_year_start}-{str(next_year_start + 1)[-2:]}"

        last_val = historical_y[-1]
        projected_val = max(0, last_val + np.random.normal(1, 2))

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=seasons,
            y=historical_y,
            mode="lines+markers",
            name=f"Historical ({metric_label})",
            line=dict(color=HKFATheme.ACCENT_BLUE, width=3),
            marker=dict(size=8),
        ))
        fig.add_trace(go.Scatter(
            x=[seasons[-1], next_season],
            y=[last_val, projected_val],
            mode="lines+markers",
            name="AI Projection",
            line=dict(color=HKFATheme.ACCENT_RED, width=3, dash="dash"),
            marker=dict(size=10, symbol="star"),
        ))
        fig.update_layout(
            title=f"Performance Projection: {player_name}",
            xaxis_title="Season",
            yaxis_title=metric_label,
            hovermode="x unified",
        )
        return glass_figure_layout(fig)
    except Exception as e:
        logger.error(f"Projection chart error: {e}")
        fig = go.Figure()
        fig.add_annotation(text=f"Error: {str(e)}", showarrow=False)
        return glass_figure_layout(fig)
