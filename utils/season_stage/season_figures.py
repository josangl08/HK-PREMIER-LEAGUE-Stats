# ABOUTME: Plotly figures for the season-stage surface, including semantic quadrant and enriched UMAP evidence visuals.
# ABOUTME: Keeps figure construction separate from context assembly and Dash component rendering.

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ai_models.clustering import fit_umap
from utils.ai_helpers import constellation_chart, _build_knn_edges
from utils.chart_helpers import HKFATheme, glass_figure_layout
from utils.cache import cache

_FIGURE_CACHE_VERSION = "v3"
_FIGURE_CACHE_TTL = 3600  # 1 hour — season data doesn't change between ETL runs


def build_season_comparison_figure(metrics: list[dict], previous_season_label: str, current_season_label: str) -> go.Figure:
    if not metrics:
        fig = go.Figure()
        fig.add_annotation(text="Season comparison is not available yet.", showarrow=False)
        return glass_figure_layout(fig)

    labels = [metric["label"] for metric in metrics]
    colors = [metric.get("color", "#f5b942") for metric in metrics]

    # Use pre-scaled values (0.0 to 1.0) calculated in season_components.py
    # This prevents the "minutes" bar or other high-value metrics from having
    # a different visual weight than others while maintaining comparability.
    prev_values = [metric.get("previous_scaled", 0.0) for metric in metrics]
    curr_values = [metric.get("current_scaled", 0.0) for metric in metrics]

    # Two-column subplot with shared Y axis so metric labels sit at the center divider.
    # Left column: previous season with reversed X axis (bars grow right-to-left).
    # Right column: current season with normal X axis (bars grow left-to-right).
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.02)

    fig.add_trace(
        go.Bar(
            y=labels,
            x=prev_values,
            orientation="h",
            marker=dict(color=colors, line=dict(color=colors, width=1)),
            text=[f"<b>{metric.get('previous_display', '0')}</b>" for metric in metrics],
            textposition="auto",
            insidetextanchor="end",
            textfont=dict(size=10, color="rgba(244,248,252,0.88)"),
            cliponaxis=False,
            customdata=[[metric.get("previous_display", "0")] for metric in metrics],
            hovertemplate=f"{previous_season_label or 'Previous'}<br>%{{y}}: %{{customdata[0]}}<extra></extra>",
            name=previous_season_label or "Previous",
            showlegend=False,
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Bar(
            y=labels,
            x=curr_values,
            orientation="h",
            marker=dict(color=colors, line=dict(color=colors, width=1)),
            text=[f"<b>{metric.get('current_display', '0')}</b>" for metric in metrics],
            textposition="auto",
            insidetextanchor="end",
            textfont=dict(size=10, color="rgba(244,248,252,0.88)"),
            cliponaxis=False,
            customdata=[[metric.get("current_display", "0")] for metric in metrics],
            hovertemplate=f"{current_season_label or 'Selected'}<br>%{{y}}: %{{customdata[0]}}<extra></extra>",
            name=current_season_label or "Selected",
            showlegend=False,
        ),
        row=1, col=2,
    )

    fig.update_layout(
        bargap=0.42,
        showlegend=False,
        height=max(300, 46 + (len(metrics) * 44)),
        margin=dict(l=10, r=2, t=46, b=0),
        xaxis=dict(autorange="reversed", range=[0, 1.25], tickvals=[], showgrid=False, zeroline=False),
        xaxis2=dict(range=[0, 1.12], tickvals=[], showgrid=False, zeroline=False),
        yaxis=dict(
            autorange="reversed",
            showgrid=False,
            showticklabels=True,
            tickfont=dict(size=9, color="rgba(244,248,252,0.88)"),
        ),
    )

    fig.add_annotation(
        x=0.25, y=1.06, xref="paper", yref="paper",
        text=previous_season_label or "Previous",
        showarrow=False, xanchor="center",
        font=dict(size=11, color="rgba(244,248,252,0.72)"),
    )
    fig.add_annotation(
        x=0.75, y=1.06, xref="paper", yref="paper",
        text=current_season_label or "Selected",
        showarrow=False, xanchor="center",
        font=dict(size=11, color="rgba(255,243,204,0.92)"),
    )

    # apply_hkfa_theme (called inside glass_figure_layout) forces showline=True on all
    # axes via update_layout. Override everything after the theme is applied.
    fig = glass_figure_layout(fig)
    fig.update_xaxes(showline=False, ticks="", showgrid=False, tickvals=[])
    fig.update_yaxes(showline=False, ticks="", showgrid=False)
    return fig


def build_season_quadrant_figure(profile_context: Dict[str, Any]) -> go.Figure:
    _player = profile_context.get("player_name", "")
    _season = profile_context.get("season", "")
    if _player and _season:
        _ck = f"season-quadrant-fig:{_FIGURE_CACHE_VERSION}:{_player}:{_season}"
        _cached = cache.get(_ck)
        if _cached is not None:
            return go.Figure(_cached)

    fig = go.Figure()
    if not profile_context.get("available"):
        fig.add_annotation(text="Profile data is not available for this season.", showarrow=False)
        return glass_figure_layout(fig)

    cohort = profile_context["cohort"]
    nearest = {item["name"] for item in profile_context.get("nearest_profiles", [])}
    player_name = profile_context.get("player_name")
    quadrant_labels = profile_context.get("quadrant_labels") or {}

    x_min = float(cohort["semantic_axis_x"].min())
    x_max = float(cohort["semantic_axis_x"].max())
    y_min = float(cohort["semantic_axis_y"].min())
    y_max = float(cohort["semantic_axis_y"].max())
    x_pad = max((x_max - x_min) * 0.18, 0.4)
    y_pad = max((y_max - y_min) * 0.18, 0.4)
    x_range = [x_min - x_pad, x_max + x_pad]
    y_range = [y_min - y_pad, y_max + y_pad]

    rects = [
        (x_range[0], 0, 0, y_range[1], "rgba(99,102,241,0.10)"),
        (0, x_range[1], 0, y_range[1], "rgba(34,197,94,0.10)"),
        (x_range[0], 0, y_range[0], 0, "rgba(239,68,68,0.08)"),
        (0, x_range[1], y_range[0], 0, "rgba(245,158,11,0.08)"),
    ]
    for x0, x1, y0, y1, fill in rects:
        fig.add_shape(
            type="rect",
            x0=x0,
            x1=x1,
            y0=y0,
            y1=y1,
            line=dict(width=0),
            fillcolor=fill,
            layer="below",
        )

    fig.add_hline(y=0, line_width=1, line_color="rgba(255,255,255,0.16)")
    fig.add_vline(x=0, line_width=1, line_color="rgba(255,255,255,0.16)")

    base = cohort[~cohort["Player"].isin(list(nearest) + [player_name])]
    if not base.empty:
        fig.add_trace(go.Scatter(
            x=base["semantic_axis_x"],
            y=base["semantic_axis_y"],
            mode="markers",
            name="League Cohort",
            marker=dict(size=10, color="rgba(255,255,255,0.18)"),
            hovertemplate="%{text}<extra></extra>",
            text=[f"{row.Player}<br>{row.Team}<br>{row.cluster_label}" for row in base.itertuples()],
        ))

    near_df = cohort[cohort["Player"].isin(nearest)]
    if not near_df.empty:
        fig.add_trace(go.Scatter(
            x=near_df["semantic_axis_x"],
            y=near_df["semantic_axis_y"],
            mode="markers+text",
            name="Nearest Profiles",
            text=near_df["Player"],
            textposition="top center",
            marker=dict(size=13, color="rgba(255,214,102,0.48)", line=dict(color="#f5b942", width=1)),
            hovertemplate="%{text}<extra></extra>",
        ))

    player_point = profile_context["player_point"]
    fig.add_trace(go.Scatter(
        x=[player_point["x"]],
        y=[player_point["y"]],
        mode="markers+text",
        name="You",
        text=[player_name],
        textposition="top center",
        marker=dict(size=18, color="#22c55e", line=dict(color="#ffffff", width=2)),
        hovertemplate=f"{player_name}<br>{profile_context.get('archetype_label')}<extra></extra>",
    ))

    label_points = [
        ((x_range[0] + 0) / 2, (0 + y_range[1]) / 2, quadrant_labels.get("top_left")),
        ((0 + x_range[1]) / 2, (0 + y_range[1]) / 2, quadrant_labels.get("top_right")),
        ((x_range[0] + 0) / 2, (y_range[0] + 0) / 2, quadrant_labels.get("bottom_left")),
        ((0 + x_range[1]) / 2, (y_range[0] + 0) / 2, quadrant_labels.get("bottom_right")),
    ]
    for x, y, text in label_points:
        if not text:
            continue
        fig.add_annotation(
            x=x,
            y=y,
            text=text,
            showarrow=False,
            font=dict(size=11, color="rgba(255,255,255,0.42)"),
            xanchor="center",
            yanchor="middle",
        )

    fig.update_layout(
        title=None,
        height=560,
        showlegend=False,
        margin=dict(l=40, r=24, t=4, b=48),
        xaxis_title=profile_context["axis_labels"]["x"],
        yaxis_title=profile_context["axis_labels"]["y"],
        xaxis=dict(range=x_range, zeroline=False),
        yaxis=dict(range=y_range, zeroline=False),
    )
    result = glass_figure_layout(fig)
    if _player and _season:
        cache.set(_ck, result.to_dict(), timeout=_FIGURE_CACHE_TTL)
    return result


def build_season_umap_evidence_figure(profile_context: Dict[str, Any]) -> go.Figure:
    _player = profile_context.get("player_name", "")
    _season = profile_context.get("season", "")
    if _player and _season:
        _ck = f"season-umap-fig:{_FIGURE_CACHE_VERSION}:{_player}:{_season}"
        _cached = cache.get(_ck)
        if _cached is not None:
            return go.Figure(_cached)

    fig = go.Figure()
    if not profile_context.get("available"):
        fig.add_annotation(text="Full profile map is not available for this season.", showarrow=False)
        return glass_figure_layout(fig)

    cohort = profile_context["cohort"]
    X_scaled = profile_context["scaled_matrix"]
    player_name = profile_context["player_name"]
    if len(cohort) < 4 or len(X_scaled) < 4:
        fig.add_trace(go.Scatter(
            x=cohort["semantic_axis_x"],
            y=cohort["semantic_axis_y"],
            mode="markers",
            marker=dict(size=11, color="rgba(0,212,255,0.38)"),
            text=cohort["Player"],
            hovertemplate="%{text}<extra></extra>",
        ))
        fig.update_layout(title="Full Profile Map")
        return glass_figure_layout(fig)
    umap_df, _ = fit_umap(X_scaled, player_names=cohort["Player"].tolist())
    umap_df["team"] = cohort["Team"].tolist()
    umap_df["cluster_id"] = cohort["cluster_id"].tolist()
    labels_by_cluster = {}
    for row in cohort[["cluster_id", "cluster_label"]].drop_duplicates().itertuples():
        labels_by_cluster[int(row.cluster_id)] = str(row.cluster_label)
    cluster_labels = np.array(cohort["cluster_id"].tolist(), dtype=int)
    archetype_labels = [
        labels_by_cluster.get(cluster_id, f"Cluster {cluster_id}")
        for cluster_id in sorted(labels_by_cluster)
    ]
    knn_edges = _build_knn_edges(umap_df, k=4)
    fig = constellation_chart(
        umap_df,
        cluster_labels=cluster_labels,
        archetype_labels=archetype_labels,
        highlight_player=player_name,
        knn_edges=knn_edges,
    )
    fig.update_layout(title="Full Profile Map", height=480, autosize=False)
    result = glass_figure_layout(fig)
    if _player and _season:
        cache.set(_ck, result.to_dict(), timeout=_FIGURE_CACHE_TTL)
    return result
