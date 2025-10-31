# ABOUTME: Tests for status and error components in shared_components module
# ABOUTME: Validates alert and empty state rendering and behavior

import pytest
from dash import html
import dash_bootstrap_components as dbc
from layouts.performance_views.shared_components import (
    create_status_alert,
    create_empty_state
)


class TestStatusAlert:
    """Tests for create_status_alert component."""

    def test_creates_alert_component(self):
        """Should return a dbc.Alert component."""
        result = create_status_alert(
            alert_id="test-alert",
            message="Test message"
        )
        assert isinstance(result, dbc.Alert)

    def test_has_correct_id(self):
        """Should have the specified ID."""
        result = create_status_alert(
            alert_id="custom-alert-id",
            message="Test"
        )
        assert result.id == "custom-alert-id"

    def test_displays_message(self):
        """Should display the provided message."""
        message = "This is a test alert message"
        result = create_status_alert(
            alert_id="test-alert",
            message=message
        )
        assert result.children == message

    def test_default_alert_type_is_info(self):
        """Should have 'info' as default alert type."""
        result = create_status_alert(
            alert_id="test-alert",
            message="Test"
        )
        assert result.color == "info"

    def test_accepts_custom_alert_type(self):
        """Should accept custom alert types."""
        types = ["success", "warning", "danger", "info"]
        for alert_type in types:
            result = create_status_alert(
                alert_id="test-alert",
                message="Test",
                alert_type=alert_type
            )
            assert result.color == alert_type

    def test_is_dismissible_by_default(self):
        """Should be dismissible by default."""
        result = create_status_alert(
            alert_id="test-alert",
            message="Test"
        )
        assert result.dismissable is True

    def test_can_disable_dismissible(self):
        """Should allow disabling dismissible."""
        result = create_status_alert(
            alert_id="test-alert",
            message="Test",
            dismissible=False
        )
        assert result.dismissable is False

    def test_is_shown_by_default(self):
        """Should be shown by default."""
        result = create_status_alert(
            alert_id="test-alert",
            message="Test"
        )
        assert result.is_open is True

    def test_can_be_hidden_initially(self):
        """Should allow hiding initially."""
        result = create_status_alert(
            alert_id="test-alert",
            message="Test",
            show=False
        )
        assert result.is_open is False

    def test_has_correct_margin_class(self):
        """Should have mb-3 margin class."""
        result = create_status_alert(
            alert_id="test-alert",
            message="Test"
        )
        assert result.className == "mb-3"


class TestEmptyState:
    """Tests for create_empty_state component."""

    def test_creates_card_component(self):
        """Should return a dbc.Card component."""
        result = create_empty_state()
        assert isinstance(result, dbc.Card)

    def test_displays_default_title(self):
        """Should display default title."""
        result = create_empty_state()
        # Extract card body
        body = result.children[0]
        content = body.children[0]
        # Find title in content
        title_found = False
        for child in content.children:
            if isinstance(child, html.H5):
                if child.children == "No Data Available":
                    title_found = True
                    break
        assert title_found

    def test_displays_custom_title(self):
        """Should display custom title."""
        custom_title = "No Players Found"
        result = create_empty_state(title=custom_title)
        body = result.children[0]
        content = body.children[0]
        title_found = False
        for child in content.children:
            if isinstance(child, html.H5):
                if child.children == custom_title:
                    title_found = True
                    break
        assert title_found

    def test_displays_default_message(self):
        """Should display default message."""
        result = create_empty_state()
        body = result.children[0]
        content = body.children[0]
        message_found = False
        for child in content.children:
            if isinstance(child, html.P):
                if child.children == "Try adjusting your filters":
                    message_found = True
                    break
        assert message_found

    def test_displays_custom_message(self):
        """Should display custom message."""
        custom_message = "No data matches your criteria"
        result = create_empty_state(message=custom_message)
        body = result.children[0]
        content = body.children[0]
        message_found = False
        for child in content.children:
            if isinstance(child, html.P):
                if child.children == custom_message:
                    message_found = True
                    break
        assert message_found

    def test_displays_default_icon(self):
        """Should display default icon."""
        result = create_empty_state()
        body = result.children[0]
        content = body.children[0]
        icon_found = False
        for child in content.children:
            if isinstance(child, html.I):
                if "bi-inbox" in child.className:
                    icon_found = True
                    break
        assert icon_found

    def test_displays_custom_icon(self):
        """Should display custom icon."""
        custom_icon = "bi-exclamation-triangle"
        result = create_empty_state(icon=custom_icon)
        body = result.children[0]
        content = body.children[0]
        icon_found = False
        for child in content.children:
            if isinstance(child, html.I):
                if custom_icon in child.className:
                    icon_found = True
                    break
        assert icon_found

    def test_has_centered_text(self):
        """Should have centered text styling."""
        result = create_empty_state()
        body = result.children[0]
        content = body.children[0]
        assert "text-center" in content.className

    def test_has_vertical_padding(self):
        """Should have vertical padding."""
        result = create_empty_state()
        body = result.children[0]
        content = body.children[0]
        assert "py-5" in content.className

    def test_icon_has_correct_styling(self):
        """Should have correct icon styling."""
        result = create_empty_state()
        body = result.children[0]
        content = body.children[0]
        for child in content.children:
            if isinstance(child, html.I):
                assert child.style["fontSize"] == "3rem"
                assert child.style["color"] == "#A7A7A7"
                break
