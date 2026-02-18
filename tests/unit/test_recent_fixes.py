"""Tests for recent fixes (v0.3.22-v0.3.25)."""
from unittest.mock import Mock, AsyncMock
import pytest
from datetime import datetime

from custom_components.max_min.const import (
    CONF_SENSOR_ENTITY,
    CONF_PERIODS,
    CONF_TYPES,
    CONF_RESET_HISTORY,
    PERIOD_DAILY,
    PERIOD_WEEKLY,
    PERIOD_YEARLY,
    TYPE_MAX,
    TYPE_MIN,
    TYPE_DELTA,
)
from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.sensor import DeltaSensor


class TestFloatingPointRounding:
    """Test floating point precision fixes (v0.3.23)."""

    def test_first_refresh_rounds_values(self):
        """Test that coordinator__init__ rounds values from sensor state."""
        ha = Mock()
        entry = Mock()
        entry.entry_id = "test"
        entry.data = {
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_MAX],
        }
        entry.options = {}

        # Simulate sensor with floating point noise
        ha.states.get.return_value = Mock(
            state="45.99999999999999",
            attributes={"friendly_name": "Test"}
        )

        coordinator = MaxMinDataUpdateCoordinator(ha, entry)
        
        # Value initially None during __init__ (populated later async)
        # Instead, simulate inline rounding by calling _handle_sensor_change manually
        event = Mock()
        event.data = {
            "new_state": Mock(
                state="45.99999999999999",
                attributes={"state_class": None}
            )
        }
        
        # Set initial timestamps to avoid comparison errors
        from homeassistant.util import dt as dt_util
        now = dt_util.now()
        coordinator.tracked_data[PERIOD_DAILY]["last_reset"] = now
        coordinator.tracked_data[PERIOD_DAILY]["max"] = 10.0
        
        coordinator._handle_sensor_change(event)
        
        # After handling change, value should be rounded
        assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 46.0

    def test_sensor_change_rounds_values(self):
        """Test that _handle_sensor_change rounds values."""
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
        
        # Use timezone-aware datetime
        from homeassistant.util import dt as dt_util
        now = dt_util.now()
        
        coordinator.tracked_data[PERIOD_DAILY] = {
            "max": 10.0,
            "min": 10.0,
            "start": 10.0,
            "end": 10.0,
            "last_reset": now
        }

        # Simulate event with floating point noise
        event = Mock()
        event.data = {
            "new_state": Mock(
                state="46.00000000000001",
                attributes={"state_class": None}
            )
        }

        coordinator._handle_sensor_change(event)
        
        # Value should be rounded to 4 decimals
        assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 46.0


