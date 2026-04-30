"""Additional Phase 0 coverage tests for defensive branches."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType

from conftest import make_config_entry, make_mock_hass
from custom_components.max_min import config_flow as max_min_config_flow
from custom_components.max_min.config_flow import MaxMinConfigFlow, MaxMinOptionsFlow
from custom_components.max_min.const import (
    CONF_PERIODS,
    CONF_RESET_HISTORY,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    PERIOD_ALL_TIME,
    PERIOD_DAILY,
    TYPE_DELTA,
    TYPE_MAX,
    TYPE_MIN,
)
from custom_components.max_min.coordinator import (
    MaxMinDataUpdateCoordinator,
    _as_float as coordinator_as_float,
)
from custom_components.max_min.sensor import (
    DeltaSensor,
    MaxSensor,
    MinSensor,
    _as_float as sensor_as_float,
)


def test_config_flow_coerce_localized_float_none_returns_none():
    """Localized float coercion accepts None as an empty value."""
    assert max_min_config_flow._coerce_localized_float(None) is None


@pytest.mark.asyncio
async def test_config_flow_optional_settings_skips_when_no_fields():
    """If no optional fields apply, the flow should create the entry immediately."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()
    flow.hass.states.get.return_value = None
    flow.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [],
    }

    result = await flow.async_step_optional_settings()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TYPES] == []


@pytest.mark.asyncio
async def test_options_flow_reset_history_uses_fallback_comparison():
    """Unparseable historical values still trigger surgical reset tracking."""
    config_entry = Mock()
    config_entry.options = {
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX],
        "daily_initial_max": "old-invalid",
    }
    config_entry.data = {CONF_SENSOR_ENTITY: "sensor.test"}
    config_entry.title = "sensor.test (Max)"

    flow = MaxMinOptionsFlow(config_entry)
    flow.hass = Mock()
    flow.hass.states.get.return_value = None
    flow.hass.config_entries.async_update_entry = Mock()

    await flow.async_step_init({
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX],
    })
    result = await flow.async_step_optional_settings({"daily_initial_max": "1,5"})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_RESET_HISTORY] == [f"{PERIOD_DAILY}_{TYPE_MAX}"]


def test_coordinator_as_float_none_returns_none():
    """Coordinator float coercion accepts None."""
    assert coordinator_as_float(None) is None


def test_sensor_as_float_none_returns_none():
    """Sensor float coercion accepts None."""
    assert sensor_as_float(None) is None


def test_coordinator_init_invalid_initial_min_ignored(hass):
    """Invalid configured initial minimum values are ignored."""
    entry = make_config_entry(daily_initial_min="broken")
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    assert coordinator._configured_initials[PERIOD_DAILY]["min"] is None


def test_is_timestamp_in_period_unknown_period_returns_true():
    """Unknown periods are treated as in-period for safety."""
    now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
    assert MaxMinDataUpdateCoordinator._is_timestamp_in_period(now, now, "custom") is True


def test_is_timestamp_in_period_without_next_reset_uses_simple_compare():
    """When next reset is unknown, timestamp comparison falls back to period start."""
    now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
    timestamp = datetime(2026, 4, 30, 0, 0, 0, tzinfo=timezone.utc)
    with patch.object(MaxMinDataUpdateCoordinator, "_compute_next_reset", return_value=None):
        assert MaxMinDataUpdateCoordinator._is_timestamp_in_period(timestamp, now, PERIOD_DAILY) is True


def test_compute_reset_seed_invalid_end_string_returns_none(hass):
    """Invalid string end values do not crash reset seeding."""
    hass.states.get.return_value = Mock(state="unavailable", attributes={})
    coordinator = MaxMinDataUpdateCoordinator(hass, make_config_entry())
    coordinator.tracked_data[PERIOD_DAILY]["end"] = "not-a-number"
    assert coordinator._compute_reset_seed(PERIOD_DAILY) is None


