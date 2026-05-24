"""Test restore state functionality."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.util import dt as dt_util

from custom_components.max_min.const import (
    CONF_SENSOR_ENTITY,
    CONF_PERIODS,
    CONF_TYPES,
    PERIOD_DAILY,
    TYPE_MAX,
    TYPE_MIN
)
from custom_components.max_min.sensor import MaxSensor, MinSensor
from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator

@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    entry = Mock()
    entry.entry_id = "test_entry"
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.source",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX, TYPE_MIN]
    }
    entry.options = {}
    return entry

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations():
    """Override global autouse to avoid pulling in real hass."""
    yield

@pytest.fixture
def mock_hass():
    """Mock hass."""
    hass = Mock()
    hass.states.get.return_value = Mock(state="10.0")
    return hass

@pytest.fixture
def mock_coordinator(mock_hass, mock_config_entry):
    """Mock coordinator."""
    coord = MaxMinDataUpdateCoordinator(mock_hass, mock_config_entry)
    # Initialize normally first (sets to 10.0)
    coord.tracked_data = {
        PERIOD_DAILY: {"max": 10.0, "min": 10.0}
    }
    return coord

def test_coordinator_update_restored_data(mock_coordinator):
    """Test coordinator update_restored_data logic."""
    # Current is 10.0 for both
    
    # Restore a lower min (5.0) -> Should update
    mock_coordinator.update_restored_data(PERIOD_DAILY, "min", 5.0)
    assert mock_coordinator.get_value(PERIOD_DAILY, "min") == 5.0
    
    # Restore a higher min (15.0) -> Should NOT update (5.0 is better)
    mock_coordinator.update_restored_data(PERIOD_DAILY, "min", 15.0)
    assert mock_coordinator.get_value(PERIOD_DAILY, "min") == 5.0
    
    # Restore a higher max (20.0) -> Should update
    mock_coordinator.update_restored_data(PERIOD_DAILY, "max", 20.0)
    assert mock_coordinator.get_value(PERIOD_DAILY, "max") == 20.0
    
    # Restore a lower max (18.0) -> Should NOT update
    mock_coordinator.update_restored_data(PERIOD_DAILY, "max", 18.0)
    assert mock_coordinator.get_value(PERIOD_DAILY, "max") == 20.0

@pytest.mark.asyncio
async def test_max_sensor_restores_state(mock_coordinator, mock_config_entry):
    """Test MaxSensor restores state."""
    sensor = MaxSensor(mock_coordinator, mock_config_entry, "Test Max", PERIOD_DAILY)
    
    # Mock last state
    last_state = Mock()
    last_state.state = "25.5"
    last_state.attributes = {"config_entry_id": "test_entry"}
    sensor.async_get_last_state = AsyncMock(return_value=last_state)
    
    # Spy on coordinator
    mock_coordinator.update_restored_data = Mock(wraps=mock_coordinator.update_restored_data)
    
    await sensor.async_added_to_hass()
    
    mock_coordinator.update_restored_data.assert_called_with(PERIOD_DAILY, "max", 25.5, None)
    # Since coord started at 10.0, it should be 25.5 now
    assert mock_coordinator.get_value(PERIOD_DAILY, "max") == 25.5

@pytest.mark.asyncio
async def test_min_sensor_restores_state(mock_coordinator, mock_config_entry):
    """Test MinSensor restores state."""
    sensor = MinSensor(mock_coordinator, mock_config_entry, "Test Min", PERIOD_DAILY)
    
    # Mock last state
    last_state = Mock()
    last_state.state = "-5.0"
    last_state.attributes = {"config_entry_id": "test_entry"}
    sensor.async_get_last_state = AsyncMock(return_value=last_state)
    
    # Spy on coordinator
    mock_coordinator.update_restored_data = Mock(wraps=mock_coordinator.update_restored_data)
    
    await sensor.async_added_to_hass()
    
    mock_coordinator.update_restored_data.assert_called_with(PERIOD_DAILY, "min", -5.0, None)
    # Since coord started at 10.0, it should be -5.0 now
    assert mock_coordinator.get_value(PERIOD_DAILY, "min") == -5.0

@pytest.mark.asyncio
async def test_sensor_restore_invalid_state(mock_coordinator, mock_config_entry):
    """Test sensor handles invalid restored state."""
    sensor = MaxSensor(mock_coordinator, mock_config_entry, "Test Max", PERIOD_DAILY)
    
    # Mock last state
    last_state = Mock()
    last_state.state = "unknown"
    sensor.async_get_last_state = AsyncMock(return_value=last_state)
    
    # Spy on coordinator
    mock_coordinator.update_restored_data = Mock(wraps=mock_coordinator.update_restored_data)
    
    await sensor.async_added_to_hass()
    
    mock_coordinator.update_restored_data.assert_not_called()


@pytest.mark.asyncio
async def test_sensor_restore_value_error(mock_coordinator, mock_config_entry):
    """ValueError during restore is ignored for max and min sensors."""
    last_state = Mock()
    last_state.state = "invalid_float"
    last_state.attributes = {}

    max_sensor = MaxSensor(mock_coordinator, mock_config_entry, "Test Max", PERIOD_DAILY)
    max_sensor.async_get_last_state = AsyncMock(return_value=last_state)
    await max_sensor.async_added_to_hass()

    min_sensor = MinSensor(mock_coordinator, mock_config_entry, "Test Min", PERIOD_DAILY)
    min_sensor.async_get_last_state = AsyncMock(return_value=last_state)
    await min_sensor.async_added_to_hass()


def test_restore_accepts_utc_last_reset_in_same_local_day():
    """Restore accepts UTC timestamps that are still in the same local period."""
    old_tz = dt_util.DEFAULT_TIME_ZONE
    try:
        dt_util.set_default_time_zone(ZoneInfo("Europe/Madrid"))

        ha = Mock()
        ha.states.get.return_value = Mock(state="10.0", attributes={})

        entry = Mock()
        entry.entry_id = "test"
        entry.data = {
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_MAX],
        }
        entry.options = {}

        coordinator = MaxMinDataUpdateCoordinator(ha, entry)
        coordinator.tracked_data[PERIOD_DAILY]["max"] = 5.0

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "custom_components.max_min.coordinator.dt_util.now",
                lambda: datetime(2026, 4, 3, 1, 30, 0, tzinfo=ZoneInfo("Europe/Madrid")),
            )
            coordinator.update_restored_data(
                PERIOD_DAILY,
                "max",
                42.0,
                last_reset="2026-04-02T22:00:00+00:00",
            )

        assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 42.0
        assert coordinator.tracked_data[PERIOD_DAILY]["last_reset"] == datetime(
            2026, 4, 3, 0, 0, 0, tzinfo=ZoneInfo("Europe/Madrid")
        )
    finally:
        dt_util.set_default_time_zone(old_tz)


def test_restore_without_last_reset_allowed():
    """Historical restore remains allowed even without last_reset metadata."""
    ha = Mock()
    ha.states.get.return_value = Mock(state="10.0", attributes={})

    entry = Mock()
    entry.entry_id = "test"
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX],
    }
    entry.options = {}

    coordinator = MaxMinDataUpdateCoordinator(ha, entry)
    coordinator.tracked_data[PERIOD_DAILY]["max"] = 10.0
    coordinator.tracked_data[PERIOD_DAILY]["last_reset"] = datetime.now()

    coordinator.update_restored_data(PERIOD_DAILY, "max", 50.0, last_reset=None)

    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 50.0


def test_restored_value_not_overwritten_by_current():
    """A restored historical max must win over the current source value."""
    ha = Mock()

    entry = Mock()
    entry.entry_id = "test"
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX],
    }
    entry.options = {}

    ha.states.get.return_value = Mock(state="10.0", attributes={})

    coordinator = MaxMinDataUpdateCoordinator(ha, entry)

    assert coordinator.tracked_data[PERIOD_DAILY]["max"] is None

    coordinator.update_restored_data(PERIOD_DAILY, "max", 50.0)

    assert coordinator.get_value(PERIOD_DAILY, "max") == 50.0


@pytest.mark.asyncio
async def test_max_sensor_restores_end_value_for_unavailable_reset(mock_hass, mock_config_entry):
    """Max sensor restore keeps period end so unavailable midnight resets stay numeric."""
    mock_hass.states.get.return_value = Mock(state="unavailable", attributes={})
    coordinator = MaxMinDataUpdateCoordinator(mock_hass, mock_config_entry)

    sensor = MaxSensor(coordinator, mock_config_entry, "Test Max", PERIOD_DAILY)
    last_state = Mock()
    last_state.state = "25.5"
    last_state.attributes = {
        "config_entry_id": "test_entry",
        "end_value": 17.2,
    }
    sensor.async_get_last_state = AsyncMock(return_value=last_state)

    await sensor.async_added_to_hass()

    assert coordinator.get_value(PERIOD_DAILY, "end") == 17.2

    now = datetime(2026, 5, 25, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._perform_reset(now, PERIOD_DAILY)

    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 17.2
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 17.2
    assert coordinator.tracked_data[PERIOD_DAILY]["start"] == 17.2
    assert coordinator.tracked_data[PERIOD_DAILY]["end"] == 17.2
