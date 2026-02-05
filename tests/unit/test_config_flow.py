"""Test config flow."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from custom_components.max_min.config_flow import MaxMinConfigFlow, MaxMinOptionsFlow
from custom_components.max_min.const import (
    CONF_PERIODS,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    DOMAIN,
    PERIOD_DAILY,
    TYPE_MAX,
    TYPE_MIN,
    TYPE_DELTA,
)


@pytest.fixture
def hass():
    """Mock hass for config flow tests."""
    return Mock()



@pytest.mark.asyncio
async def test_config_flow_options(hass):
    """Test options flow."""
    config_entry = MagicMock()
    config_entry.options = {}
    config_entry.data = {CONF_SENSOR_ENTITY: "sensor.test"}
    config_entry.title = "Max Min"
    
    flow = MaxMinOptionsFlow(config_entry)
    flow.hass = Mock()  # Simple mock instead of async fixture
    flow.hass.config_entries.async_entries = Mock(return_value=[])

    # Show form
    result = await flow.async_step_init()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    # Submit form (Step 1)
    result = await flow.async_step_init({
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX],
    })
    
    # Should proceed to Optional Settings
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "optional_settings"
    
    # Submit Optional Settings (Step 2)
    result = await flow.async_step_optional_settings({})
    
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX],
        "device_id": None,
    }


@pytest.mark.asyncio
async def test_config_flow_duplicate_unique_id(hass):
    """Test config flow aborts if unique_id already configured."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock(return_value={"type": FlowResultType.ABORT, "reason": "already_configured"})

    result = await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX],
    })

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_get_options_flow(hass):
    """Test get options flow."""
    config_entry = MagicMock()
    flow = MaxMinConfigFlow.async_get_options_flow(config_entry)
    assert isinstance(flow, MaxMinOptionsFlow)



@pytest.mark.asyncio
async def test_config_flow_user_form(hass):
    """Test user form."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()

    result = await flow.async_step_user()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_config_flow_valid_user_input(hass):
    """Test valid user input."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock(return_value=None)
    
    # Mock state
    mock_state = Mock()
    mock_state.name = "Test Sensor"
    flow.hass.states.get.return_value = mock_state

    # Step 1
    result = await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX],
    })
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "optional_settings"

    # Step 2
    result = await flow.async_step_optional_settings({})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Sensor (Max)"
    assert result["data"] == {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX],
    }


@pytest.mark.asyncio
async def test_config_flow_invalid_sensor(hass):
    """Test config flow with invalid sensor."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()  # Simple mock instead of async fixture
    flow.hass.config_entries.flow.async_progress_by_handler = AsyncMock(return_value=[])

    # Mock async_set_unique_id to avoid issues
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock(return_value=None)

    # Mock validation - in real implementation, would check if sensor exists
    result = await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.invalid",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX],
    })
    
    # Validation passed (mocked), proceeds to next step
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "optional_settings"
    
    # Complete flow
    result = await flow.async_step_optional_settings({})

    # Should still create entry, validation happens later
    assert result["type"] == FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
async def test_config_flow_weekly_period(hass):
    """Test config flow with weekly period."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()  # Simple mock instead of async fixture
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock(return_value=None)

    # Step 1
    await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: ["weekly"],
        CONF_TYPES: [TYPE_MAX],
    })
    
    # Step 2
    result = await flow.async_step_optional_settings({})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PERIODS] == ["weekly"]


@pytest.mark.asyncio
async def test_config_flow_monthly_period(hass):
    """Test config flow with monthly period."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()  # Simple mock instead of async fixture
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock(return_value=None)

    # Step 1
    await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: ["monthly"],
        CONF_TYPES: [TYPE_MIN],
    })
    
    # Step 2
    result = await flow.async_step_optional_settings({})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PERIODS] == ["monthly"]


@pytest.mark.asyncio
async def test_config_flow_yearly_period(hass):
    """Test config flow with yearly period."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()  # Simple mock instead of async fixture
    flow.async_set_unique_id = AsyncMock()

    # Step 1
    await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: ["yearly"],
        CONF_TYPES: [TYPE_MAX, TYPE_MIN],
    })

    # Step 2
    result = await flow.async_step_optional_settings({})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PERIODS] == ["yearly"]


