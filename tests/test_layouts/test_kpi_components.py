# ABOUTME: Tests for KPI card components in shared_components module
# ABOUTME: Validates KPI card structure, styling, and row composition

import pytest
from dash import html
import dash_bootstrap_components as dbc
from layouts.performance_views.shared_components import (
    create_kpi_card,
    create_kpi_row
)


class TestKPICard:
    """Tests for create_kpi_card component."""

    def test_creates_column_component(self):
        """Should return a dbc.Col component."""
        result = create_kpi_card(value=100, label="Test Metric")
        assert isinstance(result, dbc.Col)

    def test_has_responsive_breakpoints(self):
        """Should have correct responsive breakpoints."""
        result = create_kpi_card(value=100, label="Test")
        assert result.lg == 3
        assert result.md == 6
        assert result.sm == 6
        assert result.xs == 12

    def test_contains_card_component(self):
        """Should contain a dbc.Card."""
        result = create_kpi_card(value=100, label="Test")
        assert len(result.children) > 0
        card = result.children[0]
        assert isinstance(card, dbc.Card)

    def test_card_has_metric_card_class(self):
        """Should have metric-card CSS class."""
        result = create_kpi_card(value=100, label="Test")
        card = result.children[0]
        assert card.className == "metric-card"

    def test_accepts_all_parameters(self):
        """Should accept all parameters without errors."""
        result = create_kpi_card(
            value=100,
            label="Goals",
            unit="scored",
            icon="bi-target",
            trend="+12%",
            trend_color="success",
            card_id="test-card-id"
        )
        assert isinstance(result, dbc.Col)
        card = result.children[0]
        assert card.id == "test-card-id"

    def test_works_without_optional_parameters(self):
        """Should work with only required parameters."""
        result = create_kpi_card(value=100, label="Test")
        assert isinstance(result, dbc.Col)
        card = result.children[0]
        # When no card_id provided, card should not have id attribute set
        assert not hasattr(card, 'id') or card.id is None


class TestKPIRow:
    """Tests for create_kpi_row component."""

    def test_creates_row_component(self):
        """Should return a dbc.Row component."""
        card1 = create_kpi_card(value=100, label="Metric 1")
        card2 = create_kpi_card(value=200, label="Metric 2")
        result = create_kpi_row(card1, card2)
        assert isinstance(result, dbc.Row)

    def test_contains_all_cards(self):
        """Should contain all provided KPI cards."""
        card1 = create_kpi_card(value=100, label="Metric 1")
        card2 = create_kpi_card(value=200, label="Metric 2")
        card3 = create_kpi_card(value=300, label="Metric 3")
        result = create_kpi_row(card1, card2, card3)
        assert len(result.children) == 3

    def test_has_correct_margin_class(self):
        """Should have mb-4 margin class."""
        card1 = create_kpi_card(value=100, label="Test")
        result = create_kpi_row(card1)
        assert result.className == "mb-4"

    def test_accepts_variable_number_of_cards(self):
        """Should accept any number of KPI cards."""
        cards = [
            create_kpi_card(value=i*100, label=f"Metric {i}")
            for i in range(1, 6)
        ]
        result = create_kpi_row(*cards)
        assert len(result.children) == 5

    def test_works_with_single_card(self):
        """Should work with just one KPI card."""
        card = create_kpi_card(value=100, label="Single Metric")
        result = create_kpi_row(card)
        assert len(result.children) == 1
        assert isinstance(result, dbc.Row)
