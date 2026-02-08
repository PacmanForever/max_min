def test_delta_sensor_missing_start_end():

    def test_delta_sensor_device_class_and_state_class():

        def test_delta_sensor_extra_state_attributes_edge():
            """Test DeltaSensor.extra_state_attributes edge cases."""
            class DummyCoordinator:
                def get_value(self, period, key):
                    # Simulate all None
                    return None
                hass = None

            config_entry = type("ConfigEntry", (), {"entry_id": "abc", "data": {"sensor_entity": "sensor.x"}})()
            sensor = DeltaSensor(DummyCoordinator(), config_entry, "Test Delta", "daily")
            attrs = sensor.extra_state_attributes
            # Should be empty dict
            assert isinstance(attrs, dict)
            assert attrs == {}
        """Test DeltaSensor.device_class and state_class edge cases."""
        class DummyCoordinator:
            def get_value(self, period, key):
                return None
            hass = None

        config_entry = type("ConfigEntry", (), {"entry_id": "abc", "data": {"sensor_entity": "sensor.x"}})()
        sensor = DeltaSensor(DummyCoordinator(), config_entry, "Test Delta", "daily")
        # No hass, device_class is None; state_class always "measurement"
        assert sensor.device_class is None
        assert sensor.state_class == "measurement"

        # Hass present, but state missing attributes
        class Hass:
            def __init__(self):
                self.states = self
            def get(self, entity):
                class State:
                    attributes = {}
                return State()

        dummy = DummyCoordinator()
        dummy.hass = Hass()
        sensor = DeltaSensor(dummy, config_entry, "Test Delta", "daily")
        assert sensor.device_class is None
        assert sensor.state_class == "measurement"
    """Test DeltaSensor with missing start/end values."""
    class DummyCoordinator:
        def get_value(self, period, key):
            # Only 'start' is missing
            if key == "start":
                return None
            if key == "end":
                return 5.0
            return None
        hass = None

    config_entry = type("ConfigEntry", (), {"entry_id": "abc", "data": {"sensor_entity": "sensor.x"}})()
    sensor = DeltaSensor(DummyCoordinator(), config_entry, "Test Delta", "daily")
    assert sensor.native_value is None
    assert not sensor.available
"""Test sensor platform."""

from unittest.mock import Mock, patch

import pytest

from custom_components.max_min.const import (
    CONF_SENSOR_ENTITY, 
    CONF_DEVICE_ID,
    PERIOD_DAILY,
    TYPE_MAX,
    TYPE_MIN
)
from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.sensor import MaxSensor, MinSensor, DeltaSensor
from homeassistant.helpers import device_registry as dr


@pytest.fixture
def coordinator():
    """Mock coordinator."""
    coord = Mock(spec=MaxMinDataUpdateCoordinator)
    def get_value(period, type_):
        if type_ == TYPE_MAX:
            return 15.0
        elif type_ == TYPE_MIN:
            return 5.0
        elif type_ == "start":
            return 4.0
        elif type_ == "end":
            return 6.0
        else:
            return None
    coord.get_value.side_effect = get_value
    coord.hass = Mock()
    coord.hass.states.get.return_value = Mock(state="10")
    coord.hass.states.get.return_value.attributes = {
        "unit_of_measurement": "°C",
        "device_class": "measurement"
    }
    return coord
def test_delta_sensor(coordinator, config_entry, hass):
    """Test delta sensor basic functionality."""
    coordinator.hass = hass
    sensor = DeltaSensor(coordinator, config_entry, "Test Daily Delta", PERIOD_DAILY)
    assert sensor.native_value == 2.0
    assert sensor.available is True
    assert sensor.name == "Test Daily Delta"
    assert sensor.unique_id == "test_entry_daily_delta"
    assert sensor.native_unit_of_measurement == "°C"
    attrs = sensor.extra_state_attributes
    assert attrs["start_value"] == 4.0
    assert attrs["end_value"] == 6.0
def test_delta_sensor_unavailable(coordinator, config_entry, hass):
    """Test delta sensor unavailable."""
    coordinator.hass = hass
    coordinator.get_value.side_effect = lambda period, type_: None
    sensor = DeltaSensor(coordinator, config_entry, "Delta Test", PERIOD_DAILY)
    assert sensor.native_value is None
    assert sensor.available is False
def test_delta_sensor_no_unit(coordinator, config_entry, hass):
    """Test delta sensor without unit."""
    source_state = Mock()
    source_state.attributes = {}
    hass.states.get.return_value = source_state
    coordinator.hass = hass
    sensor = DeltaSensor(coordinator, config_entry, "Delta Test", PERIOD_DAILY)
    assert sensor.native_unit_of_measurement is None
def test_delta_sensor_no_hass(coordinator, config_entry):
    """Test delta sensor without hass."""
    coordinator.hass = None
    sensor = DeltaSensor(coordinator, config_entry, "Delta Test", PERIOD_DAILY)
    assert sensor.native_unit_of_measurement is None