@pytest.mark.asyncio
async def test_config_flow_only_max(hass):
    """Test config flow with only max type."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()  # Simple mock instead of async fixture
    flow.async_set_unique_id = AsyncMock()

    # Step 1
    await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX],
    })
    
    # Step 2
    result = await flow.async_step_optional_settings({})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TYPES] == [TYPE_MAX]


@pytest.mark.asyncio
async def test_config_flow_only_min(hass):
    """Test config flow with only min type."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()  # Simple mock instead of async fixture
    flow.hass.states.get.return_value = None # Ensure fallback to entity_id
    flow.async_set_unique_id = AsyncMock()

    # Step 1
    await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MIN],
    })
    
    # Step 2
    result = await flow.async_step_optional_settings({})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TYPES] == [TYPE_MIN]
    assert result["title"] == "sensor.test (Min)"


@pytest.mark.asyncio
async def test_config_flow_both_types(hass):
    """Test config flow with both types."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()
    flow.hass.states.get.return_value = None # Ensure fallback to entity_id
    flow.async_set_unique_id = AsyncMock()

    # Step 1
    await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX, TYPE_MIN],
    })
    
    # Step 2
    result = await flow.async_step_optional_settings({})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert set(result["data"][CONF_TYPES]) == {TYPE_MAX, TYPE_MIN}
    assert result["title"] == "sensor.test (Max/Min)"


@pytest.mark.asyncio
async def test_options_flow_update(hass):
    """Test options flow update."""
    config_entry = MagicMock()
    config_entry.options = {
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX, TYPE_MIN],
    }
    config_entry.data = {CONF_SENSOR_ENTITY: "sensor.test"}
    
    flow = MaxMinOptionsFlow(config_entry)
    flow.hass = Mock()  # Simple mock instead of async fixture
    flow.hass.config_entries.async_entries = Mock(return_value=[])
    flow.async_set_unique_id = AsyncMock()

    # Simulate section data structure
    # Step 1: Init
    result = await flow.async_step_init({
        CONF_PERIODS: ["weekly"],
        CONF_TYPES: [TYPE_MAX],
    })
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "optional_settings"
    
    # Step 2: Optional Settings
    result = await flow.async_step_optional_settings({
         # Empty or specific values
    })

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_PERIODS: ["weekly"],
        CONF_TYPES: [TYPE_MAX],
        "device_id": None,
    }


@pytest.mark.asyncio
async def test_options_flow_show_form(hass):
    """Test options flow shows form."""
    config_entry = MagicMock()
    config_entry.options = {
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX, TYPE_MIN],
    }
    config_entry.data = {CONF_SENSOR_ENTITY: "sensor.test"}
    
    flow = MaxMinOptionsFlow(config_entry)
    flow.hass = Mock()  # Simple mock instead of async fixture

    result = await flow.async_step_init()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"


@pytest.mark.asyncio
async def test_async_get_options_flow(hass):
    """Test async_get_options_flow."""
    config_entry = MagicMock()
    result = MaxMinConfigFlow.async_get_options_flow(config_entry)
    assert isinstance(result, MaxMinOptionsFlow)
    assert result._config_entry == config_entry


@pytest.mark.asyncio
async def test_config_flow_min_greater_than_max(hass):
    """Test config flow validation for min > max."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock(return_value=None)

    # Step 1
    await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX],
    })

    # Step 2 with error
    result = await flow.async_step_optional_settings({
        "daily_initial_min": 10.0,
        "daily_initial_max": 5.0,
    })

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "min_greater_than_max"
    assert result["errors"]["daily_initial_min"] == "min_greater_than_max"


@pytest.mark.asyncio
async def test_options_flow_min_greater_than_max(hass):
    """Test options flow validation for min > max."""
    config_entry = MagicMock()
    config_entry.options = {}
    config_entry.data = {CONF_SENSOR_ENTITY: "sensor.test"}
    
    flow = MaxMinOptionsFlow(config_entry)
    flow.hass = Mock()
    
    # Step 1: Init
    await flow.async_step_init({
        CONF_TYPES: [TYPE_MAX],
        CONF_PERIODS: [PERIOD_DAILY],
    })
    
    # Step 2: Optional Settings with error
    result = await flow.async_step_optional_settings({
        "daily_initial_min": 10.0,
        "daily_initial_max": 5.0,
    })

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "min_greater_than_max"
    assert result["errors"]["daily_initial_min"] == "min_greater_than_max"


