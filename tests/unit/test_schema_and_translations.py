"""Test schema order and translation labels."""
import json
import os
import pytest
import voluptuous as vol
from unittest.mock import Mock, AsyncMock
from homeassistant.data_entry_flow import FlowResultType

from custom_components.max_min.config_flow import MaxMinConfigFlow
from custom_components.max_min.const import (
    CONF_INITIAL_MAX,
    CONF_INITIAL_MIN,
    CONF_PERIOD,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    CONF_DEVICE_ID
)


@pytest.fixture
def hass():
    """Mock hass."""
    return Mock()

@pytest.mark.asyncio
async def test_config_flow_schema_order(hass):
    """Test that the config flow schema has fields in the correct order."""
    flow = MaxMinConfigFlow()
    flow.hass = Mock()
    
    # We need to call step_user to get the schema
    result = await flow.async_step_user()
    
    assert result["type"] == FlowResultType.FORM
    schema = result["data_schema"]
    
    # voluptuous Schema internals are a bit complex, but we can iterate over the schema
    # The schema keys are the dict keys passed to vol.Schema()
    # In recent python versions (3.7+), insertion order is preserved in dicts
    
    schema_keys = list(schema.schema.keys())
    
    # Extract the string keys from the schema markers
    field_names = []
    for key in schema_keys:
        # Key is typically a Marker object (like Required('sensor_entity'))
        # We want the actual key name
        field_names.append(str(key.schema) if hasattr(key, "schema") else str(key))

    # Check order
    # New Expected: sensor_entity, period, types, initial_min, initial_max, device_id
    
    assert CONF_SENSOR_ENTITY in field_names[0]
    assert CONF_PERIOD in field_names[1]
    assert CONF_TYPES in field_names[2]
    
    # Verify min comes before max
    min_index = -1
    max_index = -1
    device_index = -1
    
    for i, name in enumerate(field_names):
        if CONF_INITIAL_MIN in name:
            min_index = i
        if CONF_INITIAL_MAX in name:
            max_index = i
        if CONF_DEVICE_ID in name:
            device_index = i
            
    assert min_index != -1, "initial_min field missing"
    assert max_index != -1, "initial_max field missing"
    assert device_index != -1, "device_id field missing"
    
    assert min_index < max_index, f"initial_min ({min_index}) must differ before initial_max ({max_index})"
    # Device should be last or at least after max
    assert max_index < device_index, f"initial_max ({max_index}) must come before device_id ({device_index})"

def test_string_translations():
    """Test that strings.json contains the correct labels."""
    strings_path = "custom_components/max_min/strings.json"
    
    assert os.path.exists(strings_path)
    
    with open(strings_path, "r") as f:
        strings = json.load(f)
        
    user_step = strings["config"]["step"]["user"]
    
    assert user_step["title"] == "Add new Max/Min sensor/s"
    assert user_step["data"]["sensor_entity"] == "Source sensor"
    assert user_step["data"]["device_id"] == "Device (Optional)"
    assert user_step["data"]["period"] == "Period"
    assert user_step["data"]["types"] == "Sensors"
    assert user_step["data"]["initial_min"] == "Initial Min Value (Optional)"
    assert user_step["data"]["initial_max"] == "Initial Max Value (Optional)"
    
    options_step = strings["options"]["step"]["init"]
    assert options_step["title"] == "Max/Min sensor/s options"
    assert options_step["data"]["period"] == "Period"
    assert options_step["data"]["types"] == "Sensors"
    assert options_step["data"]["device_id"] == "Device (Optional)"
