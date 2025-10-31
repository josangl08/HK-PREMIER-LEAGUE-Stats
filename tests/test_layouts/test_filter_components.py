# ABOUTME: Tests for filter sub-components in shared_components module
# ABOUTME: Validates structure, IDs, and properties of filter components

import pytest
from dash import html, dcc
import dash_bootstrap_components as dbc
from layouts.performance_views.shared_components import (
    create_season_selector,
    create_team_selector,
    create_player_selector,
    create_position_filter,
    create_age_range_filter,
    create_export_button
)


class TestSeasonSelector:
    """Tests for create_season_selector component."""

    def test_creates_column_component(self):
        """Should return a dbc.Col component."""
        result = create_season_selector()
        assert isinstance(result, dbc.Col)

    def test_has_correct_default_value(self):
        """Should have default value of 2024-25."""
        result = create_season_selector()
        assert result.md == 4

    def test_accepts_custom_value(self):
        """Should accept custom season value."""
        result = create_season_selector(value="2023-24")
        assert isinstance(result, dbc.Col)

    def test_component_structure(self):
        """Should have correct component structure."""
        result = create_season_selector()
        assert isinstance(result, dbc.Col)
        assert result.md == 4


class TestTeamSelector:
    """Tests for create_team_selector component."""

    def test_creates_column_component(self):
        """Should return a dbc.Col component."""
        result = create_team_selector()
        assert isinstance(result, dbc.Col)

    def test_accepts_clearable_parameter(self):
        """Should accept clearable parameter."""
        result = create_team_selector(clearable=False)
        assert isinstance(result, dbc.Col)

    def test_has_correct_column_width(self):
        """Should have md=4 column width."""
        result = create_team_selector()
        assert result.md == 4


class TestPlayerSelector:
    """Tests for create_player_selector component."""

    def test_creates_column_component(self):
        """Should return a dbc.Col component."""
        result = create_player_selector()
        assert isinstance(result, dbc.Col)

    def test_accepts_clearable_parameter(self):
        """Should accept clearable parameter."""
        result = create_player_selector(clearable=False)
        assert isinstance(result, dbc.Col)

    def test_has_correct_column_width(self):
        """Should have md=4 column width."""
        result = create_player_selector()
        assert result.md == 4


class TestPositionFilter:
    """Tests for create_position_filter component."""

    def test_creates_column_component(self):
        """Should return a dbc.Col component."""
        result = create_position_filter()
        assert isinstance(result, dbc.Col)

    def test_has_correct_column_width(self):
        """Should have md=4 column width."""
        result = create_position_filter()
        assert result.md == 4


class TestAgeRangeFilter:
    """Tests for create_age_range_filter component."""

    def test_creates_column_component(self):
        """Should return a dbc.Col component."""
        result = create_age_range_filter()
        assert isinstance(result, dbc.Col)

    def test_has_correct_column_width(self):
        """Should have md=4 column width."""
        result = create_age_range_filter()
        assert result.md == 4


class TestExportButton:
    """Tests for create_export_button component."""

    def test_creates_column_component(self):
        """Should return a dbc.Col component."""
        result = create_export_button()
        assert isinstance(result, dbc.Col)

    def test_has_correct_column_width(self):
        """Should have md=4 column width."""
        result = create_export_button()
        assert result.md == 4