def test_is_reset_due_short_circuits_defensive_paths(hass):
    """Reset due checks short-circuit for all-time, missing data, and unknown starts."""
    coordinator = MaxMinDataUpdateCoordinator(hass, make_config_entry())
    now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)

    assert coordinator._is_reset_due(now, PERIOD_ALL_TIME) is False
    assert coordinator._is_reset_due(now, "weekly") is False

    with patch.object(coordinator, "_get_period_start", return_value=None):
        assert coordinator._is_reset_due(now, PERIOD_DAILY) is False


def test_is_reset_due_invalid_last_reset_typeerror_logs_and_continues(hass):
    """Bad last_reset comparisons are treated as missing instead of crashing."""
    coordinator = MaxMinDataUpdateCoordinator(hass, make_config_entry())
    now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)

    class BadLastReset:
        def __bool__(self):
            return True

        def __ge__(self, other):
            raise TypeError()

    coordinator.tracked_data[PERIOD_DAILY]["last_reset"] = now
    with patch.object(coordinator, "_normalize_last_reset", return_value=BadLastReset()):
        assert coordinator._is_reset_due(now, PERIOD_DAILY) is True


def test_apply_pending_initials_handles_invalid_current_value_and_missing_period(hass):
    """Initial application tolerates invalid current state and missing period data."""
    hass.states.get.return_value = Mock(state="invalid", attributes={})
    coordinator = MaxMinDataUpdateCoordinator(hass, make_config_entry())
    coordinator.tracked_data.pop(PERIOD_DAILY)
    coordinator._configured_initials = {
        PERIOD_DAILY: {"max": 20.0, "min": 5.0, "delta": 3.0},
    }

    coordinator.apply_pending_initials()

    assert coordinator._configured_initials == {}


def test_handle_sensor_change_dead_zone_updates_min_path(hass):
    """Dead-zone updates cover the min branch when max/min are uninitialized."""
    entry = make_config_entry(offset=10)
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator._source_is_cumulative = True
    now = datetime(2026, 4, 30, 23, 59, 55, tzinfo=timezone.utc)
    coordinator._next_resets[PERIOD_DAILY] = now + timedelta(seconds=5)
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": None,
        "min": None,
        "start": 1.0,
        "end": 1.0,
        "last_reset": None,
    }
    event = Mock()
    event.data = {"new_state": Mock(state="8.0", attributes={"state_class": "total_increasing"})}

    with patch("custom_components.max_min.coordinator.dt_util.now", return_value=now), \
         patch.object(coordinator, "ensure_period_current", return_value=False):
        coordinator._handle_sensor_change(event)

    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 8.0
    assert coordinator.tracked_data[PERIOD_DAILY]["end"] == 8.0


def test_handle_sensor_change_initial_delta_sets_start_from_delta(hass):
    """Configured initial deltas seed start when the first live value arrives."""
    coordinator = MaxMinDataUpdateCoordinator(hass, make_config_entry(types=[TYPE_DELTA]))
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": None,
        "min": None,
        "start": None,
        "end": None,
        "last_reset": None,
    }
    coordinator._configured_initials[PERIOD_DAILY]["delta"] = 2.5
    event = Mock()
    event.data = {"new_state": Mock(state="10.0", attributes={})}

    with patch("custom_components.max_min.coordinator.dt_util.now", return_value=datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)), \
         patch.object(coordinator, "ensure_period_current", return_value=False):
        coordinator._handle_sensor_change(event)

    assert coordinator.tracked_data[PERIOD_DAILY]["start"] == 7.5
    assert coordinator.tracked_data[PERIOD_DAILY]["end"] == 10.0


def test_schedule_single_reset_backup_callback_uses_backup_reason(hass):
    """Backup callback verifies the period using the backup reason."""
    coordinator = MaxMinDataUpdateCoordinator(hass, make_config_entry())
    schedule_time = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)

    with patch("custom_components.max_min.coordinator.async_track_point_in_time", side_effect=[Mock(), Mock()]) as mock_track, \
         patch.object(coordinator, "ensure_period_current") as mock_ensure:
        coordinator._schedule_single_reset(PERIOD_DAILY, schedule_time)
        backup_callback = mock_track.call_args_list[1][0][1]
        backup_callback(schedule_time + timedelta(seconds=30))

    mock_ensure.assert_called_once_with(PERIOD_DAILY, schedule_time + timedelta(seconds=30), reason="backup")


