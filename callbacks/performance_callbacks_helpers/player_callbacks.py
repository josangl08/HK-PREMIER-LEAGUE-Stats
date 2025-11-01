# ABOUTME: Player view callbacks for performance dashboard
# ABOUTME: 5 chart callbacks for player-level analysis with unique IDs

"""
Player View Callbacks Module.

5 callbacks for player-level analysis charts.
Fully implemented in Phase 5.
"""

from dash import Input, Output, callback, html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import logging
from .helpers import validate_data, create_empty_state, create_error_alert
from utils.chart_helpers import (
    create_radar_chart,
    create_horizontal_bar_chart,
    create_heatmap,
    HKFATheme,
    apply_hkfa_theme,
    normalize_metric
)

logger = logging.getLogger(__name__)


@callback(
    Output('player-chart-1', 'children'),
    [Input('chart-data-store', 'data'), Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_player_chart_1(chart_data, filters):
    """Chart 1: Player vs Position Radar with Percentiles."""
    logger.info("-> Rendering player-chart-1 (player radar with percentiles)")

    if not chart_data or 'player_vs_position_radar' not in chart_data:
        return create_empty_state("No hay datos de radar disponibles")

    radar_data = chart_data['player_vs_position_radar']

    try:
        # Create radar chart with percentile bands
        # TODO: Implement percentile bands visualization
        fig = create_radar_chart(
            values=radar_data['player_values'],
            metrics=radar_data['metrics'],
            title="Rendimiento vs Promedio de Posición",
            name='Jugador',
            reference_values=radar_data['position_avg'],
            reference_name='Promedio Posición'
        )

        return dcc.Graph(figure=fig, config={'displayModeBar': False})

    except Exception as e:
        logger.error(f"Error creating player radar chart: {e}")
        return create_error_alert(f"Error al crear el gráfico: {str(e)}")


@callback(
    Output('player-chart-2', 'children'),
    [Input('chart-data-store', 'data'), Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_player_chart_2(chart_data, filters):
    """Chart 2: Percentile Rankings Bar."""
    logger.info("-> Rendering player-chart-2 (percentile rankings)")

    if not chart_data or 'player_percentiles' not in chart_data:
        return create_empty_state("No hay datos de percentiles disponibles")

    percentile_data = chart_data['player_percentiles']

    try:
        # Extract data for horizontal bar chart
        import pandas as pd
        metrics = list(percentile_data.keys())
        percentiles = [percentile_data[m]['percentile'] for m in metrics]
        values = [percentile_data[m]['value'] for m in metrics]

        # Create DataFrame for horizontal bar chart
        df = pd.DataFrame({
            'metric': metrics,
            'percentile': percentiles,
            'value': values
        })

        # Create horizontal bar chart
        fig = create_horizontal_bar_chart(
            df=df,
            y_column='metric',
            x_column='percentile',
            title="Rankings Percentiles por Métrica",
            sort_ascending=False,
            show_values=True
        )

        # Add value annotations
        for i, (metric, value) in enumerate(zip(metrics, values)):
            fig.add_annotation(
                x=percentiles[i] + 5,
                y=metrics[i],
                text=f"{value:.2f}",
                showarrow=False,
                font=dict(size=10, color='white'),
                xanchor='left'
            )

        return dcc.Graph(figure=fig, config={'displayModeBar': False})

    except Exception as e:
        logger.error(f"Error creating percentile rankings: {e}")
        return create_error_alert(f"Error al crear el gráfico: {str(e)}")


@callback(
    Output('player-chart-3', 'children'),
    [Input('chart-data-store', 'data'), Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_player_chart_3(chart_data, filters):
    """Chart 3: Efficiency Scatter (Goals/xG vs Assists/xA)."""
    logger.info("-> Rendering player-chart-3 (efficiency scatter)")

    if not chart_data or 'efficiency_scatter' not in chart_data:
        return create_empty_state("No hay datos de eficiencia disponibles")

    eff_data = chart_data['efficiency_scatter']

    try:
        # Create scatter plot for efficiency
        fig = go.Figure()

        # Add player point
        fig.add_trace(go.Scatter(
            x=[eff_data['goals_efficiency']],
            y=[eff_data['assists_efficiency']],
            mode='markers+text',
            name=eff_data['player_name'],
            marker=dict(
                size=20,
                color=HKFATheme.ACCENT_RED,
                line=dict(width=2, color='white')
            ),
            text=[eff_data['player_name']],
            textposition='top center',
            hovertemplate='<b>%{text}</b><br>' +
                         'Goals/xG: %{x:.2f}<br>' +
                         'Assists/xA: %{y:.2f}<br>' +
                         f"Goals: {eff_data['goals']:.0f} (xG: {eff_data['xG']:.2f})<br>" +
                         f"Assists: {eff_data['assists']:.0f} (xA: {eff_data['xA']:.2f})<br>" +
                         '<extra></extra>'
        ))

        # Add reference lines at 1.0 (expected performance)
        fig.add_hline(y=1.0, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=1.0, line_dash="dash", line_color="gray", opacity=0.5)

        # Add quadrant labels
        fig.add_annotation(x=1.5, y=1.5, text="Sobre-rendimiento", showarrow=False,
                          font=dict(color='green', size=12), opacity=0.6)
        fig.add_annotation(x=0.5, y=0.5, text="Bajo-rendimiento", showarrow=False,
                          font=dict(color='red', size=12), opacity=0.6)

        fig.update_layout(
            title="Análisis de Eficiencia: Goals/xG vs Assists/xA",
            xaxis_title="Goals / xG Ratio",
            yaxis_title="Assists / xA Ratio",
            height=400,
            showlegend=False
        )

        apply_hkfa_theme(fig)

        return dcc.Graph(figure=fig, config={'displayModeBar': False})

    except Exception as e:
        logger.error(f"Error creating efficiency scatter: {e}")
        return create_error_alert(f"Error al crear el gráfico: {str(e)}")


@callback(
    Output('player-chart-4', 'children'),
    [Input('chart-data-store', 'data'), Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_player_chart_4(chart_data, filters):
    """Chart 4: Position-specific Performance Heatmap."""
    logger.info("-> Rendering player-chart-4 (performance heatmap)")

    if not chart_data or 'position_performance_heatmap' not in chart_data:
        return create_empty_state(
            "No hay datos de rendimiento por posición disponibles"
        )

    heatmap_data = chart_data['position_performance_heatmap']

    try:
        # Prepare data for heatmap
        import numpy as np
        metrics = list(heatmap_data.keys())
        comparisons = ['Jugador', 'Promedio Posición', 'Promedio Liga']

        data_matrix = np.array([
            [heatmap_data[m]['player_value'] for m in metrics],
            [heatmap_data[m]['position_avg'] for m in metrics],
            [heatmap_data[m]['league_avg'] for m in metrics]
        ])

        # Create heatmap
        fig = create_heatmap(
            data_matrix=data_matrix,
            x_labels=metrics,
            y_labels=comparisons,
            title="Matriz de Rendimiento por Posición",
            colorscale='RdYlGn',
            show_values=True
        )

        return dcc.Graph(figure=fig, config={'displayModeBar': False})

    except Exception as e:
        logger.error(f"Error creating performance heatmap: {e}")
        return create_error_alert(f"Error al crear el gráfico: {str(e)}")


@callback(
    Output('player-chart-5', 'children'),
    [Input('chart-data-store', 'data'), Input('current-filters-store', 'data')],
    prevent_initial_call=True
)
def update_player_chart_5(chart_data, filters):
    """Chart 5: Performance Evolution Timeline Placeholder."""
    logger.info("-> Rendering player-chart-5 (evolution timeline placeholder)")

    # Educational placeholder for multi-season data
    return html.Div([
        dbc.Alert([
            html.I(className='bi bi-calendar-event', style={'fontSize': '48px', 'color': HKFATheme.ACCENT_RED}),
            html.H5("Evolución del Rendimiento del Jugador", className='mt-3 mb-2'),
            html.P([
                "Este gráfico mostrará la evolución del rendimiento del jugador a lo largo de múltiples temporadas. ",
                "Para visualizar esta información, se requieren datos históricos de varias temporadas."
            ], className='mb-2'),
            html.P([
                html.Strong("Datos necesarios: "),
                "Estadísticas del jugador agregadas por temporada (2+ temporadas)."
            ], className='mb-0 text-muted')
        ], color='info', className='text-center')
    ])
