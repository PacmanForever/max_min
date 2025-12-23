"""Test sensor platform."""

from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.max_min import DOMAIN
from custom_components.max_min.const import CONF_PERIOD, CONF_SENSOR_ENTITY, CONF_TYPES, PERIOD_DAILY, TYPE_MAX, TYPE_MIN
from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.sensor import async_setup_entry


@pytest.fixture
def config_entry():
    """Mock config entry."""
    entry = Mock()
    entry.entry_id = "test_entry"
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIOD: PERIOD_DAILY,
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
    coordinator.max_value = 10.0
    coordinator.min_value = 5.0
    coordinator.hass = hass  # Add hass to coordinator mock

    hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}
    hass.states.get.return_value = Mock(attributes={"friendly_name": "Test Sensor"})

    async_add_entities = AsyncMock()

    await async_setup_entry(hass, config_entry, async_add_entities)

    # Check that entities were added
    assert async_add_entities.called
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 2
    assert entities[0].name == "Max Test Sensor Diari"
    assert entities[1].name == "Min Test Sensor Diari"