
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock

from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_SENSOR_ENTITY, CONF_PERIODS, CONF_TYPES, 
    PERIOD_YEARLY, PERIOD_ALL_TIME, TYPE_MAX, TYPE_MIN,
    PERIOD_DAILY, PERIOD_WEEKLY, PERIOD_MONTHLY
)

@pytest.fixture
def hass():
    hass = Mock()
    hass.config.time_zone = timezone.utc
    return hass

def _make_entry(periods):
    entry = MagicMock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: periods,
        CONF_TYPES: [TYPE_MAX, TYPE_MIN],
    }
    entry.options = {}
    entry.entry_id = "test_entry"
    entry.title = "Test"
    return entry

def test_cross_period_consistency_propagation(hass):
    # Setup with Yearly and All-time
    periods = [PERIOD_YEARLY, PERIOD_ALL_TIME]
    entry = _make_entry(periods)
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    
    # Simulate Yearly restoring -1.3 (e.g. from history)
    # And All-time being "new" or having a higher record (e.g. 2.9)
    coordinator.tracked_data[PERIOD_YEARLY]["min"] = -1.3
    coordinator.tracked_data[PERIOD_ALL_TIME]["min"] = 2.9
    
    # Run consistency check (manually or via restore sim)
    coordinator._check_consistency()
    
    # All-time must pick up the -1.3 from Yearly
    assert coordinator.get_value(PERIOD_ALL_TIME, "min") == -1.3
    assert coordinator.get_value(PERIOD_YEARLY, "min") == -1.3

def test_consistency_on_restore(hass):
    periods = [PERIOD_YEARLY, PERIOD_ALL_TIME]
    entry = _make_entry(periods)
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    
    # Yearly restores -5
    coordinator.update_restored_data(PERIOD_YEARLY, "min", -5.0)
    
    # All-time should now have -5 even if its own restore hasn't happened or was higher
    assert coordinator.get_value(PERIOD_ALL_TIME, "min") == -5.0

def test_no_backwards_propagation(hass):
    # Broader period having record shouldn't affect narrower period
    periods = [PERIOD_DAILY, PERIOD_ALL_TIME]
    entry = _make_entry(periods)
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    
    coordinator.tracked_data[PERIOD_ALL_TIME]["min"] = -10.0
    coordinator.tracked_data[PERIOD_DAILY]["min"] = 0.0
    
    coordinator._check_consistency()
    
    # Daily stays 0.0 (it hasn't hit -10 today)
    assert coordinator.get_value(PERIOD_DAILY, "min") == 0.0
    # All-time stays -10.0
    assert coordinator.get_value(PERIOD_ALL_TIME, "min") == -10.0
