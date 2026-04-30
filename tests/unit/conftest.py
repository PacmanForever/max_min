"""Shared fixtures and helpers for the max_min unit test suite."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from homeassistant.util import dt as dt_util
from datetime import timezone

from custom_components.max_min.const import (
    CONF_OFFSET,
    CONF_PERIODS,
    CONF_RESET_HISTORY,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    PERIOD_DAILY,
    TYPE_MAX,
    TYPE_MIN,
)

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


def make_config_entry(periods=None, types=None, offset=0, options=None, **extra_data):
    """Create a mock ConfigEntry with consistent defaults for unit tests."""
    entry = Mock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: periods if periods is not None else [PERIOD_DAILY],
        CONF_TYPES: types if types is not None else [TYPE_MAX, TYPE_MIN],
        CONF_OFFSET: offset,
        CONF_RESET_HISTORY: [],
        **extra_data,
    }
    entry.options = options or {}
    entry.entry_id = "test_entry"
    entry.title = "Test Entry"
    return entry


def make_mock_hass(state="10.0", state_class=None, tz=None, data=None, attrs=None):
    """Create a mock Home Assistant object for synchronous unit tests."""
    hass = Mock()
    hass.config.time_zone = tz or timezone.utc
    hass.data = {} if data is None else data
    hass.loop = Mock()
    hass.states = Mock()

    mock_state = Mock()
    mock_state.state = state
    mock_state.attributes = {"friendly_name": "Test Sensor", **(attrs or {})}
    if state_class:
        mock_state.attributes["state_class"] = state_class
    hass.states.get.return_value = mock_state
    return hass
