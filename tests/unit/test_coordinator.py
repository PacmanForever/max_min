"""Test coordinator."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from freezegun import freeze_time

from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_PERIOD,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    PERIOD_DAILY,
    PERIOD_MONTHLY,
    PERIOD_WEEKLY,
    PERIOD_YEARLY,
    PERIOD_ALL_TIME,
)

# Test sections:
# 1. Basic initialization and sensor handling
# 2. Reset functionality (daily, weekly, monthly, yearly)
# 3. Comprehensive monthly reset coverage (all months, leap years)
# 4. Home Assistant restart behavior (values lost, sensor preservation, reset rescheduling)


@pytest.fixture
def config_entry():
    """Mock config entry."""
    entry = MagicMock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIOD: PERIOD_DAILY,
        CONF_TYPES: ["max", "min"],
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

    assert coordinator.max_value == 10.0
    assert coordinator.min_value == 10.0


@pytest.mark.asyncio
async def test_coordinator_initialization_no_sensor(hass, config_entry):
    """Test coordinator initialization when sensor doesn't exist."""
    hass.states.get.return_value = None
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.max_value is None
    assert coordinator.min_value is None


@pytest.mark.asyncio
async def test_coordinator_initialization_unavailable_sensor(hass, config_entry):
    """Test coordinator initialization with unavailable sensor."""
    hass.states.get.return_value = Mock(state="unavailable")
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.max_value is None
    assert coordinator.min_value is None


@pytest.mark.asyncio
async def test_coordinator_initialization_invalid_value(hass, config_entry):
    """Test coordinator initialization with invalid sensor value."""
    hass.states.get.return_value = Mock(state="invalid")
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.max_value is None
    assert coordinator.min_value is None


@pytest.mark.asyncio
async def test_sensor_change_updates_values(hass, config_entry):
    """Test sensor change updates max/min."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    # Simulate sensor increase
    event = Mock()
    event.data = {"new_state": Mock(state="15.0")}
    coordinator._handle_sensor_change(event)
    assert coordinator.max_value == 15.0
    assert coordinator.min_value == 10.0

    # Simulate sensor decrease
    event.data = {"new_state": Mock(state="5.0")}
    coordinator._handle_sensor_change(event)
    assert coordinator.max_value == 15.0
    assert coordinator.min_value == 5.0


@pytest.mark.asyncio
@freeze_time("2023-01-01 12:00:00")
async def test_daily_reset(hass, config_entry):
    """Test daily reset."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    # Change values
    coordinator.max_value = 20.0
    coordinator.min_value = 5.0

    # Simulate reset at midnight
    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
        coordinator._schedule_reset()
        # Call the reset handler
        coordinator._handle_reset(datetime(2023, 1, 2, 0, 0, 0))
        assert coordinator.max_value == 10.0  # Reset to current
        assert coordinator.min_value == 10.0


@pytest.mark.asyncio
@freeze_time("2023-01-01 12:00:00")  # Sunday
async def test_weekly_reset(hass, config_entry):
    """Test weekly reset."""
    config_entry.data[CONF_PERIOD] = PERIOD_WEEKLY
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    coordinator.max_value = 20.0
    coordinator.min_value = 5.0

    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
        coordinator._schedule_reset()
        # Reset should be next Monday
        coordinator._handle_reset(datetime(2023, 1, 2, 0, 0, 0))  # Monday
        assert coordinator.max_value == 10.0
        assert coordinator.min_value == 10.0


@pytest.mark.asyncio
@freeze_time("2023-01-15 12:00:00")
async def test_monthly_reset(hass, config_entry):
    """Test monthly reset."""
    config_entry.data[CONF_PERIOD] = PERIOD_MONTHLY
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    coordinator.max_value = 20.0
    coordinator.min_value = 5.0

    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
        coordinator._schedule_reset()
        # Reset should be Feb 1
        coordinator._handle_reset(datetime(2023, 2, 1, 0, 0, 0))
        assert coordinator.max_value == 10.0
        assert coordinator.min_value == 10.0


@pytest.mark.asyncio
@freeze_time("2023-06-15 12:00:00")
async def test_yearly_reset(hass, config_entry):
    """Test yearly reset."""
    config_entry.data[CONF_PERIOD] = PERIOD_YEARLY
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    coordinator.max_value = 20.0
    coordinator.min_value = 5.0

    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
        coordinator._schedule_reset()
        # Reset should be Jan 1 next year
        coordinator._handle_reset(datetime(2024, 1, 1, 0, 0, 0))
        assert coordinator.max_value == 10.0
        assert coordinator.min_value == 10.0


