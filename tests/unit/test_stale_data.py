"""Test stale data handling and last_reset logic."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from freezegun import freeze_time

from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_SENSOR_ENTITY,
    CONF_PERIODS,
    CONF_TYPES,
    PERIOD_DAILY,
    PERIOD_WEEKLY,
    PERIOD_MONTHLY,
    PERIOD_YEARLY,
    PERIOD_ALL_TIME,
    TYPE_MAX,
    TYPE_MIN
)

@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    entry = Mock()
    entry.entry_id = "test_entry"
    entry.title = "Test"
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY, PERIOD_WEEKLY, PERIOD_MONTHLY, PERIOD_YEARLY, PERIOD_ALL_TIME],
        CONF_TYPES: [TYPE_MAX, TYPE_MIN]
    }
    entry.options = {}
    return entry

@pytest.fixture
def hass():
    """Mock hass."""
    hass = Mock()
    hass.states.get.return_value = Mock(state="10.0")
    return hass

@pytest.fixture
def coordinator(hass, mock_config_entry):
    """Coordinator fixture."""
    return MaxMinDataUpdateCoordinator(hass, mock_config_entry)

@pytest.mark.asyncio
async def test_get_period_start(coordinator):
    """Test _get_period_start logic."""
    now = datetime(2023, 5, 10, 15, 30, 0, tzinfo=timezone.utc) # A Wednesday
    
    # Daily
    start = coordinator._get_period_start(now, PERIOD_DAILY)
    assert start == datetime(2023, 5, 10, 0, 0, 0, tzinfo=timezone.utc)
    
    # Weekly (Monday is start)
    # May 10th 2023 is Wednesday. Monday was May 8th.
    start = coordinator._get_period_start(now, PERIOD_WEEKLY)
    assert start == datetime(2023, 5, 8, 0, 0, 0, tzinfo=timezone.utc)
    
    # Monthly
    start = coordinator._get_period_start(now, PERIOD_MONTHLY)
    assert start == datetime(2023, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    # Yearly
    start = coordinator._get_period_start(now, PERIOD_YEARLY)
    assert start == datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    # Unknown
    start = coordinator._get_period_start(now, "unknown")
    assert start is None

@pytest.mark.asyncio
async def test_update_restored_data_stale(coordinator):
    """Test that stale data is ignored."""
    # Current time: 2023-01-02 10:00:00
    now = datetime(2023, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
    
    with patch("homeassistant.util.dt.now", return_value=now):
        # We manually init the period data so checks pass
        coordinator.tracked_data[PERIOD_DAILY] = {"max": 20.0, "min": 20.0, "last_reset": now}
        
        # Restore data from YESTERDAY (2023-01-01)
        # Period start for today is 2023-01-02 00:00:00
        # last_reset passed is 2023-01-01 23:00:00 (Stale)
        stale_reset = datetime(2023, 1, 1, 23, 0, 0, tzinfo=timezone.utc)
        
        # Try to restore a MAX that is higher (30.0). Should be IGNORED because it's stale.
        coordinator.update_restored_data(PERIOD_DAILY, "max", 30.0, last_reset=stale_reset)
        
        assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 20.0
        
@pytest.mark.asyncio
async def test_update_restored_data_valid(coordinator):
    """Test that valid data is accepted."""
    # Current time: 2023-01-02 10:00:00
    now = datetime(2023, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
    
    with patch("homeassistant.util.dt.now", return_value=now):
        coordinator.tracked_data[PERIOD_DAILY] = {"max": 20.0, "min": 20.0, "last_reset": now}
        
        # Restore data from TODAY earlier (2023-01-02 08:00:00)
        valid_reset = datetime(2023, 1, 2, 8, 0, 0, tzinfo=timezone.utc)
        
        # Try to restore a MAX that is higher (30.0). Should be ACCEPTED.
        coordinator.update_restored_data(PERIOD_DAILY, "max", 30.0, last_reset=valid_reset)
        
        assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 30.0
        # Should NOT update last_reset because existing one (now) is newer than valid_reset (8:00)
        # wait, the logic is: if last_reset > data["last_reset"]: data["last_reset"] = last_reset
        # So it keeps the newer one.
        assert coordinator.tracked_data[PERIOD_DAILY]["last_reset"] == now

@pytest.mark.asyncio
async def test_update_restored_data_valid_newer_reset(coordinator):
    """Test that valid data updates last_reset if it's newer."""
    # This scenario is a bit weird (restored data newer than current?), 
    # but could happen if we just instantiated and current is None.
    
    now = datetime(2023, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
    with patch("homeassistant.util.dt.now", return_value=now):
         # Initialize with NONE
        coordinator.tracked_data[PERIOD_DAILY] = {"max": None, "min": None, "last_reset": None}
        
        valid_reset = datetime(2023, 1, 2, 8, 0, 0, tzinfo=timezone.utc)
        coordinator.update_restored_data(PERIOD_DAILY, "max", 30.0, last_reset=valid_reset)
        
        assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 30.0
        assert coordinator.tracked_data[PERIOD_DAILY]["last_reset"] == valid_reset

@pytest.mark.asyncio
async def test_string_date_parsing(coordinator):
    """Test that string dates are parsed correctly."""
    now = datetime(2023, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
    with patch("homeassistant.util.dt.now", return_value=now):
        coordinator.tracked_data[PERIOD_DAILY] = {"max": None, "min": None, "last_reset": None}
        
        valid_reset_str = "2023-01-02T08:00:00+00:00"
        coordinator.update_restored_data(PERIOD_DAILY, "max", 30.0, last_reset=valid_reset_str)
        
        assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 30.0
        assert coordinator.tracked_data[PERIOD_DAILY]["last_reset"] == datetime(2023, 1, 2, 8, 0, 0, tzinfo=timezone.utc)

@pytest.mark.asyncio
async def test_update_restored_data_all_time(coordinator):
    """Test that ALL_TIME ignores staleness."""
    now = datetime(2023, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
    
    with patch("homeassistant.util.dt.now", return_value=now):
        coordinator.tracked_data[PERIOD_ALL_TIME] = {"max": 20.0, "min": 20.0, "last_reset": now}
        
        # Very old reset
        old_reset = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        
        # Should be accepted for ALL_TIME even if it's technically "before today" (though ALL_TIME has no period start really)
        # Wait, _get_period_start returns None for ALL_TIME?
        # Let's check logic: if period != PERIOD_ALL_TIME and period_start ...
        # So simply for ALL_TIME it skips the check.
        
        coordinator.update_restored_data(PERIOD_ALL_TIME, "max", 100.0, last_reset=old_reset)
        
        assert coordinator.tracked_data[PERIOD_ALL_TIME]["max"] == 100.0


@pytest.mark.asyncio
async def test_first_refresh_sets_last_reset(coordinator, hass):
    """Test that first refresh initializes last_reset if missing."""
    now = datetime(2023, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
    expected_start = datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    
    with patch("homeassistant.util.dt.now", return_value=now), \
         patch("custom_components.max_min.coordinator.async_track_state_change_event") as mock_track:
        
        # Mock schedule_resets to avoid implementation details
        coordinator._schedule_resets = Mock()
        
        # Ensure data is clean
        coordinator.tracked_data[PERIOD_DAILY] = {"max": None, "min": None}
        
        await coordinator.async_config_entry_first_refresh()
        
        assert coordinator.tracked_data[PERIOD_DAILY]["last_reset"] == expected_start

