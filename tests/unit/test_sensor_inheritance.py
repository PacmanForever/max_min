"""Test sensor platform."""

import pytest
from unittest.mock import Mock, patch
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
from custom_components.max_min.sensor import MaxSensor, MinSensor
from custom_components.max_min.const import (
    CONF_SENSOR_ENTITY,
    CONF_DEVICE_ID,
    PERIOD_DAILY
)

@pytest.fixture
def config_entry():
    """Mock config entry."""
    entry = Mock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_DEVICE_ID: "test_device"
    }
    entry.entry_id = "test_entry"
    return entry

@pytest.fixture
def coordinator(hass):
    """Mock coordinator."""
    coordinator = Mock()
    coordinator.hass = hass
    coordinator.max_value = 20.0
    coordinator.min_value = 5.0
    return coordinator

@pytest.fixture
def hass():
    """Mock hass."""
    hass = Mock()
    hass.states.get.return_value = Mock(
        state="10.0", 
        attributes={
            "unit_of_measurement": "°C",
            "device_class": "temperature",
            "state_class": "measurement"
        }
    )
    return hass

def test_sensor_inheritance(coordinator, config_entry, hass):
    """Test that sensors inherit attributes from source."""
    coordinator.hass = hass
    
    max_sensor = MaxSensor(coordinator, config_entry, "Max Test", PERIOD_DAILY)
    
    assert max_sensor.unit_of_measurement == "°C"
    assert max_sensor.device_class == "temperature"
    assert max_sensor.state_class == "measurement"
    
    min_sensor = MinSensor(coordinator, config_entry, "Min Test", PERIOD_DAILY)
    
    assert min_sensor.unit_of_measurement == "°C"
    assert min_sensor.device_class == "temperature"
    assert min_sensor.state_class == "measurement"

def test_sensor_defaults_if_source_missing(coordinator, config_entry, hass):
    """Test defaults when source sensor has no attributes."""
    hass.states.get.return_value = Mock(state="10.0", attributes={})
    coordinator.hass = hass
    
    max_sensor = MaxSensor(coordinator, config_entry, "Max Test", PERIOD_DAILY)
    
    # Should use defaults or None
    assert max_sensor.device_class is None # Previously "measurement"
    assert max_sensor.state_class is None  # Previously "measurement"
