# ABOUTME: Helper functions for rendering Stage scenarios and AI widgets.
# ABOUTME: Dispatches rendering for post-match, pre-match, and career-insights.

import logging
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc
from typing import Dict, List, Any, Optional

from data.hong_kong_data_manager import HongKongDataManager
from utils.chart_helpers import apply_hkfa_theme, HKFATheme
from utils.ai_helpers import umap_scatter_chart

logger = logging.getLogger(__name__)

def render_post_match(payload: Dict[str, Any]) -> html.Div:
    """
    Renders the Post-Match analysis stage.
    Shows a match header, Radar Chart, and Percentile bars for the player's season stats.
    """
    opponent = payload.get("opponent", "Rival")
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
    player_name = basic.get("name", "Jugador")
    position = basic.get("position_primary", basic.get("position", ""))

    # Radar: use available numeric stats normalized 0-100 via percentiles
    radar_metrics = ["Goals", "Assists", "Accurate passes, %", "Minutes played"]
    radar_values = [percentiles.get(m, 50) for m in radar_metrics]
    radar_labels = ["Goles", "Asistencias", "Precisión pases", "Minutos"]

    from utils.chart_helpers import create_radar_chart
    radar_fig = create_radar_chart(
        values=radar_values,
        metrics=radar_labels,
        title=f"{player_name} — Percentiles de temporada",
        name=player_name,
    )

    from utils.chart_helpers import create_percentile_bars
    percentile_display = {
        "Goles": percentiles.get("Goals", 0),
        "Asistencias": percentiles.get("Assists", 0),
        "Pases %": percentiles.get("Accurate passes, %", 0),
        "Minutos": percentiles.get("Minutes played", 0),
    }

    # ── Layout ─────────────────────────────────────────────────────────────
    return html.Div([
        header,
        html.P([
            html.I(className="bi bi-person-fill me-1"),
            html.Span(f"{player_name}", className="fw-semibold me-2"),
            html.Small(position, className="text-muted badge bg-secondary"),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col([
                html.H6("Radar de Rendimiento", className="text-muted mb-2"),
                dcc.Graph(figure=radar_fig, config={"displayModeBar": False}, className="w-100"),
            ], width=12, md=7),
            dbc.Col([
                html.H6("Percentiles", className="text-muted mb-3"),
                create_percentile_bars(percentile_display),
            ], width=12, md=5),
        ]),
    ])


def render_pre_match(payload: Dict[str, Any]) -> html.Div:
    """
    Renders the Pre-Match preparation hub.
    Shows fixture details, opponent info, and a rule-based Game-Plan insight.
    """
    opponent = payload.get("opponent", "Rival")
    home = payload.get("home_team", "")
    away = payload.get("away_team", "")
    date_str = payload.get("kickoff_display") or str(payload.get("date", ""))[:16]
    stadium = payload.get("stadium", "")
    streaming_url = payload.get("streaming_url")
    competition = payload.get("competition", "HK Premier League")

    # ── Fixture header ─────────────────────────────────────────────────────
    streaming_link = html.A(
        [html.I(className="bi bi-play-circle me-1"), "Ver en streaming"],
        href=streaming_url,
        target="_blank",
        className="btn btn-sm btn-outline-primary mt-2",
    ) if streaming_url else html.Small("Sin retransmisión disponible", className="text-muted")

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
                html.Span(stadium or "Estadio por confirmar"),
            ], className="small text-muted"),
            html.Div(streaming_link, className="mt-2"),
        ])
    ], className="mb-3 border-0 shadow-sm")

    # ── Game-Plan insight (rule-based) ─────────────────────────────────────
    try:
        dm = HongKongDataManager()
        opp_stats = dm.get_player_overview(opponent)
        has_opp_data = opp_stats and "error" not in opp_stats
    except Exception:
        has_opp_data = False

    if has_opp_data:
        game_plan_text = (
            f"Análisis disponible para {opponent}. "
            "Revisa sus estadísticas defensivas y ofensivas para preparar la táctica."
        )
    else:
        game_plan_text = (
            f"Prepárate para el partido contra {opponent}. "
            "Enfócate en transiciones rápidas y presión alta en el mediocampo."
        )

    game_plan_card = dbc.Card([
        dbc.CardHeader([
            html.I(className="bi bi-robot me-2"),
            html.Span("Game-Plan AI", className="fw-semibold"),
        ], className="border-0"),
        dbc.CardBody([
            html.P(game_plan_text, className="mb-0 small"),
        ])
    ], className="border-0 shadow-sm mb-3", color="dark", outline=True)

    return html.Div([fixture_card, game_plan_card])


