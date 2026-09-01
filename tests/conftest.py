"""Test configuration."""

import pytest
from homeassistant.components import http


if not hasattr(http, "start_http_server_and_save_config"):
    async def start_http_server_and_save_config(*args, **kwargs):
        """Compatibility shim for newer Home Assistant test environments."""

    http.start_http_server_and_save_config = start_http_server_and_save_config


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    yield


@pytest.fixture(autouse=True)
def enable_event_loop_debug():
    """Override plugin fixture to keep setup compatible with sync tests."""
    yield


@pytest.fixture(autouse=True)
def configure_event_loop():
    """Override plugin fixture to keep setup compatible with sync tests."""
    yield
