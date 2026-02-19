"""Test coordinator."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from freezegun import freeze_time

from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_PERIODS,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    PERIOD_DAILY,
    PERIOD_MONTHLY,
    PERIOD_WEEKLY,
    PERIOD_YEARLY,
    PERIOD_ALL_TIME,
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
    entry.options = {}
    entry.entry_id = "test_entry"
    entry.title = "Test"
    return entry


@pytest.fixture
def hass():
    """Mock hass."""
    hass = Mock()
    hass.config.time_zone = timezone.utc
    hass.loop = Mock()
    hass.loop.time.return_value = 1000.0  # Mock current time
    hass.data = {"custom_components": {}}
    hass.states.get.return_value = Mock(state="10.0", attributes={"friendly_name": "Test Sensor"})
    return hass


@pytest.mark.asyncio
async def test_coordinator_initialization(hass, config_entry):
    """Test coordinator initialization."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.get_value(PERIOD_DAILY, TYPE_MAX) == 10.0
    assert coordinator.get_value(PERIOD_DAILY, TYPE_MIN) == 10.0


@pytest.mark.asyncio
async def test_coordinator_initialization_no_sensor(hass, config_entry):
    """Test coordinator initialization when sensor doesn't exist."""
    hass.states.get.return_value = None
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.get_value(PERIOD_DAILY, TYPE_MAX) is None
    assert coordinator.get_value(PERIOD_DAILY, TYPE_MIN) is None


@pytest.mark.asyncio
async def test_coordinator_initialization_unavailable_sensor(hass, config_entry):
    """Test coordinator initialization with unavailable sensor."""
    hass.states.get.return_value = Mock(state="unavailable")
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.get_value(PERIOD_DAILY, TYPE_MAX) is None
    assert coordinator.get_value(PERIOD_DAILY, TYPE_MIN) is None


@pytest.mark.asyncio
async def test_coordinator_initialization_invalid_value(hass, config_entry):
    """Test coordinator initialization with invalid sensor value."""
    hass.states.get.return_value = Mock(state="invalid")
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.get_value(PERIOD_DAILY, TYPE_MAX) is None
    assert coordinator.get_value(PERIOD_DAILY, TYPE_MIN) is None


@pytest.mark.asyncio
@freeze_time("2026-02-19 09:00:00")
async def test_first_refresh_forces_missed_reset_catchup(hass, config_entry):
    """First refresh should immediately force overdue resets."""
    hass.states.get.return_value = Mock(state="unavailable", attributes={})

    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 2.7,
        "min": 0.0,
        "start": 0.0,
        "end": 0.0,
        "last_reset": datetime(2026, 2, 18, 0, 0, 0, tzinfo=timezone.utc),
    }

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"), \
         patch.object(coordinator, "_handle_reset") as mock_reset:
        await coordinator.async_config_entry_first_refresh()

    mock_reset.assert_called_once()
    args, kwargs = mock_reset.call_args
    assert args[1] == PERIOD_DAILY
    assert kwargs["reason"] == "watchdog"


@pytest.mark.asyncio
async def test_sensor_change_updates_values(hass, config_entry):
    """Test sensor change updates max/min."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    # Simulate sensor increase
    event = Mock()
    event.data = {"new_state": Mock(state="15.0")}
    coordinator._handle_sensor_change(event)
    assert coordinator.get_value(PERIOD_DAILY, TYPE_MAX) == 15.0
    assert coordinator.get_value(PERIOD_DAILY, TYPE_MIN) == 10.0

    # Simulate sensor decrease
    event.data = {"new_state": Mock(state="5.0")}
    coordinator._handle_sensor_change(event)
    assert coordinator.get_value(PERIOD_DAILY, TYPE_MAX) == 15.0
    assert coordinator.get_value(PERIOD_DAILY, TYPE_MIN) == 5.0


@pytest.mark.asyncio
@freeze_time("2023-01-01 12:00:00")
async def test_daily_reset(hass, config_entry):
    """Test daily reset."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    # Change values
    coordinator.tracked_data[PERIOD_DAILY][TYPE_MAX] = 20.0
    coordinator.tracked_data[PERIOD_DAILY][TYPE_MIN] = 5.0

    # Simulate reset at midnight
    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
        coordinator._schedule_resets()
        # Call the reset handler
        coordinator._handle_reset(datetime(2023, 1, 2, 0, 0, 0), PERIOD_DAILY)
        assert coordinator.get_value(PERIOD_DAILY, TYPE_MAX) == 10.0  # Reset to current
        assert coordinator.get_value(PERIOD_DAILY, TYPE_MIN) == 10.0


