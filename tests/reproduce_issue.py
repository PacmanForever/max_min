
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock
from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_SENSOR_ENTITY, CONF_PERIODS, CONF_TYPES, 
    PERIOD_YEARLY, PERIOD_ALL_TIME, TYPE_MAX, TYPE_MIN,
    PERIOD_DAILY, CONF_INITIAL_MAX
)

@pytest.fixture
def hass():
    hass = Mock()
    hass.config.time_zone = timezone.utc
    hass.states.get.return_value = Mock(state="13.107")
    return hass

def test_reproduce_yearly_initial_ignored(hass):
    # Setup with Yearly
    entry = MagicMock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        # Configured periods: Daily and Yearly
        CONF_PERIODS: [PERIOD_DAILY, PERIOD_YEARLY],
        CONF_TYPES: [TYPE_MAX],
    }
    # User entered 45.0 in Options Flow for Yearly Max
    entry.options = {
        "yearly_initial_max": 45.0,
        CONF_PERIODS: [PERIOD_DAILY, PERIOD_YEARLY],
        CONF_TYPES: [TYPE_MAX],
    }
    entry.entry_id = "test_entry"
    entry.title = "Test"
    
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    
    # Verify __init__ picked it up
    assert coordinator._configured_initials[PERIOD_YEARLY]["max"] == 45.0
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 45.0
    
    # Run first refresh (sensor value is 13.107)
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(coordinator.async_config_entry_first_refresh())
    
    # Yearly max should still be 45.0
    assert coordinator.tracked_data[PERIOD_YEARLY]["max"] == 45.0
    
    # What about Daily?
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 13.107
