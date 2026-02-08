"""Test inline period-boundary reset detection in _handle_sensor_change."""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from freezegun import freeze_time

from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_PERIODS,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    PERIOD_DAILY,
    PERIOD_WEEKLY,
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
    hass.data = {"custom_components": {}}
    hass.states.get.return_value = Mock(
        state="10.0", attributes={"friendly_name": "Test Sensor"}
    )
    return hass


@pytest.mark.asyncio
@freeze_time("2023-01-02 00:00:05")
async def test_inline_reset_on_period_boundary(hass, config_entry):
    """Test that a sensor update after midnight triggers inline reset.

    Scenario: last_reset is from yesterday, now is just after midnight.
    A sensor change arrives before the scheduled async_track_point_in_time fires.
    The inline check should reset max/min to the current sensor value before
    applying the new reading.
    """
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Simulate state from yesterday: max=25, min=3
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 25.0,
        "min": 3.0,
        "start": 5.0,
        "end": 20.0,
        "last_reset": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    }

    # Pending scheduled reset listener from yesterday
    cancel_mock = Mock()
    coordinator._reset_listeners = {PERIOD_DAILY: cancel_mock}
    coordinator._next_resets = {}

    # New sensor value arrives at 00:00:05 on Jan 2
    hass.states.get.return_value = Mock(
        state="8.0", attributes={"friendly_name": "Test Sensor"}
    )
    event = Mock()
    event.data = {
        "new_state": Mock(state="8.0", attributes={})
    }

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_sensor_change(event)

    # The old scheduled listener should have been cancelled
    cancel_mock.assert_called_once()

    # After inline reset + processing: max and min should be 8.0 (current value)
    # because _handle_reset sets both to current sensor value (8.0),
    # and 8.0 == 8.0 so no further update from _handle_sensor_change
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 8.0
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 8.0


@pytest.mark.asyncio
@freeze_time("2023-01-02 00:00:05")
async def test_inline_reset_no_pending_listener(hass, config_entry):
    """Test inline reset when no scheduled listener exists (already fired/cancelled)."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 25.0,
        "min": 3.0,
        "start": 5.0,
        "end": 20.0,
        "last_reset": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    }

    # No pending listener
    coordinator._reset_listeners = {}
    coordinator._next_resets = {}

    hass.states.get.return_value = Mock(
        state="12.0", attributes={"friendly_name": "Test Sensor"}
    )
    event = Mock()
    event.data = {
        "new_state": Mock(state="12.0", attributes={})
    }

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_sensor_change(event)

    # Should still have reset and set to current value
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 12.0
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 12.0


@pytest.mark.asyncio
@freeze_time("2023-01-01 23:59:59")
async def test_no_inline_reset_before_boundary(hass, config_entry):
    """Test that inline reset does NOT fire when still within the same period."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 25.0,
        "min": 3.0,
        "start": 5.0,
        "end": 20.0,
        "last_reset": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    }
    coordinator._reset_listeners = {}
    coordinator._next_resets = {}

    event = Mock()
    event.data = {
        "new_state": Mock(state="30.0", attributes={})
    }

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_sensor_change(event)

    # Should NOT have reset — values should update normally
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 30.0
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 3.0


@pytest.mark.asyncio
@freeze_time("2023-01-02 00:00:05")
async def test_inline_reset_all_time_skipped(hass, config_entry):
    """Test that all_time period is never inline-reset."""
    config_entry.data[CONF_PERIODS] = [PERIOD_ALL_TIME]
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    coordinator.tracked_data[PERIOD_ALL_TIME] = {
        "max": 50.0,
        "min": -5.0,
        "start": 0.0,
        "end": 20.0,
        "last_reset": datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    }
    coordinator._reset_listeners = {}
    coordinator._next_resets = {}

    event = Mock()
    event.data = {
        "new_state": Mock(state="10.0", attributes={})
    }

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_sensor_change(event)

    # Should NOT reset — all_time never resets
    assert coordinator.tracked_data[PERIOD_ALL_TIME]["max"] == 50.0
    assert coordinator.tracked_data[PERIOD_ALL_TIME]["min"] == -5.0


@pytest.mark.asyncio
@freeze_time("2023-01-08 00:00:05")
async def test_inline_reset_weekly_boundary(hass, config_entry):
    """Test inline reset at weekly boundary."""
    config_entry.data[CONF_PERIODS] = [PERIOD_WEEKLY]
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Jan 8 2023 is a Sunday, weekday=6. Week starts Monday Jan 2.
    # last_reset from Dec 26 (previous Monday) = previous week
    coordinator.tracked_data[PERIOD_WEEKLY] = {
        "max": 30.0,
        "min": 2.0,
        "start": 5.0,
        "end": 20.0,
        "last_reset": datetime(2022, 12, 26, 0, 0, 0, tzinfo=timezone.utc),
    }
    coordinator._reset_listeners = {}
    coordinator._next_resets = {}

    hass.states.get.return_value = Mock(
        state="15.0", attributes={"friendly_name": "Test Sensor"}
    )
    event = Mock()
    event.data = {
        "new_state": Mock(state="15.0", attributes={})
    }

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_sensor_change(event)

    # Should have reset to current value
    assert coordinator.tracked_data[PERIOD_WEEKLY]["max"] == 15.0
    assert coordinator.tracked_data[PERIOD_WEEKLY]["min"] == 15.0


@pytest.mark.asyncio
@freeze_time("2023-01-02 00:00:05")
async def test_inline_reset_then_new_value_applied(hass, config_entry):
    """Test that after inline reset, the incoming value is still applied.

    Edge case: sensor reports a new extreme that differs from what
    hass.states.get returns at reset time.
    """
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 25.0,
        "min": 3.0,
        "start": 5.0,
        "end": 20.0,
        "last_reset": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    }
    coordinator._reset_listeners = {}
    coordinator._next_resets = {}

    # hass.states.get returns 10 at reset time, but the event carries 15
    hass.states.get.return_value = Mock(
        state="10.0", attributes={"friendly_name": "Test Sensor"}
    )
    event = Mock()
    event.data = {
        "new_state": Mock(state="15.0", attributes={})
    }

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_sensor_change(event)

    # After inline reset: max/min set to 10.0 (from hass.states.get)
    # Then normal update: 15.0 > 10.0 → max becomes 15.0
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 15.0
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 10.0
