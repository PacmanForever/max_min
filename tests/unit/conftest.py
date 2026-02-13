import pytest
from unittest.mock import Mock, MagicMock, patch
from homeassistant.util import dt as dt_util
from datetime import timezone

@pytest.fixture(autouse=True)
def mock_track_time_interval():
    """Mock async_track_time_interval normally used in coordinator init."""
    with patch("custom_components.max_min.coordinator.async_track_time_interval") as mock_track:
        yield mock_track

@pytest.fixture(autouse=True)
def set_utc_timezone():
    """Set default timezone to UTC for all unit tests to match CI environment."""
    dt_util.set_default_time_zone(timezone.utc)
    yield

@pytest.fixture
def hass():
    """Mock Home Assistant object for unit tests.
    
    This overrides the 'hass' fixture from pytest-homeassistant-custom-component
    to avoid async/sync conflicts in unit tests that don't need the full HA loop.
    """
    hass = Mock()
    hass.config.time_zone = timezone.utc
    hass.data = {}
    hass.loop = Mock()
    hass.states = Mock()
    hass.states.get.return_value = None
    return hass

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations():
    """Override and disable the global fixture that tries to load integrations."""
    yield