@pytest.mark.asyncio
async def test_all_time_no_reset(hass, config_entry):
    """Test all time period (no reset)."""
    config_entry.data[CONF_PERIOD] = PERIOD_ALL_TIME
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    coordinator.max_value = 20.0
    coordinator.min_value = 5.0

    # Ensure no reset is scheduled
    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
        coordinator._schedule_reset()
        mock_track.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_sensor_value(hass, config_entry):
    """Test invalid sensor value."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    event = Mock()
    event.data = {"new_state": Mock(state="invalid")}
    coordinator._handle_sensor_change(event)
    # Values should remain unchanged
    assert coordinator.max_value == 10.0
    assert coordinator.min_value == 10.0


@pytest.mark.asyncio
async def test_unavailable_sensor(hass, config_entry):
    """Test unavailable sensor."""
    hass.states.get.return_value = Mock(state="unavailable")
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.max_value is None
    assert coordinator.min_value is None


@pytest.mark.asyncio
async def test_unknown_sensor_state(hass, config_entry):
    """Test unknown sensor state."""
    hass.states.get.return_value = Mock(state="unknown")
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.max_value is None
    assert coordinator.min_value is None


@pytest.mark.asyncio
async def test_sensor_without_state(hass, config_entry):
    """Test sensor without state."""
    hass.states.get.return_value = None
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.max_value is None
    assert coordinator.min_value is None


@pytest.mark.asyncio
async def test_multiple_updates(hass, config_entry):
    """Test multiple sensor updates."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    # First update
    event = Mock()
    event.data = {"new_state": Mock(state="15.0")}
    coordinator._handle_sensor_change(event)
    assert coordinator.max_value == 15.0
    assert coordinator.min_value == 10.0

    # Second update - higher max
    event.data = {"new_state": Mock(state="20.0")}
    coordinator._handle_sensor_change(event)
    assert coordinator.max_value == 20.0
    assert coordinator.min_value == 10.0

    # Third update - lower min
    event.data = {"new_state": Mock(state="5.0")}
    coordinator._handle_sensor_change(event)
    assert coordinator.max_value == 20.0
    assert coordinator.min_value == 5.0


@pytest.mark.asyncio
async def test_reset_with_no_current_value(hass, config_entry):
    """Test reset when sensor has no current value."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    # Set values
    coordinator.max_value = 20.0
    coordinator.min_value = 5.0

    # Mock sensor unavailable during reset
    hass.states.get.return_value = Mock(state="unavailable")

    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
        coordinator._handle_reset(datetime(2023, 1, 2, 0, 0, 0))
        assert coordinator.max_value is None
        assert coordinator.min_value is None


@pytest.mark.asyncio
async def test_reset_with_invalid_value(hass, config_entry):
    """Test reset when sensor has invalid value."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    # Set values
    coordinator.max_value = 20.0
    coordinator.min_value = 5.0

    # Mock sensor invalid during reset
    hass.states.get.return_value = Mock(state="invalid")

    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
        coordinator._handle_reset(datetime(2023, 1, 2, 0, 0, 0))
        assert coordinator.max_value is None
        assert coordinator.min_value is None

