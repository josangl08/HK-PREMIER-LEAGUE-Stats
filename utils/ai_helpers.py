# ABOUTME: Helper functions for AI/LLM operations and AI Insights visualizations.
# ABOUTME: Provides chart builders (SHAP, UMAP, similarity, trend) and gcloud utilities.
# ABOUTME: Implements trend injection logic for the elite design agency.

# Standard Library
import subprocess
import logging
import os
import json
from pathlib import Path
from typing import List, Optional, Dict

# Safeguard for Numba threading layer on macOS (Silicon)
if "NUMBA_THREADING_LAYER" not in os.environ:
    os.environ["NUMBA_THREADING_LAYER"] = "workqueue"

# Third-party
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import html

# Project
from utils.chart_helpers import HKFATheme, apply_hkfa_theme

logger = logging.getLogger(__name__)


# ── Friendly feature name translation ────────────────────────────────────────

_FEATURE_SUFFIX_MAP = {
    "_lag_1": "(last season)",
    "_roll_3": "(3-season trend)",
    "_zscore_positional": "(vs position avg)",
    "_delta_league_avg": "(vs league avg)",
    "_delta_team_avg": "(vs team avg)",
    "_delta_positional_league_avg": "(vs position league avg)",
    "_delta_positional_team_avg": "(vs position team avg)",
    "_per90": "per 90 min",
    "_per90_benchmark": "(per 90, benchmark)",
}

_FRIENDLY_NAMES = {
    "Goals": "Goals Scored",
    "Assists": "Assists",
    "xG": "Expected Goals",
    "xA": "Expected Assists",
    "Accurate passes, %": "Pass Accuracy",
    "Shots on target, %": "Shot Accuracy",
    "Goal conversion, %": "Conversion Rate",
    "Dribbles per 90": "Dribbles / 90 min",
    "Crosses per 90": "Crosses / 90 min",
    "Key passes per 90": "Key Passes / 90 min",
    "Interceptions per 90": "Interceptions / 90 min",
    "Defensive duels won, %": "Defensive Duel Win %",
    "Aerial duels won, %": "Aerial Win %",
    "Shots blocked per 90": "Shots Blocked / 90",
    "Save rate, %": "Save Rate",
    "Clean sheets": "Clean Sheets",
    "Prevented goals per 90": "Prevented Goals / 90",
    "Minutes played": "Minutes Played",
    "Matches played": "Matches Played",
    "Yellow cards": "Yellow Cards",
    "Red cards": "Red Cards",
    "efficiency_index": "Efficiency Index",
    "defensive_wall": "Defensive Contribution",
    "Tackles": "Tackles",
    "Duels won, %": "Duel Win %",
    "Progressive runs per 90": "Progressive Runs / 90",
    "Forward passes per 90": "Forward Passes / 90",
    "Pass completion, %": "Pass Completion",
}


def _friendly_feature_name(raw: str) -> str:
    """
    Translates a raw ML feature column name into a human-readable label.
    Strips known suffixes, looks up base name, appends context tag.
    """
    suffix_tag = ""
    base = raw
    for suffix, tag in _FEATURE_SUFFIX_MAP.items():
        if raw.endswith(suffix):
            base = raw[: -len(suffix)]
            suffix_tag = f" {tag}"
            break
    friendly_base = _FRIENDLY_NAMES.get(base, base.replace("_", " ").title())
    return friendly_base + suffix_tag


# ── gcloud utilities ─────────────────────────────────────────────────────────

def get_session_cookie():
    """Returns the Gemini Session Cookie from .env for subscription bridging."""
    return os.getenv("GEMINI_SESSION_COOKIE")


def get_gcloud_auth_token():
    """
    Extracts the current gcloud access token from the system.
    This token carries the identity and subscription benefits of the logged-in user.
    """
    try:
        result = subprocess.run(
            ['gcloud', 'auth', 'print-access-token'],
            capture_output=True,
            text=True,
            check=True,
        )
        token = result.stdout.strip()
        if token:
            logger.info("✅ GCLOUD TOKEN: Successfully extracted Pro subscription token.")
            return token
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ GCLOUD ERROR: Failed to get token. Are you logged in? ({e.stderr.strip()})")
    except FileNotFoundError:
        logger.error("❌ GCLOUD NOT FOUND: Please install Google Cloud SDK.")
    return None


