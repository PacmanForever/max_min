import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, call
from homeassistant.util import dt as dt_util

from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_SENSOR_ENTITY, CONF_PERIODS, CONF_TYPES, CONF_OFFSET,
    PERIOD_DAILY, TYPE_MAX
)

@pytest.fixture
def mock_hass():
    hass = Mock()
    hass.config.time_zone = timezone.utc
    # Ensure has loop and basic loop methods
    hass.loop = Mock()
    hass.loop.call_later = Mock()
    hass.data = {} # Needed for initialization
    return hass

@pytest.fixture
def config_entry():
    entry = Mock()
    entry.entry_id = "test_entry"
    entry.title = "Test"
    # Ensure get method works for defaults in coordinator init
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX],
        CONF_OFFSET: 0
    }
    entry.options = {}
    
    entry.options = {}
    return entry

def test_chain_break_protection(mock_hass, config_entry):
    """Test that rescheduling happens even if reset logic crashes."""
    with patch("custom_components.max_min.coordinator.async_track_time_interval"):
        coordinator = MaxMinDataUpdateCoordinator(mock_hass, config_entry)
    
    # Setup initial state
    coordinator.tracked_data[PERIOD_DAILY] = {"max": 10.0, "min": 5.0}
    
    # Mock async_set_updated_data to raise exception (Simulate crash)
    coordinator.async_set_updated_data = Mock(side_effect=ValueError("CRASH BOOM"))
    
    # Mock scheduling to verify it gets called
    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_schedule:
        # Trigger reset
        now = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        coordinator._handle_reset(now, PERIOD_DAILY)
        
        # Verify rescheduling happened ("The Chain remains unbroken")
        assert mock_schedule.called
        # Primary reset timer should target next day's midnight.
        primary_schedule_time = mock_schedule.call_args_list[0][0][2]
        assert primary_schedule_time == datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

def test_watchdog_detects_missed_reset(mock_hass, config_entry):
    """Test standard watchdog detection."""
    with patch("custom_components.max_min.coordinator.async_track_time_interval"):
        coordinator = MaxMinDataUpdateCoordinator(mock_hass, config_entry)
    
    # Setup scenario:
    # Current time: Jan 1st, 00:05 (5 minutes into new day)
    # Last reset: Dec 31st (Old)
    # This means reset was missed!
    
    now = datetime(2023, 1, 1, 0, 5, 0, tzinfo=timezone.utc)
    day_start = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    old_reset = datetime(2022, 12, 31, 0, 0, 0, tzinfo=timezone.utc)
    
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 10.0, 
        "last_reset": old_reset
    }
    
    with patch.object(coordinator, "_handle_reset") as mock_reset:
        coordinator._check_watchdog(now)
        
        # Watchdog should scream and force reset
        mock_reset.assert_called_once_with(now, PERIOD_DAILY, reason="watchdog")

def test_watchdog_respects_offset(mock_hass, config_entry):
    """Test watchdog waits for offset."""
    # Add offset of 900s (15 min)
    with patch("custom_components.max_min.coordinator.async_track_time_interval"):
        coordinator = MaxMinDataUpdateCoordinator(mock_hass, config_entry)
        coordinator.offset = 900 
    
    day_start = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    old_reset = datetime(2022, 12, 31, 0, 0, 0, tzinfo=timezone.utc)
    
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 10.0, 
        "last_reset": old_reset # Old!
    }
    
    with patch.object(coordinator, "_handle_reset") as mock_reset:
        # 1. Check at 00:10 (Before offset expiry)
        # Should NOT trigger because we are waiting for offset
        time_early = day_start + timedelta(minutes=10)
        coordinator._check_watchdog(time_early)
        mock_reset.assert_not_called()
        
        # 2. Check at 00:20 (After offset expiry)
        # Should TRIGGER now
        time_late = day_start + timedelta(minutes=20)
        coordinator._check_watchdog(time_late)
        mock_reset.assert_called_once_with(time_late, PERIOD_DAILY, reason="watchdog")

def test_watchdog_ignores_fresh_resets(mock_hass, config_entry):
    """Test watchdog sleeps if everything is fine."""
    with patch("custom_components.max_min.coordinator.async_track_time_interval"):
        coordinator = MaxMinDataUpdateCoordinator(mock_hass, config_entry)
    
    # Current time: 08:00
    # Last reset: 00:00 Today (Correct)
    now = datetime(2023, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
    today_reset = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    coordinator.tracked_data[PERIOD_DAILY] = {
        "last_reset": today_reset
    }
    
    with patch.object(coordinator, "_handle_reset") as mock_reset:
        coordinator._check_watchdog(now)
        mock_reset.assert_not_called()
