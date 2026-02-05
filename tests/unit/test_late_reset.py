"""Test late reset logic."""
from unittest.mock import Mock, patch
from datetime import timedelta
import pytest
from homeassistant.util import dt as dt_util

from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_PERIODS,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    PERIOD_DAILY,
    TYPE_MAX,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

@pytest.fixture
def hass():
    """Mock hass."""
    hass = Mock()
    hass.config.time_zone = dt_util.UTC
    hass.data = {"custom_components": {}}
    hass.loop.time.return_value = 1000.0
    return hass

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock external dependencies to avoid event loop usage."""
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"), \
         patch("custom_components.max_min.coordinator.async_track_state_change_event"):
        yield

@pytest.mark.asyncio
async def test_late_reset_grace_period(hass):
    """Test that a reset arriving shortly AFTER the scheduled reset re-triggers the logic."""
    # Setup
    now = dt_util.utcnow()
    
    entry = MockConfigEntry(
        domain="max_min",
        data={
            CONF_SENSOR_ENTITY: "sensor.rain",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_MAX],
        },
        options={} # No offset
    )
    
    # Initial state: 10mm rain
    hass.states.get.return_value = Mock(
        state="10.0", 
        attributes={"state_class": "total_increasing"}
    )
    
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    # Initialize. Max = 10.0
    with patch("custom_components.max_min.coordinator.dt_util.now", return_value=now):
        await coordinator.async_config_entry_first_refresh()
    
    assert coordinator.get_value(PERIOD_DAILY, "max") == 10.0
    
    # 1. Simulate Midnight Reset (Scheduled)
    # This sets Max = current value (10.0) and updates last_reset
    midnight = now # treat 'now' as midnight for simplicity
    with patch("custom_components.max_min.coordinator.dt_util.now", return_value=midnight):
        coordinator._handle_reset(midnight, PERIOD_DAILY)
    
    assert coordinator.get_value(PERIOD_DAILY, "max") == 10.0
    assert coordinator.get_value(PERIOD_DAILY, "last_reset") == midnight
    
    # 2. Simulate Sensor Reset arriving 30 seconds later
    # 10.0 -> 0.0
    late_time = midnight + timedelta(seconds=30)
    
    source_state = Mock(
        state="0.0",
        attributes={"state_class": "total_increasing"}
    )
    # CRITICAL: _handle_reset reads the CURRENT state from hass, so we must mock it to match the event
    hass.states.get.return_value = source_state
    
    event = Mock()
    event.data = {"new_state": source_state}
    
    with patch("custom_components.max_min.coordinator.dt_util.now", return_value=late_time):
        coordinator._handle_sensor_change(event)
        
    # verify that the reset was re-triggered and captured the 0.0
    assert coordinator.get_value(PERIOD_DAILY, "max") == 0.0
    
    # Verify last_reset was updated to the late correction time
    assert coordinator.get_value(PERIOD_DAILY, "last_reset") == late_time
