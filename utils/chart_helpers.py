# ABOUTME: Reusable Plotly chart utilities with HKFA theme
# ABOUTME: Provides theme configuration, common chart patterns, helper functions

"""
utils/chart_helpers.py

Provides:
1. HKFA theme configuration and appliers
2. Common chart creation functions with sensible defaults
3. Interactive pattern helpers (hover templates, callbacks)
4. Data normalization utilities
5. Performance optimization strategies
"""

from typing import Dict, List, Optional, Any, Tuple
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import dash_bootstrap_components as dbc
from dash import html


# ============================================================================
# SECTION 1: HKFA THEME CONFIGURATION
# ============================================================================

class HKFATheme:
    """HKFA color theme and styling constants."""

    # Primary colors
    BG_PRIMARY = "#18181A"
    BG_SECONDARY = "#18181A"
    BG_TERTIARY = "#232326"

    # Accents
    ACCENT_RED = "#ED1C24"
    ACCENT_GOLD = "#FFB81C"
    ACCENT_BLUE = "#00A3E0"

    # Text
    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#A7A7A7"
    TEXT_TERTIARY = "#6B6B6F"

    # Borders
    BORDER_COLOR = "#3A3A3C"

    # Grid lines (lighter than border for chart readability)
    GRID_COLOR = "#525255"

    # Data series palette (colorblind-safe)
    DATA_SERIES = [
        "#ED1C24",  # HKFA Red
        "#FFB81C",  # Gold
        "#00A3E0",  # Blue
        "#6ED47E",  # Green
        "#E74856",  # Dark Red
        "#9B59B6",  # Purple
        "#F39C12",  # Orange
        "#16A085"   # Teal
    ]

    # Semantic colors
    POSITIVE = "#6ED47E"
    NEGATIVE = "#E74856"
    NEUTRAL = "#00A3E0"
    WARNING = "#FFB81C"
    CRITICAL = "#ED1C24"


def apply_hkfa_theme(fig: go.Figure) -> go.Figure:
    """
    Apply HKFA dark theme to any Plotly figure.

    Args:
        fig: Plotly Figure object

    Returns:
        Figure with HKFA theme applied
    """
    fig.update_layout(
        # Background colors
        paper_bgcolor=HKFATheme.BG_PRIMARY,
        plot_bgcolor=HKFATheme.BG_SECONDARY,

        # Text styling
        font=dict(
            family='Roboto, sans-serif',
            size=13,
            color=HKFATheme.TEXT_PRIMARY
        ),

        # Titles
        title_font=dict(
            family='Roboto, sans-serif',
            size=18,
            color=HKFATheme.TEXT_PRIMARY,
        ),

        # Gridlines
        xaxis=dict(
            gridcolor=HKFATheme.GRID_COLOR,
            gridwidth=0.5,
            showgrid=True,
            zeroline=False,
            showline=True,
            linewidth=1,
            linecolor="rgba(255,255,255,0.35)",
            layer="below traces",
            title_font=dict(color=HKFATheme.TEXT_SECONDARY)
        ),
        yaxis=dict(
            gridcolor=HKFATheme.GRID_COLOR,
            gridwidth=0.5,
            showgrid=True,
            zeroline=False,
            showline=True,
            linewidth=1,
            linecolor="rgba(255,255,255,0.35)",
            layer="below traces",
            title_font=dict(color=HKFATheme.TEXT_SECONDARY)
        ),

        # Legend styling
        legend=dict(
            bgcolor='rgba(35, 35, 38, 0.8)',
            bordercolor=HKFATheme.BORDER_COLOR,
            borderwidth=1,
            font=dict(color=HKFATheme.TEXT_PRIMARY)
        ),

        # Margins for labels
        margin=dict(l=60, r=40, t=60, b=60),

        # Hover styling
        hoverlabel=dict(
            bgcolor=HKFATheme.BG_SECONDARY,
            bordercolor=HKFATheme.ACCENT_RED,
            font_size=13,
            font_family='Roboto, sans-serif',
            font_color=HKFATheme.TEXT_PRIMARY
        ),

        # Responsive
        autosize=True,
        hovermode='closest'
    )

    # Update all axes with theme
    fig.update_xaxes(
        showgrid=True,
        gridwidth=0.5,
        gridcolor=HKFATheme.GRID_COLOR
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=0.5,
        gridcolor=HKFATheme.GRID_COLOR
    )

    return fig


