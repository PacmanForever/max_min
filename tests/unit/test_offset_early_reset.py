"""Test offset logic early reset."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
from freezegun import freeze_time

from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_PERIODS,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    CONF_OFFSET,
    PERIOD_DAILY,
    TYPE_MAX,
    TYPE_MIN,
)

@pytest.fixture
def config_entry():
    """Mock config entry."""
    entry = MagicMock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX, TYPE_MIN],
    }
    # Set offset to 10 seconds in options
    entry.options = {
        CONF_OFFSET: 10
    }
    entry.entry_id = "test_entry"
    entry.title = "Test"
    return entry

@pytest.fixture
def hass():
    """Mock hass."""
    hass = Mock()
    hass.config.time_zone = timezone.utc
    hass.data = {"custom_components": {}}
    hass.states.get.return_value = Mock(
        state="10.0",
        attributes={"friendly_name": "Test Sensor", "state_class": "total_increasing"},
    )
    return hass

@pytest.mark.asyncio
async def test_offset_dead_zone_early_reset(hass, config_entry):
    """Test that a value drop (reset) in dead zone triggers immediate reset."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    
    # Initialize coordinator with data from yesterday
    # Reset Period: Daily
    # Next Reset: 2023-01-02 00:00:00
    coordinator._next_resets = {
        PERIOD_DAILY: datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    }
    coordinator.tracked_data[PERIOD_DAILY] = {"max": 10.0, "min": 10.0, "start": 5.0, "end": 10.0}
    
    # Init reset listeners dict
    cancel_mock = Mock()
    coordinator._reset_listeners = {
        PERIOD_DAILY: cancel_mock
    }

    # Simulate update inside Dead Zone (Before Reset Time)
    # Time: 2023-01-01 23:59:55 
    # (Offset is 10s. Deadzone: 23:59:50 to 00:00:10)
    # Update: Value drops to 0.0 (Reset!)
    with freeze_time("2023-01-01 23:59:55"):
        event = Mock()
        event.data = {
            "new_state": Mock(
                state="0.0",
                attributes={"state_class": "total_increasing"}
            )
        }
        
        # Ensure hass.states.get returns the new state so handle_reset reads it
        hass.states.get.return_value = Mock(state="0.0")

        # Mock _handle_reset to verify it gets called
        with patch.object(coordinator, '_handle_reset', wraps=coordinator._handle_reset) as mock_reset:
             # We also need to patch async_track_point_in_time because _handle_reset calls it to schedule NEXT reset
             with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
                 coordinator._handle_sensor_change(event)
             
                 # Should have called reset
                 mock_reset.assert_called_once()
                 
                 # Verify passed args (should be NOW and PERIOD)
                 args = mock_reset.call_args
                 assert args[0][1] == PERIOD_DAILY
                 # reset time passed is usually "now"
                 
                 # Listener should be cancelled
                 cancel_mock.assert_called_once()

    # After reset, Max should be 0.0
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 0.0
    # Listener for next period should be scheduled
    assert PERIOD_DAILY in coordinator._reset_listeners
    # Wait, _handle_reset reschedules! So it should contain the NEW listener.
    # checking that old one is gone is implicit by cancel_mock call.
    # coordinator._reset_listeners might contain the NEW listener for next day.
