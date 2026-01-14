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
    assert CONF_DEVICE_ID in field_names_1[3]
    
    # Step 2: Optional Settings
    # We need to pass valid data to step 1 to reach step 2
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock(return_value=None)
    
    await flow.async_step_user({
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: ["daily"],
        CONF_TYPES: ["max", "min"]
    })
    
    result = await flow.async_step_optional_settings()
    assert result["type"] == FlowResultType.FORM
    schema_2 = result["data_schema"]
    schema_keys_2 = list(schema_2.schema.keys())
    
    field_names_2 = []
    for key in schema_keys_2:
        field_names_2.append(str(key.schema) if hasattr(key, "schema") else str(key))
        
    # Check order for step 2
    # Expected: initial_min, initial_max (Device ID is now in step 1)
    min_index = -1
    max_index = -1
    
    for i, name in enumerate(field_names_2):
        if CONF_INITIAL_MIN in name:
            min_index = i
        if CONF_INITIAL_MAX in name:
            max_index = i
            
    assert min_index != -1, "initial_min field missing"
    assert max_index != -1, "initial_max field missing"
    
    # Verify device_id is NOT in optional settings
    for name in field_names_2:
        assert CONF_DEVICE_ID not in name, "device_id should not be in optional settings"


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
    assert user_step["data"]["device_id"] == "Device to link"
    
    # Optional settings step
    optional_step = strings["config"]["step"]["optional_settings"]
    assert optional_step["title"] == "Optional settings"
    assert optional_step["data"]["daily_initial_min"] == "Daily: Initial Min Value"
    assert optional_step["data"]["daily_initial_max"] == "Daily: Initial Max Value"
    assert "device_id" not in optional_step["data"]
    
    options_step = strings["options"]["step"]["init"]
    assert options_step["title"] == "Max/Min sensor/s options"
    assert options_step["data"]["periods"] == "Periods"
    assert options_step["data"]["types"] == "Sensors"
    assert options_step["data"]["device_id"] == "Device to link"
    
    # Check optional settings step in options
    options_optional_step = strings["options"]["step"]["optional_settings"]
    assert options_optional_step["title"] == "Optional settings"
    assert options_optional_step["data"]["daily_initial_min"] == "Daily: Initial Min Value"
    assert options_optional_step["data"]["daily_initial_max"] == "Daily: Initial Max Value"
    assert "device_id" not in options_optional_step["data"]

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