def glass_figure_layout(fig: go.Figure) -> go.Figure:
    """
    Apply transparent backgrounds to a Plotly figure for glass-card visual coherence.

    Applies HKFA theme first, then overrides paper_bgcolor and plot_bgcolor
    to transparent so the figure blends with the glass-card surface.

    Args:
        fig: Plotly Figure object

    Returns:
        Figure with transparent backgrounds applied
    """
    fig = apply_hkfa_theme(fig)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ============================================================================
# SECTION 2: COMMON CHART CREATION PATTERNS
# ============================================================================

def create_horizontal_bar_chart(
    df: pd.DataFrame,
    y_column: str,
    x_column: str,
    title: str = "",
    color_column: Optional[str] = None,
    hover_data: Optional[List[str]] = None,
    sort_ascending: bool = False,
    max_categories: int = 20,
    height: int = 500,
    show_values: bool = True
) -> go.Figure:
    """
    Create horizontal bar chart with HKFA theme.

    Ideal for: Rankings, comparisons with readable labels

    Args:
        df: DataFrame with data
        y_column: Column for Y-axis (categories)
        x_column: Column for X-axis (values)
        title: Chart title
        color_column: Column for color encoding (categorical)
        hover_data: Additional columns to show on hover
        sort_ascending: Sort by x_column ascending (default: descending)
        max_categories: Limit to top N categories
        height: Chart height in pixels
        show_values: Show values on bar ends

    Returns:
        Plotly Figure object
    """
    # Prepare data
    plot_df = df.copy()
    plot_df = plot_df.sort_values(by=x_column, ascending=sort_ascending)
    plot_df = plot_df.head(max_categories)

    # Create figure
    fig = go.Figure()

    if color_column:
        # Categorical coloring
        unique_categories = plot_df[color_column].unique()
        colors_map = {
            cat: HKFATheme.DATA_SERIES[i % len(HKFATheme.DATA_SERIES)]
            for i, cat in enumerate(unique_categories)
        }

        for category in unique_categories:
            subset = plot_df[plot_df[color_column] == category]
            fig.add_trace(go.Bar(
                y=subset[y_column],
                x=subset[x_column],
                name=str(category),
                orientation='h',
                marker=dict(color=colors_map[category]),
                hovertemplate='<b>%{y}</b><br>%{x:.0f}<extra></extra>',
                text=subset[x_column].astype(int) if show_values else None,
                textposition='auto' if show_values else None
            ))
    else:
        # Single color
        fig.add_trace(go.Bar(
            y=plot_df[y_column],
            x=plot_df[x_column],
            orientation='h',
            marker=dict(color=HKFATheme.ACCENT_RED),
            hovertemplate='<b>%{y}</b><br>%{x:.0f}<extra></extra>',
            text=plot_df[x_column].astype(int) if show_values else None,
            textposition='auto' if show_values else None
        ))

    fig.update_layout(
        title=title,
        xaxis_title=x_column,
        yaxis_title=y_column,
        height=height,
        showlegend=color_column is not None,
        barmode='group'
    )

    apply_hkfa_theme(fig)
    return fig