def is_gcloud_available():
    """Checks if gcloud CLI is installed and accessible."""
    try:
        subprocess.run(['gcloud', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


# ── UMAP scatter chart ────────────────────────────────────────────────────────

_CONSTELLATION_PALETTE = [
    "#00b4d8", "#06d6a0", "#ffb703", "#e63946", "#a8dadc",
    "#8338ec", "#fb8500", "#3a86ff", "#ff006e", "#43aa8b",
]


def _build_knn_edges(umap_df: pd.DataFrame, k: int = 4) -> list:
    """
    Calculates k nearest neighbours per player by euclidean distance on UMAP (x, y).
    Returns list of unique (i, j) pairs without inverse duplicates.
    """
    if umap_df.empty or len(umap_df) < 2:
        return []
    coords = umap_df[["x", "y"]].values
    edges = set()
    n = len(coords)
    for i in range(n):
        dists = np.sqrt(((coords - coords[i]) ** 2).sum(axis=1))
        dists[i] = np.inf  # exclude self
        nn_indices = np.argsort(dists)[:k]
        for j in nn_indices:
            pair = (min(i, int(j)), max(i, int(j)))
            edges.add(pair)
    return list(edges)


def constellation_chart(
    umap_df: pd.DataFrame,
    cluster_labels: Optional[np.ndarray] = None,
    archetype_labels: Optional[List[str]] = None,
    highlight_player: Optional[str] = None,
    knn_edges: Optional[list] = None,
) -> go.Figure:
    """
    Constellation Map: UMAP players as stars connected by kNN edges.
    Clusters rendered with 3-layer glow (exterior/mid/core). Highlight player in ACCENT_RED.
    """
    fig = go.Figure()
    palette = _CONSTELLATION_PALETTE

    coords = umap_df[["x", "y"]].values
    names  = umap_df["player_name"].tolist() if "player_name" in umap_df.columns else [str(i) for i in range(len(umap_df))]
    teams  = umap_df["team"].tolist() if "team" in umap_df.columns else [""] * len(umap_df)

    # ── Trace 0: kNN edge lines ───────────────────────────────────────────
    if knn_edges:
        ex, ey = [], []
        for i, j in knn_edges:
            ex += [coords[i][0], coords[j][0], None]
            ey += [coords[i][1], coords[j][1], None]
        fig.add_trace(go.Scatter(
            x=ex, y=ey,
            mode="lines",
            line=dict(color="rgba(255,255,255,0.3)", width=0.6),
            opacity=0.12,
            showlegend=False,
            hoverinfo="skip",
        ))

    # ── Cluster node layers (glow) ────────────────────────────────────────
    if cluster_labels is not None:
        unique_clusters = sorted(set(cluster_labels))
        centroid_positions = {}

        for layer_idx, (size, opacity) in enumerate([(16, 0.08), (11, 0.18), (7, 1.0)]):
            is_core = layer_idx == 2
            for ci in unique_clusters:
                mask = cluster_labels == ci
                sub_x = coords[mask, 0]
                sub_y = coords[mask, 1]
                sub_names = [names[k] for k, m in enumerate(mask) if m]
                sub_teams = [teams[k] for k, m in enumerate(mask) if m]
                color = palette[ci % len(palette)]
                arch = (archetype_labels[ci] if archetype_labels and ci < len(archetype_labels)
                        else f"Cluster {ci}")

                hover = [
                    f"{n}<br>{t}<br>{arch}"
                    for n, t in zip(sub_names, sub_teams)
                ] if is_core else None

                fig.add_trace(go.Scatter(
                    x=sub_x, y=sub_y,
                    mode="markers",
                    name=arch if is_core else None,
                    showlegend=is_core,
                    marker=dict(size=size, color=color, opacity=opacity,
                                line=dict(width=0)),
                    text=hover,
                    hovertemplate="%{text}<extra></extra>" if is_core else None,
                    hoverinfo="skip" if not is_core else None,
                ))

                # Track centroid for label placement
                if is_core and len(sub_x):
                    centroid_positions[ci] = (float(sub_x.mean()), float(sub_y.mean()), arch)

        # ── Cluster centroid labels ───────────────────────────────────────
        if centroid_positions:
            cx = [v[0] for v in centroid_positions.values()]
            cy = [v[1] for v in centroid_positions.values()]
            ct = [v[2] for v in centroid_positions.values()]
            fig.add_trace(go.Scatter(
                x=cx, y=cy,
                mode="text",
                text=ct,
                textfont=dict(size=11, color="rgba(255,255,255,0.4)"),
                showlegend=False,
                hoverinfo="skip",
            ))
    else:
        # No cluster labels — single grey scatter
        fig.add_trace(go.Scatter(
            x=coords[:, 0], y=coords[:, 1],
            mode="markers",
            marker=dict(size=7, color="rgba(0,242,255,0.7)"),
            text=names, hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        ))

    # ── Highlight player (3 layers) ───────────────────────────────────────
    if highlight_player:
        hp_mask = [n == highlight_player for n in names]
        hp_x = coords[[i for i, m in enumerate(hp_mask) if m], 0]
        hp_y = coords[[i for i, m in enumerate(hp_mask) if m], 1]
        _HP_COLOR = "#a855f7"
        if len(hp_x):
            for hp_size, hp_op in [(36, 0.07), (26, 0.15), (16, 1.0)]:
                fig.add_trace(go.Scatter(
                    x=hp_x, y=hp_y,
                    mode="markers" + ("+text" if hp_size == 16 else ""),
                    marker=dict(size=hp_size, color=_HP_COLOR, opacity=hp_op,
                                line=dict(width=0)),
                    text=[highlight_player] if hp_size == 16 else None,
                    textposition="top center",
                    textfont=dict(size=11, color=_HP_COLOR),
                    name="Selected" if hp_size == 16 else None,
                    showlegend=hp_size == 16,
                    hoverinfo="skip" if hp_size != 16 else None,
                    hovertemplate=f"{highlight_player}<extra></extra>" if hp_size == 16 else None,
                ))

    fig.update_layout(
        plot_bgcolor="#000000",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=True,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="white")),
    )
    return fig


