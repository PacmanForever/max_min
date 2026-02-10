import pytest
from unittest.mock import MagicMock
from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_SENSOR_ENTITY, CONF_PERIODS, CONF_TYPES, 
    PERIOD_YEARLY, TYPE_MAX, CONF_INITIAL_MAX, PERIOD_DAILY
)

# No pytest markers, no fixtures, just a manual test runner
def verify_hardened_logic():
    """Manual verification of the hardened logic using Mocks."""
    print("Testing hardened initial values logic...")
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_YEARLY],
        CONF_TYPES: [TYPE_MAX],
    }
    entry.options = {f"{PERIOD_YEARLY}_initial_max": 45.0}
    entry.entry_id = "test_entry"
    entry.title = "Test"

    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_YEARLY]["max"] = 13.107

    val = coordinator.get_value(PERIOD_YEARLY, "max")
    assert val == 45.0, f"Expected 45.0, got {val}"
    print("✓ Hardened logic OK")

    print("Testing consistency vs initials...")
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY, PERIOD_YEARLY],
        CONF_TYPES: [TYPE_MAX],
    }
    entry.options = {f"{PERIOD_YEARLY}_initial_max": 45.0}
    entry.entry_id = "test_entry"

    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_DAILY]["max"] = 15.0
    coordinator.tracked_data[PERIOD_YEARLY]["max"] = None

    coordinator._check_consistency()
    
    val = coordinator.get_value(PERIOD_YEARLY, "max")
    assert val == 45.0, f"Expected 45.0 (Initial), got {val} (Consistency result)"
    print("✓ Consistency protection OK")

def test_reset_history_flag():
    """Verify that reset_history flag blocks restoration."""
    print("Testing reset_history flag...")
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_YEARLY],
        CONF_TYPES: [TYPE_MAX],
    }
    entry.options = {
        f"{PERIOD_YEARLY}_initial_max": 45.0,
        "reset_history": True
    }
    entry.entry_id = "test_entry"

    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    # Simulator sensor restoration
    coordinator.update_restored_data(PERIOD_YEARLY, "max", 100.0)
    
    # Should be at Initial value, NOT restored 100.0
    # Because __init__ sets it to 45.0 and update_restored_data is blocked
    val = coordinator.tracked_data[PERIOD_YEARLY]["max"]
    assert val == 45.0, f"Expected 45.0 (Initial), got {val} (restoration was probably NOT blocked)"
    
    # But get_value still reports 45.0
    assert coordinator.get_value(PERIOD_YEARLY, "max") == 45.0
    print("✓ Reset history flag OK")

def test_surgical_reset_automatic():
    """Verify that only the changed sensor is reset."""
    print("Testing surgical reset detection...")
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test", 
        CONF_PERIODS: [PERIOD_DAILY, PERIOD_YEARLY],
        CONF_TYPES: [TYPE_MAX]
    }
    # Pretend Yearly Max was just updated, but Daily wasn't
    entry.options = {
        f"{PERIOD_YEARLY}_initial_max": 45.0,
        "reset_history": ["yearly_max"]
    }
    entry.entry_id = "test_entry"
    entry.title = "Test"

    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    
    # Try restoring both
    coordinator.update_restored_data(PERIOD_DAILY, "max", 10.0)
    coordinator.update_restored_data(PERIOD_YEARLY, "max", 10.0)
    
    # Daily should be 10 (Restored)
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 10.0
    
    # Yearly should be 45 (Restored 10 was IGNORED because it was in reset_history)
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 45.0
    
    print("✓ Surgical reset OK")

if __name__ == "__main__":
    verify_hardened_logic()
    test_reset_history_flag()
    test_surgical_reset_automatic()