@pytest.mark.asyncio
@freeze_time("2023-01-01 12:00:00")  # Sunday
async def test_weekly_reset(hass, config_entry):
    """Test weekly reset."""
    config_entry.data[CONF_PERIODS] = [PERIOD_WEEKLY]
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    coordinator.tracked_data[PERIOD_WEEKLY][TYPE_MAX] = 20.0
    coordinator.tracked_data[PERIOD_WEEKLY][TYPE_MIN] = 5.0

    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
        coordinator._schedule_resets()
        # Reset should be next Monday
        coordinator._handle_reset(datetime(2023, 1, 2, 0, 0, 0), PERIOD_WEEKLY)
        assert coordinator.get_value(PERIOD_WEEKLY, TYPE_MAX) == 10.0
        assert coordinator.get_value(PERIOD_WEEKLY, TYPE_MIN) == 10.0


@pytest.mark.asyncio
@freeze_time("2023-01-15 12:00:00")
async def test_monthly_reset(hass, config_entry):
    """Test monthly reset."""
    config_entry.data[CONF_PERIODS] = [PERIOD_MONTHLY]
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    coordinator.tracked_data[PERIOD_MONTHLY][TYPE_MAX] = 20.0
    coordinator.tracked_data[PERIOD_MONTHLY][TYPE_MIN] = 5.0

    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
        coordinator._schedule_resets()
        # Reset should be Feb 1
        coordinator._handle_reset(datetime(2023, 2, 1, 0, 0, 0), PERIOD_MONTHLY)
        assert coordinator.get_value(PERIOD_MONTHLY, TYPE_MAX) == 10.0
        assert coordinator.get_value(PERIOD_MONTHLY, TYPE_MIN) == 10.0


@pytest.mark.asyncio
@freeze_time("2023-06-15 12:00:00")
async def test_yearly_reset(hass, config_entry):
    """Test yearly reset."""
    config_entry.data[CONF_PERIODS] = [PERIOD_YEARLY]
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    coordinator.tracked_data[PERIOD_YEARLY][TYPE_MAX] = 20.0
    coordinator.tracked_data[PERIOD_YEARLY][TYPE_MIN] = 5.0

    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
        coordinator._schedule_resets()
        # Reset should be Jan 1 next year
        coordinator._handle_reset(datetime(2024, 1, 1, 0, 0, 0), PERIOD_YEARLY)
        assert coordinator.get_value(PERIOD_YEARLY, TYPE_MAX) == 10.0
        assert coordinator.get_value(PERIOD_YEARLY, TYPE_MIN) == 10.0


@pytest.mark.asyncio
async def test_all_time_no_reset(hass, config_entry):
    """Test all time period (no reset)."""
    config_entry.data[CONF_PERIODS] = [PERIOD_ALL_TIME]
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    coordinator.tracked_data[PERIOD_ALL_TIME][TYPE_MAX] = 20.0
    coordinator.tracked_data[PERIOD_ALL_TIME][TYPE_MIN] = 5.0

    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
        coordinator._schedule_resets()
        mock_track.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_sensor_value_update(hass, config_entry):
    """Test invalid sensor value update."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    event = Mock()
    event.data = {"new_state": Mock(state="invalid")}
    coordinator._handle_sensor_change(event)
    # Values should remain unchanged
    assert coordinator.get_value(PERIOD_DAILY, TYPE_MAX) == 10.0
    assert coordinator.get_value(PERIOD_DAILY, TYPE_MIN) == 10.0


@pytest.mark.asyncio
async def test_reset_with_no_current_value(hass, config_entry):
    """Test reset when sensor has no current value."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    # Set values
    coordinator.tracked_data[PERIOD_DAILY][TYPE_MAX] = 20.0
    coordinator.tracked_data[PERIOD_DAILY][TYPE_MIN] = 5.0

    # Mock sensor unavailable during reset
    hass.states.get.return_value = Mock(state="unavailable")

    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
        coordinator._handle_reset(datetime(2023, 1, 2, 0, 0, 0), PERIOD_DAILY)
        # Falls back to last known end value from previous period
        assert coordinator.get_value(PERIOD_DAILY, TYPE_MAX) == 10.0
        assert coordinator.get_value(PERIOD_DAILY, TYPE_MIN) == 10.0


