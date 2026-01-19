"""Test extra coverage for edge cases."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

from custom_components.max_min.sensor import MaxSensor, MinSensor
from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import PERIOD_DAILY, CONF_SENSOR_ENTITY

@pytest.fixture
def hass():
    """Mock hass."""
    hass = Mock()
    hass.states.get.return_value = Mock(state="10.0")
    return hass

@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    entry = Mock()
    entry.entry_id = "test_entry"
    entry.title = "Test"
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.demo_entity"
    }
    entry.options = {}
    return entry

@pytest.fixture
def coordinator(hass, mock_config_entry):
    """Coordinator fixture."""
    return MaxMinDataUpdateCoordinator(hass, mock_config_entry)

@pytest.mark.asyncio
async def test_sensor_restore_value_error(coordinator, mock_config_entry):
    """Test ValueError handling during restore."""
    # MaxSensor
    sensor = MaxSensor(coordinator, mock_config_entry, "Test Max", PERIOD_DAILY)
    
    last_state = Mock()
    last_state.state = "invalid_float"
    last_state.attributes = {}
    sensor.async_get_last_state = AsyncMock(return_value=last_state)
    
    # Check that it doesn't raise exception
    await sensor.async_added_to_hass()
    
    # MinSensor
    sensor_min = MinSensor(coordinator, mock_config_entry, "Test Min", PERIOD_DAILY)
    sensor_min.async_get_last_state = AsyncMock(return_value=last_state)
    
    await sensor_min.async_added_to_hass()

@pytest.mark.asyncio
async def test_sensor_extra_state_attributes(coordinator, mock_config_entry):
    """Test extra_state_attributes."""
    now = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    coordinator.tracked_data[PERIOD_DAILY] = {"max": 10.0, "min": 5.0, "last_reset": now}
    
    # MaxSensor
    sensor = MaxSensor(coordinator, mock_config_entry, "Test Max", PERIOD_DAILY)
    attrs = sensor.extra_state_attributes
    assert attrs["last_reset"] == now.isoformat()
    
    # MinSensor
    sensor_min = MinSensor(coordinator, mock_config_entry, "Test Min", PERIOD_DAILY)
    attrs = sensor_min.extra_state_attributes
    assert attrs["last_reset"] == now.isoformat()
    
    # Case when last_reset is None
    coordinator.tracked_data[PERIOD_DAILY]["last_reset"] = None
    attrs = sensor.extra_state_attributes
    assert "last_reset" not in attrs

@pytest.mark.asyncio
async def test_coordinator_unload(coordinator):
    """Test async_unload."""
    # Add a dummy listener
    listener = Mock()
    coordinator._reset_listeners["test"] = listener
    
    unsub = Mock()
    coordinator._unsub_sensor_state_listener = unsub
    
    await coordinator.async_unload()
    
    listener.assert_called_once()
    unsub.assert_called_once()
    assert coordinator._reset_listeners == {}
    assert coordinator._unsub_sensor_state_listener is None
