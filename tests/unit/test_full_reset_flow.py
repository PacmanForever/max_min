"""Test the full reset flow including notifications."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.const import (
    CONF_SENSOR_ENTITY,
    CONF_PERIODS,
    CONF_TYPES,
    PERIOD_DAILY,
    TYPE_MAX,
)

@pytest.fixture
def hass():
    """Mock hass."""
    hass = Mock()
    hass.config.time_zone = timezone.utc
    hass.states.get.return_value = Mock(state="10.0")
    hass.data = {"custom_components": {}}
    return hass

@pytest.fixture
def config_entry():
    """Mock config entry."""
    entry = Mock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: [PERIOD_DAILY],
        CONF_TYPES: [TYPE_MAX],
    }
    entry.options = {}
    entry.entry_id = "test_entry"
    entry.title = "Test"
    return entry

@pytest.mark.asyncio
async def test_reset_updates_entities(hass, config_entry):
    """Test that reset updates entities."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    
    # Mock an entity attached to this coordinator
    mock_entity = Mock()
    mock_entity.period = PERIOD_DAILY
    mock_entity.async_write_ha_state = Mock()
    
    # Attach listener
    coordinator.async_add_listener(mock_entity.async_write_ha_state)
    
    # Initial state
    coordinator.tracked_data[PERIOD_DAILY] = {"max": 20.0, "min": 5.0}
    
    # Trigger Reset
    now = datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    
    # Patch rescheduling to avoid event loop errors
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_reset(now, PERIOD_DAILY)
    
    # 1. Verify Data Reset to Current Value (10.0)
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 10.0
    
    # 2. Verify Listener Called (Notification)
    mock_entity.async_write_ha_state.assert_called()

@pytest.mark.asyncio
async def test_reset_with_unavailable_source(hass, config_entry):
    """Test reset behavior when source is unavailable."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    
    # Set current state to unavailable
    hass.states.get.return_value = Mock(state="unavailable")
    
    # Initial state
    coordinator.tracked_data[PERIOD_DAILY] = {"max": 20.0, "min": 5.0}
    
    now = datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_reset(now, PERIOD_DAILY)
    
    # Logic: if unavailable, current_val is None.
    # self.tracked_data[period]["max"] = current_val (None)
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] is None


@pytest.mark.asyncio
async def test_reset_with_unavailable_source_uses_last_end_fallback(hass, config_entry):
    """Reset uses last end value when source is unavailable at boundary."""
    coordinator = MaxMinDataUpdateCoordinator(hass, config_entry)
    coordinator._source_is_cumulative = True

    hass.states.get.return_value = Mock(
        state="unavailable",
        attributes={"state_class": "total_increasing"},
    )

    # Simulate previous period state where latest reading was 0.0
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 2.7,
        "min": 0.0,
        "start": 0.0,
        "end": 0.0,
        "last_reset": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    }

    now = datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_reset(now, PERIOD_DAILY)

    # Daily period starts from last known source value, not previous-day max
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 0.0
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 0.0
    assert coordinator.tracked_data[PERIOD_DAILY]["start"] == 0.0
    assert coordinator.tracked_data[PERIOD_DAILY]["end"] == 0.0