def umap_scatter_chart(
    umap_df: pd.DataFrame,
    cluster_labels: Optional[np.ndarray] = None,
    archetype_labels: Optional[List[str]] = None,
) -> go.Figure:
    # Deprecated — usar constellation_chart()
    """
    Creates a Plotly scatter chart from a UMAP DataFrame.
    Expected columns: x, y, player_name, and optionally team, season.

    When cluster_labels are provided, one trace per cluster is rendered
    using the HKFATheme DATA_SERIES palette.  archetype_labels maps each
    cluster integer to a human-readable name shown in the legend.
    """
    if cluster_labels is not None:
        unique_clusters = sorted(set(cluster_labels))
        fig = go.Figure()
        palette = HKFATheme.DATA_SERIES

        for i, cluster_id in enumerate(unique_clusters):
            mask = cluster_labels == cluster_id
            sub = umap_df[mask]

            arch_name = (
                archetype_labels[cluster_id]
                if archetype_labels and cluster_id < len(archetype_labels)
                else f"Cluster {cluster_id}"
            )
            color = palette[i % len(palette)]

            hover_text = sub.get("player_name", sub.index).astype(str)
            if "team" in sub.columns:
                hover_text = hover_text + "<br>" + sub["team"].astype(str)
            hover_text = hover_text + f"<br>{arch_name}"

            fig.add_trace(go.Scatter(
                x=sub["x"],
                y=sub["y"],
                mode="markers",
                name=arch_name,
                marker=dict(size=8, color=color, line=dict(width=1, color=HKFATheme.BG_PRIMARY)),
                text=hover_text,
                hovertemplate="%{text}<extra></extra>",
            ))

        fig.update_layout(showlegend=True)
    else:
        # Backward-compatible single-trace path (used by stage_helpers.py)
        hover_text = umap_df.get("player_name", umap_df.index).astype(str)
        if "team" in umap_df.columns:
            hover_text = hover_text + "<br>" + umap_df["team"].astype(str)
        if "season" in umap_df.columns:
            hover_text = hover_text + "<br>" + umap_df["season"].astype(str)

        fig = go.Figure(go.Scatter(
            x=umap_df["x"],
            y=umap_df["y"],
            mode="markers",
            marker=dict(size=8, color="rgba(0,242,255,0.7)", line=dict(width=1, color="#1a1a2e")),
            text=hover_text,
            hovertemplate="%{text}<extra></extra>",
        ))
        fig.update_layout(showlegend=False)

    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
    return apply_hkfa_theme(fig)


