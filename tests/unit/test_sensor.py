"""Test sensor platform."""

from unittest.mock import Mock, patch

import pytest

from custom_components.max_min.const import CONF_SENSOR_ENTITY, CONF_DEVICE_ID
from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.sensor import MaxSensor, MinSensor
from homeassistant.helpers import device_registry as dr


@pytest.fixture
def coordinator():
    """Mock coordinator."""
    coord = Mock(spec=MaxMinDataUpdateCoordinator)
    coord.max_value = 15.0
    coord.min_value = 5.0
    coord.hass = Mock()
    coord.hass.states.get.return_value = Mock(state="10")
    coord.hass.states.get.return_value.attributes = {
        "unit_of_measurement": "°C",
        "device_class": "measurement"
    }
    return coord

@pytest.mark.asyncio
async def test_sensor_device_info(coordinator):
    """Test sensor with device info."""
    config_entry = Mock()
    config_entry.entry_id = "test_entry"
    config_entry.options = {}
    config_entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_DEVICE_ID: "test_device_id"
    }

    # Mock device registry
    device_registry = Mock()
    device = Mock()
    device.identifiers = {("test_domain", "test_id")}
    device.connections = {("mac", "00:00:00:00:00:00")}
    device_registry.async_get.return_value = device
    
    # We need to mock dr.async_get to return our mock registry
    with patch("homeassistant.helpers.device_registry.async_get", return_value=device_registry):
        sensor = MaxSensor(coordinator, config_entry, "Test Max")
        
        # device_info is a property that calls the registry
        device_info = sensor.device_info
        
        assert device_info is not None
        assert device_info["identifiers"] == {("test_domain", "test_id")}
        assert device_info["connections"] == {("mac", "00:00:00:00:00:00")}
        
        device_registry.async_get.assert_called_with("test_device_id")

        # Test MinSensor device info as well to cover that code path
        min_sensor = MinSensor(coordinator, config_entry, "Test Min")
        min_device_info = min_sensor.device_info
        assert min_device_info is not None
        assert min_device_info["identifiers"] == {("test_domain", "test_id")}


@pytest.mark.asyncio
async def test_sensor_no_device_info(coordinator):
    """Test sensor without device info."""
    config_entry = Mock()
    config_entry.entry_id = "test_entry"
    config_entry.options = {}
    config_entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test"
    }
    
    sensor = MaxSensor(coordinator, config_entry, "Test Max")
    assert sensor.device_info is None


@pytest.fixture
def config_entry():
    """Mock config entry."""
    entry = Mock()
    entry.entry_id = "test_entry"
    entry.data = {CONF_SENSOR_ENTITY: "sensor.test"}
    return entry


@pytest.fixture
def hass():
    """Mock hass."""
    hass = Mock()
    # Mock source sensor with unit
    source_state = Mock()
    source_state.attributes = {
        "unit_of_measurement": "°C",
        "device_class": "measurement"
    }
    hass.states.get.return_value = source_state
    return hass


def test_max_sensor(coordinator, config_entry, hass):
    """Test max sensor."""
    # Set hass on coordinator
    coordinator.hass = hass
    
    sensor = MaxSensor(coordinator, config_entry, "Test Daily Max")
    assert sensor.native_value == 15.0
    assert sensor.available is True
    assert sensor.name == "Test Daily Max"
    assert sensor.unique_id == "test_entry_max"
    assert sensor._attr_native_unit_of_measurement == "°C"


def test_min_sensor(coordinator, config_entry, hass):
    """Test min sensor."""
    coordinator.hass = hass
    
    sensor = MinSensor(coordinator, config_entry, "Test Daily Min")
    assert sensor.native_value == 5.0
    assert sensor.available is True
    assert sensor.name == "Test Daily Min"
    assert sensor.unique_id == "test_entry_min"
    assert sensor._attr_native_unit_of_measurement == "°C"


def test_sensor_unavailable(coordinator, config_entry, hass):
    """Test sensor unavailable."""
    coordinator.hass = hass
    coordinator.max_value = None
    coordinator.min_value = None

    max_sensor = MaxSensor(coordinator, config_entry, "Max Test")
    min_sensor = MinSensor(coordinator, config_entry, "Min Test")

    assert max_sensor.available is False
    assert min_sensor.available is False


def test_sensor_no_unit(coordinator, config_entry, hass):
    """Test sensor without unit."""
    # Mock source sensor without unit
    source_state = Mock()
    source_state.attributes = {}
    hass.states.get.return_value = source_state
    coordinator.hass = hass
    
    sensor = MaxSensor(coordinator, config_entry, "Max Test")
    assert sensor.unit_of_measurement is None


def test_max_sensor_no_hass(coordinator, config_entry):
    """Test max sensor without hass."""
    # coordinator.hass is already None
    coordinator.hass = None
    sensor = MaxSensor(coordinator, config_entry, "Max Test")
    assert sensor.unit_of_measurement is None


def test_min_sensor_no_hass(coordinator, config_entry):
    """Test min sensor without hass."""
    # coordinator.hass is already None
    coordinator.hass = None
    sensor = MinSensor(coordinator, config_entry, "Min Test")
    assert sensor.unit_of_measurement is None


def test_sensor_source_unavailable(coordinator, config_entry, hass):
    """Test sensor when source sensor is unavailable."""
    hass.states.get.return_value = None
    coordinator.hass = hass
    
    sensor = MaxSensor(coordinator, config_entry, "Max Test")
    assert sensor.unit_of_measurement is None


def test_max_sensor_device_class(coordinator, config_entry, hass):
    """Test max sensor device class."""
    coordinator.hass = hass
    sensor = MaxSensor(coordinator, config_entry, "Max Test")
    assert sensor.device_class == "measurement"


def test_min_sensor_device_class(coordinator, config_entry, hass):
    """Test min sensor device class."""
    coordinator.hass = hass
    sensor = MinSensor(coordinator, config_entry, "Min Test")
    assert sensor.device_class == "measurement"


def test_sensor_attributes(coordinator, config_entry, hass):
    """Test sensor attributes."""
    coordinator.hass = hass
    max_sensor = MaxSensor(coordinator, config_entry, "Max Test")
    min_sensor = MinSensor(coordinator, config_entry, "Min Test")

    # Check that sensors have proper attributes
    assert hasattr(max_sensor, "_attr_name")
    assert hasattr(max_sensor, "_attr_unique_id")
    assert hasattr(max_sensor, "_attr_device_class")
    assert hasattr(max_sensor, "_attr_native_unit_of_measurement")

    assert hasattr(min_sensor, "_attr_name")
    assert hasattr(min_sensor, "_attr_unique_id")
    assert hasattr(min_sensor, "_attr_device_class")
    assert hasattr(min_sensor, "_attr_native_unit_of_measurement")