@pytest.mark.asyncio
async def test_weekly_reset_scheduling(hass, config_entry):
    """Test weekly reset scheduling."""
    config_entry.data[CONF_PERIODS] = [PERIOD_WEEKLY]

    # Test on a specific date: Monday 2023-01-02
    with freeze_time("2023-01-02 12:00:00"):
        coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator.async_config_entry_first_refresh()

        with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
            coordinator._schedule_resets()

            assert mock_track.call_count == 2
            primary_call = mock_track.call_args_list[0][0]
            reset_time = primary_call[2]

            # Expect reset next Monday: 2023-01-09 00:00:00
            assert reset_time == datetime(2023, 1, 9, 0, 0, 0).replace(tzinfo=timezone.utc)
        
        # Verify call to _handle_reset matches signature
        callback = mock_track.call_args_list[0][0][1]
        # Simulate firing callback
        with patch.object(coordinator, '_handle_reset') as mock_handle_reset:
            callback(datetime.now())
            mock_handle_reset.assert_called_once()
            assert mock_handle_reset.call_args[0][1] == PERIOD_WEEKLY


@pytest.mark.asyncio
async def test_coordinator_with_options(hass, config_entry):
    """Test coordinator with options."""
    config_entry.options = {
        CONF_PERIODS: [PERIOD_WEEKLY],
        CONF_TYPES: ["max"]
    }
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    
    assert coordinator.periods == [PERIOD_WEEKLY]
    assert coordinator.types == ["max"]


@pytest.mark.asyncio
async def test_reset_rescheduling_all_periods(hass, config_entry):
    """Test that handle_reset schedules the next reset."""
    for period in [PERIOD_DAILY, PERIOD_WEEKLY, PERIOD_MONTHLY, PERIOD_YEARLY]:
        config_entry.data[CONF_PERIODS] = [period]
        coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator.async_config_entry_first_refresh()

        # Mock current time
        with freeze_time("2023-01-15 12:00:00"), \
             patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
            
            # Call handle_reset directly
            coordinator._handle_reset(datetime.now(), period)
            
            # Verify it scheduled next reset
            assert mock_track.called
            args = mock_track.call_args[0]
            scheduled_time = args[2]
            
            if period == PERIOD_DAILY:
                # Should be Jan 16
                assert scheduled_time.day == 16
            elif period == PERIOD_WEEKLY:
                # Jan 15 is Sunday. Next reset Monday Jan 16.
                assert scheduled_time.day == 16
            elif period == PERIOD_MONTHLY:
                # Feb 1
                assert scheduled_time.month == 2
                assert scheduled_time.day == 1
            elif period == PERIOD_YEARLY:
                # Jan 1 2024
                assert scheduled_time.year == 2024
                assert scheduled_time.day == 1

@pytest.mark.asyncio
async def test_reset_rescheduling_edge_cases(hass, config_entry):
    """Test edge cases for rescheduling."""
    
    # 1. Weekly reset when today is reset day (should schedule next week)
    # 2. Monthly reset in December (should schedule next year)
    
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    
    # December monthly reset
    with freeze_time("2023-12-15 12:00:00"), \
         patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
         
        coordinator._handle_reset(datetime.now(), PERIOD_MONTHLY)
        args = mock_track.call_args[0]
        reset_time = args[2]
        assert reset_time.year == 2024
        assert reset_time.month == 1
        assert reset_time.day == 1

@pytest.mark.asyncio
async def test_coordinator_per_period_initial_values(hass, config_entry):
    """Test coordinator respects per-period initial values."""
    config_entry.options = {
        CONF_PERIODS: [PERIOD_DAILY, PERIOD_WEEKLY],
        "daily_initial_max": 20.0,
        "daily_initial_min": 5.0,
        "weekly_initial_max": 30.0,
        "weekly_initial_min": 0.0,
    }
    
    # Set global values in data (legacy fallback test)
    # The coordinator logic: specific > global
    config_entry.data["initial_max"] = 100.0
    config_entry.data["initial_min"] = -100.0

    # Ensure no current state updates overwrite initial values
    hass.states.get.return_value = None 
    
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.get_value(PERIOD_DAILY, TYPE_MAX) == 20.0
    assert coordinator.get_value(PERIOD_DAILY, TYPE_MIN) == 5.0
    assert coordinator.get_value(PERIOD_WEEKLY, TYPE_MAX) == 30.0
    assert coordinator.get_value(PERIOD_WEEKLY, TYPE_MIN) == 0.0