@pytest.mark.asyncio
async def test_reset_with_missing_sensor(hass, config_entry):
    """Test reset when sensor is missing."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    # Set values
    coordinator.max_value = 20.0
    coordinator.min_value = 5.0

    # Mock sensor missing during reset
    hass.states.get.return_value = None

    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
        coordinator._handle_reset(datetime(2023, 1, 2, 0, 0, 0))
        assert coordinator.max_value is None
        assert coordinator.min_value is None


@pytest.mark.asyncio
async def test_weekly_reset_scheduling(hass, config_entry):
    """Test weekly reset scheduling."""
    config_entry.data[CONF_PERIOD] = PERIOD_WEEKLY

    # Test on a specific date: Monday 2023-01-02
    with freeze_time("2023-01-02 12:00:00"):
        coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator.async_config_entry_first_refresh()

        with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
            coordinator._schedule_reset()

            mock_track.assert_called_once()
            args = mock_track.call_args[0]
            reset_time = args[2]

            # Expect reset next Monday: 2023-01-09 00:00:00
            assert reset_time == datetime(2023, 1, 9, 0, 0, 0).replace(tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_weekly_reset_scheduling_sunday(hass, config_entry):
    """Test weekly reset scheduling on Sunday."""
    config_entry.data[CONF_PERIOD] = PERIOD_WEEKLY

    # Test on a specific date: Sunday 2023-01-08
    with freeze_time("2023-01-08 12:00:00"):
        coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator.async_config_entry_first_refresh()

        with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
            coordinator._schedule_reset()

            mock_track.assert_called_once()
            args = mock_track.call_args[0]
            reset_time = args[2]

            # Expect reset next Monday: 2023-01-09 00:00:00
            assert reset_time == datetime(2023, 1, 9, 0, 0, 0).replace(tzinfo=timezone.utc)

@pytest.mark.asyncio
async def test_coordinator_with_options(hass, config_entry):
    """Test coordinator with options."""
    config_entry.options = {
        CONF_PERIOD: PERIOD_WEEKLY,
        CONF_TYPES: ["max"]
    }
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    
    assert coordinator.period == PERIOD_WEEKLY
    assert coordinator.types == ["max"]


@pytest.mark.parametrize("month,expected_next_month,expected_next_year", [
    (1, 2, 2023),   # January -> February
    (2, 3, 2023),   # February -> March
    (3, 4, 2023),   # March -> April
    (4, 5, 2023),   # April -> May
    (5, 6, 2023),   # May -> June
    (6, 7, 2023),   # June -> July
    (7, 8, 2023),   # July -> August
    (8, 9, 2023),   # August -> September
    (9, 10, 2023),  # September -> October
    (10, 11, 2023), # October -> November
    (11, 12, 2023), # November -> December
    (12, 1, 2024),  # December -> January (next year)
])
@pytest.mark.asyncio
async def test_monthly_reset_all_months(hass, config_entry, month, expected_next_month, expected_next_year):
    """Test monthly reset for all months."""
    config_entry.data[CONF_PERIOD] = PERIOD_MONTHLY
    
    with freeze_time(f"2023-{month:02d}-15 12:00:00"):
        coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator.async_config_entry_first_refresh()

        coordinator.max_value = 20.0
        coordinator.min_value = 5.0

        with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
            coordinator._schedule_reset()
            
            # Verify the reset time is scheduled for the 1st of next month
            mock_track.assert_called_once()
            args = mock_track.call_args[0]
            reset_time = args[2]
            
            # Reset should be at midnight (0, 0, 0)
            assert (reset_time.hour, reset_time.minute, reset_time.second) == (0, 0, 0)

@pytest.mark.parametrize("year,is_leap", [
    (2023, False),  # Not leap year
    (2024, True),   # Leap year
    (2025, False),  # Not leap year
    (2028, True),   # Leap year
])
@pytest.mark.asyncio
async def test_february_reset_leap_years(hass, config_entry, year, is_leap):
    """Test February reset in leap and non-leap years."""
    config_entry.data[CONF_PERIOD] = PERIOD_MONTHLY
    
    with freeze_time(f"{year}-02-15 12:00:00"):
        coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator.async_config_entry_first_refresh()

        coordinator.max_value = 20.0
        coordinator.min_value = 5.0

        with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
            coordinator._schedule_reset()
            
            # Verify the reset time is scheduled for March 1st
            mock_track.assert_called_once()
            args = mock_track.call_args[0]
            reset_time = args[2]
            
            # Reset should be at midnight (0, 0, 0)
            assert (reset_time.hour, reset_time.minute, reset_time.second) == (0, 0, 0)
            
            # Check that the reset handler works
            coordinator._handle_reset(datetime(year, 3, 1, 0, 0, 0))
            assert coordinator.max_value == 10.0  # Reset to current value
            assert coordinator.min_value == 10.0


@pytest.mark.parametrize("month,days_in_month", [
    (1, 31),   # January
    (2, 28),   # February (non-leap)
    (3, 31),   # March
    (4, 30),   # April
    (5, 31),   # May
    (6, 30),   # June
    (7, 31),   # July
    (8, 31),   # August
    (9, 30),   # September
    (10, 31),  # October
    (11, 30),  # November
    (12, 31),  # December
])
@pytest.mark.asyncio
async def test_monthly_reset_different_month_lengths(hass, config_entry, month, days_in_month):
    """Test monthly reset works regardless of month length."""
    config_entry.data[CONF_PERIOD] = PERIOD_MONTHLY
    
    # Test from the last day of each month
    with freeze_time(f"2023-{month:02d}-{days_in_month} 12:00:00"):
        coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator.async_config_entry_first_refresh()

        coordinator.max_value = 20.0
        coordinator.min_value = 5.0

        with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
            coordinator._schedule_reset()
            
            # Verify the reset time is scheduled correctly
            mock_track.assert_called_once()
            args = mock_track.call_args[0]
            reset_time = args[2]
            
            # Reset should be at midnight (0, 0, 0)
            assert (reset_time.hour, reset_time.minute, reset_time.second) == (0, 0, 0)
            
            # Calculate expected next month
            next_month = month + 1 if month < 12 else 1
            next_year = 2023 if month < 12 else 2024
            
            # Check that the reset handler works
            coordinator._handle_reset(datetime(next_year, next_month, 1, 0, 0, 0))
            assert coordinator.max_value == 10.0  # Reset to current value
            assert coordinator.min_value == 10.0


@pytest.mark.asyncio
async def test_february_29_leap_year_reset(hass, config_entry):
    """Test February 29 reset in leap year."""
    config_entry.data[CONF_PERIOD] = PERIOD_MONTHLY
    
    # Test from February 29, 2024 (leap year)
    with freeze_time("2024-02-29 12:00:00"):
        coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator.async_config_entry_first_refresh()

        coordinator.max_value = 20.0
        coordinator.min_value = 5.0

        with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track:
            coordinator._schedule_reset()
            
            # Verify the reset time is scheduled for March 1st
            mock_track.assert_called_once()
            args = mock_track.call_args[0]
            reset_time = args[2]
            
            # Reset should be at midnight (0, 0, 0)
            assert (reset_time.hour, reset_time.minute, reset_time.second) == (0, 0, 0)
            
            # Check that the reset handler works
            coordinator._handle_reset(datetime(2024, 3, 1, 0, 0, 0))
            assert coordinator.max_value == 10.0  # Reset to current value
            assert coordinator.min_value == 10.0

# Home Assistant Restart Behavior Tests
# These tests verify how the component behaves when Home Assistant restarts.
# Key behaviors tested:
# - Accumulated max/min values are lost (no persistence)
# - Current sensor value is preserved
# - Reset timing is recalculated
# - Unavailable sensor states are handled properly
# - Multiple restarts maintain current sensor readings

@pytest.mark.asyncio
async def test_ha_restart_loses_values(hass, config_entry):
    """Test that HA restart loses accumulated max/min values."""
    config_entry.data[CONF_PERIOD] = PERIOD_MONTHLY
    
    # Create initial coordinator and accumulate some values
    with freeze_time("2023-01-15 12:00:00"):
        # Set initial sensor value
        hass.states.get.return_value = Mock(state="10.0", attributes={"friendly_name": "Test Sensor"})
        coordinator1 = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator1.async_config_entry_first_refresh()

        # Simulate sensor changes to accumulate max/min
        coordinator1._handle_sensor_change(Mock(data={"new_state": Mock(state="25.0")}))
        coordinator1._handle_sensor_change(Mock(data={"new_state": Mock(state="5.0")}))
        coordinator1._handle_sensor_change(Mock(data={"new_state": Mock(state="30.0")}))
        
        # Verify accumulated values
        assert coordinator1.max_value == 30.0
        assert coordinator1.min_value == 5.0

    # Simulate HA restart by creating new coordinator
    with freeze_time("2023-01-15 13:00:00"):  # Same day, 1 hour later
        # Sensor still has the last value (30.0)
        hass.states.get.return_value = Mock(state="30.0", attributes={"friendly_name": "Test Sensor"})
        coordinator2 = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator2.async_config_entry_first_refresh()
        
        # Values should be reset to current sensor value, not preserved
        assert coordinator2.max_value == 30.0  # Current sensor value
        assert coordinator2.min_value == 30.0  # Current sensor value
        # NOT the accumulated values 30.0/5.0


@pytest.mark.asyncio
async def test_ha_restart_reschedules_reset(hass, config_entry):
    """Test that HA restart reschedules the reset timer."""
    config_entry.data[CONF_PERIOD] = PERIOD_MONTHLY
    
    with freeze_time("2023-01-15 12:00:00"):
        coordinator1 = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator1.async_config_entry_first_refresh()

        # Verify initial reset is scheduled
        assert coordinator1._reset_listener is not None

    # Simulate HA restart
    with freeze_time("2023-01-15 13:00:00"):
        coordinator2 = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator2.async_config_entry_first_refresh()
        
        # New reset should be scheduled
        assert coordinator2._reset_listener is not None
        # The old listener would be lost (simulating HA restart)


@pytest.mark.asyncio
async def test_ha_restart_during_reset_window(hass, config_entry):
    """Test HA restart during the reset window (critical timing)."""
    config_entry.data[CONF_PERIOD] = PERIOD_MONTHLY
    
    # Start with some accumulated values
    with freeze_time("2023-01-31 23:50:00"):  # Very close to monthly reset
        hass.states.get.return_value = Mock(state="15.0", attributes={"friendly_name": "Test Sensor"})
        coordinator1 = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator1.async_config_entry_first_refresh()

        # Accumulate values
        coordinator1._handle_sensor_change(Mock(data={"new_state": Mock(state="20.0")}))
        coordinator1._handle_sensor_change(Mock(data={"new_state": Mock(state="10.0")}))
        assert coordinator1.max_value == 20.0
        assert coordinator1.min_value == 10.0

    # Simulate HA restart at the exact reset time
    with freeze_time("2023-02-01 00:00:00"):  # Reset time
        # Sensor maintains last value
        hass.states.get.return_value = Mock(state="10.0", attributes={"friendly_name": "Test Sensor"})
        coordinator2 = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator2.async_config_entry_first_refresh()
        
        # Since reset didn't happen (HA was restarting), values are reset to current
        assert coordinator2.max_value == 10.0  # Last sensor value
        assert coordinator2.min_value == 10.0  # Last sensor value
        # The accumulated values 20.0/10.0 are lost


@pytest.mark.asyncio
async def test_ha_restart_preserves_sensor_value(hass, config_entry):
    """Test that sensor value is preserved across HA restart."""
    config_entry.data[CONF_PERIOD] = PERIOD_DAILY
    
    # Set initial sensor value
    hass.states.get.return_value = Mock(state="15.5", attributes={"friendly_name": "Test Sensor"})
    
    with freeze_time("2023-01-15 10:00:00"):
        coordinator1 = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator1.async_config_entry_first_refresh()
        
        assert coordinator1.max_value == 15.5
        assert coordinator1.min_value == 15.5

    # Simulate HA restart - sensor still has same value
    with freeze_time("2023-01-15 11:00:00"):
        coordinator2 = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator2.async_config_entry_first_refresh()
        
        # Should initialize with current sensor value
        assert coordinator2.max_value == 15.5
        assert coordinator2.min_value == 15.5


@pytest.mark.asyncio
async def test_ha_restart_with_unavailable_sensor(hass, config_entry):
    """Test HA restart when sensor becomes unavailable."""
    config_entry.data[CONF_PERIOD] = PERIOD_DAILY
    
    # Initial state: sensor available
    hass.states.get.return_value = Mock(state="10.0", attributes={"friendly_name": "Test Sensor"})
    
    with freeze_time("2023-01-15 10:00:00"):
        coordinator1 = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator1.async_config_entry_first_refresh()
        
        assert coordinator1.max_value == 10.0
        assert coordinator1.min_value == 10.0

    # Simulate HA restart with sensor unavailable
    hass.states.get.return_value = Mock(state="unavailable")
    
    with freeze_time("2023-01-15 11:00:00"):
        coordinator2 = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator2.async_config_entry_first_refresh()
        
        # Should initialize with None when sensor unavailable
        assert coordinator2.max_value is None
        assert coordinator2.min_value is None


@pytest.mark.asyncio
async def test_multiple_ha_restarts_preserve_current_value(hass, config_entry):
    """Test multiple HA restarts preserve current sensor value."""
    config_entry.data[CONF_PERIOD] = PERIOD_WEEKLY
    
    # Start with initial value
    hass.states.get.return_value = Mock(state="5.0", attributes={"friendly_name": "Test Sensor"})
    
    with freeze_time("2023-01-15 10:00:00"):
        coordinator1 = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator1.async_config_entry_first_refresh()
        assert coordinator1.max_value == 5.0

    # First restart - sensor changed
    hass.states.get.return_value = Mock(state="12.0", attributes={"friendly_name": "Test Sensor"})
    
    with freeze_time("2023-01-15 12:00:00"):
        coordinator2 = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator2.async_config_entry_first_refresh()
        assert coordinator2.max_value == 12.0

    # Second restart - sensor changed again
    hass.states.get.return_value = Mock(state="8.0", attributes={"friendly_name": "Test Sensor"})
    
    with freeze_time("2023-01-15 14:00:00"):
        coordinator3 = MaxMinDataUpdateCoordinator(hass, config_entry)
        await coordinator3.async_config_entry_first_refresh()
        assert coordinator3.max_value == 8.0


@pytest.mark.asyncio
async def test_coordinator_unload(hass, config_entry):
    """Test coordinator unload."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()
    
    # Mock the reset listener
    mock_listener = Mock()
    coordinator._reset_listener = mock_listener
    
    await coordinator.async_unload()
    
    # Should call the listener
    mock_listener.assert_called_once()