class TestSurgicalReset:
    """Test surgical reset functionality (v0.3.22)."""

    def test_reset_only_changed_sensor(self):
        """Test that only changed sensors are reset."""
        ha = Mock()
        ha.states.get.return_value = Mock(state="10.0", attributes={})
        
        entry = Mock()
        entry.entry_id = "test"
        entry.data = {
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY, PERIOD_YEARLY],
            CONF_TYPES: [TYPE_MAX],
        }
        # Simulate that yearly_max was changed
        entry.options = {
            CONF_RESET_HISTORY: ["yearly_max"]
        }

        coordinator = MaxMinDataUpdateCoordinator(ha, entry)

        # Try to restore both
        coordinator.update_restored_data(PERIOD_DAILY, "max", 50.0)
        coordinator.update_restored_data(PERIOD_YEARLY, "max", 50.0)

        # Daily should be restored
        assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 50.0
        
        # Yearly should NOT be restored (blocked by surgical reset)
        # It keeps None (not the sensor value, because no propagation in tests)
        assert coordinator.tracked_data[PERIOD_YEARLY]["max"] is None

    def test_no_reset_when_list_empty(self):
        """Test that restoration works normally when reset list is empty."""
        ha = Mock()
        ha.states.get.return_value = Mock(state="10.0", attributes={})
        
        entry = Mock()
        entry.entry_id = "test"
        entry.data = {
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_MAX],
        }
        entry.options = {CONF_RESET_HISTORY: []}

        coordinator = MaxMinDataUpdateCoordinator(ha, entry)
        coordinator.update_restored_data(PERIOD_DAILY, "max", 100.0)

        assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 100.0

    def test_consistency_respects_reset_history(self):
        """Test that _check_consistency() does not propagate to periods in reset_history.
        
        This is the fix for the bug where surgical reset was bypassed by consistency propagation.
        """
        ha = Mock()
        ha.states.get.return_value = Mock(state="10.0", attributes={})
        
        entry = Mock()
        entry.entry_id = "test"
        entry.data = {
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY, PERIOD_YEARLY],
            CONF_TYPES: [TYPE_MAX, TYPE_MIN],
        }
        # Simulate that yearly sensors were changed
        entry.options = {
            CONF_RESET_HISTORY: ["yearly_max", "yearly_min"]
        }

        coordinator = MaxMinDataUpdateCoordinator(ha, entry)
        
        # Set daily values
        coordinator.tracked_data[PERIOD_DAILY]["max"] = 50.0
        coordinator.tracked_data[PERIOD_DAILY]["min"] = 5.0
        
        # Yearly should be None initially
        assert coordinator.tracked_data[PERIOD_YEARLY]["max"] is None
        assert coordinator.tracked_data[PERIOD_YEARLY]["min"] is None
        
        # Manually trigger consistency check (normally called by update_restored_data)
        coordinator._check_consistency()
        
        # Yearly should STILL be None (not propagated due to reset_history)
        assert coordinator.tracked_data[PERIOD_YEARLY]["max"] is None
        assert coordinator.tracked_data[PERIOD_YEARLY]["min"] is None
        
    def test_consistency_propagates_when_not_in_reset_history(self):
        """Test that _check_consistency() DOES propagate when period is NOT in reset_history."""
        ha = Mock()
        ha.states.get.return_value = Mock(state="10.0", attributes={})
        
        entry = Mock()
        entry.entry_id = "test"
        entry.data = {
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY, PERIOD_YEARLY],
            CONF_TYPES: [TYPE_MAX, TYPE_MIN],
        }
        # Empty reset history - normal propagation should work
        entry.options = {CONF_RESET_HISTORY: []}

        coordinator = MaxMinDataUpdateCoordinator(ha, entry)
        
        # Set daily values
        coordinator.tracked_data[PERIOD_DAILY]["max"] = 50.0
        coordinator.tracked_data[PERIOD_DAILY]["min"] = 5.0
        
        # Trigger consistency check
        coordinator._check_consistency()
        
        # Yearly SHOULD receive propagated values
        assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 50.0
        assert coordinator.tracked_data[PERIOD_YEARLY]["min"] == 5.0


