"""Test configuration."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    yield


@pytest.fixture(autouse=True)
def enable_event_loop_debug():
    """Override plugin fixture to keep setup compatible with sync tests."""
    yield
