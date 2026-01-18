"""Test restore state functionality."""
from unittest.mock import Mock, patch, AsyncMock
import pytest

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
    last_state.attributes = {}
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
    last_state.attributes = {}
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