class TestDeltaPersistence:
    """Test Delta sensor persistence (v0.3.25)."""

    @pytest.mark.asyncio
    async def test_delta_sensor_restores_start_end(self):
        """Test that DeltaSensor restores start and end values."""
        ha = Mock()
        ha.states.get.return_value = Mock(state="10.0", attributes={})
        
        entry = Mock()
        entry.entry_id = "test"
        entry.data = {
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        }
        entry.options = {}

        coordinator = MaxMinDataUpdateCoordinator(ha, entry)
        coordinator.update_restored_data = Mock(wraps=coordinator.update_restored_data)

        sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)

        # Mock last state with start/end attributes
        last_state = Mock()
        last_state.state = "5.0"
        last_state.attributes = {
            "start_value": 10.0,
            "end_value": 15.0,
            "last_reset": "2026-02-10T00:00:00+00:00"
        }
        sensor.async_get_last_state = AsyncMock(return_value=last_state)

        await sensor.async_added_to_hass()

        # Verify that restore was called for both start and end
        assert coordinator.update_restored_data.call_count == 2
        coordinator.update_restored_data.assert_any_call(
            PERIOD_DAILY, "start", 10.0, "2026-02-10T00:00:00+00:00"
        )
        coordinator.update_restored_data.assert_any_call(
            PERIOD_DAILY, "end", 15.0, "2026-02-10T00:00:00+00:00"
        )

    def test_coordinator_restores_start_end_values(self):
        """Test that coordinator properly stores start/end in update_restored_data."""
        ha = Mock()
        ha.states.get.return_value = Mock(state="10.0", attributes={})
        
        entry = Mock()
        entry.entry_id = "test"
        entry.data = {
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        }
        entry.options = {}

        coordinator = MaxMinDataUpdateCoordinator(ha, entry)

        # Restore start and end
        coordinator.update_restored_data(PERIOD_DAILY, "start", 100.0)
        coordinator.update_restored_data(PERIOD_DAILY, "end", 150.0)

        assert coordinator.tracked_data[PERIOD_DAILY]["start"] == 100.0
        assert coordinator.tracked_data[PERIOD_DAILY]["end"] == 150.0

    @pytest.mark.asyncio
    async def test_delta_sensor_available_after_restore(self):
        """Test that Delta sensor is available after restoring start/end."""
        ha = Mock()
        ha.states.get.return_value = Mock(state="10.0", attributes={})
        
        entry = Mock()
        entry.entry_id = "test"
        entry.data = {
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        }
        entry.options = {}

        coordinator = MaxMinDataUpdateCoordinator(ha, entry)
        sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)

        # Mock restoration
        last_state = Mock()
        last_state.state = "5.0"
        last_state.attributes = {"start_value": 10.0, "end_value": 15.0}
        sensor.async_get_last_state = AsyncMock(return_value=last_state)

        await sensor.async_added_to_hass()

        # Sensor should be available and calculate delta correctly
        assert sensor.available is True
        assert sensor.native_value == 5.0  # 15.0 - 10.0

    @pytest.mark.asyncio
    async def test_delta_sensor_ignores_invalid_restored_values(self):
        """Test that DeltaSensor gracefully handles invalid start/end values (ValueError)."""
        ha = Mock()
        ha.states.get.return_value = Mock(state="10.0", attributes={})
        
        entry = Mock()
        entry.entry_id = "test"
        entry.data = {
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        }
        entry.options = {}

        coordinator = MaxMinDataUpdateCoordinator(ha, entry)
        sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)

        # Mock restoration with invalid (non-numeric) values
        last_state = Mock()
        last_state.state = "5.0"
        last_state.attributes = {
            "start_value": "invalid",  # Will cause ValueError
            "end_value": "also_invalid"
        }
        sensor.async_get_last_state = AsyncMock(return_value=last_state)

        # Should not raise exception - ValueError caught and ignored
        await sensor.async_added_to_hass()

        # Sensor should be unavailable (no valid start/end)
        assert sensor.available is False
        assert sensor.native_value is None  # No valid start/end = no delta

    @pytest.mark.asyncio
    async def test_delta_sensor_restores_unit_and_keeps_it_if_source_unavailable(self):
        """Regression: Delta should keep restored unit during startup unavailability."""
        ha = Mock()
        # Source sensor unavailable at startup (common HA restart race)
        ha.states.get.return_value = Mock(state="unavailable", attributes={})

        entry = Mock()
        entry.entry_id = "test"
        entry.data = {
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        }
        entry.options = {}

        coordinator = MaxMinDataUpdateCoordinator(ha, entry)
        sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)

        last_state = Mock()
        last_state.state = "5.0"
        last_state.attributes = {
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "start_value": 10.0,
            "end_value": 15.0,
        }
        sensor.async_get_last_state = AsyncMock(return_value=last_state)

        await sensor.async_added_to_hass()

        # Must keep restored unit (no temporary empty unit)
        assert sensor.native_unit_of_measurement == "kWh"


