"""Test sensor entity cleanup."""
from unittest.mock import Mock, patch, ANY

import pytest

from custom_components.max_min.const import (
    CONF_SENSOR_ENTITY,
    CONF_DEVICE_ID,
    CONF_PERIODS,
    CONF_TYPES,
    PERIOD_DAILY,
    TYPE_MAX,
    TYPE_MIN
)
from custom_components.max_min.sensor import async_setup_entry
from homeassistant.helpers import entity_registry as er

@pytest.fixture
def hass():
    """Mock hass."""
    return Mock()

@pytest.fixture
def mock_registry_entry():
    """Mock registry entry."""
    entry = Mock()
    entry.entry_id = "test_entry"
    return entry

@pytest.mark.asyncio
async def test_sensor_cleanup_on_options_update(hass, mock_registry_entry):
    """Test that stale entities are removed when options change."""
    config_entry = Mock()
    config_entry.runtime_data = Mock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {
        CONF_SENSOR_ENTITY: "sensor.source",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX, TYPE_MIN]  # Original config had both
    }
    # User updated options to only have MAX
    config_entry.options = {
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX]  # Only MAX now
    }
    
    async_add_entities = Mock()
    
    # Mock Entity Registry
    mock_er = Mock()
    
    # Create two existing entries: one MAX, one MIN
    entry_max = Mock()
    entry_max.entity_id = "sensor.max"
    entry_max.unique_id = "test_entry_daily_max"
    entry_max.device_id = None
    
    entry_min = Mock()
    entry_min.entity_id = "sensor.min"
    entry_min.unique_id = "test_entry_daily_min"
    entry_min.device_id = None
    
    # Return these entries when looking up for this config entry
    # Note: er.async_entries_for_config_entry is imported in sensor.py, so we mock where it's used or the method on the registry if mocked differently.
    # Actually, in sensor.py: 
    # ent_reg = er.async_get(hass)
    # entity_entries = er.async_entries_for_config_entry(ent_reg, config_entry.entry_id)
    
    # We need to patch er.async_get and er.async_entries_for_config_entry
    # Also need to patch dr.async_get because it's called in the device cleanup block
    
    mock_dr = Mock()
    mock_dr.devices = {}  # Empty devices for this test
    
    with patch("custom_components.max_min.sensor.er.async_get", return_value=mock_er), \
         patch("custom_components.max_min.sensor.er.async_entries_for_config_entry", return_value=[entry_max, entry_min]), \
         patch("custom_components.max_min.sensor.dr.async_get", return_value=mock_dr):
        
        # Configure hass mock states for source entity
        mock_state = Mock()
        mock_state.name = "Source"
        mock_state.attributes = {}
        hass.states.get.return_value = mock_state
        
        await async_setup_entry(hass, config_entry, async_add_entities)
        
        # Check that async_remove was called for the MIN sensor (which is not in options)
        mock_er.async_remove.assert_called_with("sensor.min")
        
        # Check that async_remove was NOT called for the MAX sensor
        # We can't easily check what *wasn't* called without inspecting all calls, but verify 'sensor.max' is not in calls
        call_args_list = mock_er.async_remove.call_args_list
        assert len(call_args_list) == 1
        assert call_args_list[0][0][0] == "sensor.min"

@pytest.mark.asyncio
async def test_sensor_cleanup_on_period_change(hass, mock_registry_entry):
    """Test that stale entities are removed when periods change."""
    config_entry = Mock()
    config_entry.runtime_data = Mock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {
        CONF_SENSOR_ENTITY: "sensor.source",
        CONF_TYPES: [TYPE_MAX] 
    }
    # Changed from Daily to Weekly
    config_entry.options = {
        CONF_PERIODS: ["weekly"],
        CONF_TYPES: [TYPE_MAX]
    }
    
    async_add_entities = Mock()
    
    mock_er = Mock()
    
    # Old Daily Max
    entry_daily = Mock()
    entry_daily.entity_id = "sensor.daily_max"
    entry_daily.unique_id = "test_entry_daily_max"
    entry_daily.device_id = None
    
    mock_dr = Mock()
    mock_dr.devices = {}
    
    with patch("custom_components.max_min.sensor.er.async_get", return_value=mock_er), \
         patch("custom_components.max_min.sensor.er.async_entries_for_config_entry", return_value=[entry_daily]), \
         patch("custom_components.max_min.sensor.dr.async_get", return_value=mock_dr):
        
        hass.states.get.return_value = Mock(name="Source")
        
        await async_setup_entry(hass, config_entry, async_add_entities)
        
        # Should remove daily max
        mock_er.async_remove.assert_called_with("sensor.daily_max")
        
    # And async_add_entities should have been called with the new Weekly Max
    assert async_add_entities.called
    new_entities = async_add_entities.call_args[0][0]
    assert len(new_entities) == 1
    assert new_entities[0].period == "weekly"
