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
    """Test that restored max below initial is kept (initials are one-shot, not enforced on restore)."""
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

    # Initials are one-shot: 45.0 was set in __init__, restore 13.107 < 45.0 → keeps 45.0
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 45.0


def test_enforce_max_floor_after_data_corruption(hass):
    """Test that restore does NOT re-enforce initials (one-shot semantics).

    After __init__ seeds max=45.0, if tracked_data is manually set to 10.0
    and restore brings 12.0, the result is 12.0 (restore wins, no enforcement).
    """
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"max": 45.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Manually set tracked_data below the configured initial
    coordinator.tracked_data[PERIOD_YEARLY]["max"] = 10.0

    # Restore with value above current but below initial
    coordinator.update_restored_data(
        PERIOD_YEARLY, "max", 12.0,
        last_reset=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    # Initials are one-shot: no enforcement on restore. 12 > 10 → max=12
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 12.0


def test_enforce_min_ceiling_after_data_corruption(hass):
    """Test that restore does NOT re-enforce initials for min (one-shot semantics)."""
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"min": -5.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Manually set tracked_data above the configured initial min
    coordinator.tracked_data[PERIOD_YEARLY]["min"] = 10.0

    # Restore with value below current but above initial
    coordinator.update_restored_data(
        PERIOD_YEARLY, "min", 8.0,
        last_reset=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    # Initials are one-shot: no enforcement on restore. 8 < 10 → min=8
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] == 8.0


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
    """Test restore min above initial: restore does not re-enforce (one-shot)."""
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"min": -5.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Verify initial min is set
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] == -5.0

    # Manually set min above configured so restoration scenario is clear
    coordinator.tracked_data[PERIOD_YEARLY]["min"] = 20.0

    # Simulate restore with a value (3.0) still above initial (-5.0)
    coordinator.update_restored_data(
        PERIOD_YEARLY, "min", 3.0,
        last_reset=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    # Initials are one-shot: 3.0 < 20.0 → min=3.0 (no enforcement back to -5.0)
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] == 3.0


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
        last_reset=datetime.now(timezone.utc),
    )
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 13.107


def test_configured_initial_zero_is_enforced(hass):
    """Test that configured initial value of 0.0 works at creation (one-shot)."""
    config_entry = _make_config_entry(
        periods=[PERIOD_DAILY],
        period_initials={PERIOD_DAILY: {"max": 0.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 0.0

    # Restore with a negative value — no enforcement, but -5 < 0 so max stays 0
    coordinator.update_restored_data(
        PERIOD_DAILY, "max", -5.0,
        last_reset=datetime(2026, 2, 8, 0, 0, 0, tzinfo=timezone.utc),
    )
    # -5.0 < 0.0 (current) → max stays 0.0 (restore only updates if more extreme)
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 0.0


def test_restore_without_last_reset_ignored_when_period_initialized(hass):
    """Test that restored data without last_reset is applied if more extreme (v0.3.24+).

    Since v0.3.24, we allow restoration without last_reset metadata to prevent
    data loss during integration updates/reloads. The more extreme value wins.
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

    # Restore a higher max value (2.18) WITHOUT last_reset
    coordinator.update_restored_data(PERIOD_DAILY, "max", 2.18, last_reset=None)

    # SHOULD apply because it's more extreme (v0.3.24 change to prevent data loss)
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 2.18


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
# _perform_reset — enforce configured initial values
# ---------------------------------------------------------------------------


def test_perform_reset_enforces_initial_max(hass):
    """Test that _perform_reset uses seed only (initials are one-shot).

    After reset, max = seed. Initials do NOT act as floor on resets.
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
        coordinator._perform_reset(
            datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc), PERIOD_YEARLY
        )

    # Max should be seed (13.107), NOT 45.0 (initials are one-shot)
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 13.107
    assert coordinator.tracked_data[PERIOD_YEARLY]["start"] == 13.107
    assert coordinator.tracked_data[PERIOD_YEARLY]["end"] == 13.107


def test_perform_reset_enforces_initial_min(hass):
    """Test that _perform_reset uses seed only for min (initials are one-shot)."""
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"min": -5.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Sensor currently reads 10.0
    hass.states.get.return_value = Mock(
        state="10.0", attributes={"friendly_name": "Test"}
    )

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._perform_reset(
            datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc), PERIOD_YEARLY
        )

    # Min should be seed (10.0), NOT -5.0 (initials are one-shot)
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] == 10.0


def test_perform_reset_keeps_sensor_value_when_more_extreme_than_initial(hass):
    """Test that _perform_reset keeps sensor value when it's more extreme than initial.

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
        coordinator._perform_reset(
            datetime(2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc), PERIOD_DAILY
        )

    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 50.0

    # Now test with sensor value below initial min
    hass.states.get.return_value = Mock(
        state="-10.0", attributes={"friendly_name": "Test"}
    )

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._perform_reset(
            datetime(2026, 2, 10, 0, 0, 0, tzinfo=timezone.utc), PERIOD_DAILY
        )

    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == -10.0


def test_perform_reset_with_sensor_unavailable_uses_initial(hass):
    """Test _perform_reset when sensor unavailable: seed is None, max/min=None."""
    config_entry = _make_config_entry(
        periods=[PERIOD_DAILY],
        period_initials={PERIOD_DAILY: {"max": 45.0, "min": -5.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Sensor unavailable → seed = fallback to end_val or None
    hass.states.get.return_value = Mock(state="unavailable", attributes={})
    # No end value → seed is None
    coordinator.tracked_data[PERIOD_DAILY]["end"] = None

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._perform_reset(
            datetime(2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc), PERIOD_DAILY
        )

    # With sensor unavailable and no end_val, seed=None → max/min=None
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] is None
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] is None


def test_perform_reset_without_initials_uses_sensor_value(hass):
    """Test that _perform_reset works normally when no initials are configured."""
    config_entry = _make_config_entry(periods=[PERIOD_DAILY])
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    hass.states.get.return_value = Mock(
        state="13.107", attributes={"friendly_name": "Test"}
    )

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._perform_reset(
            datetime(2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc), PERIOD_DAILY
        )

    # Without initials, should use sensor value directly
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 13.107
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 13.107


def test_perform_reset_initial_max_zero_is_enforced(hass):
    """Test that reset with initial 0.0 uses seed, not initial (one-shot)."""
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
        coordinator._perform_reset(
            datetime(2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc), PERIOD_DAILY
        )

    # Max should be seed (-3.5), NOT 0.0 (initials are one-shot)
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == -3.5


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