# ── SHAP bar chart ────────────────────────────────────────────────────────────

def shap_bar_chart(
    shap_vals: np.ndarray,
    feature_names: List[str],
    top_k: int = 10,
) -> go.Figure:
    """
    Horizontal bar chart of SHAP feature importances for a single prediction.

    shap_vals: 2D array (n_samples, n_features) — only the first row is used.
               If 3D (TabPFN multi-output), the last axis is squeezed first.
    feature_names: Raw column names aligned with shap_vals columns.
    top_k: Number of top features (by absolute SHAP value) to display.
    """
    vals = np.array(shap_vals)

    # Handle TabPFN 3D output: (n_samples, n_features, n_outputs)
    if vals.ndim == 3:
        vals = vals[:, :, 0]

    # Take first (only) player row
    row = vals[0] if vals.ndim == 2 else vals

    # Sort by absolute value, keep top_k
    pairs = sorted(zip(feature_names, row.tolist()), key=lambda x: abs(x[1]), reverse=True)
    pairs = pairs[:top_k]

    labels = [_friendly_feature_name(name) for name, _ in pairs]
    values = [v for _, v in pairs]
    colors = [HKFATheme.POSITIVE if v >= 0 else HKFATheme.NEGATIVE for v in values]

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h",
        marker=dict(color=colors),
        hovertemplate="<b>%{y}</b><br>SHAP: %{x:.3f}<extra></extra>",
    ))
    fig.update_layout(
        xaxis_title="SHAP value (impact on prediction)",
        margin=dict(l=10, r=10, t=30, b=10),
        yaxis=dict(autorange="reversed"),
    )
    return apply_hkfa_theme(fig)


# ── Similarity table ──────────────────────────────────────────────────────────

def similarity_table(results_df: pd.DataFrame) -> html.Div:
    """
    Renders a styled table of similar players with progress-bar similarity scores.

    results_df must have columns: player_name, season, team, similarity_score.
    Player name cells use pattern-matched ids for click-through navigation.
    """
    header = html.Thead(html.Tr([
        html.Th("Player", className="text-white"),
        html.Th("Season", className="text-white"),
        html.Th("Team", className="text-white"),
        html.Th("Similarity", className="text-white"),
    ]))

    rows = []
    for _, row in results_df.iterrows():
        score = float(row.get("similarity_score", 0))
        score_pct = round(score * 100, 1)
        rows.append(html.Tr([
            html.Td(html.Button(
                str(row.get("player_name", "")),
                id={"type": "similarity-player-link", "index": str(row.get("player_name", ""))},
                n_clicks=0,
                className="btn btn-link p-0 text-start",
                style={"color": HKFATheme.ACCENT_BLUE, "fontSize": "0.9rem"},
            )),
            html.Td(str(row.get("season", "—")), className="text-secondary"),
            html.Td(str(row.get("team", "—")), className="text-secondary"),
            html.Td(dbc.Progress(
                value=score_pct,
                label=f"{score_pct}%",
                color="info",
                style={"minWidth": "90px", "height": "18px"},
            )),
        ]))

    table = dbc.Table(
        [header, html.Tbody(rows)],
        bordered=False,
        hover=True,
        responsive=True,
        size="sm",
        style={"color": HKFATheme.TEXT_PRIMARY},
    )
    return html.Div(table, className="mt-2")


# ── Trend chart with prediction range ────────────────────────────────────────

