# ABOUTME: Shared helpers for AI visualizations and components.
# ABOUTME: Provides SHAP bar charts, UMAP scatter plots, and similarity tables for the dashboard.

# Standard Library
from typing import List, Optional

# Third-party
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import html

# Project
from utils.chart_helpers import HKFATheme, apply_hkfa_theme


def shap_bar_chart(
    shap_values: np.ndarray,
    feature_names: List[str],
    top_k: int = 10,
) -> go.Figure:
    """
    Generates a horizontal bar chart of SHAP values (top_k features by abs value).

    Positive SHAP values are shown in HKFA Blue, negative in HKFA Red.

    Args:
        shap_values: 1D or 2D array. If 2D, uses the mean across samples.
        feature_names: Feature names corresponding to SHAP columns.
        top_k: Number of top features to display.

    Returns:
        Plotly Figure.
    """
    values = np.array(shap_values)
    if values.ndim == 2:
        values = values.mean(axis=0)

    # Select top_k by absolute value
    indices = np.argsort(np.abs(values))[::-1][:top_k]
    top_values = values[indices]
    top_names = [feature_names[i] for i in indices]

    # Sort ascending so most important appears at top
    order = np.argsort(top_values)
    sorted_values = top_values[order]
    sorted_names = [top_names[i] for i in order]

    colors = [
        HKFATheme.ACCENT_BLUE if v >= 0 else HKFATheme.ACCENT_RED
        for v in sorted_values
    ]

    fig = go.Figure(go.Bar(
        x=sorted_values,
        y=sorted_names,
        orientation="h",
        marker_color=colors,
        hovertemplate="<b>%{y}</b><br>SHAP: %{x:.4f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text="Feature Importance (SHAP)", font=dict(size=14)),
        xaxis_title="SHAP Value",
        yaxis=dict(tickfont=dict(size=11)),
        margin=dict(l=10, r=20, t=50, b=40),
        height=max(300, top_k * 30),
    )
    return apply_hkfa_theme(fig)


def umap_scatter_chart(
    umap_df: pd.DataFrame,
    cluster_labels: Optional[np.ndarray] = None,
    archetype_labels: Optional[List[str]] = None,
) -> go.Figure:
    """
    Generates an interactive Plotly scatter plot for UMAP 2D projections.

    Each point represents a player-season. Points are colored by cluster.
    Hover shows player name, team, season, and archetype label.

    Args:
        umap_df: DataFrame with columns: x, y, player_name.
                 May also contain: team, season, cluster.
        cluster_labels: Integer array of cluster assignments (one per row).
        archetype_labels: List of archetype label strings, one per unique cluster.

    Returns:
        Plotly Figure.
    """
    df = umap_df.copy()
    if cluster_labels is not None:
        df["cluster"] = cluster_labels

    if "cluster" not in df.columns:
        df["cluster"] = 0

    unique_clusters = sorted(df["cluster"].unique())
    colors = HKFATheme.DATA_SERIES

    fig = go.Figure()

    for i, cluster_id in enumerate(unique_clusters):
        mask = df["cluster"] == cluster_id
        subset = df[mask]

        label = (
            archetype_labels[cluster_id]
            if archetype_labels and cluster_id < len(archetype_labels)
            else f"Cluster {cluster_id}"
        )

        hover_parts = ["<b>%{customdata[0]}</b>"]
        custom_cols = ["player_name"]
        if "team" in subset.columns:
            hover_parts.append("Team: %{customdata[1]}")
            custom_cols.append("team")
        if "season" in subset.columns:
            hover_parts.append("Season: %{customdata[2]}")
            custom_cols.append("season")
        hover_parts.append(f"Archetype: {label}")
        hover_parts.append("<extra></extra>")

        customdata = subset[custom_cols].values

        fig.add_trace(go.Scatter(
            x=subset["x"],
            y=subset["y"],
            mode="markers",
            name=label,
            marker=dict(
                color=colors[i % len(colors)],
                size=8,
                opacity=0.75,
                line=dict(width=0.5, color=HKFATheme.BG_TERTIARY),
            ),
            customdata=customdata,
            hovertemplate="<br>".join(hover_parts),
        ))

    fig.update_layout(
        title=dict(text="Player Archetypes — UMAP Projection", font=dict(size=14)),
        xaxis=dict(title="UMAP-1", showgrid=False, zeroline=False),
        yaxis=dict(title="UMAP-2", showgrid=False, zeroline=False),
        legend=dict(
            orientation="v",
            x=1.02,
            y=0.5,
            font=dict(size=11),
        ),
        margin=dict(l=10, r=10, t=50, b=40),
        height=500,
    )
    return apply_hkfa_theme(fig)


def similarity_table(results_df: pd.DataFrame) -> dbc.Table:
    """
    Returns a styled dbc.Table component for player similarity results.

    Args:
        results_df: DataFrame with columns: player_name, season, team, similarity_score.

    Returns:
        dbc.Table component.
    """
    if results_df is None or results_df.empty:
        return html.P("No similar players found.", className="text-muted text-center mt-3")

    df = results_df.copy().reset_index(drop=True)
    df.insert(0, "Rank", range(1, len(df) + 1))

    # Format similarity score as percentage
    if "similarity_score" in df.columns:
        df["similarity_score"] = df["similarity_score"].apply(lambda v: f"{v * 100:.1f}%")

    column_rename = {
        "player_name": "Player",
        "season": "Season",
        "team": "Team",
        "similarity_score": "Similarity",
    }
    df = df.rename(columns=column_rename)

    header = html.Thead(
        html.Tr([html.Th(col) for col in df.columns]),
        className="table-dark",
    )

    rows = []
    for _, row in df.iterrows():
        cells = [html.Td(str(row.get(col, ""))) for col in df.columns]
        # Make player name a link to /performance
        player_val = row.get("Player", "")
        cells[1] = html.Td(
            dbc.Button(
                player_val,
                id={"type": "similarity-player-link", "index": str(player_val)},
                color="link",
                size="sm",
                className="p-0 text-start",
                style={"color": HKFATheme.ACCENT_BLUE},
            )
        )
        rows.append(html.Tr(cells))

    body = html.Tbody(rows)

    return dbc.Table(
        [header, body],
        bordered=False,
        hover=True,
        responsive=True,
        striped=True,
        className="table-dark table-sm",
        style={"fontSize": "0.875rem"},
    )