@pytest.mark.asyncio
async def test_async_unload_cleans_backup_and_watchdog_listeners(hass):
    """Unload unsubscribes backup listeners and watchdog callbacks."""
    coordinator = MaxMinDataUpdateCoordinator(hass, make_config_entry())
    coordinator._backup_reset_listeners[PERIOD_DAILY] = Mock()
    coordinator._watchdog_unsub = Mock()

    await coordinator.async_unload()

    assert coordinator._backup_reset_listeners == {}
    assert coordinator._watchdog_unsub is None


def test_sensor_device_class_filters_total_classes(coordinator):
    """Sensors do not mirror unsupported totalizing device classes."""
    config_entry = make_config_entry()
    coordinator.hass.states.get.return_value = Mock(
        state="10.0",
        attributes={"device_class": "energy"},
    )
    sensor = MaxSensor(coordinator, config_entry, "Test Max", PERIOD_DAILY)
    assert sensor.device_class is None


@pytest.mark.asyncio
async def test_min_sensor_restore_skips_other_config_entry(hass):
    """Min sensor ignores restored state from a different config entry."""
    entry = make_config_entry()
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = MinSensor(coordinator, entry, "Test Min", PERIOD_DAILY)
    sensor.async_get_last_state = AsyncMock(return_value=Mock(state="1.0", attributes={"config_entry_id": "other"}))

    with patch.object(MinSensor.__mro__[1], "async_added_to_hass", new_callable=AsyncMock), \
         patch.object(coordinator, "update_restored_data") as mock_restore:
        await sensor.async_added_to_hass()

    mock_restore.assert_not_called()


@pytest.mark.asyncio
async def test_max_sensor_restore_without_last_state_returns_early(hass):
    """Base restore path exits cleanly when there is no previous state."""
    entry = make_config_entry()
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = MaxSensor(coordinator, entry, "Test Max", PERIOD_DAILY)
    sensor.async_get_last_state = AsyncMock(return_value=None)

    with patch("homeassistant.helpers.restore_state.RestoreEntity.async_added_to_hass", new_callable=AsyncMock), \
         patch.object(sensor, "_restore_sensor_data") as mock_restore:
        await sensor.async_added_to_hass()

    mock_restore.assert_not_called()


@pytest.mark.asyncio
async def test_delta_sensor_restore_skips_other_config_entry(hass):
    """Delta sensor ignores restored state from a different config entry."""
    entry = make_config_entry(types=[TYPE_DELTA])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
    sensor.async_get_last_state = AsyncMock(return_value=Mock(state="1.0", attributes={"config_entry_id": "other"}))

    with patch.object(DeltaSensor.__mro__[1], "async_added_to_hass", new_callable=AsyncMock), \
         patch.object(coordinator, "update_restored_data") as mock_restore:
        await sensor.async_added_to_hass()

    mock_restore.assert_not_called()


@pytest.mark.asyncio
async def test_delta_sensor_restore_invalid_partial_values_are_ignored(hass):
    """Invalid single-sided restored boundaries are ignored safely."""
    entry = make_config_entry(types=[TYPE_DELTA])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
    last_state = Mock(
        state="3.0",
        attributes={
            "start_value": "bad-start",
            "end_value": "bad-end",
            "config_entry_id": entry.entry_id,
        },
    )

    with patch.object(coordinator, "update_restored_data") as mock_restore:
        sensor._restore_sensor_data(last_state)

    mock_restore.assert_not_called()


@pytest.mark.asyncio
async def test_delta_sensor_restore_start_and_end_attributes(hass):
    """Delta restore keeps the common base flow and restores both boundaries."""
    entry = make_config_entry(types=[TYPE_DELTA])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
    last_state = Mock(
        state="3.0",
        attributes={
            "start_value": "2.0",
            "end_value": "5.0",
            "config_entry_id": entry.entry_id,
        },
    )

    with patch.object(coordinator, "update_restored_data") as mock_restore:
        sensor._restore_sensor_data(last_state)

    assert mock_restore.call_count == 2
    mock_restore.assert_any_call(PERIOD_DAILY, "start", 2.0, None)
    mock_restore.assert_any_call(PERIOD_DAILY, "end", 5.0, None)


