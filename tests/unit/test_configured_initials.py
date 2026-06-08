"""Test that configured initial values are enforced after restore and reset."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_INITIAL_DELTA,
    CONF_INITIAL_MAX,
    CONF_INITIAL_MIN,
    CONF_PERIODS,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    PERIOD_DAILY,
    PERIOD_WEEKLY,
    PERIOD_YEARLY,
    TYPE_DELTA,
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


def _make_config_entry(periods=None, initial_max=None, initial_min=None, period_initials=None, types=None):
    """Create a mock config entry with optional initial values."""
    entry = MagicMock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: periods or [PERIOD_DAILY],
        CONF_TYPES: types or [TYPE_MAX, TYPE_MIN],
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
            if "delta" in vals:
                entry.options[f"{period}_{CONF_INITIAL_DELTA}"] = vals["delta"]

    return entry


def test_restore_max_below_configured_initial(hass):
    """On restart, restore is accepted and apply_pending_initials skips that type."""
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"max": 45.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # After __init__, max is None (initials NOT seeded to tracked_data)
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] is None
    # But _configured_initials stores the initial
    assert coordinator._configured_initials[PERIOD_YEARLY]["max"] == 45.0

    # Simulate restore with 13.107 (RestoreEntity accepted it)
    coordinator.update_restored_data(
        PERIOD_YEARLY, "max", 13.107,
        last_reset=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    # Restore accepted → type marked
    assert (PERIOD_YEARLY, "max") in coordinator._restore_accepted
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 13.107

    # apply_pending_initials skips restored max → max stays 13.107
    coordinator.apply_pending_initials()
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 13.107


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
    """On restart, restore min is accepted; apply_pending_initials skips."""
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"min": -5.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # After __init__, min is None
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] is None

    # Simulate restore with 3.0
    coordinator.update_restored_data(
        PERIOD_YEARLY, "min", 3.0,
        last_reset=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    # Restore accepted → min=3.0, period marked
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] == 3.0

    # apply_pending_initials skips → min stays 3.0 (NOT -5.0)
    coordinator.apply_pending_initials()
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
    """Initial value 0.0 is applied via apply_pending_initials for new entries."""
    config_entry = _make_config_entry(
        periods=[PERIOD_DAILY],
        period_initials={PERIOD_DAILY: {"max": 0.0}},
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # After __init__, max is None
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] is None

    # No restore → apply_pending_initials applies initial 0.0
    coordinator.apply_pending_initials()
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
async def test_first_refresh_then_apply_initials_new_entry(hass):
    """Full flow for new entry: first_refresh → apply_pending_initials.

    first_refresh only uses sensor value. apply_pending_initials
    enforces initials because no restore happened.
    """
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"max": 45.0, "min": -5.0}},
    )

    # Sensor reads 13.107
    hass.states.get.return_value = Mock(
        state="13.107", attributes={"friendly_name": "Test"}
    )

    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    with patch("custom_components.max_min.coordinator.async_track_state_change_event"), \
         patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        await coordinator.async_config_entry_first_refresh()

    # first_refresh only seeds with sensor value
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 13.107
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] == 13.107

    # No restore → apply_pending_initials applies initials
    coordinator.apply_pending_initials()
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 45.0
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


# ---------------------------------------------------------------------------
# apply_pending_initials — one-shot post-restore override
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_pending_initials_overrides_restored_delta(hass):
    """apply_pending_initials forces delta initials AFTER restore overwrites first_refresh."""
    config_entry = _make_config_entry(
        periods=[PERIOD_DAILY, PERIOD_WEEKLY],
        types=[TYPE_DELTA],
        period_initials={
            PERIOD_DAILY: {"delta": 100.0},
            PERIOD_WEEKLY: {"delta": 500.0},
        },
    )

    # Sensor reads 5.0
    hass.states.get.return_value = Mock(
        state="5.0", attributes={"friendly_name": "Test"}
    )

    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    with patch("custom_components.max_min.coordinator.async_track_state_change_event"), \
         patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        await coordinator.async_config_entry_first_refresh()

    # first_refresh sets start = 5.0 - 100 = -95, end = 5.0  →  delta = 100
    assert coordinator.tracked_data[PERIOD_DAILY]["start"] == pytest.approx(-95.0)
    assert coordinator.tracked_data[PERIOD_WEEKLY]["start"] == pytest.approx(-495.0)

    # Simulate RestoreEntity overwriting start/end with old stale data
    coordinator.tracked_data[PERIOD_DAILY]["start"] = 1.0
    coordinator.tracked_data[PERIOD_DAILY]["end"] = 3.0
    coordinator.tracked_data[PERIOD_WEEKLY]["start"] = 10.0
    coordinator.tracked_data[PERIOD_WEEKLY]["end"] = 20.0

    # apply_pending_initials must win over restored data
    coordinator.apply_pending_initials()

    assert coordinator.tracked_data[PERIOD_DAILY]["start"] == pytest.approx(-95.0)
    assert coordinator.tracked_data[PERIOD_DAILY]["end"] == 5.0
    assert coordinator.tracked_data[PERIOD_WEEKLY]["start"] == pytest.approx(-495.0)
    assert coordinator.tracked_data[PERIOD_WEEKLY]["end"] == 5.0


@pytest.mark.asyncio
async def test_apply_pending_initials_skips_when_restore_accepted(hass):
    """apply_pending_initials does NOT apply initials for types with valid restore."""
    config_entry = _make_config_entry(
        periods=[PERIOD_DAILY],
        period_initials={PERIOD_DAILY: {"max": 100.0, "min": -50.0}},
    )

    hass.states.get.return_value = Mock(
        state="20.0", attributes={"friendly_name": "Test"}
    )

    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    with patch("custom_components.max_min.coordinator.async_track_state_change_event"), \
         patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        await coordinator.async_config_entry_first_refresh()

    # Simulate RestoreEntity via update_restored_data (marks _restore_accepted)
    coordinator.update_restored_data(
        PERIOD_DAILY, "max", 30.0,
        last_reset=datetime.now(timezone.utc),
    )
    coordinator.update_restored_data(
        PERIOD_DAILY, "min", 5.0,
        last_reset=datetime.now(timezone.utc),
    )

    # apply_pending_initials skips because both types were restored
    coordinator.apply_pending_initials()

    # Restored values win — initials NOT applied
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 30.0
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 5.0


@pytest.mark.asyncio
async def test_apply_pending_initials_clears_configured_initials(hass):
    """apply_pending_initials clears _configured_initials (one-shot)."""
    config_entry = _make_config_entry(
        periods=[PERIOD_DAILY],
        types=[TYPE_DELTA],
        period_initials={PERIOD_DAILY: {"delta": 200.0}},
    )

    hass.states.get.return_value = Mock(
        state="10.0", attributes={"friendly_name": "Test"}
    )

    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    with patch("custom_components.max_min.coordinator.async_track_state_change_event"), \
         patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        await coordinator.async_config_entry_first_refresh()

    assert coordinator._configured_initials  # populated before apply

    coordinator.apply_pending_initials()

    assert coordinator._configured_initials == {}  # cleared after apply

    # Calling again should be a no-op
    coordinator.tracked_data[PERIOD_DAILY]["start"] = 999.0
    coordinator.apply_pending_initials()
    assert coordinator.tracked_data[PERIOD_DAILY]["start"] == 999.0  # unchanged


# ---------------------------------------------------------------------------
# Regression tests — ensure initials never re-apply on restart
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_regression_restart_does_not_reapply_initials(hass):
    """REGRESSION: On restart, restored data must override initials.

    Scenario: initial_max=45, sensor=10, real tracked max=30 (from before restart).
    After the full flow (first_refresh → restore → apply_pending_initials),
    max must be 30 (restored), NOT 45 (initial).
    """
    config_entry = _make_config_entry(
        periods=[PERIOD_DAILY],
        period_initials={PERIOD_DAILY: {"max": 45.0, "min": -5.0}},
    )

    hass.states.get.return_value = Mock(
        state="10.0", attributes={"friendly_name": "Test"}
    )

    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    with patch("custom_components.max_min.coordinator.async_track_state_change_event"), \
         patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        await coordinator.async_config_entry_first_refresh()

    # Simulate RestoreEntity restoring real values from before restart
    coordinator.update_restored_data(
        PERIOD_DAILY, "max", 30.0,
        last_reset=datetime.now(timezone.utc),
    )
    coordinator.update_restored_data(
        PERIOD_DAILY, "min", 2.0,
        last_reset=datetime.now(timezone.utc),
    )

    # apply_pending_initials must SKIP restored period
    coordinator.apply_pending_initials()

    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 30.0  # NOT 45.0
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 2.0   # NOT -5.0


@pytest.mark.asyncio
async def test_regression_restart_after_reset_no_initial_rebleed(hass):
    """REGRESSION: After a period reset, initials must NOT reappear on restart.

    Scenario: initial_max=45. Period reset happened → max=sensor_value=10.
    HA restarts. Restore brings max=10. apply_pending_initials must SKIP.
    If initials rebled, max would go back to 45 — breaking one-shot semantics.
    """
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"max": 45.0}},
    )

    hass.states.get.return_value = Mock(
        state="10.0", attributes={"friendly_name": "Test"}
    )

    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    with patch("custom_components.max_min.coordinator.async_track_state_change_event"), \
         patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        await coordinator.async_config_entry_first_refresh()

    # Simulate RestoreEntity restoring post-reset value of 10.0
    coordinator.update_restored_data(
        PERIOD_YEARLY, "max", 10.0,
        last_reset=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    coordinator.apply_pending_initials()

    # Must be 10.0 (restored), NOT 45.0 (initial)
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 10.0


@pytest.mark.asyncio
async def test_regression_delta_not_reapplied_on_restart(hass):
    """REGRESSION: Delta initial must not recompute start on restart."""
    config_entry = _make_config_entry(
        periods=[PERIOD_DAILY],
        types=[TYPE_DELTA],
        period_initials={PERIOD_DAILY: {"delta": 500.0}},
    )

    hass.states.get.return_value = Mock(
        state="1000.0", attributes={"friendly_name": "Test"}
    )

    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    with patch("custom_components.max_min.coordinator.async_track_state_change_event"), \
         patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        await coordinator.async_config_entry_first_refresh()

    # first_refresh: start = 1000 - 500 = 500, end = 1000
    assert coordinator.tracked_data[PERIOD_DAILY]["start"] == 500.0

    # Simulate RestoreEntity restoring real values (start=800, end=1050)
    coordinator.update_restored_data(
        PERIOD_DAILY, "start", 800.0,
        last_reset=datetime.now(timezone.utc),
    )
    coordinator.update_restored_data(
        PERIOD_DAILY, "end", 1050.0,
        last_reset=datetime.now(timezone.utc),
    )

    coordinator.apply_pending_initials()

    # Restored values must be kept (delta = 1050 - 800 = 250, NOT 500)
    assert coordinator.tracked_data[PERIOD_DAILY]["start"] == 800.0
    assert coordinator.tracked_data[PERIOD_DAILY]["end"] == 1050.0


def test_regression_surgery_blocks_restore_enables_initial(hass):
    """REGRESSION: Surgical reset blocks restore → initial applied via apply_pending_initials."""
    config_entry = _make_config_entry(
        periods=[PERIOD_DAILY, PERIOD_YEARLY],
        period_initials={PERIOD_YEARLY: {"max": 45.0}},
    )
    # Surgical reset on yearly_max
    config_entry.options["reset_history"] = ["yearly_max"]

    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    # Try restoring both periods
    coordinator.update_restored_data(PERIOD_DAILY, "max", 10.0)
    coordinator.update_restored_data(PERIOD_YEARLY, "max", 10.0)  # blocked by surgery

    # Daily restored, yearly blocked
    assert (PERIOD_DAILY, "max") in coordinator._restore_accepted
    assert (PERIOD_YEARLY, "max") not in coordinator._restore_accepted

    coordinator.apply_pending_initials()

    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 10.0   # restored
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 45.0  # initial (surgery blocked restore)


@pytest.mark.asyncio
async def test_regression_surgery_on_max_still_applies_initial_when_min_restores(hass):
    """Surgical max reset must not be canceled by a valid min restore in the same period."""
    config_entry = _make_config_entry(
        periods=[PERIOD_YEARLY],
        types=[TYPE_MAX, TYPE_MIN],
        period_initials={PERIOD_YEARLY: {"max": 85.0}},
    )
    config_entry.options["reset_history"] = ["yearly_max"]

    hass.states.get.return_value = Mock(
        state="0.0", attributes={"friendly_name": "Test Sensor"}
    )

    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)

    with patch("custom_components.max_min.coordinator.async_track_state_change_event"), \
         patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        await coordinator.async_config_entry_first_refresh()

    coordinator.update_restored_data(
        PERIOD_YEARLY, "max", 10.0,
        last_reset=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    coordinator.update_restored_data(
        PERIOD_YEARLY, "min", 0.0,
        last_reset=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    assert (PERIOD_YEARLY, "max") not in coordinator._restore_accepted
    assert (PERIOD_YEARLY, "min") in coordinator._restore_accepted

    coordinator.apply_pending_initials()

    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 85.0
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] == 0.0