def create_radar_chart(
    values: List[float],
    metrics: List[str],
    title: str = "",
    name: str = "Player",
    reference_values: Optional[List[float]] = None,
    reference_name: str = "League Avg",
    percentile_bands: Optional[Dict[str, List[float]]] = None,
    height: int = 600,
    fill_opacity: float = 0.6
) -> go.Figure:
    """
    Create radar/spider chart with optional percentile overlays.

    Ideal for: Multi-metric player comparisons, position profiles

    Args:
        values: Player/team values (should be normalized 0-100)
        metrics: List of metric names
        title: Chart title
        name: Trace name
        reference_values: Optional reference values (e.g., league avg)
        reference_name: Name for reference trace
        percentile_bands: Dict with 'p25', 'p50', 'p75', 'p90' values
        height: Chart height
        fill_opacity: Fill opacity (0-1)

    Returns:
        Plotly Figure object
    """
    fig = go.Figure()

    # Add percentile bands if provided
    if percentile_bands:
        # 90th percentile ring
        if 'p90' in percentile_bands:
            fig.add_trace(go.Scatterpolar(
                r=percentile_bands['p90'],
                theta=metrics,
                fill=None,
                line=dict(color=HKFATheme.ACCENT_BLUE, width=1, dash='dash'),
                name='90th %ile',
                showlegend=True
            ))

        # 75-90 percentile band
        if 'p90' in percentile_bands and 'p75' in percentile_bands:
            fig.add_trace(go.Scatterpolar(
                r=percentile_bands['p90'],
                theta=metrics,
                fill='tonext',
                fillcolor='rgba(0, 163, 224, 0.1)',
                line=dict(color='rgba(0, 0, 0, 0)'),
                showlegend=False
            ))

        # 50th percentile (median)
        if 'p50' in percentile_bands:
            fig.add_trace(go.Scatterpolar(
                r=percentile_bands['p50'],
                theta=metrics,
                fill=None,
                line=dict(
                    color=HKFATheme.TEXT_SECONDARY, width=1, dash='dot'
                ),
                name='50th %ile (Median)',
                showlegend=True
            ))

    # Close the polygon explicitly by repeating first point
    metrics_closed = list(metrics) + [metrics[0]]

    # Add reference values — purple
    if reference_values:
        ref_closed = list(reference_values) + [reference_values[0]]
        fig.add_trace(go.Scatterpolar(
            r=ref_closed,
            theta=metrics_closed,
            fill='toself',
            fillcolor='rgba(155, 89, 182, 0.2)',
            line=dict(color='#9B59B6', width=2),
            name=reference_name,
            opacity=0.85
        ))

    # Add primary values — green
    values_closed = list(values) + [values[0]]
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=metrics_closed,
        fill='toself',
        fillcolor='rgba(46, 204, 113, 0.25)',
        line=dict(color='#2ECC71', width=2.5),
        name=name
    ))

    fig.update_layout(
        title=title,
        height=height,
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont=dict(color=HKFATheme.TEXT_SECONDARY),
                gridcolor=HKFATheme.GRID_COLOR
            ),
            bgcolor=HKFATheme.BG_SECONDARY
        ),
        showlegend=True
    )

    apply_hkfa_theme(fig)
    return fig


def create_scatter_with_trend(
    df: pd.DataFrame,
    x_column: str,
    y_column: str,
    title: str = "",
    color_column: Optional[str] = None,
    size_column: Optional[str] = None,
    hover_text: Optional[str] = None,
    trendline: bool = True,
    height: int = 500
) -> go.Figure:
    """
    Create scatter plot with optional trend line.

    Ideal for: Relationship analysis, age vs performance, etc.

    Args:
        df: DataFrame with data
        x_column: X-axis column
        y_column: Y-axis column
        title: Chart title
        color_column: Column for color encoding
        size_column: Column for point sizing
        hover_text: Column for hover information
        trendline: Whether to add trend line
        height: Chart height

    Returns:
        Plotly Figure object
    """
    # Use Plotly Express for quick setup
    fig = px.scatter(
        df,
        x=x_column,
        y=y_column,
        color=color_column,
        size=size_column,
        hover_name=hover_text,
        trendline='lowess' if trendline else None,
        title=title,
        height=height,
        color_discrete_sequence=HKFATheme.DATA_SERIES
    )

    # Update marker styling
    fig.update_traces(
        marker=dict(
            size=10 if not size_column else None,
            line=dict(width=1, color=HKFATheme.BG_SECONDARY),
            opacity=0.8
        ),
        selector=dict(mode='markers')
    )

    apply_hkfa_theme(fig)
    return fig