@pytest.mark.asyncio
async def test_delta_sensor_restore_invalid_start_only_is_ignored(hass):
    """Invalid restored start values are ignored in the one-sided fallback path."""
    entry = make_config_entry(types=[TYPE_DELTA])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
    last_state = Mock(
        state="3.0",
        attributes={
            "start_value": "bad-start",
            "config_entry_id": entry.entry_id,
        },
    )

    with patch.object(coordinator, "update_restored_data") as mock_restore:
        sensor._restore_sensor_data(last_state)

    mock_restore.assert_not_called()


@pytest.mark.asyncio
async def test_delta_sensor_restore_valid_start_only_updates_start(hass):
    """One-sided delta restore updates start when only start_value is present."""
    entry = make_config_entry(types=[TYPE_DELTA])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
    last_state = Mock(
        state="3.0",
        attributes={
            "start_value": "2.0",
            "config_entry_id": entry.entry_id,
        },
    )

    with patch.object(coordinator, "update_restored_data") as mock_restore:
        sensor._restore_sensor_data(last_state)

    mock_restore.assert_called_once_with(PERIOD_DAILY, "start", 2.0, None)


@pytest.mark.asyncio
async def test_delta_sensor_restore_invalid_end_only_is_ignored(hass):
    """Invalid restored end values are ignored in the one-sided fallback path."""
    entry = make_config_entry(types=[TYPE_DELTA])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
    last_state = Mock(
        state="3.0",
        attributes={
            "end_value": "bad-end",
            "config_entry_id": entry.entry_id,
        },
    )

    with patch.object(coordinator, "update_restored_data") as mock_restore:
        sensor._restore_sensor_data(last_state)

    mock_restore.assert_not_called()


@pytest.mark.asyncio
async def test_delta_sensor_restore_valid_end_only_updates_end(hass):
    """One-sided delta restore updates end when only end_value is present."""
    entry = make_config_entry(types=[TYPE_DELTA])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
    last_state = Mock(
        state="3.0",
        attributes={
            "end_value": "5.0",
            "config_entry_id": entry.entry_id,
        },
    )

    with patch.object(coordinator, "update_restored_data") as mock_restore:
        sensor._restore_sensor_data(last_state)

    mock_restore.assert_called_once_with(PERIOD_DAILY, "end", 5.0, None)


@pytest.mark.asyncio
async def test_delta_sensor_restore_invalid_reconstructed_delta_is_ignored(hass):
    """Invalid restored delta values do not trigger reconstructed boundaries."""
    hass.states.get.return_value = Mock(state="12.0", attributes={})
    entry = make_config_entry(types=[TYPE_DELTA])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
    last_state = Mock(
        state="bad-delta",
        attributes={"config_entry_id": entry.entry_id},
    )

    with patch.object(coordinator, "update_restored_data") as mock_restore:
        sensor._restore_sensor_data(last_state)

    mock_restore.assert_not_called()


@pytest.mark.asyncio
async def test_delta_sensor_restore_reconstructs_from_numeric_delta(hass):
    """Delta restore reconstructs start/end from the current source when needed."""
    hass.states.get.return_value = Mock(state="12.0", attributes={})
    entry = make_config_entry(types=[TYPE_DELTA])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
    last_state = Mock(
        state="3.0",
        attributes={"config_entry_id": entry.entry_id},
    )

    with patch.object(coordinator, "update_restored_data") as mock_restore:
        sensor._restore_sensor_data(last_state)

    assert mock_restore.call_count == 2
    mock_restore.assert_any_call(PERIOD_DAILY, "start", 9.0, None)
    mock_restore.assert_any_call(PERIOD_DAILY, "end", 12.0, None)


@pytest.fixture
def coordinator():
    """Coordinator fixture for sensor-focused tests."""
    coordinator = Mock(spec=MaxMinDataUpdateCoordinator)
    coordinator.hass = make_mock_hass()
    coordinator.get_value.return_value = None
    coordinator.last_update_success = True
    return coordinator