@pytest.mark.asyncio
async def test_options_flow_update_title(hass):
    """Test options flow updates title based on types."""
    config_entry = MagicMock()
    config_entry.options = {
        CONF_TYPES: [TYPE_MAX, TYPE_MIN],
    }
    config_entry.data = {CONF_SENSOR_ENTITY: "sensor.test"}
    
    flow = MaxMinOptionsFlow(config_entry)
    flow.hass = Mock()
    flow.hass.states.get.return_value = None
    flow.hass.config_entries.async_update_entry = Mock()
    
    # Step 1: Init - Change to only Max
    await flow.async_step_init({
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX],
    })
    
    # Step 2: Optional Settings
    result = await flow.async_step_optional_settings({})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    
    # Check if update_entry was called with updated title
    assert flow.hass.config_entries.async_update_entry.called
    call_args = flow.hass.config_entries.async_update_entry.call_args
    assert call_args[1]["title"] == "sensor.test (Max)"

    # Test with Min & Friendly Name
    config_entry.options = {CONF_TYPES: [TYPE_MAX]}
    flow = MaxMinOptionsFlow(config_entry)
    flow.hass = Mock()
    
    mock_state = Mock()
    mock_state.name = "My Temp"
    flow.hass.states.get.return_value = mock_state
    
    flow.hass.config_entries.async_update_entry = Mock()

    await flow.async_step_init({
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MIN],
    })
    await flow.async_step_optional_settings({})
    
    assert flow.hass.config_entries.async_update_entry.called
    call_args = flow.hass.config_entries.async_update_entry.call_args
    assert call_args[1]["title"] == "My Temp (Min)"

    # Test with Both Types
    config_entry.options = {CONF_TYPES: [TYPE_MAX]}
    flow = MaxMinOptionsFlow(config_entry)
    flow.hass = Mock()
    flow.hass.states.get.return_value = None
    flow.hass.config_entries.async_update_entry = Mock()

    await flow.async_step_init({
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX, TYPE_MIN],
    })
    await flow.async_step_optional_settings({})
    
    assert flow.hass.config_entries.async_update_entry.called
    call_args = flow.hass.config_entries.async_update_entry.call_args
    assert call_args[1]["title"] == "sensor.test (Max/Min)"


@pytest.mark.asyncio
async def test_config_flow_validation_requirements(hass):
    """Test that validation fails if periods or types are empty."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()
    
    # Empty periods
    result = await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test", 
        CONF_PERIODS: [],
        CONF_TYPES: [TYPE_MAX]
    })
    
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_PERIODS: "periods_required"}

    # Empty types
    result = await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: []
    })
    
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_TYPES: "types_required"}


@pytest.mark.asyncio
async def test_options_flow_validation_requirements(hass):
    """Test that options validation fails if periods or types are empty."""
    config_entry = MagicMock()
    config_entry.options = {}
    config_entry.data = {CONF_SENSOR_ENTITY: "sensor.test"}
    
    flow = MaxMinOptionsFlow(config_entry)
    flow.hass = Mock()
    
    # Empty periods
    result = await flow.async_step_init({
        CONF_PERIODS: [],
        CONF_TYPES: [TYPE_MAX]
    })
    
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_PERIODS: "periods_required"}

    # Empty types
    result = await flow.async_step_init({
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: []
    })
    
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_TYPES: "types_required"}


@pytest.mark.asyncio
async def test_config_flow_delta_selection(hass):
    """Test config flow allowing delta selection."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock(return_value=None)
    
    flow.hass.states.get.return_value = Mock(name="Test Sensor")

    result = await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_DELTA],
    })
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "optional_settings"
    
    result = await flow.async_step_optional_settings({})
    
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TYPES] == [TYPE_DELTA]