class TestHistoryPreservation:
    """Test history preservation across reloads (v0.3.24)."""

    def test_restore_without_last_reset_allowed(self):
        """Test that restoration works even without last_reset metadata."""
        ha = Mock()
        ha.states.get.return_value = Mock(state="10.0", attributes={})
        
        entry = Mock()
        entry.entry_id = "test"
        entry.data = {
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_MAX],
        }
        entry.options = {}

        coordinator = MaxMinDataUpdateCoordinator(ha, entry)
        
        # Initialize with current value (10.0)
        coordinator.tracked_data[PERIOD_DAILY]["max"] = 10.0
        coordinator.tracked_data[PERIOD_DAILY]["last_reset"] = datetime.now()

        # Restore a higher max WITHOUT last_reset info
        # This simulates old persisted data without metadata
        coordinator.update_restored_data(PERIOD_DAILY, "max", 50.0, last_reset=None)

        # Should accept the higher value
        assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 50.0

    def test_initial_values_survive_first_refresh(self):
        """Test that configured initial values are not overwritten by first_refresh."""
        ha = Mock()
        
        entry = Mock()
        entry.entry_id = "test"
        entry.data = {
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_YEARLY],
            CONF_TYPES: [TYPE_MAX],
        }
        # User configured initial max of 45
        entry.options = {f"{PERIOD_YEARLY}_initial_max": 45.0}

        # Current sensor is at 13.0
        ha.states.get.return_value = Mock(state="13.0", attributes={})

        coordinator = MaxMinDataUpdateCoordinator(ha, entry)

        # After initialization, max should be 45 (the floor), not 13
        assert coordinator.get_value(PERIOD_YEARLY, "max") == 45.0

    def test_restored_value_not_overwritten_by_current(self):
        """Test that a restored historical max is not overwritten by current sensor value."""
        ha = Mock()
        
        entry = Mock()
        entry.entry_id = "test"
        entry.data = {
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_MAX],
        }
        entry.options = {}

        # Current sensor at reload time is 10.0
        ha.states.get.return_value = Mock(state="10.0", attributes={})

        coordinator = MaxMinDataUpdateCoordinator(ha, entry)
        
        # After init, max is None (not populated until async_first_refresh)
        assert coordinator.tracked_data[PERIOD_DAILY]["max"] is None

        # Now restore a historical max of 50.0 (simulating entity restoration)
        coordinator.update_restored_data(PERIOD_DAILY, "max", 50.0)

        # Historical max should win
        assert coordinator.get_value(PERIOD_DAILY, "max") == 50.0


class TestInitialValueEnforcement:
    """Test that initial values are always enforced (v0.3.20+)."""

    def test_get_value_enforces_floor_for_max(self):
        """Test that get_value returns initial max if internal value is lower."""
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
        
        # Manually set internal value to something lower
        coordinator.tracked_data[PERIOD_YEARLY]["max"] = 13.0

        # get_value should return the configured floor
        assert coordinator.get_value(PERIOD_YEARLY, "max") == 45.0

    def test_get_value_enforces_ceiling_for_min(self):
        """Test that get_value returns initial min if internal value is higher."""
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
        
        # Manually set internal value to something higher
        coordinator.tracked_data[PERIOD_DAILY]["min"] = 20.0

        # get_value should return the configured ceiling
        assert coordinator.get_value(PERIOD_DAILY, "min") == 5.0

    def test_consistency_cannot_override_initials(self):
        """Test that cross-period consistency cannot override configured initials."""
        ha = Mock()
        ha.states.get.return_value = Mock(state="10.0", attributes={})
        
        entry = Mock()
        entry.entry_id = "test"
        entry.data = {
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY, PERIOD_YEARLY],
            CONF_TYPES: [TYPE_MAX],
        }
        entry.options = {f"{PERIOD_YEARLY}_initial_max": 45.0}

        coordinator = MaxMinDataUpdateCoordinator(ha, entry)
        
        # Set daily max to 15
        coordinator.tracked_data[PERIOD_DAILY]["max"] = 15.0
        coordinator.tracked_data[PERIOD_YEARLY]["max"] = None

        # Trigger consistency check
        coordinator._check_consistency()

        # Even if consistency tries to propagate 15 to yearly,
        # get_value should still return the configured floor
        assert coordinator.get_value(PERIOD_YEARLY, "max") == 45.0