def render_career_insights(payload: Dict[str, Any], user_role: str = "player") -> html.Div:
    """
    Renders the Career Insights stage with projection, UMAP clustering,
    and a role-conditional Dossier export button.
    """
    season = payload.get("season", "")
    player_id = payload.get("player_id", "")
    player_name = payload.get("player_name", "Jugador")

    # ── Projection figure ──────────────────────────────────────────────────
    projection_fig = get_projection_figure(player_id, season)
    projection_section = dbc.Card([
        dbc.CardHeader([
            html.I(className="bi bi-graph-up-arrow me-2"),
            html.Span("Proyección de Rendimiento", className="fw-semibold"),
        ], className="border-0"),
        dbc.CardBody([
            dcc.Graph(figure=projection_fig, config={"displayModeBar": False}),
        ])
    ], className="border-0 shadow-sm mb-3")

    # ── UMAP clustering figure ─────────────────────────────────────────────
    umap_fig = get_umap_figure(player_id)
    umap_section = dbc.Card([
        dbc.CardHeader([
            html.I(className="bi bi-diagram-3 me-2"),
            html.Span("Mapa de Estilo de Juego (UMAP)", className="fw-semibold"),
        ], className="border-0"),
        dbc.CardBody([
            dcc.Graph(figure=umap_fig, config={"displayModeBar": False}),
        ])
    ], className="border-0 shadow-sm mb-3")

    # ── Agent role: Dossier export button ──────────────────────────────────
    dossier_button = html.Div()
    if user_role == "agent":
        dossier_button = html.Div([
            dbc.Button(
                [html.I(className="bi bi-file-earmark-pdf me-2"), "Exportar Dossier PDF"],
                id="export-dossier-btn",
                color="danger",
                outline=True,
                className="mt-2",
                n_clicks=0,
            ),
            dcc.Download(id="dossier-download"),
        ])

    return html.Div([
        html.H6([
            html.I(className="bi bi-calendar3 me-2"),
            f"Perspectiva de Carrera — Temporada {season}",
        ], className="mb-3 text-muted"),
        dbc.Row([
            dbc.Col(projection_section, width=12, lg=6),
            dbc.Col(umap_section, width=12, lg=6),
        ]),
        dossier_button,
    ])

def get_umap_figure(player_id: str) -> go.Figure:
    """
    Wraps clustering_engine output into a Plotly figure.
    Highlights the selected player's point.
    """
    try:
        from ai_models.clustering import fit_umap
        from data.hong_kong_data_manager import HongKongDataManager
        from utils.player_index import get_player_index
        
        dm = HongKongDataManager()
        df = dm.processed_data
        if df is None or df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No hay datos disponibles para clustering", showarrow=False)
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
                    name="Seleccionado",
                    showlegend=True
                ))

        fig.update_layout(title="Mapa de Estilo de Juego (UMAP)")
        return apply_hkfa_theme(fig)
    except Exception as e:
        logger.error(f"Error generating UMAP figure: {e}")
        fig = go.Figure()
        fig.add_annotation(text=f"Error: {str(e)}", showarrow=False)
        return apply_hkfa_theme(fig)

def get_projection_figure(player_id: str, season: str) -> go.Figure:
    """
    Wraps predictor_engine output into a Plotly line chart.
    Shows historical stats + projected next season.
    """
    try:
        from utils.player_index import get_player_index
        
        pi = get_player_index()
        player_info = pi.get_player_info(player_id)
        if not player_info:
            fig = go.Figure()
            fig.add_annotation(text="Jugador no encontrado", showarrow=False)
            return apply_hkfa_theme(fig)
        
        player_name = player_info.get("canonical_name")
        seasons = player_info.get("seasons", [])
        
        if not seasons:
            fig = go.Figure()
            fig.add_annotation(text="Datos insuficientes para proyección", showarrow=False)
            return apply_hkfa_theme(fig)

        # Mock historical + projection for the stub
        # In a real scenario, we'd fetch actual goals/metrics per season
        fig = go.Figure()
        
        # Historical
        historical_y = [np.random.randint(2, 12) for _ in seasons]
        fig.add_trace(go.Scatter(
            x=seasons,
            y=historical_y,
            mode="lines+markers",
            name="Histórico (Goles)",
            line=dict(color=HKFATheme.ACCENT_BLUE, width=3),
            marker=dict(size=8)
        ))
        
        # Projection
        last_val = historical_y[-1]
        projected_val = max(0, last_val + np.random.normal(1, 2))
        next_season = "2026-27"
        
        fig.add_trace(go.Scatter(
            x=[seasons[-1], next_season],
            y=[last_val, projected_val],
            mode="lines+markers",
            name="Proyección AI",
            line=dict(color=HKFATheme.ACCENT_RED, width=3, dash="dash"),
            marker=dict(size=10, symbol="star")
        ))

        fig.update_layout(
            title=f"Proyección de Rendimiento: {player_name}",
            xaxis_title="Temporada",
            yaxis_title="Goles",
            hovermode="x unified"
        )
        return apply_hkfa_theme(fig)
    except Exception as e:
        logger.error(f"Error generating projection figure: {e}")
        fig = go.Figure()
        fig.add_annotation(text=f"Error: {str(e)}", showarrow=False)
        return apply_hkfa_theme(fig)
