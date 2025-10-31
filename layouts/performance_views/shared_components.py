# ABOUTME: Reusable UI components for the performance dashboard
# ABOUTME: KPI cards, chart containers, filters, and status alerts

from dash import html, dcc
import dash_bootstrap_components as dbc


# =============================================================================
# FILTER SUB-COMPONENTS
# =============================================================================

def create_season_selector(value="2024-25"):
    """
    Create season dropdown selector.

    Args:
        value: Default season value (str)

    Returns:
        dbc.Col: Season selector column
    """
    return dbc.Col([
        dbc.Label("Season:", html_for="season-selector"),
        html.Div(
            dcc.Dropdown(
                id="season-selector",
                options=[],  # Filled dynamically by callback
                value=value,
                className="mb-3"
            ),
            className="filter-container"
        )
    ], md=4)


def create_team_selector(clearable=True):
    """
    Create team dropdown selector.

    Args:
        clearable: Allow clearing selection (bool)

    Returns:
        dbc.Col: Team selector column
    """
    return dbc.Col([
        dbc.Label("Team:", html_for="team-selector"),
        html.Div(
            dcc.Dropdown(
                id="team-selector",
                placeholder="All teams...",
                className="mb-3",
                clearable=clearable
            ),
            className="filter-container"
        )
    ], md=4)


def create_player_selector(clearable=True):
    """
    Create player dropdown selector.

    Args:
        clearable: Allow clearing selection (bool)

    Returns:
        dbc.Col: Player selector column
    """
    return dbc.Col([
        dbc.Label("Player:", html_for="player-selector"),
        html.Div(
            dcc.Dropdown(
                id="player-selector",
                placeholder="All players...",
                className="mb-3",
                clearable=clearable
            ),
            className="filter-container"
        )
    ], md=4)


def create_position_filter():
    """
    Create position filter dropdown.

    Returns:
        dbc.Col: Position filter column
    """
    return dbc.Col([
        dbc.Label("Position:", html_for="position-filter"),
        html.Div(
            dcc.Dropdown(
                id="position-filter",
                options=[
                    {"label": "All Positions", "value": "all"},
                    {"label": "Goalkeeper", "value": "Goalkeeper"},
                    {"label": "Defender", "value": "Defender"},
                    {"label": "Midfielder", "value": "Midfielder"},
                    {"label": "Winger", "value": "Winger"},
                    {"label": "Forward", "value": "Forward"}
                ],
                value="all",
                className="mb-3"
            ),
            className="filter-container"
        )
    ], md=4)


def create_age_range_filter():
    """
    Create age range slider filter.

    Returns:
        dbc.Col: Age range filter column
    """
    return dbc.Col([
        dbc.Label("Age Range:", html_for="age-range"),
        dcc.RangeSlider(
            id="age-range",
            min=15,
            max=45,
            value=[15, 45],
            marks={
                15: '15', 20: '20', 25: '25',
                30: '30', 35: '35', 40: '40', 45: '45'
            },
            tooltip={"placement": "bottom", "always_visible": True},
            className="mb-3"
        )
    ], md=4)


def create_export_button():
    """
    Create export PDF button.

    Returns:
        dbc.Col: Export button column
    """
    return dbc.Col([
        dbc.Label("Options:", html_for="action-buttons"),
        html.Div([
            dbc.Button(
                [
                    html.I(className="bi bi-file-earmark-pdf me-2"),
                    "Export PDF"
                ],
                id="export-pdf-button",
                color="success",
                size="sm"
            )
        ])
    ], md=4)


# =============================================================================
# KPI CARD COMPONENTS
# =============================================================================