def test_delta_sensor_attributes(coordinator, config_entry, hass):
    """Test delta sensor attributes."""
    coordinator.hass = hass
    sensor = DeltaSensor(coordinator, config_entry, "Delta Test", PERIOD_DAILY)
    attrs = sensor.extra_state_attributes
    assert "start_value" in attrs
    assert "end_value" in attrs

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
        sensor = MaxSensor(coordinator, config_entry, "Test Max", PERIOD_DAILY)
        
        # device_info is a property that calls the registry
        device_info = sensor.device_info
        
        assert device_info is not None
        assert device_info["identifiers"] == {("test_domain", "test_id")}
        assert device_info["connections"] == {("mac", "00:00:00:00:00:00")}
        
        device_registry.async_get.assert_called_with("test_device_id")

        # Test MinSensor device info as well to cover that code path
        min_sensor = MinSensor(coordinator, config_entry, "Test Min", PERIOD_DAILY)
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
    
    sensor = MaxSensor(coordinator, config_entry, "Test Max", PERIOD_DAILY)
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
    
    sensor = MaxSensor(coordinator, config_entry, "Test Daily Max", PERIOD_DAILY)
    assert sensor.native_value == 15.0
    assert sensor.available is True
    assert sensor.name == "Test Daily Max"
    assert sensor.unique_id == "test_entry_daily_max"
    assert sensor.native_unit_of_measurement == "°C"


def test_min_sensor(coordinator, config_entry, hass):
    """Test min sensor."""
    coordinator.hass = hass
    
    sensor = MinSensor(coordinator, config_entry, "Test Daily Min", PERIOD_DAILY)
    assert sensor.native_value == 5.0
    assert sensor.available is True
    assert sensor.name == "Test Daily Min"
    assert sensor.unique_id == "test_entry_daily_min"
    assert sensor.native_unit_of_measurement == "°C"


def test_sensor_unavailable(coordinator, config_entry, hass):
    """Test sensor unavailable."""
    coordinator.hass = hass
    coordinator.get_value.return_value = None
    coordinator.get_value.side_effect = None # Remove side_effect to return None

    max_sensor = MaxSensor(coordinator, config_entry, "Max Test", PERIOD_DAILY)
    min_sensor = MinSensor(coordinator, config_entry, "Min Test", PERIOD_DAILY)

    assert max_sensor.available is False
    assert min_sensor.available is False


def test_sensor_no_unit(coordinator, config_entry, hass):
    """Test sensor without unit."""
    # Mock source sensor without unit
    source_state = Mock()
    source_state.attributes = {}
    hass.states.get.return_value = source_state
    coordinator.hass = hass
    
    sensor = MaxSensor(coordinator, config_entry, "Max Test", PERIOD_DAILY)
    assert sensor.unit_of_measurement is None


def test_max_sensor_no_hass(coordinator, config_entry):
    """Test max sensor without hass."""
    # coordinator.hass is already None
    coordinator.hass = None
    sensor = MaxSensor(coordinator, config_entry, "Max Test", PERIOD_DAILY)
    assert sensor.unit_of_measurement is None


def test_min_sensor_no_hass(coordinator, config_entry):
    """Test min sensor without hass."""
    # coordinator.hass is already None
    coordinator.hass = None
    sensor = MinSensor(coordinator, config_entry, "Min Test", PERIOD_DAILY)
    assert sensor.unit_of_measurement is None


def test_sensor_source_unavailable(coordinator, config_entry, hass):
    """Test sensor when source sensor is unavailable."""
    hass.states.get.return_value = None
    coordinator.hass = hass
    
    sensor = MaxSensor(coordinator, config_entry, "Max Test", PERIOD_DAILY)
    assert sensor.unit_of_measurement is None


def test_max_sensor_device_class(coordinator, config_entry, hass):
    """Test max sensor device class."""
    coordinator.hass = hass
    sensor = MaxSensor(coordinator, config_entry, "Max Test", PERIOD_DAILY)
    assert sensor.device_class == "measurement"


def test_min_sensor_device_class(coordinator, config_entry, hass):
    """Test min sensor device class."""
    coordinator.hass = hass
    sensor = MinSensor(coordinator, config_entry, "Min Test", PERIOD_DAILY)
    assert sensor.device_class == "measurement"


def test_sensor_attributes(coordinator, config_entry, hass):
    """Test sensor attributes."""
    coordinator.hass = hass
    max_sensor = MaxSensor(coordinator, config_entry, "Max Test", PERIOD_DAILY)
    min_sensor = MinSensor(coordinator, config_entry, "Min Test", PERIOD_DAILY)

    # Check that sensors have proper attributes
    assert hasattr(max_sensor, "_attr_name")
    assert hasattr(max_sensor, "_attr_unique_id")
    assert max_sensor.device_class == "measurement"
    assert hasattr(min_sensor, "device_class")


@pytest.mark.asyncio
async def test_min_sensor_no_device_info(coordinator):
    """Test min sensor without device info."""
    config_entry = Mock()
    config_entry.entry_id = "test_entry"
    config_entry.options = {}
    config_entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test"
    }
    
    sensor = MinSensor(coordinator, config_entry, "Test Min", PERIOD_DAILY)
    assert sensor.device_info is None
