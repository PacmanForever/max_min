"""Test sensor platform."""

from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.max_min import DOMAIN
from custom_components.max_min.const import CONF_PERIODS, CONF_SENSOR_ENTITY, CONF_TYPES, PERIOD_DAILY, TYPE_MAX, TYPE_MIN
from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.sensor import async_setup_entry
from unittest.mock import patch

@pytest.fixture
def config_entry():
    """Mock config entry."""
    entry = Mock()
    entry.entry_id = "test_entry"
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX, TYPE_MIN],
    }
    entry.options = {}
    return entry


@pytest.fixture
def hass():
    """Mock hass."""
    hass = Mock()
    hass.config.time_zone = Mock()
    hass.loop = Mock()
    hass.loop.time.return_value = 1000.0  # Mock current time
    hass.data = {"custom_components": {}}
    hass.states.get.return_value = Mock(state="10.0", attributes={"friendly_name": "Test Sensor"})
    return hass


@pytest.mark.asyncio
async def test_sensor_setup(hass, config_entry):
    """Test sensor setup."""
    # Mock coordinator
    coordinator = Mock(spec=MaxMinDataUpdateCoordinator)
    coordinator.get_value.return_value = 10.0 # Simplify mock for now
    coordinator.hass = hass  # Add hass to coordinator mock

    hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}
    hass.states.get.return_value = Mock(attributes={"friendly_name": "Test Sensor"})

    async_add_entities = Mock()

    with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get, \
            patch("homeassistant.helpers.device_registry.async_get") as mock_dr_get, \
            patch("homeassistant.helpers.entity_registry.async_entries_for_config_entry", return_value=[]):
        mock_registry = Mock()
        mock_registry.async_get_entity_id.return_value = None  # Use return_value to mock a method call
        # Mock async_get to return None so it falls back to state machine for name
        mock_registry.async_get.return_value = None
        mock_er_get.return_value = mock_registry

        mock_dev_reg = Mock()
        mock_dev_reg.devices = {} # Empty devices dict
        mock_dr_get.return_value = mock_dev_reg
        
        await async_setup_entry(hass, config_entry, async_add_entities)

    # Check that entities were added
    assert async_add_entities.called
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 2
    assert entities[0].name == "Test Sensor Daily Max"
    assert entities[1].name == "Test Sensor Daily Min"


@pytest.mark.asyncio
async def test_device_cleanup(hass, config_entry):
    """Test device cleanup when device_id is missing from config."""
    # Ensure no device_id in options or data
    config_entry.options = {}
    config_entry.data = {
         CONF_SENSOR_ENTITY: "sensor.test",
         CONF_PERIODS: [PERIOD_DAILY],
         CONF_TYPES: [TYPE_MAX],
         # No device_id
    }
    
    coordinator = Mock(spec=MaxMinDataUpdateCoordinator)
    coordinator.get_value.return_value = 10.0
    coordinator.hass = hass
    hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}
    
    async_add_entities = Mock()
    
    # Mock entities that have device_id set
    mock_entity_entry = Mock()
    mock_entity_entry.entity_id = "sensor.test_daily_max"
    mock_entity_entry.device_id = "old_device_id"
    
    # Mock device registry having a device linked to this config entry
    mock_device = Mock()
    mock_device.id = "old_device_id"
    mock_device.config_entries = {config_entry.entry_id}

    with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get, \
         patch("homeassistant.helpers.device_registry.async_get") as mock_dr_get, \
         patch("homeassistant.helpers.entity_registry.async_entries_for_config_entry", return_value=[mock_entity_entry]):
         
        mock_registry = Mock()
        mock_registry.async_get.return_value = None
        mock_er_get.return_value = mock_registry
        
        mock_dev_reg = Mock()
        mock_dev_reg.devices = {"old_device_id": mock_device}
        mock_dr_get.return_value = mock_dev_reg
        
        await async_setup_entry(hass, config_entry, async_add_entities)
        
        # Verify entity was updated to remove device_id
        mock_registry.async_update_entity.assert_called_with("sensor.test_daily_max", device_id=None)
        
        # Verify device was updated to remove config entry connection
        mock_dev_reg.async_update_device.assert_called_with("old_device_id", remove_config_entry_id=config_entry.entry_id)