def trend_chart(
    seasons: List[str],
    actuals: List[float],
    predicted_next_season: str,
    predicted_value: float,
    lower: float,
    upper: float,
    metric_name: str,
) -> go.Figure:
    """
    Line chart showing a player's historical metric values and a predicted next-season point.

    seasons / actuals: historical data (aligned lists).
    predicted_next_season: label for the forecast point (e.g. "2025-26").
    predicted_value / lower / upper: forecast ± confidence interval.
    metric_name: human-readable metric label for axis title.
    """
    fig = go.Figure()

    all_seasons = list(seasons) + [predicted_next_season]

    # Historical line
    fig.add_trace(go.Scatter(
        x=list(seasons),
        y=actuals,
        mode="lines+markers",
        name="Actual",
        line=dict(color=HKFATheme.ACCENT_BLUE, width=2),
        marker=dict(size=7),
        hovertemplate="Season: %{x}<br>" + metric_name + ": %{y:.2f}<extra></extra>",
    ))

    # Confidence band around forecast point
    fig.add_trace(go.Scatter(
        x=[predicted_next_season, predicted_next_season],
        y=[lower, upper],
        mode="lines",
        line=dict(color=HKFATheme.ACCENT_GOLD, width=0),
        showlegend=False,
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=[predicted_next_season, predicted_next_season],
        y=[upper, lower],
        fill="tonexty",
        fillcolor=f"rgba(255,184,28,0.18)",
        line=dict(color="rgba(0,0,0,0)"),
        showlegend=False,
        hoverinfo="skip",
        name="Confidence range",
    ))

    # Predicted point
    fig.add_trace(go.Scatter(
        x=[predicted_next_season],
        y=[predicted_value],
        mode="markers",
        name="Forecast",
        marker=dict(
            size=12,
            color=HKFATheme.ACCENT_GOLD,
            symbol="diamond",
            line=dict(width=2, color=HKFATheme.BG_PRIMARY),
        ),
        hovertemplate="Forecast %{x}<br>" + metric_name + ": %{y:.2f}<extra></extra>",
    ))

    # Dashed connector from last actual to forecast
    if actuals:
        fig.add_trace(go.Scatter(
            x=[seasons[-1], predicted_next_season],
            y=[actuals[-1], predicted_value],
            mode="lines",
            line=dict(color=HKFATheme.ACCENT_GOLD, width=1.5, dash="dash"),
            showlegend=False,
            hoverinfo="skip",
        ))

    fig.update_layout(
        xaxis_title="Season",
        yaxis_title=metric_name,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return apply_hkfa_theme(fig)


# ── Design Trend Injection (RAG-lite) ────────────────────────────────────────

def get_all_design_trends() -> List[Dict]:
    """
    Loads all design trends from assets/design_trends/*.json.
    """
    trends_dir = Path("assets/design_trends")
    if not trends_dir.exists():
        return []

    trends = []
    for f in sorted(trends_dir.glob("*.json")):
        try:
            with open(f, "r") as jf:
                trends.append(json.load(jf))
        except Exception as e:
            logger.error(f"Error loading trend {f.name}: {e}")
    return trends


def get_trend_by_name(name: str) -> Optional[Dict]:
    """Retrieves a specific design trend by its 'name' field."""
    trends = get_all_design_trends()
    for t in trends:
        if t.get("name") == name:
            return t
    return None


def format_trends_for_prompt(trends: List[Dict]) -> str:
    """
    Formats a list of design trends into a structured string for LLM injection.
    """
    if not trends:
        return "No specific design trends available."

    output = "## AVAILABLE DESIGN TRENDS & MOODBOARDS:\n"
    for t in trends:
        output += f"\n### Trend: {t.get('name')}\n"
        output += f"- Description: {t.get('description')}\n"

        vi = t.get("visual_identity", {})
        output += f"- Typography: {vi.get('typography', {}).get('primary')} ({vi.get('typography', {}).get('style')})\n"
        color_p = vi.get('color_palette', {})
        output += f"- Colors: Base: {color_p.get('base')}, Accents: {', '.join(color_p.get('accents', []))}\n"
        output += f"- Composition: {vi.get('elements', {}).get('composition')}\n"
        output += f"- Nanobana Keywords: {t.get('nanobana_prompt_injection')}\n"

    return output