def create_kpi_card(
    value,
    label,
    unit="",
    icon=None,
    trend=None,
    trend_color=None,
    card_id=None
):
    """
    Create a KPI card component with consistent styling.

    Args:
        value: Main metric value (int/float/str)
        label: Metric label (str)
        unit: Unit of measurement (str, optional)
        icon: Icon class for Bootstrap Icons (str, optional)
        trend: Trend indicator ("+5%", "-2.3%", etc.)
        trend_color: Bootstrap color for trend ("success", "danger", "warning")
        card_id: Optional ID for targeting via CSS/callbacks

    Returns:
        dbc.Col: Responsive column with KPI card
    """
    content = []

    # Icon (if provided)
    if icon:
        content.append(
            html.Div([
                html.I(className=f"bi {icon}")
            ], className="metric-icon mb-2")
        )

    # Value
    content.append(
        html.P(
            str(value),
            className="metric-value mb-1"
        )
    )

    # Unit (if provided)
    if unit:
        content.append(
            html.Span(
                f"{unit}",
                className="metric-unit text-secondary"
            )
        )

    # Label
    content.append(
        html.P(
            label,
            className="metric-label mb-0"
        )
    )

    # Trend (if provided)
    if trend:
        content.append(
            html.Span(
                trend,
                className=f"metric-trend badge badge-{trend_color} mt-2"
            )
        )

    # Build card props conditionally
    card_props = {
        "children": dbc.CardBody(content),
        "className": "metric-card"
    }
    if card_id is not None:
        card_props["id"] = card_id

    return dbc.Col([
        dbc.Card(**card_props)
    ], lg=3, md=6, sm=6, xs=12)


def create_kpi_row(*kpi_cards):
    """
    Wrap multiple KPI cards in a responsive row.

    Args:
        *kpi_cards: Variable number of KPI card components

    Returns:
        dbc.Row: Row containing KPI cards
    """
    return dbc.Row(list(kpi_cards), className="mb-4")


# =============================================================================
# CHART CONTAINER COMPONENTS
# =============================================================================

def create_chart_container(
    chart_id,
    title,
    subtitle=None,
    loading_type="default",
    show_legend=True,
    full_width=False,
    container_id=None
):
    """
    Create a standardized chart container with loading state.

    Args:
        chart_id: ID for the dcc.Graph component
        title: Chart title (str)
        subtitle: Optional subtitle (str)
        loading_type: Type of loading indicator
                     ("default", "dot", "graph", "circle")
        show_legend: Show chart legend (bool)
        full_width: Use full width (bool, md=12) or half width (md=6)
        container_id: Optional ID for the container div

    Returns:
        dbc.Col: Chart container with loading state
    """
    chart_md = 12 if full_width else 6

    header_content = [
        html.H5(title, className="mb-0 d-inline-block")
    ]

    if subtitle:
        header_content.append(
            html.Small(
                subtitle,
                className="text-secondary d-block mt-1"
            )
        )

    return dbc.Col([
        dbc.Card([
            dbc.CardHeader(html.Div(header_content)),
            dbc.CardBody([
                dcc.Loading(
                    id=f"loading-{chart_id}",
                    type=loading_type,
                    children=[
                        html.Div(id=chart_id)
                    ],
                    color="#ED1C24"  # HKFA red
                )
            ])
        ])
    ], md=chart_md, className="mb-4")


def create_chart_row(*chart_containers):
    """
    Wrap chart containers in a responsive row.

    Args:
        *chart_containers: Variable number of chart container components

    Returns:
        dbc.Row: Row containing chart containers
    """
    return dbc.Row(list(chart_containers), className="mb-4")


# =============================================================================
# STATUS AND ERROR COMPONENTS
# =============================================================================

def create_status_alert(
    alert_id,
    message="",
    alert_type="info",
    dismissible=True,
    show=True
):
    """
    Create a status/error alert component.

    Args:
        alert_id: ID for the alert div
        message: Alert message (str)
        alert_type: Bootstrap alert type
                   ("success", "warning", "danger", "info")
        dismissible: Show dismiss button (bool)
        show: Initially show alert (bool)

    Returns:
        dbc.Alert: Alert component
    """
    return dbc.Alert(
        message,
        id=alert_id,
        color=alert_type,
        dismissable=dismissible,
        is_open=show,
        className="mb-3"
    )


def create_empty_state(
    title="No Data Available",
    message="Try adjusting your filters",
    icon="bi-inbox"
):
    """
    Create an empty state placeholder.

    Useful when no data matches current filters or when
    an error occurs during data loading.

    Args:
        title: Empty state title (str)
        message: Helpful message for user (str)
        icon: Bootstrap icon class (str)

    Returns:
        dbc.Card: Empty state card
    """
    return dbc.Card([
        dbc.CardBody([
            html.Div(
                [
                    html.I(
                        className=f"bi {icon}",
                        style={"fontSize": "3rem", "color": "#A7A7A7"}
                    ),
                    html.H5(title, className="mt-3"),
                    html.P(message, className="text-secondary")
                ],
                className="text-center py-5"
            )
        ])
    ])
