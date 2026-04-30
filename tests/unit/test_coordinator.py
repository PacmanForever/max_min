"""Test coordinator."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from freezegun import freeze_time
from conftest import make_config_entry

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
    """start_listeners should immediately force overdue resets after restore."""
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
         patch.object(coordinator, "_perform_reset") as mock_reset:
        await coordinator.async_config_entry_first_refresh()
        # Catch-up is deferred to start_listeners (after entity restore)
        mock_reset.assert_not_called()
        coordinator.start_listeners()

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
        coordinator._perform_reset(datetime(2023, 1, 2, 0, 0, 0), PERIOD_DAILY)
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
        coordinator._perform_reset(datetime(2023, 1, 2, 0, 0, 0), PERIOD_WEEKLY)
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
        coordinator._perform_reset(datetime(2023, 2, 1, 0, 0, 0), PERIOD_MONTHLY)
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
        coordinator._perform_reset(datetime(2024, 1, 1, 0, 0, 0), PERIOD_YEARLY)
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
        coordinator._perform_reset(datetime(2023, 1, 2, 0, 0, 0), PERIOD_DAILY)
        # With source unavailable, seed falls back to last end value (10.0 from first_refresh)
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
        
        # Verify scheduler callback calls ensure_period_current
        callback = mock_track.call_args_list[0][0][1]
        # Simulate firing callback
        with patch.object(coordinator, 'ensure_period_current') as mock_ensure:
            callback(datetime.now())
            mock_ensure.assert_called_once()
            assert mock_ensure.call_args[0][0] == PERIOD_WEEKLY


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
            coordinator._perform_reset(datetime.now(), period)
            
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
         
        coordinator._perform_reset(datetime.now(), PERIOD_MONTHLY)
        args = mock_track.call_args[0]
        reset_time = args[2]
        assert reset_time.year == 2024
        assert reset_time.month == 1
        assert reset_time.day == 1

@pytest.mark.asyncio
async def test_coordinator_per_period_initial_values(hass, config_entry):
    """Test coordinator respects per-period initial values (one-shot seeding)."""
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

    # Sensor reports 10.0 — between the per-period min/max initials
    hass.states.get.return_value = Mock(
        state="10.0", attributes={"friendly_name": "Test"}
    )
    
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    # first_refresh only uses sensor value (10.0)
    # No restore → apply_pending_initials applies per-period initials
    coordinator.apply_pending_initials()

    assert coordinator.get_value(PERIOD_DAILY, TYPE_MAX) == 20.0
    assert coordinator.get_value(PERIOD_DAILY, TYPE_MIN) == 5.0
    assert coordinator.get_value(PERIOD_WEEKLY, TYPE_MAX) == 30.0
    assert coordinator.get_value(PERIOD_WEEKLY, TYPE_MIN) == 0.0


def test_init_periods_as_string(hass):
    """Periods configured as a plain string are coerced to a one-item list."""
    entry = make_config_entry(periods=PERIOD_DAILY)
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    assert coordinator.periods == [PERIOD_DAILY]


def test_init_invalid_initial_max_ignored(hass):
    """Invalid configured initial max values are ignored safely."""
    entry = make_config_entry(daily_initial_max="not_a_number")
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    assert coordinator._configured_initials[PERIOD_DAILY]["max"] is None


def test_init_invalid_initial_delta_ignored(hass):
    """Invalid configured initial delta values are ignored safely."""
    entry = make_config_entry(daily_initial_delta="invalid")
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    assert coordinator._configured_initials[PERIOD_DAILY]["delta"] is None


def test_compute_next_reset_daily():
    """_compute_next_reset returns next midnight for daily."""
    now = datetime(2026, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
    result = MaxMinDataUpdateCoordinator._compute_next_reset(now, PERIOD_DAILY)
    assert result == datetime(2026, 6, 16, 0, 0, 0, tzinfo=timezone.utc)


def test_compute_next_reset_monthly_non_december():
    """_compute_next_reset returns 1st of next month for non-December."""
    now = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    result = MaxMinDataUpdateCoordinator._compute_next_reset(now, PERIOD_MONTHLY)
    assert result == datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_compute_next_reset_monthly_december():
    """_compute_next_reset wraps to January for December."""
    now = datetime(2026, 12, 15, 10, 0, 0, tzinfo=timezone.utc)
    result = MaxMinDataUpdateCoordinator._compute_next_reset(now, PERIOD_MONTHLY)
    assert result == datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_compute_next_reset_unknown_period():
    """_compute_next_reset returns None for unknown period."""
    now = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
    assert MaxMinDataUpdateCoordinator._compute_next_reset(now, "unknown") is None


def test_get_value_unknown_period(hass):
    """get_value returns None for a period not in tracked_data."""
    coordinator = MaxMinDataUpdateCoordinator(hass, make_config_entry())
    assert coordinator.get_value("nonexistent_period", "max") is None


def test_get_period_start_unknown_period(hass):
    """_get_period_start returns None for an unrecognised period string."""
    coordinator = MaxMinDataUpdateCoordinator(hass, make_config_entry())
    now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
    assert coordinator._get_period_start(now, "custom_period") is None


def test_handle_sensor_change_creates_missing_period(hass):
    """A sensor change for a period not in tracked_data creates it."""
    entry = make_config_entry(periods=[PERIOD_DAILY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)

    coordinator.tracked_data.pop(PERIOD_DAILY, None)
    coordinator._next_resets = {}

    event = Mock()
    event.data = {"new_state": Mock(state="5.0", attributes={})}

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_sensor_change(event)

    assert PERIOD_DAILY in coordinator.tracked_data
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 5.0
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 5.0


def test_perform_reset_reschedule_monthly_december(hass):
    """_perform_reset reschedules monthly correctly in December (-> Jan next year)."""
    entry = make_config_entry(periods=[PERIOD_MONTHLY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_MONTHLY] = {
        "max": 20.0, "min": 5.0, "start": 5.0, "end": 20.0, "last_reset": None,
    }
    coordinator._next_resets = {}
    coordinator._reset_listeners = {}

    dec_now = datetime(2026, 12, 31, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track, \
         patch("custom_components.max_min.coordinator.dt_util.now", return_value=dec_now):
        coordinator._perform_reset(dec_now, PERIOD_MONTHLY)

    assert PERIOD_MONTHLY in coordinator._next_resets
    nr = coordinator._next_resets[PERIOD_MONTHLY]
    assert nr.year == 2027 and nr.month == 1 and nr.day == 1
    mock_track.assert_called()


def test_perform_reset_reschedule_monthly_non_december(hass):
    """_perform_reset reschedules monthly correctly outside December."""
    entry = make_config_entry(periods=[PERIOD_MONTHLY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_MONTHLY] = {
        "max": 20.0, "min": 5.0, "start": 5.0, "end": 20.0, "last_reset": None,
    }
    coordinator._next_resets = {}
    coordinator._reset_listeners = {}

    jun_now = datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"), \
         patch("custom_components.max_min.coordinator.dt_util.now", return_value=jun_now):
        coordinator._perform_reset(jun_now, PERIOD_MONTHLY)

    nr = coordinator._next_resets[PERIOD_MONTHLY]
    assert nr.month == 7 and nr.day == 1


def test_perform_reset_reschedule_yearly(hass):
    """_perform_reset reschedules yearly correctly."""
    entry = make_config_entry(periods=[PERIOD_YEARLY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_YEARLY] = {
        "max": 20.0, "min": 5.0, "start": 5.0, "end": 20.0, "last_reset": None,
    }
    coordinator._next_resets = {}
    coordinator._reset_listeners = {}

    feb_now = datetime(2026, 2, 8, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track, \
         patch("custom_components.max_min.coordinator.dt_util.now", return_value=feb_now):
        coordinator._perform_reset(feb_now, PERIOD_YEARLY)

    nr = coordinator._next_resets[PERIOD_YEARLY]
    assert nr.year == 2027 and nr.month == 1 and nr.day == 1
    mock_track.assert_called()


def test_update_restored_data_unknown_period(hass):
    """update_restored_data creates tracked_data for a period not yet present."""
    entry = make_config_entry(periods=[PERIOD_DAILY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)

    assert PERIOD_WEEKLY not in coordinator.tracked_data

    coordinator.update_restored_data(PERIOD_WEEKLY, "max", 42.0)

    assert PERIOD_WEEKLY in coordinator.tracked_data
    assert coordinator.tracked_data[PERIOD_WEEKLY]["max"] == 42.0


def test_schedule_resets_yearly(hass):
    """_schedule_resets covers the yearly period branch."""
    entry = make_config_entry(periods=[PERIOD_YEARLY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_YEARLY] = {
        "max": 10.0, "min": 10.0, "start": 10.0, "end": 10.0, "last_reset": None,
    }

    feb_now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track, \
         patch("custom_components.max_min.coordinator.dt_util.now", return_value=feb_now):
        coordinator._schedule_resets()

    assert PERIOD_YEARLY in coordinator._next_resets
    nr = coordinator._next_resets[PERIOD_YEARLY]
    assert nr.year == 2027 and nr.month == 1 and nr.day == 1
    mock_track.assert_called()


def test_schedule_resets_monthly_december(hass):
    """_schedule_resets covers the monthly/December branch."""
    entry = make_config_entry(periods=[PERIOD_MONTHLY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_MONTHLY] = {
        "max": 10.0, "min": 10.0, "start": 10.0, "end": 10.0, "last_reset": None,
    }

    dec_now = datetime(2026, 12, 15, 12, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track, \
         patch("custom_components.max_min.coordinator.dt_util.now", return_value=dec_now):
        coordinator._schedule_resets()

    assert PERIOD_MONTHLY in coordinator._next_resets
    nr = coordinator._next_resets[PERIOD_MONTHLY]
    assert nr.year == 2027 and nr.month == 1 and nr.day == 1
    mock_track.assert_called()


def test_perform_reset_with_invalid_sensor_value(hass):
    """_perform_reset handles ValueError when sensor state is not a float."""
    entry = make_config_entry(periods=[PERIOD_DAILY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 20.0, "min": 5.0, "start": 5.0, "end": 20.0, "last_reset": None,
    }
    coordinator._next_resets = {}
    coordinator._reset_listeners = {}

    hass.states.get.return_value = Mock(
        state="not_a_number",
        attributes={"friendly_name": "Test"},
    )

    now = datetime(2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"), \
         patch("custom_components.max_min.coordinator.dt_util.now", return_value=now):
        coordinator._perform_reset(now, PERIOD_DAILY)

    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 20.0
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 20.0


def test_perform_reset_calls_set_updated_data(hass):
    """_perform_reset calls async_set_updated_data to notify entities."""
    entry = make_config_entry(periods=[PERIOD_DAILY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 20.0, "min": 5.0, "start": 5.0, "end": 20.0, "last_reset": None,
    }
    coordinator._next_resets = {}
    coordinator._reset_listeners = {}

    now = datetime(2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"), \
         patch("custom_components.max_min.coordinator.dt_util.now", return_value=now), \
         patch.object(coordinator, "async_set_updated_data") as mock_notify:
        coordinator._perform_reset(now, PERIOD_DAILY)

    mock_notify.assert_called_once_with({})


def test_perform_reset_reschedule_weekly_same_weekday(hass):
    """_perform_reset reschedules weekly when today is the reset day."""
    entry = make_config_entry(periods=[PERIOD_WEEKLY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_WEEKLY] = {
        "max": 20.0, "min": 5.0, "start": 5.0, "end": 20.0, "last_reset": None,
    }
    coordinator._next_resets = {}
    coordinator._reset_listeners = {}

    monday = datetime(2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track, \
         patch("custom_components.max_min.coordinator.dt_util.now", return_value=monday):
        coordinator._perform_reset(monday, PERIOD_WEEKLY)

    nr = coordinator._next_resets[PERIOD_WEEKLY]
    assert nr == datetime(2026, 2, 16, 0, 0, 0, tzinfo=timezone.utc)
    mock_track.assert_called()


def test_first_refresh_rounds_values():
    """Coordinator rounds noisy floats during live updates."""
    ha = Mock()
    entry = Mock()
    entry.entry_id = "test"
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX],
    }
    entry.options = {}

    ha.states.get.return_value = Mock(
        state="45.99999999999999",
        attributes={"friendly_name": "Test"},
    )

    coordinator = MaxMinDataUpdateCoordinator(ha, entry)

    event = Mock()
    event.data = {
        "new_state": Mock(
            state="45.99999999999999",
            attributes={"state_class": None},
        )
    }

    from homeassistant.util import dt as dt_util

    now = dt_util.now()
    coordinator.tracked_data[PERIOD_DAILY]["last_reset"] = now
    coordinator.tracked_data[PERIOD_DAILY]["max"] = 10.0

    coordinator._handle_sensor_change(event)

    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 46.0


def test_sensor_change_rounds_values():
    """_handle_sensor_change rounds values."""
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

    from homeassistant.util import dt as dt_util

    now = dt_util.now()
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 10.0,
        "min": 10.0,
        "start": 10.0,
        "end": 10.0,
        "last_reset": now,
    }

    event = Mock()
    event.data = {
        "new_state": Mock(
            state="46.00000000000001",
            attributes={"state_class": None},
        )
    }

    coordinator._handle_sensor_change(event)

    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 46.0


def test_initial_values_survive_first_refresh():
    """Configured initial values are applied for new entries with no restore."""
    ha = Mock()
    entry = Mock()
    entry.entry_id = "test"
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_YEARLY],
        CONF_TYPES: [TYPE_MAX],
    }
    entry.options = {f"{PERIOD_YEARLY}_initial_max": 45.0}

    ha.states.get.return_value = Mock(state="13.0", attributes={})

    coordinator = MaxMinDataUpdateCoordinator(ha, entry)

    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] is None

    coordinator.apply_pending_initials()
    assert coordinator.get_value(PERIOD_YEARLY, "max") == 45.0


def test_get_value_returns_tracked_data_for_max():
    """get_value returns tracked_data directly, not enforcing initials."""
    ha = Mock()
    ha.states.get.return_value = Mock(state="10.0", attributes={})

    entry = Mock()
    entry.entry_id = "test"
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_YEARLY],
        CONF_TYPES: [TYPE_MAX],
    }
    entry.options = {f"{PERIOD_YEARLY}_initial_max": 45.0}

    coordinator = MaxMinDataUpdateCoordinator(ha, entry)
    coordinator.tracked_data[PERIOD_YEARLY]["max"] = 13.0

    assert coordinator.get_value(PERIOD_YEARLY, "max") == 13.0


def test_get_value_returns_tracked_data_for_min():
    """get_value returns tracked_data directly, not enforcing initials."""
    ha = Mock()
    ha.states.get.return_value = Mock(state="10.0", attributes={})

    entry = Mock()
    entry.entry_id = "test"
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MIN],
    }
    entry.options = {f"{PERIOD_DAILY}_initial_min": 5.0}

    coordinator = MaxMinDataUpdateCoordinator(ha, entry)
    coordinator.tracked_data[PERIOD_DAILY]["min"] = 20.0

    assert coordinator.get_value(PERIOD_DAILY, "min") == 20.0


@pytest.mark.asyncio
async def test_coordinator_unload_clears_reset_listener_state(hass):
    """async_unload removes listeners and clears unsubscribe handles."""
    coordinator = MaxMinDataUpdateCoordinator(hass, make_config_entry())
    listener = Mock()
    coordinator._reset_listeners["test"] = listener

    unsub = Mock()
    coordinator._unsub_sensor_state_listener = unsub

    await coordinator.async_unload()

    listener.assert_called_once()
    unsub.assert_called_once()
    assert coordinator._reset_listeners == {}
    assert coordinator._unsub_sensor_state_listener is None