def create_heatmap(
    data_matrix: np.ndarray,
    x_labels: List[str],
    y_labels: List[str],
    title: str = "",
    colorscale: str = "Blues",
    show_values: bool = True,
    height: int = 400,
    click_enabled: bool = False
) -> go.Figure:
    """
    Create heatmap with HKFA theme.

    Ideal for: Tactical matrices, player × metrics, team comparisons

    Args:
        data_matrix: 2D numpy array or list of lists
        x_labels: Column labels
        y_labels: Row labels
        title: Chart title
        colorscale: Plotly colorscale name
        show_values: Show values in cells
        height: Chart height
        click_enabled: Enable click interactions

    Returns:
        Plotly Figure object
    """
    # Prepare text for cells
    text_display = None
    if show_values:
        text_display = [
            [f'{val:.0f}' for val in row]
            for row in data_matrix
        ]

    fig = go.Figure(data=go.Heatmap(
        z=data_matrix,
        x=x_labels,
        y=y_labels,
        colorscale=colorscale,
        text=text_display if show_values else None,
        texttemplate='%{text}' if show_values else None,
        textfont=dict(color=HKFATheme.TEXT_PRIMARY, size=12),
        colorbar=dict(
            title="Value",
            tickfont=dict(color=HKFATheme.TEXT_PRIMARY),
            thickness=20
        ),
        hovertemplate='<b>%{y}</b><br>%{x}<br>Value: %{z:.0f}<extra></extra>'
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Metrics",
        yaxis_title="Players/Teams",
        height=height,
        xaxis=dict(tickfont=dict(size=11)),
        yaxis=dict(tickfont=dict(size=11))
    )

    apply_hkfa_theme(fig)
    return fig


def create_match_heatmap(
    heatmap_points: List[Dict[str, Any]],
    title: str = "",
    height: int = 450
) -> go.Figure:
    """
    Renders a football field heatmap based on Sofascore coordinates.
    heatmap_points: list of {x, y, value} where x,y are usually 0-100.
    """
    fig = go.Figure()

    if heatmap_points and isinstance(heatmap_points, list):
        try:
            df = pd.DataFrame(heatmap_points)
            if not df.empty and 'x' in df.columns and 'y' in df.columns:
                x_values = (df['x'] * 105.0) / 100.0
                # Sofascore event heatmaps already use a top-origin pitch frame for this feed.
                # Reversing again pushes activity into the wrong band.
                y_values = (df['y'] * 68.0) / 100.0
                heatmap_scale = [
                    [0.00, "rgba(0,0,0,0)"],
                    [0.08, "rgba(201, 60, 39, 0.38)"],
                    [0.24, "rgba(232, 104, 35, 0.60)"],
                    [0.50, "rgba(247, 171, 43, 0.82)"],
                    [0.78, "rgba(255, 226, 84, 0.96)"],
                    [1.00, "rgba(255, 247, 214, 1.00)"],
                ]
                fig.add_trace(go.Histogram2dContour(
                    x=x_values,
                    y=y_values,
                    z=df.get('value', [1]*len(df)),
                    histfunc="sum",
                    colorscale=heatmap_scale,
                    ncontours=22,
                    contours=dict(coloring="heatmap", showlines=False),
                    line=dict(width=0),
                    opacity=1.0,
                    showscale=False,
                    hoverinfo='skip',
                    xbins=dict(start=0, end=105, size=4.2),
                    ybins=dict(start=0, end=68, size=3.2),
                ))
        except Exception as e:
            logger.warning(f"Error drawing heatmap contour: {e}")

    # Draw Pitch Markings (White, subtle)
    line_style = dict(color="rgba(255,255,255,0.42)", width=2)
    
    # Outer boundary
    fig.add_shape(type="rect", x0=0, y0=0, x1=105, y1=68, line=line_style, fillcolor="rgba(88, 128, 86, 0.42)", layer="below")
    # Half-way line
    fig.add_shape(type="line", x0=52.5, y0=0, x1=52.5, y1=68, line=line_style)
    # Center circle
    fig.add_shape(type="circle", x0=43.35, y0=24.85, x1=61.65, y1=43.15, line=line_style)
    # Penalty areas
    fig.add_shape(type="rect", x0=0, y0=13.84, x1=16.5, y1=54.16, line=line_style)
    fig.add_shape(type="rect", x0=88.5, y0=13.84, x1=105, y1=54.16, line=line_style)
    # Six-yard boxes
    fig.add_shape(type="rect", x0=0, y0=24.84, x1=5.5, y1=43.16, line=line_style)
    fig.add_shape(type="rect", x0=99.5, y0=24.84, x1=105, y1=43.16, line=line_style)
    # Penalty spots
    fig.add_shape(type="circle", x0=10.3, y0=33.4, x1=11.7, y1=34.6, line=dict(color="rgba(255,255,255,0.55)", width=2), fillcolor="rgba(255,255,255,0.55)")
    fig.add_shape(type="circle", x0=93.3, y0=33.4, x1=94.7, y1=34.6, line=dict(color="rgba(255,255,255,0.55)", width=2), fillcolor="rgba(255,255,255,0.55)")
    fig.update_layout(
        title=title,
        height=height,
        xaxis=dict(range=[-1, 106], showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(range=[68.5, -0.5], showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1),
        margin=dict(l=2, r=2, t=2, b=2),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode=False
    )

    return fig


# ============================================================================
# SECTION 3: DATA NORMALIZATION UTILITIES
# ============================================================================

def normalize_metric(
    values: pd.Series,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    scale: int = 100
) -> pd.Series:
    """
    Normalize values to 0-scale range (default 0-100).

    Args:
        values: Series of values to normalize
        min_val: Minimum value (auto-detect if None)
        max_val: Maximum value (auto-detect if None)
        scale: Target scale (default 100)

    Returns:
        Normalized Series
    """
    min_val = min_val or values.min()
    max_val = max_val or values.max()

    if max_val == min_val:
        return pd.Series(scale / 2, index=values.index)

    return ((values - min_val) / (max_val - min_val)) * scale


def calculate_percentile(
    value: float,
    reference_distribution: List[float]
) -> float:
    """
    Calculate percentile rank for a value.

    Args:
        value: Value to rank
        reference_distribution: List of reference values

    Returns:
        Percentile rank (0-100)
    """
    percentile = (
        sum(1 for v in reference_distribution if v <= value)
        / len(reference_distribution)
    ) * 100
    return round(percentile, 1)


def get_percentile_bands(
    reference_data: pd.Series,
    percentiles: List[int] = [25, 50, 75, 90]
) -> Dict[str, float]:
    """
    Calculate percentile values for banding visualization.

    Args:
        reference_data: Series of reference values
        percentiles: List of percentile thresholds

    Returns:
        Dict mapping 'pNN' -> value
    """
    return {
        f'p{p}': reference_data.quantile(p / 100)
        for p in percentiles
    }


# ============================================================================
# SECTION 4: HOVER TEMPLATE BUILDERS
# ============================================================================

def build_rich_hover_template(
    metric_name: str,
    value_format: str = ".0f",
    include_percentile: bool = True,
    include_delta: bool = True
) -> str:
    """
    Build rich hover template with metric context.

    Args:
        metric_name: Name of metric
        value_format: Format string for value
        include_percentile: Include percentile rank
        include_delta: Include delta vs average

    Returns:
        Hover template string
    """
    template = f'<b>{metric_name}</b><br>'
    template += '━━━━━━━━━━━━━━<br>'
    template += f'Value: %{{y:{value_format}}}<br>'

    if include_percentile:
        template += 'Percentile: %{customdata[0]:.0f}th ↑<br>'

    if include_delta:
        template += 'Δ vs Avg: %{customdata[1]:+.0f}%<br>'

    template += '<extra></extra>'
    return template


# ============================================================================
# SECTION 5: PERFORMANCE OPTIMIZATION
# ============================================================================

def optimize_for_large_dataset(
    fig: go.Figure,
    num_points: int,
    use_webgl: bool = True
) -> go.Figure:
    """
    Optimize figure for large datasets (>1000 points).

    Args:
        fig: Plotly Figure object
        num_points: Number of data points
        use_webgl: Use WebGL renderer for scatter plots

    Returns:
        Optimized figure
    """
    if num_points > 1000 and use_webgl:
        # Use WebGL for scatter plots with many points
        fig.update_traces(
            selector=dict(type='scatter'),
            marker=dict(opacity=0.6)
        )

    # Disable hover template complexity for large datasets
    if num_points > 5000:
        fig.update_traces(hoverinfo='skip')

    # Use simplified hover for medium datasets
    elif num_points > 1000:
        fig.update_traces(
            hovertemplate='Value: %{y:.0f}<extra></extra>'
        )

    return fig


# ============================================================================
# SECTION 6: CONFIGURATION HELPERS
# ============================================================================

def get_chart_config(
    responsive: bool = True,
    show_toolbar: bool = True
) -> Dict:
    """
    Get standard Plotly chart configuration.

    Args:
        responsive: Enable responsive sizing
        show_toolbar: Show toolbar on hover

    Returns:
        Config dictionary for fig.show() or Dash Graph
    """
    return {
        'responsive': responsive,
        'displayModeBar': show_toolbar,
        'displaylogo': False,
        'toImageButtonOptions': {
            'format': 'png',
            'filename': 'chart',
            'height': 800,
            'width': 1200,
            'scale': 2
        }
    }


# ============================================================================
# SECTION 7: DASH COMPONENT HELPERS
# ============================================================================

def create_percentile_bars(percentiles_dict: Dict[str, Any]) -> html.Div:
    """
    Returns an html.Div with dbc.Progress bars for each stat.
    Includes benchmark markers for Group and Position averages if available.

    Args:
        percentiles_dict: Dict mapping stat_name -> percentile (float) or 
                         stat_name -> data_dict (with 'percentile', 'group_avg_percentile', etc.)

    Returns:
        html.Div containing labeled progress bars with benchmark markers
    """
    if not percentiles_dict:
        return html.Div("No hay datos de percentiles disponibles",
                        style={"color": HKFATheme.TEXT_SECONDARY})

    # Normalizar datos: asegurar que cada entrada sea un dict
    normalized_data = {}
    for stat, data in percentiles_dict.items():
        if isinstance(data, dict):
            normalized_data[stat] = data
        else:
            normalized_data[stat] = {'percentile': float(data)}

    # Definir descripciones para los índices
    descriptions = {
        'efficiency_index': ' (Opportunity conversion ratio)',
        'defensive_wall': ' (Interception & duel capacity)'
    }

    # Separar métricas normales del índice para asegurar que el índice sea el último
    normal_metrics = []
    index_metrics = []
    
    for stat, data in normalized_data.items():
        if stat in ['efficiency_index', 'defensive_wall']:
            index_metrics.append((stat, data))
        else:
            normal_metrics.append((stat, data))

    # Ordenar métricas normales por valor descendente
    normal_metrics.sort(key=lambda x: x[1].get('percentile', 0), reverse=True)
    
    # Combinar (normales primero, índices al final)
    all_metrics = normal_metrics + index_metrics

    rows = []
    
    # ── Legend for Benchmarks ──────────────────────────────────────────────
    has_benchmarks = any('group_avg_percentile' in d or 'pos_avg_percentile' in d for d in normalized_data.values())
    if has_benchmarks:
        legend_items = []
        # Group Avg item (White)
        if any('group_avg_percentile' in d for d in normalized_data.values()):
            legend_items.append(html.Div([
                html.Div(style={"width": "8px", "height": "8px", "backgroundColor": "#FFFFFF", "borderRadius": "50%", "marginRight": "4px"}),
                html.Span("Group Avg", style={"fontSize": "0.65rem", "color": HKFATheme.TEXT_SECONDARY}),
            ], style={"display": "flex", "alignItems": "center", "marginRight": "12px"}))
        
        # Pos Avg item (Purple)
        if any('pos_avg_percentile' in d for d in normalized_data.values()):
            legend_items.append(html.Div([
                html.Div(style={"width": "8px", "height": "8px", "backgroundColor": "#9B59B6", "borderRadius": "50%", "marginRight": "4px"}),
                html.Span("Pos Avg", style={"fontSize": "0.65rem", "color": HKFATheme.TEXT_SECONDARY}),
            ], style={"display": "flex", "alignItems": "center"}))

        if legend_items:
            rows.append(html.Div(legend_items, style={"display": "flex", "justifyContent": "flex-end", "marginBottom": "10px"}))

    for stat, data in all_metrics:
        val = data.get('percentile', 0)
        group_avg = data.get('group_avg_percentile')
        pos_avg = data.get('pos_avg_percentile')

        # Formatear nombre de la métrica
        display_name = stat.replace('_', ' ').title()
        if stat in descriptions:
            display_name += descriptions[stat]

        # Determine color based on threshold
        if val >= 90:
            color = HKFATheme.ACCENT_BLUE   # Elite
        elif val >= 75:
            color = HKFATheme.POSITIVE     # Good
        elif val >= 50:
            color = HKFATheme.WARNING      # Average
        else:
            color = HKFATheme.NEGATIVE     # Below Average

        rows.append(html.Div([
            html.Div([
                html.Span(
                    display_name,
                    style={"color": HKFATheme.TEXT_SECONDARY, "fontSize": "0.85rem"}
                ),
                html.Span(
                    f"{val:.0f}%",
                    style={
                        "color": HKFATheme.TEXT_PRIMARY,
                        "fontSize": "0.85rem",
                        "fontWeight": "bold"
                    }
                )
            ], style={"display": "flex", "justifyContent": "space-between"}),
            
            # Container for Progress bar + Markers
            html.Div(style={"position": "relative", "marginTop": "4px", "marginBottom": "12px"}, children=[
                dbc.Progress(
                    value=val,
                    color=color,
                    style={
                        "height": "8px",
                        "borderRadius": "4px",
                        "backgroundColor": "rgba(255,255,255,0.05)"
                    }
                ),
                # Group Average Marker (White) - Larger and shifted left if overlap
                html.Div(style={
                    "position": "absolute",
                    "left": f"{max(0.5, group_avg - (1.5 if abs(group_avg - (pos_avg or 0)) < 1.0 else 0))}%",
                    "top": "-6px",
                    "height": "20px",
                    "width": "3px",
                    "backgroundColor": "#FFFFFF",
                    "boxShadow": "0 0 8px rgba(255, 255, 255, 0.9)",
                    "zIndex": "21",
                }) if group_avg is not None else None,
                # Position Average Marker (Purple) - Shifted right if overlap
                html.Div(style={
                    "position": "absolute",
                    "left": f"{min(99.5, pos_avg + (1.5 if abs(group_avg - (pos_avg or 0)) < 1.0 else 0))}%",
                    "top": "-4px",
                    "height": "16px",
                    "width": "2px",
                    "backgroundColor": "#9B59B6",
                    "boxShadow": "0 0 8px rgba(155, 89, 182, 0.9)",
                    "zIndex": "22",
                }) if pos_avg is not None else None,
            ])
        ]))

    return html.Div(rows)
