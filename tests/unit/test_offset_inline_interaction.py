"""Test interaction between offset logic and inline reset detection.

The inline reset must NOT fire within the offset window, but MUST fire
after the offset window has passed if the scheduled reset was missed.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
from freezegun import freeze_time

from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_OFFSET,
    CONF_PERIODS,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    PERIOD_DAILY,
    TYPE_MAX,
    TYPE_MIN,
)


@pytest.fixture
def config_entry_offset():
    """Config entry with offset=300 (5 minutes)."""
    entry = MagicMock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.energy",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX, TYPE_MIN],
    }
    entry.options = {CONF_OFFSET: 300}
    entry.entry_id = "test_offset"
    entry.title = "Energy Sensor"
    return entry


@pytest.fixture
def hass():
    """Mock hass."""
    hass = Mock()
    hass.config.time_zone = timezone.utc
    hass.data = {"custom_components": {}}
    hass.states.get.return_value = Mock(
        state="50.0", attributes={"friendly_name": "Energy"}
    )
    return hass


def _make_coordinator(hass, config_entry, last_reset_dt):
    """Create a coordinator with realistic tracked_data including last_reset."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 100.0,
        "min": 5.0,
        "start": 5.0,
        "end": 100.0,
        "last_reset": last_reset_dt,
    }
    coordinator._next_resets = {
        PERIOD_DAILY: datetime(2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc),
    }
    cancel_mock = Mock()
    coordinator._reset_listeners = {PERIOD_DAILY: cancel_mock}
    return coordinator, cancel_mock


# ---------------------------------------------------------------------------
# 1. Inline reset must NOT fire within the offset window
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@freeze_time("2026-02-09 00:01:00")
async def test_inline_reset_blocked_within_offset_window(hass, config_entry_offset):
    """Sensor update at 00:01 (within 5-min offset) must NOT trigger inline reset.

    Without the fix, the inline check (last_reset < period_start) would fire
    immediately, bypassing the offset delay intended for cumulative sensors.
    """
    yesterday = datetime(2026, 2, 8, 0, 0, 0, tzinfo=timezone.utc)
    coordinator, cancel_mock = _make_coordinator(hass, config_entry_offset, yesterday)

    event = Mock()
    event.data = {"new_state": Mock(state="55.0", attributes={"state_class": "measurement"})}

    coordinator._handle_sensor_change(event)

    # Inline reset must NOT have fired — the scheduled listener must remain
    cancel_mock.assert_not_called()

    # The old max/min from yesterday must still be present (offset dead zone skips updates)
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 100.0
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 5.0


@pytest.mark.asyncio
@freeze_time("2026-02-09 00:04:59")
async def test_inline_reset_blocked_at_offset_boundary(hass, config_entry_offset):
    """At 00:04:59 (1 second before offset expires), inline reset must NOT fire."""
    yesterday = datetime(2026, 2, 8, 0, 0, 0, tzinfo=timezone.utc)
    coordinator, cancel_mock = _make_coordinator(hass, config_entry_offset, yesterday)

    event = Mock()
    event.data = {"new_state": Mock(state="55.0", attributes={"state_class": "measurement"})}

    coordinator._handle_sensor_change(event)

    cancel_mock.assert_not_called()
    # Dead zone still active → values unchanged
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 100.0


# ---------------------------------------------------------------------------
# 2. Inline reset MUST fire after the offset window (safety net)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@freeze_time("2026-02-09 00:06:00")
async def test_inline_reset_fires_after_offset_window(hass, config_entry_offset):
    """At 00:06 (past the 5-min offset), inline reset fires as a safety net.

    If the scheduled reset at 00:05 was missed (e.g., HA restart/overload),
    the inline reset should catch it on the next sensor update.
    """
    yesterday = datetime(2026, 2, 8, 0, 0, 0, tzinfo=timezone.utc)
    coordinator, cancel_mock = _make_coordinator(hass, config_entry_offset, yesterday)

    hass.states.get.return_value = Mock(
        state="12.0", attributes={"friendly_name": "Energy"}
    )
    event = Mock()
    event.data = {"new_state": Mock(state="12.0", attributes={"state_class": "measurement"})}

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_sensor_change(event)

    # The old scheduled listener should have been cancelled
    cancel_mock.assert_called_once()

    # After inline reset: max and min reset to current sensor value (12.0)
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 12.0
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 12.0


# ---------------------------------------------------------------------------
# 3. With offset=0, inline reset fires immediately (no change in behaviour)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@freeze_time("2026-02-09 00:00:01")
async def test_inline_reset_immediate_when_no_offset(hass):
    """With offset=0, inline reset fires immediately at period boundary."""
    entry = MagicMock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.temp",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX, TYPE_MIN],
    }
    entry.options = {}  # offset defaults to 0
    entry.entry_id = "test_no_offset"
    entry.title = "Temp Sensor"

    yesterday = datetime(2026, 2, 8, 0, 0, 0, tzinfo=timezone.utc)
    coordinator, cancel_mock = _make_coordinator(hass, entry, yesterday)

    hass.states.get.return_value = Mock(
        state="15.0", attributes={"friendly_name": "Temp"}
    )
    event = Mock()
    event.data = {"new_state": Mock(state="15.0", attributes={})}

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_sensor_change(event)

    cancel_mock.assert_called_once()
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 15.0
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 15.0


# ---------------------------------------------------------------------------
# 4. Offset dead zone correctly ignores updates when last_reset is set
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@freeze_time("2026-02-09 00:02:00")
async def test_offset_dead_zone_with_realistic_last_reset(hass, config_entry_offset):
    """Dead zone ignores updates even with last_reset properly set.

    This validates that with the inline-reset-offset guard, the dead zone
    logic is still reached and works correctly for non-cumulative sensors.
    """
    yesterday = datetime(2026, 2, 8, 0, 0, 0, tzinfo=timezone.utc)
    coordinator, _ = _make_coordinator(hass, config_entry_offset, yesterday)

    event = Mock()
    event.data = {"new_state": Mock(state="200.0", attributes={"state_class": "measurement"})}

    coordinator._handle_sensor_change(event)

    # Value must NOT have changed — dead zone is active
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 100.0
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 5.0
