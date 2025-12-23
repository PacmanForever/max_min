"""Test config flow."""

from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from custom_components.max_min.config_flow import MaxMinConfigFlow, MaxMinOptionsFlow
from custom_components.max_min.const import (
    CONF_PERIOD,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    DOMAIN,
    PERIOD_DAILY,
    TYPE_MAX,
    TYPE_MIN,
)


@pytest.fixture
def hass():
    """Mock hass for config flow tests."""
    return Mock()


@pytest.mark.asyncio
async def test_config_flow_user(hass):
    """Test user config flow."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()  # Simple mock instead of async fixture

    # Mock async_set_unique_id to avoid issues
    flow.async_set_unique_id = AsyncMock()

    result = await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIOD: PERIOD_DAILY,
        CONF_TYPES: [TYPE_MAX, TYPE_MIN],
    })

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Max Min"
    assert result["data"] == {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIOD: PERIOD_DAILY,
        CONF_TYPES: [TYPE_MAX, TYPE_MIN],
    }


@pytest.mark.asyncio
async def test_config_flow_options(hass):
    """Test options flow."""
    config_entry = Mock()
    config_entry.options = {}
    
    flow = MaxMinOptionsFlow(config_entry)
    flow.hass = Mock()  # Simple mock instead of async fixture

    result = await flow.async_step_init({
        CONF_PERIOD: "weekly",
        CONF_TYPES: [TYPE_MAX],
    })

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_PERIOD: "weekly",
        CONF_TYPES: [TYPE_MAX],
    }


@pytest.mark.asyncio
async def test_config_flow_invalid_sensor(hass):
    """Test config flow with invalid sensor."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()  # Simple mock instead of async fixture

    # Mock validation - in real implementation, would check if sensor exists
    result = await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.invalid",
        CONF_PERIOD: PERIOD_DAILY,
        CONF_TYPES: [TYPE_MAX],
    })

    # Should still create entry, validation happens later
    assert result["type"] == FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
async def test_config_flow_weekly_period(hass):
    """Test config flow with weekly period."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()  # Simple mock instead of async fixture
    flow.async_set_unique_id = AsyncMock()

    result = await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIOD: "weekly",
        CONF_TYPES: [TYPE_MAX],
    })

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PERIOD] == "weekly"


@pytest.mark.asyncio
async def test_config_flow_monthly_period(hass):
    """Test config flow with monthly period."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()  # Simple mock instead of async fixture
    flow.async_set_unique_id = AsyncMock()

    result = await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIOD: "monthly",
        CONF_TYPES: [TYPE_MIN],
    })

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PERIOD] == "monthly"


@pytest.mark.asyncio
async def test_config_flow_yearly_period(hass):
    """Test config flow with yearly period."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()  # Simple mock instead of async fixture
    flow.async_set_unique_id = AsyncMock()

    result = await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIOD: "yearly",
        CONF_TYPES: [TYPE_MAX, TYPE_MIN],
    })

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PERIOD] == "yearly"


@pytest.mark.asyncio
async def test_config_flow_only_max(hass):
    """Test config flow with only max type."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()  # Simple mock instead of async fixture
    flow.async_set_unique_id = AsyncMock()

    result = await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIOD: PERIOD_DAILY,
        CONF_TYPES: [TYPE_MAX],
    })

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TYPES] == [TYPE_MAX]


@pytest.mark.asyncio
async def test_config_flow_only_min(hass):
    """Test config flow with only min type."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()  # Simple mock instead of async fixture
    flow.async_set_unique_id = AsyncMock()

    result = await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIOD: PERIOD_DAILY,
        CONF_TYPES: [TYPE_MIN],
    })

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TYPES] == [TYPE_MIN]


@pytest.mark.asyncio
async def test_options_flow_update(hass):
    """Test options flow update."""
    config_entry = Mock()
    config_entry.options = {
        CONF_PERIOD: PERIOD_DAILY,
        CONF_TYPES: [TYPE_MAX, TYPE_MIN],
    }
    
    flow = MaxMinOptionsFlow(config_entry)
    flow.hass = Mock()  # Simple mock instead of async fixture

    result = await flow.async_step_init({
        CONF_PERIOD: "weekly",
        CONF_TYPES: [TYPE_MAX],
    })

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_PERIOD: "weekly",
        CONF_TYPES: [TYPE_MAX],
    }