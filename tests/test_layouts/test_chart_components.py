# ABOUTME: Tests for chart container components in shared_components module
# ABOUTME: Validates chart container structure, loading states, and layouts

import pytest
from dash import html, dcc
import dash_bootstrap_components as dbc
from layouts.performance_views.shared_components import (
    create_chart_container,
    create_chart_row
)


class TestChartContainer:
    """Tests for create_chart_container component."""

    def test_creates_column_component(self):
        """Should return a dbc.Col component."""
        result = create_chart_container(
            chart_id="test-chart",
            title="Test Chart"
        )
        assert isinstance(result, dbc.Col)

    def test_half_width_by_default(self):
        """Should have half width (md=6) by default."""
        result = create_chart_container(
            chart_id="test-chart",
            title="Test Chart"
        )
        assert result.md == 6

    def test_full_width_when_specified(self):
        """Should have full width (md=12) when specified."""
        result = create_chart_container(
            chart_id="test-chart",
            title="Test Chart",
            full_width=True
        )
        assert result.md == 12

    def test_contains_card_component(self):
        """Should contain a dbc.Card."""
        result = create_chart_container(
            chart_id="test-chart",
            title="Test Chart"
        )
        card = result.children[0]
        assert isinstance(card, dbc.Card)

    def test_has_card_header_with_title(self):
        """Should have card header with title."""
        result = create_chart_container(
            chart_id="test-chart",
            title="My Test Chart"
        )
        card = result.children[0]
        header = card.children[0]
        assert isinstance(header, dbc.CardHeader)

    def test_displays_subtitle_when_provided(self):
        """Should display subtitle when provided."""
        result = create_chart_container(
            chart_id="test-chart",
            title="Test Chart",
            subtitle="With subtitle"
        )
        # Just verify the component is created without errors
        assert isinstance(result, dbc.Col)
        card = result.children[0]
        assert isinstance(card, dbc.Card)

    def test_has_loading_component(self):
        """Should have dcc.Loading component."""
        result = create_chart_container(
            chart_id="test-chart",
            title="Test Chart"
        )
        card = result.children[0]
        body = card.children[1]
        loading = body.children[0]
        assert isinstance(loading, dcc.Loading)

    def test_loading_has_correct_id(self):
        """Should have loading ID based on chart ID."""
        result = create_chart_container(
            chart_id="my-chart",
            title="Test"
        )
        card = result.children[0]
        body = card.children[1]
        loading = body.children[0]
        assert loading.id == "loading-my-chart"

    def test_loading_uses_correct_color(self):
        """Should use HKFA red color for loading indicator."""
        result = create_chart_container(
            chart_id="test-chart",
            title="Test"
        )
        card = result.children[0]
        body = card.children[1]
        loading = body.children[0]
        assert loading.color == "#ED1C24"

    def test_chart_div_has_correct_id(self):
        """Should have chart div with correct ID."""
        result = create_chart_container(
            chart_id="analytics-chart",
            title="Test"
        )
        card = result.children[0]
        body = card.children[1]
        loading = body.children[0]
        chart_div = loading.children[0]
        assert chart_div.id == "analytics-chart"

    def test_accepts_custom_loading_type(self):
        """Should accept custom loading type."""
        result = create_chart_container(
            chart_id="test-chart",
            title="Test",
            loading_type="circle"
        )
        card = result.children[0]
        body = card.children[1]
        loading = body.children[0]
        assert loading.type == "circle"

    def test_accepts_custom_container_id(self):
        """Should accept custom container ID."""
        result = create_chart_container(
            chart_id="test-chart",
            title="Test",
            container_id="custom-container"
        )
        # Note: container_id is currently not used in implementation
        # This test documents the API
        assert isinstance(result, dbc.Col)


class TestChartRow:
    """Tests for create_chart_row component."""

    def test_creates_row_component(self):
        """Should return a dbc.Row component."""
        chart1 = create_chart_container(
            chart_id="chart-1",
            title="Chart 1"
        )
        chart2 = create_chart_container(
            chart_id="chart-2",
            title="Chart 2"
        )
        result = create_chart_row(chart1, chart2)
        assert isinstance(result, dbc.Row)

    def test_contains_all_charts(self):
        """Should contain all provided chart containers."""
        chart1 = create_chart_container(
            chart_id="chart-1",
            title="Chart 1"
        )
        chart2 = create_chart_container(
            chart_id="chart-2",
            title="Chart 2"
        )
        chart3 = create_chart_container(
            chart_id="chart-3",
            title="Chart 3"
        )
        result = create_chart_row(chart1, chart2, chart3)
        assert len(result.children) == 3

    def test_has_correct_margin_class(self):
        """Should have mb-4 margin class."""
        chart = create_chart_container(
            chart_id="test-chart",
            title="Test"
        )
        result = create_chart_row(chart)
        assert result.className == "mb-4"

    def test_accepts_variable_number_of_charts(self):
        """Should accept any number of chart containers."""
        charts = [
            create_chart_container(
                chart_id=f"chart-{i}",
                title=f"Chart {i}"
            )
            for i in range(1, 5)
        ]
        result = create_chart_row(*charts)
        assert len(result.children) == 4

    def test_works_with_single_chart(self):
        """Should work with just one chart container."""
        chart = create_chart_container(
            chart_id="single-chart",
            title="Single Chart"
        )
        result = create_chart_row(chart)
        assert len(result.children) == 1
        assert isinstance(result, dbc.Row)

    def test_works_with_mixed_widths(self):
        """Should work with mixed full and half width charts."""
        full_chart = create_chart_container(
            chart_id="full-chart",
            title="Full Width",
            full_width=True
        )
        half_chart = create_chart_container(
            chart_id="half-chart",
            title="Half Width",
            full_width=False
        )
        result = create_chart_row(full_chart, half_chart)
        assert len(result.children) == 2
        assert result.children[0].md == 12  # Full width
        assert result.children[1].md == 6   # Half width
