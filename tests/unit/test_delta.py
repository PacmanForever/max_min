"""Test Delta sensor implementation."""
from unittest.mock import Mock, patch

import pytest
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.max_min.const import (
    CONF_PERIODS,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    DOMAIN,
    PERIOD_DAILY,
    TYPE_DELTA,
)
from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from datetime import timezone
from custom_components.max_min.sensor import DeltaSensor
from pytest_homeassistant_custom_component.common import MockConfigEntry

@pytest.fixture
def hass():
    """Mock hass."""
    hass = Mock()
    hass.config.time_zone = timezone.utc
    hass.states.get.return_value = Mock(state="10.0")
    hass.states.async_set = Mock() # Helper we used in test
    hass.data = {"custom_components": {}}
    # Mock loop time for any internal calls that might slip through
    hass.loop.time.return_value = 1000.0
    return hass

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock external dependencies to avoid event loop usage."""
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"), \
         patch("custom_components.max_min.coordinator.async_track_state_change_event"):
        yield

@pytest.fixture
def mock_delta_config_entry():
    """Create a mock config entry with Delta type."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.test_source",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
        title="Test Sensor",
        unique_id="sensor.test_source"
    )

@pytest.mark.asyncio
async def test_delta_sensor_initialization(hass):
    """Test proper initialization of the Delta sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.source",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
    )
    
    # Mock source sensor state
    hass.states.async_set("sensor.source", "10.0")
    
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    sensor = DeltaSensor(coordinator, entry, "Delta Sensor", PERIOD_DAILY)
    sensor.entity_id = "sensor.delta_sensor"
    
    # Validate initial state
    # value = end - start = 10.0 - 10.0 = 0.0
    assert sensor.native_value == 0.0
    
    # Check attributes
    attrs = sensor.extra_state_attributes
    assert attrs["start_value"] == 10.0
    assert attrs["end_value"] == 10.0

@pytest.mark.asyncio
async def test_delta_sensor_updates(hass):
    """Test that delta sensor updates correctly when source changes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.source",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
    )
    hass.states.async_set("sensor.source", "10.0")
    
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    # 1. Update source to 15.0
    # Expected: start=10.0 (unchanged), end=15.0, delta=5.0
    hass.states.get.return_value = Mock(state="15.0")
    
    # Simulating the event manually mainly because async_track_state_change_event 
    # might not fire as expected in this isolated unit test environment without full loop.
    event = Mock()
    event.data = {"new_state": hass.states.get("sensor.source")}
    coordinator._handle_sensor_change(event)
    
    assert coordinator.get_value(PERIOD_DAILY, "start") == 10.0
    assert coordinator.get_value(PERIOD_DAILY, "end") == 15.0
    
    sensor = DeltaSensor(coordinator, entry, "Delta Sensor", PERIOD_DAILY)
    assert sensor.native_value == 5.0

@pytest.mark.asyncio
async def test_delta_sensor_reset(hass):
    """Test that delta sensor resets correctly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.source",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
    )
    hass.states.async_set("sensor.source", "10.0")
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    # Move to 20.0
    hass.states.get.return_value = Mock(state="20.0")
    event = Mock()
    event.data = {"new_state": hass.states.get("sensor.source")}
    coordinator._handle_sensor_change(event)
    
    assert coordinator.get_value(PERIOD_DAILY, "start") == 10.0
    assert coordinator.get_value(PERIOD_DAILY, "end") == 20.0
    
    # Perform Reset
    # Reset should set start = current (20.0), end = current (20.0) -> Delta = 0.0
    from homeassistant.util import dt as dt_util
    now = dt_util.now()
    coordinator._handle_reset(now, PERIOD_DAILY)
    
    assert coordinator.get_value(PERIOD_DAILY, "start") == 20.0
    assert coordinator.get_value(PERIOD_DAILY, "end") == 20.0
    
    sensor = DeltaSensor(coordinator, entry, "Delta Sensor", PERIOD_DAILY)
    assert sensor.native_value == 0.0

@pytest.mark.asyncio
async def test_delta_negative_change(hass):
    """Test delta with decreasing values."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.source",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
    )
    hass.states.async_set("sensor.source", "10.0")
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    # Drop to 5.0
    hass.states.get.return_value = Mock(state="5.0")
    event = Mock()
    event.data = {"new_state": hass.states.get("sensor.source")}
    coordinator._handle_sensor_change(event)
    
    # Delta should be 5.0 - 10.0 = -5.0
    sensor = DeltaSensor(coordinator, entry, "Delta Sensor", PERIOD_DAILY)
    assert sensor.native_value == -5.0
