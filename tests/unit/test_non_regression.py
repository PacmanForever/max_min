"""Non-regression test suite – consensus contract between GPT and Claude.

These 15 scenarios cover every critical reset path and must ALL pass before
any release.  Each test is numbered to match the contract document.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from freezegun import freeze_time
from homeassistant.util import dt as dt_util
from conftest import make_config_entry, make_mock_hass

from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_OFFSET,
    CONF_PERIODS,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    PERIOD_DAILY,
    PERIOD_WEEKLY,
    PERIOD_ALL_TIME,
    TYPE_MAX,
    TYPE_MIN,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(periods=None, types=None, offset=0, **extra):
    return make_config_entry(periods=periods, types=types, offset=offset, **extra)


def _hass(state="10.0", state_class=None, last_updated=None, last_changed=None):
    hass = make_mock_hass(state=state, state_class=state_class)
    if last_updated is not None:
        hass.states.get.return_value.last_updated = last_updated
    if last_changed is not None:
        hass.states.get.return_value.last_changed = last_changed
    return hass


# ===================================================================
# NR-01  Reset exacte a mitjanit
# ===================================================================

@freeze_time("2026-02-22 00:00:00", tz_offset=0)
def test_nr01_reset_at_exact_midnight():
    """Scheduler fires at midnight; last_reset becomes period_start (not now)."""
    hass = _hass("5.0")
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry())
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 25.0, "min": 3.0, "start": 5.0, "end": 20.0,
        "last_reset": datetime(2026, 2, 21, 0, 0, 0, tzinfo=timezone.utc),
    }

    now = datetime(2026, 2, 22, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._perform_reset(now, PERIOD_DAILY, reason="scheduler")

    data = coordinator.tracked_data[PERIOD_DAILY]
    # last_reset == period_start, NOT wall-clock now
    assert data["last_reset"] == datetime(2026, 2, 22, 0, 0, 0, tzinfo=timezone.utc)
    assert data["last_reset_reason"] == "scheduler"
    assert data["last_reset_triggered_at"] == now
    assert data["max"] == 5.0
    assert data["min"] == 5.0
    assert data["start"] == 5.0
    assert data["end"] == 5.0


# ===================================================================
# NR-02  Doble trigger no duplica reset
# ===================================================================

@freeze_time("2026-02-22 00:00:05", tz_offset=0)
def test_nr02_double_trigger_no_duplicate_reset():
    """If scheduler and watchdog fire close together, only one reset happens."""
    hass = _hass("7.0")
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry())
    now = datetime(2026, 2, 22, 0, 0, 5, tzinfo=timezone.utc)

    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 25.0, "min": 3.0, "start": 5.0, "end": 20.0,
        "last_reset": datetime(2026, 2, 21, 0, 0, 0, tzinfo=timezone.utc),
    }

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        # First trigger (scheduler)
        result1 = coordinator.ensure_period_current(PERIOD_DAILY, now, reason="scheduler")
        # Second trigger (watchdog) — should be a no-op
        result2 = coordinator.ensure_period_current(PERIOD_DAILY, now, reason="watchdog")

    assert result1 is True
    assert result2 is False
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 7.0


# ===================================================================
# NR-03  Catch-up post-reinici
# ===================================================================

@pytest.mark.asyncio
@freeze_time("2026-02-22 00:05:00", tz_offset=0)
async def test_nr03_catchup_after_restart():
    """HA offline during midnight; startup catch-up resets the period."""
    hass = _hass("12.0")
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry())

    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 25.0, "min": 3.0, "start": 5.0, "end": 20.0,
        "last_reset": datetime(2026, 2, 21, 0, 0, 0, tzinfo=timezone.utc),
    }

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"), \
         patch("custom_components.max_min.coordinator.async_track_state_change_event"):
        await coordinator.async_config_entry_first_refresh()
        # Catch-up is deferred to start_listeners (after entity restore)
        coordinator.start_listeners()

    data = coordinator.tracked_data[PERIOD_DAILY]
    assert data["last_reset"] == datetime(2026, 2, 22, 0, 0, 0, tzinfo=timezone.utc)
    assert data["max"] == 12.0
    assert data["min"] == 12.0


# ===================================================================
# NR-04  Measurement no carry-over
# ===================================================================

@freeze_time("2026-02-22 00:00:00", tz_offset=0)
def test_nr04_measurement_seed_uses_last_end():
    """Measurement sensor unavailable at reset → seed = last end value.

    This ensures the entity keeps a numeric state so the HA history
    graph shows a clean break at the period boundary instead of a flat
    line of the previous maximum (which happens when the entity goes
    unavailable/None).
    """
    hass = _hass("unavailable")
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry())
    coordinator._source_is_cumulative = False

    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 25.0, "min": 3.0, "start": 5.0, "end": 20.0,
        "last_reset": datetime(2026, 2, 21, 0, 0, 0, tzinfo=timezone.utc),
    }

    now = datetime(2026, 2, 22, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._perform_reset(now, PERIOD_DAILY)

    data = coordinator.tracked_data[PERIOD_DAILY]
    # Seed = last end value (20.0) — not None
    assert data["max"] == 20.0
    assert data["min"] == 20.0
    assert data["start"] == 20.0
    assert data["end"] == 20.0


@freeze_time("2026-05-04 00:00:00", tz_offset=0)
def test_nr04b_weekly_reset_ignores_stale_measurement_source():
    """Weekly reset must ignore a pre-midnight measurement state.

    Real-world case: a device-provided daily peak sensor can still expose
    Sunday's peak at Monday 00:00 until the inverter publishes again.
    That stale state must not seed the new weekly max.
    """
    stale_timestamp = datetime(2026, 5, 3, 23, 55, 0, tzinfo=timezone.utc)
    hass = _hass("3603.0", last_updated=stale_timestamp, last_changed=stale_timestamp)
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry(periods=[PERIOD_WEEKLY]))
    coordinator._source_is_cumulative = False

    coordinator.tracked_data[PERIOD_WEEKLY] = {
        "max": 4220.0, "min": 0.0, "start": 0.0, "end": 3603.0,
        "last_reset": datetime(2026, 4, 27, 0, 0, 0, tzinfo=timezone.utc),
    }

    now = datetime(2026, 5, 4, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._perform_reset(now, PERIOD_WEEKLY)

    data = coordinator.tracked_data[PERIOD_WEEKLY]
    assert data["last_reset"] == datetime(2026, 5, 4, 0, 0, 0, tzinfo=timezone.utc)
    assert data["max"] is None
    assert data["min"] is None
    assert data["start"] is None
    assert data["end"] is None


@freeze_time("2026-05-04 08:00:00", tz_offset=0)
def test_nr04c_weekly_reset_accepts_first_fresh_measurement_update():
    """After a stale-safe reset, the first fresh value becomes the new weekly max."""
    fresh_timestamp = datetime(2026, 5, 4, 8, 0, 0, tzinfo=timezone.utc)
    hass = _hass("1875.0", last_updated=fresh_timestamp, last_changed=fresh_timestamp)
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry(periods=[PERIOD_WEEKLY]))
    coordinator._source_is_cumulative = False

    coordinator.tracked_data[PERIOD_WEEKLY] = {
        "max": None, "min": None, "start": None, "end": None,
        "last_reset": datetime(2026, 5, 4, 0, 0, 0, tzinfo=timezone.utc),
    }
    coordinator._pending_start_reanchor.add(PERIOD_WEEKLY)

    event = Mock()
    event.data = {
        "new_state": Mock(
            state="1875.0",
            attributes={},
            last_updated=fresh_timestamp,
            last_changed=fresh_timestamp,
        )
    }

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_sensor_change(event)

    data = coordinator.tracked_data[PERIOD_WEEKLY]
    assert data["max"] == 1875.0
    assert data["min"] == 1875.0
    assert data["start"] == 1875.0
    assert data["end"] == 1875.0


# ===================================================================
# NR-05  Cumulative sí carry-over
# ===================================================================

@freeze_time("2026-02-22 00:00:00", tz_offset=0)
def test_nr05_cumulative_carryover():
    """Cumulative sensor unavailable → seed = last end value."""
    hass = _hass("unavailable", state_class="total_increasing")
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry())
    coordinator._source_is_cumulative = True

    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 150.0, "min": 100.0, "start": 100.0, "end": 145.5,
        "last_reset": datetime(2026, 2, 21, 0, 0, 0, tzinfo=timezone.utc),
    }

    now = datetime(2026, 2, 22, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._perform_reset(now, PERIOD_DAILY)

    data = coordinator.tracked_data[PERIOD_DAILY]
    assert data["max"] == 145.5
    assert data["min"] == 145.5
    assert data["start"] == 145.5


# ===================================================================
# NR-06  Offset respectat
# ===================================================================

@freeze_time("2026-02-22 00:01:00", tz_offset=0)
def test_nr06_offset_respected():
    """With offset=120s, reset not due until period_start+120s."""
    hass = _hass("10.0", state_class="total_increasing")
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry(offset=120))
    coordinator._source_is_cumulative = True

    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 50.0, "min": 10.0, "start": 10.0, "end": 50.0,
        "last_reset": datetime(2026, 2, 21, 0, 0, 0, tzinfo=timezone.utc),
    }

    # 00:01 < 00:02 (period_start + 120s) → NOT due
    now_early = datetime(2026, 2, 22, 0, 1, 0, tzinfo=timezone.utc)
    assert coordinator._is_reset_due(now_early, PERIOD_DAILY) is False

    # 00:03 > 00:02 → due
    now_late = datetime(2026, 2, 22, 0, 3, 0, tzinfo=timezone.utc)
    assert coordinator._is_reset_due(now_late, PERIOD_DAILY) is True


# ===================================================================
# NR-07  Early offset detection
# ===================================================================

def test_nr07_early_offset_detection():
    """Cumulative sensor drops inside dead zone → immediate reset."""
    hass = _hass("0.0", state_class="total_increasing")
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry(offset=10))
    coordinator._source_is_cumulative = True

    # Period already reset today — we're testing the dead zone before TOMORROW
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 100.0, "min": 50.0, "start": 50.0, "end": 100.0,
        "last_reset": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    }
    coordinator._next_resets = {
        PERIOD_DAILY: datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    }
    coordinator._reset_listeners = {}

    event = Mock()
    event.data = {"new_state": Mock(
        state="0.0", attributes={"state_class": "total_increasing"}
    )}

    # 23:59:55 is within dead zone (offset=10 → 23:59:50..00:00:10)
    with freeze_time("2023-01-01 23:59:55"):
        with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
            with patch.object(coordinator, "_perform_reset") as mock_reset:
                coordinator._handle_sensor_change(event)
                mock_reset.assert_called_once()
                assert mock_reset.call_args[1]["reason"] == "early_offset"


# ===================================================================
# NR-08  DST spring forward (rellotge salta 01:59 → 03:00)
# ===================================================================

def test_nr08_dst_spring_forward():
    """Daily reset at midnight is unaffected by spring-forward at 02:00."""
    hass = _hass("5.0")
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry())

    # Last reset was yesterday
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 20.0, "min": 2.0, "start": 5.0, "end": 15.0,
        "last_reset": datetime(2026, 3, 28, 0, 0, 0, tzinfo=timezone.utc),
    }

    # Now it's 03:00 on March 29 (day clocks moved forward at 02:00)
    now_after_dst = datetime(2026, 3, 29, 2, 0, 0, tzinfo=timezone.utc)
    assert coordinator._is_reset_due(now_after_dst, PERIOD_DAILY) is True

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._perform_reset(now_after_dst, PERIOD_DAILY)

    assert coordinator.tracked_data[PERIOD_DAILY]["last_reset"] == \
        datetime(2026, 3, 29, 0, 0, 0, tzinfo=timezone.utc)


# ===================================================================
# NR-09  DST fall back (rellotge repeteix 02:00-03:00) — no double reset
# ===================================================================

def test_nr09_dst_fall_back_no_double_reset():
    """Fall-back DST: watchdog at 02:30 should NOT double-reset."""
    hass = _hass("8.0")
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry())

    # Reset already done at midnight
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 8.0, "min": 8.0, "start": 8.0, "end": 8.0,
        "last_reset": datetime(2026, 10, 25, 0, 0, 0, tzinfo=timezone.utc),
    }

    # Now 02:30 (second occurrence due to fall-back) same day
    now_fallback = datetime(2026, 10, 25, 2, 30, 0, tzinfo=timezone.utc)
    assert coordinator._is_reset_due(now_fallback, PERIOD_DAILY) is False


# ===================================================================
# NR-10  Restore amb last_reset string
# ===================================================================

def test_nr10_restore_last_reset_string():
    """Restored last_reset as ISO string is handled correctly."""
    hass = _hass("10.0")
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry())

    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 10.0, "min": 10.0, "start": 10.0, "end": 10.0,
        "last_reset": "2026-02-22T00:00:00+00:00",
    }

    now = datetime(2026, 2, 22, 8, 0, 0, tzinfo=timezone.utc)
    # Should NOT be due — string parses to today's period start
    assert coordinator._is_reset_due(now, PERIOD_DAILY) is False


# ===================================================================
# NR-11  Restore amb last_reset naive
# ===================================================================

def test_nr11_restore_last_reset_naive():
    """Restored naive datetime last_reset is normalised with TZ."""
    hass = _hass("10.0")
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry())

    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 10.0, "min": 10.0, "start": 10.0, "end": 10.0,
        "last_reset": datetime(2026, 2, 22, 0, 0, 0),  # naive!
    }

    now = datetime(2026, 2, 22, 8, 0, 0, tzinfo=timezone.utc)
    # Should NOT be due — naive datetime normalised to UTC
    assert coordinator._is_reset_due(now, PERIOD_DAILY) is False


# ===================================================================
# NR-12  Restore amb last_reset absent
# ===================================================================

def test_nr12_restore_last_reset_absent():
    """Missing last_reset → _is_reset_due returns True (catch-up)."""
    hass = _hass("10.0")
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry())

    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 10.0, "min": 10.0, "start": 10.0, "end": 10.0,
        # no "last_reset" key
    }

    now = datetime(2026, 2, 22, 8, 0, 0, tzinfo=timezone.utc)
    assert coordinator._is_reset_due(now, PERIOD_DAILY) is True


# ===================================================================
# NR-13  Inline reset
# ===================================================================

@freeze_time("2026-02-22 00:00:05", tz_offset=0)
def test_nr13_inline_reset():
    """Sensor change at 00:00:05 triggers inline reset before normal update."""
    hass = _hass("8.0")
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry())

    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 25.0, "min": 3.0, "start": 5.0, "end": 20.0,
        "last_reset": datetime(2026, 2, 21, 0, 0, 0, tzinfo=timezone.utc),
    }
    coordinator._reset_listeners = {}

    event = Mock()
    event.data = {"new_state": Mock(state="8.0", attributes={})}

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_sensor_change(event)

    data = coordinator.tracked_data[PERIOD_DAILY]
    # inline reset seeded with current state (8.0), then 8.0 processed
    assert data["max"] == 8.0
    assert data["min"] == 8.0
    assert data["last_reset"] == datetime(2026, 2, 22, 0, 0, 0, tzinfo=timezone.utc)


# ===================================================================
# NR-14  Surgical reset (reset_history)
# ===================================================================

def test_nr14_surgical_reset():
    """Period in reset_history skips restore data."""
    hass = _hass("10.0")
    entry = _entry()
    entry.options = {"reset_history": ["daily_max"]}
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)

    coordinator.update_restored_data(PERIOD_DAILY, "max", 99.0,
                                     last_reset=datetime(2026, 2, 22, 0, 0, 0, tzinfo=timezone.utc))

    # Should be ignored — surgical reset blocks this combo
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] is None or \
           coordinator.tracked_data[PERIOD_DAILY]["max"] != 99.0


# ===================================================================
# NR-15  Initial value enforcement post-reset
# ===================================================================

@freeze_time("2026-02-22 00:00:00", tz_offset=0)
def test_nr15_initial_value_enforcement():
    """After reset, initials are one-shot: max/min = seed."""
    hass = _hass("13.0")
    entry = _entry()
    entry.data["daily_initial_max"] = 45.0
    entry.data["daily_initial_min"] = -5.0
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)

    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 100.0, "min": 0.5, "start": 5.0, "end": 50.0,
        "last_reset": datetime(2026, 2, 21, 0, 0, 0, tzinfo=timezone.utc),
    }

    now = datetime(2026, 2, 22, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._perform_reset(now, PERIOD_DAILY)

    data = coordinator.tracked_data[PERIOD_DAILY]
    # seed=13.0, initials are one-shot → max=seed, min=seed
    assert data["max"] == 13.0
    assert data["min"] == 13.0
    # start/end use seed, will be re-anchored on first sensor update
    assert data["start"] == 13.0
    assert data["end"] == 13.0


# ===================================================================
# NR-16  Measurement sensor seed fallback to end_val
# ===================================================================

@freeze_time("2026-02-22 00:00:00", tz_offset=0)
def test_nr16_measurement_seed_fallback():
    """Non-cumulative sensor unavailable at reset uses last end value as seed.

    This fixes the graph stale-line problem: when the source sensor
    (e.g. UV index) is unavailable at midnight, the entity keeps a
    numeric state so HA history shows a clean break instead of a flat
    continuation of the previous maximum.
    """
    hass = _hass("unavailable")
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry())
    coordinator._source_is_cumulative = False

    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 3.1, "min": 0.2, "start": 0.1, "end": 0.3,
        "last_reset": datetime(2026, 2, 21, 0, 0, 0, tzinfo=timezone.utc),
    }

    now = datetime(2026, 2, 22, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._perform_reset(now, PERIOD_DAILY)

    data = coordinator.tracked_data[PERIOD_DAILY]
    # Seed = last end value (0.3), NOT None and NOT yesterday's max (3.1)
    assert data["max"] == 0.3
    assert data["min"] == 0.3
    assert data["start"] == 0.3
    assert data["end"] == 0.3


# ===================================================================
# NR-17  Measurement sensor with NO end_val falls to None
# ===================================================================

@freeze_time("2026-02-22 00:00:00", tz_offset=0)
def test_nr17_measurement_no_end_val_seed_none():
    """Non-cumulative sensor unavailable with no end value → seed is None.

    This can happen on a fresh setup where the source never reported.
    The entity shows 'unknown' in HA (not 'unavailable').
    """
    hass = _hass("unavailable")
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry())
    coordinator._source_is_cumulative = False

    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": None, "min": None, "start": None, "end": None,
        "last_reset": datetime(2026, 2, 21, 0, 0, 0, tzinfo=timezone.utc),
    }

    now = datetime(2026, 2, 22, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._perform_reset(now, PERIOD_DAILY)

    data = coordinator.tracked_data[PERIOD_DAILY]
    # No end value to fall back to → seed = None
    assert data["max"] is None
    assert data["min"] is None
    assert data["start"] is None
    assert data["end"] is None


# ===================================================================
# NR-18  Scheduler callbacks are @callback-decorated (event-loop)
# ===================================================================

def test_nr18_scheduler_callbacks_are_ha_callbacks():
    """Timer callbacks passed to async_track_point_in_time must have the
    _hass_callback marker so HA runs them in the event loop.

    Without this, async_write_ha_state runs in the thread-pool executor
    and the HA state machine is never updated at reset time — the graph
    shows the change only when the source sensor next reports (minutes
    or hours later).
    """
    hass = _hass("10.0")
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry())

    captured_callbacks = []

    def capture(hass, cb, point_in_time):
        captured_callbacks.append(cb)
        return lambda: None  # unsub

    with patch(
        "custom_components.max_min.coordinator.async_track_point_in_time",
        side_effect=capture,
    ):
        coordinator._schedule_resets()

    # Daily period → 2 callbacks (main + backup)
    assert len(captured_callbacks) >= 2, (
        f"Expected at least 2 callbacks, got {len(captured_callbacks)}"
    )

    for cb in captured_callbacks:
        assert getattr(cb, "_hass_callback", False), (
            f"Callback {cb} is missing @callback decorator — HA will run it "
            f"in the executor instead of the event loop"
        )


# ===================================================================
# NR-19  DeltaSensor initial_delta offset enforcement
# ===================================================================

import pytest

@pytest.mark.asyncio
async def test_nr19_delta_initial_value_offset(hass):
    """initial_delta acts as an offset for the delta sensor value.

    When configured, the coordinator initializes the `start` value by
    subtracting `initial_delta` from the current source value. This ensures
    the delta (end - start) starts at `initial_delta` and increments naturally.
    """
    from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
    from custom_components.max_min.sensor import DeltaSensor
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from unittest.mock import patch, MagicMock

    state_mock = MagicMock()
    state_mock.state = "100.0"
    state_mock.attributes = {}
    hass.states.get.return_value = state_mock

    entry = MockConfigEntry(
        domain="max_min",
        title="Test",
        data={"sensor_entity": "sensor.source", "periods": ["weekly"], "types": ["delta"], "weekly_initial_delta": 42.0},
        options={},
    )

    coord = MaxMinDataUpdateCoordinator(hass, entry)
    
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"), \
         patch("custom_components.max_min.coordinator.async_track_state_change_event"):
        await coord.async_config_entry_first_refresh()

    # The coordinator should have initialized start = 100 - 42 = 58
    assert coord.get_value("weekly", "start") == 58.0
    assert coord.get_value("weekly", "end") == 100.0

    # The sensor should return end - start = 42.0
    s = DeltaSensor(coord, entry, "D", "weekly")
    assert s.native_value == 42.0

    # When source increases by 5, delta should be 47.0
    state_mock2 = MagicMock()
    state_mock2.state = "105.0"
    state_mock2.attributes = {}
    event_mock = MagicMock()
    event_mock.data = {"new_state": state_mock2}
    coord._handle_sensor_change(event_mock)
    
    assert coord.get_value("weekly", "start") == 58.0
    assert coord.get_value("weekly", "end") == 105.0
    assert s.native_value == 47.0

    # Case: no start/end yet -> returns initial_delta
    class DummyCoord:
        hass = None
        last_update_success = True
        def get_value(self, period, key):
            return None
    
    s_none = DeltaSensor(DummyCoord(), entry, "D", "weekly")
    assert s_none.native_value == 42.0

@pytest.mark.asyncio
async def test_nr20_delta_legacy_state_migration(hass):
    """
    NR-20: Verify that legacy states (v0.3.38) where `start` was not offset
    are correctly migrated when restored.
    """
    from custom_components.max_min.sensor import DeltaSensor
    from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
    from homeassistant.core import State
    from unittest.mock import patch, MagicMock

    # Setup mock config entry with initial_delta = 35
    config_entry = MagicMock()
    config_entry.options = {"weekly_initial_delta": 35.0}
    config_entry.data = {"sensor_entity": "sensor.test", "periods": ["weekly"], "offset": 0}
    config_entry.entry_id = "test_entry"

    # Setup coordinator
    coord = MaxMinDataUpdateCoordinator(hass, config_entry)
    coord.tracked_data["weekly"] = {"max": None, "min": None, "start": None, "end": None, "last_reset": None}

    # Setup sensor
    sensor = DeltaSensor(coord, config_entry, "Test Delta", "weekly")
    sensor.hass = hass
    sensor.entity_id = "sensor.test_delta"

    # Mock the last state to simulate a v0.3.38 state
    # In v0.3.38, start was not offset. So raw_delta = 1001.8 - 1000 = 1.8
    # Since 1.8 < 35, it should trigger the migration.
    import homeassistant.util.dt as dt_util
    now = dt_util.now()
    mock_last_state = State(
        "sensor.test_delta",
        "35.0", # In v0.3.38, it showed max(1.8, 35) = 35
        attributes={
            "config_entry_id": "test_entry",
            "start_value": 1000.0,
            "end_value": 1001.8,
            "last_reset": now.isoformat()
        }
    )

    with patch("custom_components.max_min.sensor.RestoreEntity.async_get_last_state", return_value=mock_last_state):
        await sensor.async_added_to_hass()

    # Legacy migration removed (was harmful — corrupted start after resets).
    # Now start is restored as-is.
    assert coord.tracked_data["weekly"]["start"] == 1000.0
    assert coord.tracked_data["weekly"]["end"] == 1001.8

    # native_value = end - start = 1001.8 - 1000.0 = 1.8
    assert sensor.native_value == pytest.approx(1.8)

    # Simulate already-migrated state (start already offset)
    mock_last_state_migrated = State(
        "sensor.test_delta",
        "36.8",
        attributes={
            "config_entry_id": "test_entry",
            "start_value": 965.0,
            "end_value": 1001.8,
            "last_reset": now.isoformat()
        }
    )

    # Reset coordinator data
    coord.tracked_data["weekly"] = {"max": None, "min": None, "start": None, "end": None, "last_reset": None}

    with patch("custom_components.max_min.sensor.RestoreEntity.async_get_last_state", return_value=mock_last_state_migrated):
        await sensor.async_added_to_hass()

    # Restored as-is
    assert coord.tracked_data["weekly"]["start"] == 965.0
    assert coord.tracked_data["weekly"]["end"] == 1001.8
    assert sensor.native_value == pytest.approx(36.8)

@pytest.mark.asyncio
async def test_nr21_delta_legacy_state_migration_partial_restore(hass):
    """
    NR-21: Verify that if only start or only end is restored, it falls back
    to the normal restore logic without migration.
    """
    from custom_components.max_min.sensor import DeltaSensor
    from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
    from homeassistant.core import State
    from unittest.mock import patch, MagicMock
    import homeassistant.util.dt as dt_util

    config_entry = MagicMock()
    config_entry.options = {"weekly_initial_delta": 35.0}
    config_entry.data = {"sensor_entity": "sensor.test", "periods": ["weekly"], "offset": 0}
    config_entry.entry_id = "test_entry"

    coord = MaxMinDataUpdateCoordinator(hass, config_entry)
    coord.tracked_data["weekly"] = {"max": None, "min": None, "start": None, "end": None, "last_reset": None}

    sensor = DeltaSensor(coord, config_entry, "Test Delta", "weekly")
    sensor.hass = hass
    sensor.entity_id = "sensor.test_delta"

    now = dt_util.now()
    
    # Only start is present
    mock_last_state_start_only = State(
        "sensor.test_delta",
        "35.0",
        attributes={
            "config_entry_id": "test_entry",
            "start_value": 1000.0,
            "last_reset": now.isoformat()
        }
    )

    with patch("custom_components.max_min.sensor.RestoreEntity.async_get_last_state", return_value=mock_last_state_start_only):
        await sensor.async_added_to_hass()

    assert coord.tracked_data["weekly"]["start"] == 1000.0
    assert coord.tracked_data["weekly"]["end"] is None

    # Reset
    coord.tracked_data["weekly"] = {"max": None, "min": None, "start": None, "end": None, "last_reset": None}

    # Only end is present
    mock_last_state_end_only = State(
        "sensor.test_delta",
        "35.0",
        attributes={
            "config_entry_id": "test_entry",
            "end_value": 1001.8,
            "last_reset": now.isoformat()
        }
    )

    with patch("custom_components.max_min.sensor.RestoreEntity.async_get_last_state", return_value=mock_last_state_end_only):
        await sensor.async_added_to_hass()

    assert coord.tracked_data["weekly"]["start"] is None
    assert coord.tracked_data["weekly"]["end"] == 1001.8


@pytest.mark.asyncio
async def test_nr22_delta_restore_reconstructs_boundaries_when_attrs_missing(hass):
    """If restored delta lacks start/end attrs, rebuild boundaries from source value."""
    from custom_components.max_min.sensor import DeltaSensor
    from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
    from homeassistant.core import State
    from unittest.mock import patch, MagicMock
    import homeassistant.util.dt as dt_util

    config_entry = MagicMock()
    config_entry.options = {}
    config_entry.data = {"sensor_entity": "sensor.test", "periods": ["weekly"], "offset": 0}
    config_entry.entry_id = "test_entry"

    # Current source state used to reconstruct end_value on startup.
    hass.states.get.return_value = State("sensor.test", "121.6", {"friendly_name": "Test"})

    coord = MaxMinDataUpdateCoordinator(hass, config_entry)
    coord.tracked_data["weekly"] = {"max": None, "min": None, "start": None, "end": None, "last_reset": None}

    sensor = DeltaSensor(coord, config_entry, "Test Delta", "weekly")
    sensor.hass = hass
    sensor.entity_id = "sensor.test_delta"

    now = dt_util.now()
    # State has only delta + last_reset, but missing start/end attributes.
    mock_last_state = State(
        "sensor.test_delta",
        "18.4",
        attributes={
            "config_entry_id": "test_entry",
            "last_reset": now.isoformat(),
        },
    )

    with patch("custom_components.max_min.sensor.RestoreEntity.async_get_last_state", return_value=mock_last_state):
        await sensor.async_added_to_hass()

    assert coord.tracked_data["weekly"]["end"] == pytest.approx(121.6)
    assert coord.tracked_data["weekly"]["start"] == pytest.approx(103.2)
    assert sensor.native_value == pytest.approx(18.4)


@pytest.mark.asyncio
async def test_nr23_delta_restore_reconstructs_without_last_reset(hass):
    """If restored delta has no attrs and no last_reset, keep continuity from source."""
    from custom_components.max_min.sensor import DeltaSensor
    from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
    from homeassistant.core import State
    from unittest.mock import patch, MagicMock

    config_entry = MagicMock()
    config_entry.options = {}
    config_entry.data = {"sensor_entity": "sensor.test", "periods": ["weekly"], "offset": 0}
    config_entry.entry_id = "test_entry"

    hass.states.get.return_value = State("sensor.test", "240.5", {"friendly_name": "Test"})

    coord = MaxMinDataUpdateCoordinator(hass, config_entry)
    coord.tracked_data["weekly"] = {"max": None, "min": None, "start": None, "end": None, "last_reset": None}

    sensor = DeltaSensor(coord, config_entry, "Test Delta", "weekly")
    sensor.hass = hass
    sensor.entity_id = "sensor.test_delta"

    # Restored entity state contains only delta value (legacy or trimmed recorder attrs).
    mock_last_state = State(
        "sensor.test_delta",
        "14.3",
        attributes={
            "config_entry_id": "test_entry",
        },
    )

    with patch("custom_components.max_min.sensor.RestoreEntity.async_get_last_state", return_value=mock_last_state):
        await sensor.async_added_to_hass()

    assert coord.tracked_data["weekly"]["end"] == pytest.approx(240.5)
    assert coord.tracked_data["weekly"]["start"] == pytest.approx(226.2)
    assert sensor.native_value == pytest.approx(14.3)


# ===================================================================
# NR-16  Delta survives restart when source unavailable at boot
# ===================================================================

@pytest.mark.asyncio
@freeze_time("2026-04-07 18:30:00", tz_offset=0)
async def test_nr16_delta_survives_restart_source_unavailable():
    """Delta must NOT drop to 0 when source sensor is unavailable at startup.

    Regression test for the bug where:
    1. first_refresh sees source as unavailable → last_reset never set
    2. _check_watchdog triggers a false reset → _pending_start_reanchor set
    3. Entity restore correctly sets start/end
    4. But first state change honoured _pending_start_reanchor → start=end=current → delta=0
    """
    hass = _hass("unavailable")

    entry = _entry()
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"), \
         patch("custom_components.max_min.coordinator.async_track_state_change_event"):
        await coordinator.async_config_entry_first_refresh()

    # After first_refresh with unavailable source, no false reset should have
    # happened (catch-up is deferred to start_listeners).
    assert PERIOD_DAILY not in coordinator._pending_start_reanchor

    # Simulate entity restore (as RestoreEntity would do after platform setup)
    coordinator.update_restored_data(PERIOD_DAILY, "start", 100.0, "2026-04-07T00:00:00+00:00")
    coordinator.update_restored_data(PERIOD_DAILY, "end", 110.5, "2026-04-07T00:00:00+00:00")

    # Now start listeners (as __init__.py does after platform setup)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"), \
         patch("custom_components.max_min.coordinator.async_track_state_change_event"):
        coordinator.start_listeners()

    # No false reset should have happened (last_reset is current period)
    assert PERIOD_DAILY not in coordinator._pending_start_reanchor

    # Delta must be preserved
    assert coordinator.get_value(PERIOD_DAILY, "start") == 100.0
    assert coordinator.get_value(PERIOD_DAILY, "end") == 110.5

    # Simulate first sensor state change after boot
    hass.states.get.return_value = Mock(state="111.0", attributes={"friendly_name": "Test"})
    event = Mock()
    event.data = {"new_state": Mock(state="111.0", attributes={})}
    coordinator._handle_sensor_change(event)

    # Delta must NOT have dropped to 0
    assert coordinator.get_value(PERIOD_DAILY, "start") == 100.0
    assert coordinator.get_value(PERIOD_DAILY, "end") == 111.0
