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
    CONF_PERIODS,
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
    
    # Step 1: User
    result = await flow.async_step_user()
    
    assert result["type"] == FlowResultType.FORM
    schema_1 = result["data_schema"]
    schema_keys_1 = list(schema_1.schema.keys())
    
    field_names_1 = []
    for key in schema_keys_1:
        field_names_1.append(str(key.schema) if hasattr(key, "schema") else str(key))
        
    # Check order for step 1
    assert CONF_SENSOR_ENTITY in field_names_1[0]
    assert CONF_PERIODS in field_names_1[1]
    assert CONF_TYPES in field_names_1[2]
    
    # Step 2: Optional Settings
    # We need to pass valid data to step 1 to reach step 2
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock(return_value=None)
    
    await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: ["daily"],
        CONF_TYPES: ["max"]
    })
    
    result = await flow.async_step_optional_settings()
    assert result["type"] == FlowResultType.FORM
    schema_2 = result["data_schema"]
    schema_keys_2 = list(schema_2.schema.keys())
    
    field_names_2 = []
    for key in schema_keys_2:
        field_names_2.append(str(key.schema) if hasattr(key, "schema") else str(key))
        
    # Check order for step 2
    # Expected: initial_min, initial_max, device_id
    min_index = -1
    max_index = -1
    device_index = -1
    
    for i, name in enumerate(field_names_2):
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
    assert user_step["data"]["periods"] == "Periods"
    assert user_step["data"]["types"] == "Sensors"
    
    # Optional settings step
    optional_step = strings["config"]["step"]["optional_settings"]
    assert optional_step["title"] == "Optional settings"
    assert optional_step["data"]["initial_min"] == "Initial Min Value (Optional)"
    assert optional_step["data"]["initial_max"] == "Initial Max Value (Optional)"
    assert optional_step["data"]["device_id"] == "Device (Optional)"
    
    options_step = strings["options"]["step"]["init"]
    assert options_step["title"] == "Max/Min sensor/s options"
    assert options_step["data"]["periods"] == "Periods"
    assert options_step["data"]["types"] == "Sensors"
    
    # Check sections
    assert options_step["sections"]["optional_section"]["name"] == "Optional settings"
    section_data = options_step["sections"]["optional_section"]["data"]
    assert section_data["initial_min"] == "Initial Min Value (Optional)"
    assert section_data["initial_max"] == "Initial Max Value (Optional)"
    assert section_data["device_id"] == "Device (Optional)"

def test_en_translation_match():
    """Test that en.json matches strings.json."""
    strings_path = "custom_components/max_min/strings.json"
    en_path = "custom_components/max_min/translations/en.json"
    
    if os.path.exists(en_path):
        with open(strings_path, "r") as f:
            strings = json.load(f)
        with open(en_path, "r") as f:
            en_strings = json.load(f)
            
        assert strings == en_strings, "en.json does not match strings.json"
