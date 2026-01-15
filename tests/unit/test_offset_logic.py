"""Test offset logic."""

from datetime import datetime, timedelta, timezone
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
    hass.states.get.return_value = Mock(state="10.0", attributes={"friendly_name": "Test Sensor"})
    return hass

@pytest.mark.asyncio
async def test_offset_schedule(hass, config_entry):
    """Test that reset is scheduled with offset."""
    # Freeze time at 2023-01-01 10:00:00 UTC
    with freeze_time("2023-01-01 10:00:00"):
        coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
        
        # Mock async_track_point_in_time to capture when it's called
        with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
            coordinator._schedule_resets()
            
            # Daily reset should be at Jan 2nd 00:00:00 + 10s offset
            expected_reset_base = datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
            expected_schedule = expected_reset_base + timedelta(seconds=10)
            
            assert mock_track.call_count == 1
            call_args = mock_track.call_args
            # arg 2 is the time
            scheduled_time = call_args[0][2]
            assert scheduled_time == expected_schedule

            # Check if internal helper stored the base reset time correctly
            assert coordinator._next_resets[PERIOD_DAILY] == expected_reset_base

@pytest.mark.asyncio
async def test_offset_dead_zone_ignore_updates(hass, config_entry):
    """Test that updates are ignored in the dead zone."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    
    # Initialize coordinator
    coordinator._next_resets = {
        PERIOD_DAILY: datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    }
    coordinator.tracked_data[PERIOD_DAILY] = {"max": 10.0, "min": 10.0}
    
    # CASE 1: Normal time (Safe zone)
    # 2023-01-01 23:59:40 - 20s before reset (Safe, outside 10s offset)
    with freeze_time("2023-01-01 23:59:40"):
        event = Mock()
        event.data = {"new_state": Mock(state="20.0")}
        coordinator._handle_sensor_change(event)
        
        # Should update
        assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 20.0

    # CASE 2: Inside Dead Zone (Before)
    # 2023-01-01 23:59:55 - 5s before reset (Unsafe, inside 10s offset)
    with freeze_time("2023-01-01 23:59:55"):
        event = Mock()
        event.data = {"new_state": Mock(state="30.0")}
        coordinator._handle_sensor_change(event)
        
        # Should NOT update (still 20.0)
        assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 20.0

    # CASE 3: Inside Dead Zone (After)
    # 2023-01-02 00:00:05 - 5s after reset (Unsafe, inside 10s offset)
    with freeze_time("2023-01-02 00:00:05"):
        event = Mock()
        event.data = {"new_state": Mock(state="40.0")}
        coordinator._handle_sensor_change(event)
        
        # Should NOT update (still 20.0)
        assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 20.0

    # CASE 4: Normal time (After Safe Zone)
    # 2023-01-02 00:00:15 - 15s after reset (Safe)
    with freeze_time("2023-01-02 00:00:15"):
        event = Mock()
        event.data = {"new_state": Mock(state="50.0")}
        coordinator._handle_sensor_change(event)
        
        # Should update
        assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 50.0

