"""Test that configured initial values are enforced after restore and reset."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_INITIAL_MAX,
    CONF_INITIAL_MIN,
    CONF_PERIODS,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    PERIOD_DAILY,
    PERIOD_YEARLY,
    TYPE_MAX,
    TYPE_MIN,
)


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


def _make_config_entry(periods=None, initial_max=None, initial_min=None, period_initials=None):
    """Create a mock config entry with optional initial values."""
    entry = MagicMock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: periods or [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX, TYPE_MIN],
    }
    entry.options = {}
    entry.entry_id = "test_entry"
    entry.title = "Test"

    # Set global initial values
    if initial_max is not None:
        entry.options[CONF_INITIAL_MAX] = initial_max
    if initial_min is not None:
        entry.options[CONF_INITIAL_MIN] = initial_min

    # Set per-period initial values
    if period_initials:
        for period, vals in period_initials.items():
            if "max" in vals:
                entry.options[f"{period}_{CONF_INITIAL_MAX}"] = vals["max"]
            if "min" in vals:
                entry.options[f"{period}_{CONF_INITIAL_MIN}"] = vals["min"]

    return entry


def test_restore_max_below_configured_initial(hass):
    """Test that restored max value below configured initial is overridden."""
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"max": 45.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Verify initial max is set
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 45.0

    # Simulate restore with a lower value (e.g. 13.107 from previous state)
    coordinator.update_restored_data(
        PERIOD_YEARLY, "max", 13.107,
        last_reset=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    # The configured initial (45.0) should be enforced as floor
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 45.0


def test_enforce_max_floor_after_data_corruption(hass):
    """Test enforcement when tracked_data max drops below configured initial.

    Simulates a scenario where tracked_data gets a value below the configured
    initial (e.g. after a reset or data corruption), then restore triggers
    enforcement.
    """
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"max": 45.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Manually set tracked_data below the configured initial
    # (simulates post-reset or corrupted state)
    coordinator.tracked_data[PERIOD_YEARLY]["max"] = 10.0

    # Restore with value still below configured initial
    coordinator.update_restored_data(
        PERIOD_YEARLY, "max", 12.0,
        last_reset=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    # Value was 10, restore sets it to 12 (12 > 10), but enforcement
    # brings it back up to 45 (configured floor)
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 45.0


def test_enforce_min_ceiling_after_data_corruption(hass):
    """Test enforcement when tracked_data min rises above configured initial.

    Simulates a scenario where tracked_data gets a value above the configured
    initial min (e.g. after a reset), then restore triggers enforcement.
    """
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"min": -5.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Manually set tracked_data above the configured initial min
    coordinator.tracked_data[PERIOD_YEARLY]["min"] = 10.0

    # Restore with value still above configured initial
    coordinator.update_restored_data(
        PERIOD_YEARLY, "min", 8.0,
        last_reset=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    # Value was 10, restore sets it to 8 (8 < 10), but enforcement
    # brings it back down to -5.0 (configured ceiling)
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] == -5.0


def test_restore_max_above_configured_initial(hass):
    """Test that restored max value above configured initial is kept."""
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"max": 45.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Simulate restore with a higher value
    coordinator.update_restored_data(
        PERIOD_YEARLY, "max", 50.0,
        last_reset=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    # The restored value (50.0) is higher, should be kept
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 50.0


def test_restore_min_above_configured_initial(hass):
    """Test that restored min value above configured initial is overridden."""
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"min": -5.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Verify initial min is set
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] == -5.0

    # Manually set min above configured so restoration triggers enforcement
    coordinator.tracked_data[PERIOD_YEARLY]["min"] = 20.0

    # Simulate restore with a higher value (e.g. 3.0, still above -5)
    coordinator.update_restored_data(
        PERIOD_YEARLY, "min", 3.0,
        last_reset=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    # The configured initial (-5.0) should be enforced as ceiling
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] == -5.0


def test_restore_min_below_configured_initial(hass):
    """Test that restored min value below configured initial is kept."""
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"min": -5.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Simulate restore with a lower value
    coordinator.update_restored_data(
        PERIOD_YEARLY, "min", -10.0,
        last_reset=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    # The restored value (-10.0) is lower, should be kept
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] == -10.0


def test_configured_initials_stored(hass):
    """Test that _configured_initials stores the values from config."""
    config_entry = _make_config_entry(
        periods=[PERIOD_DAILY, PERIOD_YEARLY],
        period_initials={
            PERIOD_DAILY: {"max": 0.0, "min": 100.0},
            PERIOD_YEARLY: {"max": 45.0},
        },
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    assert coordinator._configured_initials[PERIOD_DAILY]["max"] == 0.0
    assert coordinator._configured_initials[PERIOD_DAILY]["min"] == 100.0
    assert coordinator._configured_initials[PERIOD_YEARLY]["max"] == 45.0
    assert coordinator._configured_initials[PERIOD_YEARLY]["min"] is None


def test_no_configured_initial_does_not_enforce(hass):
    """Test that without configured initial, restore works normally."""
    config_entry = _make_config_entry(periods=[PERIOD_DAILY])
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # No configured initial → max starts as None
    assert coordinator._configured_initials[PERIOD_DAILY]["max"] is None

    # Restore sets the value normally
    coordinator.update_restored_data(
        PERIOD_DAILY, "max", 13.107,
        last_reset=datetime(2026, 2, 8, 0, 0, 0, tzinfo=timezone.utc),
    )
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 13.107


def test_configured_initial_zero_is_enforced(hass):
    """Test that configured initial value of 0.0 is correctly enforced (not treated as None)."""
    config_entry = _make_config_entry(
        periods=[PERIOD_DAILY],
        period_initials={PERIOD_DAILY: {"max": 0.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 0.0

    # Restore with a negative value — should keep it since -5 < 0
    coordinator.update_restored_data(
        PERIOD_DAILY, "max", -5.0,
        last_reset=datetime(2026, 2, 8, 0, 0, 0, tzinfo=timezone.utc),
    )
    # -5.0 < 0.0 → enforced back to 0.0
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 0.0


def test_restore_without_last_reset_ignored_when_period_initialized(hass):
    """Test that restored data without last_reset is ignored when coordinator
    already has period data initialized (from first_refresh).

    This prevents stale values from a previous day bleeding into the new period
    when the restored state doesn't carry last_reset info.
    """
    config_entry = _make_config_entry(periods=[PERIOD_DAILY])
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Simulate first_refresh having set the period data
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 0.0,
        "min": 0.0,
        "start": 0.0,
        "end": 0.0,
        "last_reset": datetime(2026, 2, 8, 0, 0, 0, tzinfo=timezone.utc),
    }

    # Restore a stale max value (2.18 from yesterday) WITHOUT last_reset
    coordinator.update_restored_data(PERIOD_DAILY, "max", 2.18, last_reset=None)

    # Should NOT override — no last_reset means we can't verify it's current
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 0.0


def test_restore_without_last_reset_applied_when_period_not_initialized(hass):
    """Test that restored data without last_reset IS applied when coordinator
    hasn't initialized the period yet (last_reset is None).
    """
    config_entry = _make_config_entry(periods=[PERIOD_DAILY])
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Period has no last_reset (not yet initialized by first_refresh)
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": None,
        "min": None,
        "start": None,
        "end": None,
    }

    # Restore without last_reset — should apply since period isn't initialized
    coordinator.update_restored_data(PERIOD_DAILY, "max", 15.0, last_reset=None)

    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 15.0


# ---------------------------------------------------------------------------
# _handle_reset — enforce configured initial values
# ---------------------------------------------------------------------------


def test_handle_reset_enforces_initial_max(hass):
    """Test that _handle_reset applies configured initial max as floor.

    When sensor value (13.107) is below configured initial max (45.0),
    the reset should use the configured initial instead.
    """
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"max": 45.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Set max to a high value (simulating pre-reset accumulated data)
    coordinator.tracked_data[PERIOD_YEARLY]["max"] = 100.0

    # Sensor currently reads 13.107 (below configured initial of 45)
    hass.states.get.return_value = Mock(
        state="13.107", attributes={"friendly_name": "Test"}
    )

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_reset(
            datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc), PERIOD_YEARLY
        )

    # Max should be 45.0 (configured initial), not 13.107
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 45.0
    # start/end should be the actual sensor value
    assert coordinator.tracked_data[PERIOD_YEARLY]["start"] == 13.107
    assert coordinator.tracked_data[PERIOD_YEARLY]["end"] == 13.107


def test_handle_reset_enforces_initial_min(hass):
    """Test that _handle_reset applies configured initial min as ceiling.

    When sensor value (10.0) is above configured initial min (-5.0),
    the reset should use the configured initial instead.
    """
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"min": -5.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Sensor currently reads 10.0 (above configured initial min of -5.0)
    hass.states.get.return_value = Mock(
        state="10.0", attributes={"friendly_name": "Test"}
    )

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_reset(
            datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc), PERIOD_YEARLY
        )

    # Min should be -5.0 (configured initial), not 10.0
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] == -5.0


def test_handle_reset_keeps_sensor_value_when_more_extreme_than_initial(hass):
    """Test that _handle_reset keeps sensor value when it's more extreme than initial.

    Max: sensor value (50.0) > initial max (45.0) → keep 50.0
    Min: sensor value (-10.0) < initial min (-5.0) → keep -10.0
    """
    config_entry = _make_config_entry(
        periods=[PERIOD_DAILY],
        period_initials={PERIOD_DAILY: {"max": 45.0, "min": -5.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    hass.states.get.return_value = Mock(
        state="50.0", attributes={"friendly_name": "Test"}
    )

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_reset(
            datetime(2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc), PERIOD_DAILY
        )

    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 50.0

    # Now test with sensor value below initial min
    hass.states.get.return_value = Mock(
        state="-10.0", attributes={"friendly_name": "Test"}
    )

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_reset(
            datetime(2026, 2, 10, 0, 0, 0, tzinfo=timezone.utc), PERIOD_DAILY
        )

    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == -10.0


def test_handle_reset_with_sensor_unavailable_uses_initial(hass):
    """Test that _handle_reset uses configured initial when sensor is unavailable."""
    config_entry = _make_config_entry(
        periods=[PERIOD_DAILY],
        period_initials={PERIOD_DAILY: {"max": 45.0, "min": -5.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Sensor unavailable → current_val = None
    hass.states.get.return_value = Mock(state="unavailable", attributes={})

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_reset(
            datetime(2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc), PERIOD_DAILY
        )

    # With sensor unavailable, should still apply configured initials
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 45.0
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == -5.0


def test_handle_reset_without_initials_uses_sensor_value(hass):
    """Test that _handle_reset works normally when no initials are configured."""
    config_entry = _make_config_entry(periods=[PERIOD_DAILY])
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    hass.states.get.return_value = Mock(
        state="13.107", attributes={"friendly_name": "Test"}
    )

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_reset(
            datetime(2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc), PERIOD_DAILY
        )

    # Without initials, should use sensor value directly
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 13.107
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 13.107


def test_handle_reset_initial_max_zero_is_enforced(hass):
    """Test that configured initial max of 0.0 is correctly enforced after reset."""
    config_entry = _make_config_entry(
        periods=[PERIOD_DAILY],
        period_initials={PERIOD_DAILY: {"max": 0.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Sensor reads a negative value
    hass.states.get.return_value = Mock(
        state="-3.5", attributes={"friendly_name": "Test"}
    )

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_reset(
            datetime(2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc), PERIOD_DAILY
        )

    # Max should be 0.0 (configured floor), not -3.5
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 0.0


# ---------------------------------------------------------------------------
# first_refresh — enforce configured initial values
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_refresh_enforces_initial_max(hass):
    """Test that first_refresh applies configured initial max as floor.
    
    When sensor value (13.107) is below configured initial max (45.0),
    first refresh should enforce the configured initial.
    """
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"max": 45.0}},
    )
    
    # Sensor reads 13.107 (below configured initial of 45)
    hass.states.get.return_value = Mock(
        state="13.107", attributes={"friendly_name": "Test"}
    )
    
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    
    with patch("custom_components.max_min.coordinator.async_track_state_change_event"), \
         patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        await coordinator.async_config_entry_first_refresh()
    
    # Max should be 45.0 (configured floor), not 13.107
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 45.0


@pytest.mark.asyncio
async def test_first_refresh_enforces_initial_min(hass):
    """Test that first_refresh applies configured initial min as ceiling."""
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"min": -5.0}},
    )
    
    # Sensor reads 10.0 (above configured initial min of -5.0)
    hass.states.get.return_value = Mock(
        state="10.0", attributes={"friendly_name": "Test"}
    )
    
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    
    with patch("custom_components.max_min.coordinator.async_track_state_change_event"), \
         patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        await coordinator.async_config_entry_first_refresh()
    
    # Min should be -5.0 (configured ceiling), not 10.0
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] == -5.0


@pytest.mark.asyncio
async def test_first_refresh_keeps_sensor_value_when_more_extreme(hass):
    """Test that first_refresh keeps sensor value when it's more extreme than initial."""
    config_entry = _make_config_entry(
        periods=[PERIOD_DAILY],
        period_initials={PERIOD_DAILY: {"max": 45.0, "min": -5.0}},
    )
    
    # Sensor reads 50.0 (above initial max of 45.0)
    hass.states.get.return_value = Mock(
        state="50.0", attributes={"friendly_name": "Test"}
    )
    
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    
    with patch("custom_components.max_min.coordinator.async_track_state_change_event"), \
         patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        await coordinator.async_config_entry_first_refresh()
    
    # Should keep the more extreme sensor value
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 50.0
    
    # Now test with sensor value below initial min
    hass.states.get.return_value = Mock(
        state="-10.0", attributes={"friendly_name": "Test"}
    )
    
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    
    with patch("custom_components.max_min.coordinator.async_track_state_change_event"), \
         patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        await coordinator.async_config_entry_first_refresh()
    
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == -10.0
