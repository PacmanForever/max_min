
import pytest
from unittest.mock import MagicMock
from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_SENSOR_ENTITY, CONF_PERIODS, CONF_TYPES, 
    PERIOD_YEARLY, PERIOD_ALL_TIME, TYPE_MAX, TYPE_MIN,
    PERIOD_DAILY, PERIOD_WEEKLY, PERIOD_MONTHLY,
    CONF_INITIAL_MAX
)

def test_initial_value_all_time_repro():
    hass = MagicMock()
    
    # 1. Setup entry with All-time initial max = 45.0
    entry = MagicMock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY, PERIOD_ALL_TIME],
        CONF_TYPES: [TYPE_MAX],
    }
    # User puts 45.0 in options
    entry.options = {
        f"{PERIOD_ALL_TIME}_{CONF_INITIAL_MAX}": 45.0
    }
    entry.entry_id = "test_entry"
    
    # Current sensor state is 13.107
    mock_state = MagicMock()
    mock_state.state = "13.107"
    hass.states.get.return_value = mock_state
    
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    
    # 2. Simulate refresh (as done in async_setup_entry)
    # This should call first_refresh which calls _check_consistency
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    from homeassistant.util import dt as dt_util
    
    # Force first refresh manually (simulated)
    # Initialize info for all periods (mirroring first_refresh logic)
    current_value = 13.107
    now = dt_util.now()
    for period, data in coordinator.tracked_data.items():
        if data["max"] is None or current_value > data["max"]:
            data["max"] = current_value
        
        # Enforce initials
        initials = coordinator._configured_initials.get(period, {})
        initial_max = initials.get("max")
        if initial_max is not None and (data["max"] is None or data["max"] < initial_max):
            data["max"] = initial_max

    coordinator._check_consistency()
    
    print(f"Daily Max: {coordinator.get_value(PERIOD_DAILY, TYPE_MAX)}")
    print(f"All-time Max: {coordinator.get_value(PERIOD_ALL_TIME, TYPE_MAX)}")
    
    assert coordinator.get_value(PERIOD_ALL_TIME, TYPE_MAX) == 45.0

if __name__ == "__main__":
    test_initial_value_all_time_repro()
