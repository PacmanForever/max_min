
"""Tests for cross-period consistency propagation and surgical reset guards."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock
from conftest import make_config_entry, make_mock_hass

from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_PERIODS,
    CONF_RESET_HISTORY,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    PERIOD_YEARLY,
    PERIOD_ALL_TIME,
    TYPE_MAX,
    TYPE_MIN,
    PERIOD_DAILY,
    PERIOD_WEEKLY,
    PERIOD_MONTHLY,
)

@pytest.fixture
def hass():
    return make_mock_hass(state=None)

def _make_entry(periods):
    return make_config_entry(periods=periods, types=[TYPE_MAX, TYPE_MIN])

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

def test_max_consistency_propagation(hass):
    # Setup for Max
    periods = [PERIOD_DAILY, PERIOD_WEEKLY]
    entry = _make_entry(periods)
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    
    # Daily hits a very high value (e.g. 40)
    coordinator.tracked_data[PERIOD_DAILY]["max"] = 40.0
    # Weekly was sitting at 35
    coordinator.tracked_data[PERIOD_WEEKLY]["max"] = 35.0
    
    coordinator._check_consistency()
    
    # Weekly must be at least 40
    assert coordinator.get_value(PERIOD_WEEKLY, "max") == 40.0


def test_reset_only_changed_sensor(hass):
    """Only periods outside reset_history should accept restored values."""
    entry = make_config_entry(periods=[PERIOD_DAILY, PERIOD_YEARLY], types=[TYPE_MAX])
    entry.options = {CONF_RESET_HISTORY: ["yearly_max"]}

    coordinator = MaxMinDataUpdateCoordinator(hass, entry)

    coordinator.update_restored_data(PERIOD_DAILY, "max", 50.0)
    coordinator.update_restored_data(PERIOD_YEARLY, "max", 50.0)

    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 50.0
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] is None


def test_no_reset_when_list_empty(hass):
    """Empty reset_history keeps normal restoration behavior."""
    entry = make_config_entry(periods=[PERIOD_DAILY], types=[TYPE_MAX])
    entry.options = {CONF_RESET_HISTORY: []}

    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.update_restored_data(PERIOD_DAILY, "max", 100.0)

    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 100.0


def test_consistency_respects_reset_history(hass):
    """Consistency propagation does not bypass surgical reset history."""
    entry = make_config_entry(
        periods=[PERIOD_DAILY, PERIOD_YEARLY],
        types=[TYPE_MAX, TYPE_MIN],
    )
    entry.options = {CONF_RESET_HISTORY: ["yearly_max", "yearly_min"]}

    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_DAILY]["max"] = 50.0
    coordinator.tracked_data[PERIOD_DAILY]["min"] = 5.0

    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] is None
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] is None

    coordinator._check_consistency()

    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] is None
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] is None


def test_consistency_propagates_when_not_in_reset_history(hass):
    """Consistency propagation works normally outside reset_history."""
    entry = make_config_entry(
        periods=[PERIOD_DAILY, PERIOD_YEARLY],
        types=[TYPE_MAX, TYPE_MIN],
    )
    entry.options = {CONF_RESET_HISTORY: []}

    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_DAILY]["max"] = 50.0
    coordinator.tracked_data[PERIOD_DAILY]["min"] = 5.0

    coordinator._check_consistency()

    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 50.0
    assert coordinator.tracked_data[PERIOD_YEARLY]["min"] == 5.0


def test_consistency_propagates_without_initial_override(hass):
    """Cross-period consistency propagates freely without initial interference."""
    entry = make_config_entry(periods=[PERIOD_DAILY, PERIOD_YEARLY], types=[TYPE_MAX])
    entry.options = {f"{PERIOD_YEARLY}_initial_max": 45.0}

    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_DAILY]["max"] = 15.0
    coordinator.tracked_data[PERIOD_YEARLY]["max"] = None

    coordinator._check_consistency()

    assert coordinator.get_value(PERIOD_YEARLY, "max") == 15.0
