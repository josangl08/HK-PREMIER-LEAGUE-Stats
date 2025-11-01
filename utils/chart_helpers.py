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


# ============================================================================
# SECTION 1: HKFA THEME CONFIGURATION
# ============================================================================

class HKFATheme:
    """HKFA color theme and styling constants."""

    # Primary colors
    BG_PRIMARY = "#18181A"
    BG_SECONDARY = "#232326"
    BG_TERTIARY = "#2A2A2D"

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
            gridcolor=HKFATheme.BG_TERTIARY,
            gridwidth=0.5,
            showgrid=True,
            zeroline=False,
            showline=True,
            linewidth=1,
            linecolor=HKFATheme.BORDER_COLOR,
            title_font=dict(color=HKFATheme.TEXT_SECONDARY)
        ),
        yaxis=dict(
            gridcolor=HKFATheme.BG_TERTIARY,
            gridwidth=0.5,
            showgrid=True,
            zeroline=False,
            showline=True,
            linewidth=1,
            linecolor=HKFATheme.BORDER_COLOR,
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
        gridcolor=HKFATheme.BG_TERTIARY
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=0.5,
        gridcolor=HKFATheme.BG_TERTIARY
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

    # Add reference values (league average)
    if reference_values:
        fig.add_trace(go.Scatterpolar(
            r=reference_values,
            theta=metrics,
            fill='toself',
            fillcolor='rgba(167, 167, 167, 0.2)',
            line=dict(color=HKFATheme.TEXT_SECONDARY, width=2),
            name=reference_name,
            opacity=0.7
        ))

    # Add primary values
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=metrics,
        fill='toself',
        fillcolor='rgba(237, 28, 36, 0.3)',
        line=dict(color=HKFATheme.ACCENT_RED, width=2),
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
                gridcolor=HKFATheme.BG_TERTIARY
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
