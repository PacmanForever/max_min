"""Test Delta sensor implementation."""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.max_min.const import (
    CONF_DEVICE_ID,
    CONF_PERIODS,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    DOMAIN,
    PERIOD_DAILY,
    TYPE_DELTA,
)
from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from datetime import timezone
from custom_components.max_min.sensor import DeltaSensor
from pytest_homeassistant_custom_component.common import MockConfigEntry

@pytest.fixture
def hass():
    """Mock hass."""
    hass = Mock()
    hass.config.time_zone = timezone.utc
    hass.states.get.return_value = Mock(state="10.0")
    hass.states.async_set = Mock() # Helper we used in test
    hass.data = {"custom_components": {}}
    # Mock loop time for any internal calls that might slip through
    hass.loop.time.return_value = 1000.0
    return hass

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock external dependencies to avoid event loop usage."""
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"), \
         patch("custom_components.max_min.coordinator.async_track_state_change_event"):
        yield

@pytest.fixture
def mock_delta_config_entry():
    """Create a mock config entry with Delta type."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.test_source",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
        title="Test Sensor",
        unique_id="sensor.test_source"
    )

@pytest.mark.asyncio
async def test_delta_sensor_initialization(hass):
    """Test proper initialization of the Delta sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.source",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
    )
    
    # Mock source sensor state
    hass.states.async_set("sensor.source", "10.0")
    
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    sensor = DeltaSensor(coordinator, entry, "Delta Sensor", PERIOD_DAILY)
    sensor.entity_id = "sensor.delta_sensor"
    
    # Validate initial state
    # value = end - start = 10.0 - 10.0 = 0.0
    assert sensor.native_value == 0.0
    
    # Check attributes
    attrs = sensor.extra_state_attributes
    assert attrs["start_value"] == 10.0
    assert attrs["end_value"] == 10.0

@pytest.mark.asyncio
async def test_delta_sensor_updates(hass):
    """Test that delta sensor updates correctly when source changes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.source",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
    )
    hass.states.async_set("sensor.source", "10.0")
    
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    # 1. Update source to 15.0
    # Expected: start=10.0 (unchanged), end=15.0, delta=5.0
    hass.states.get.return_value = Mock(state="15.0")
    
    # Simulating the event manually mainly because async_track_state_change_event 
    # might not fire as expected in this isolated unit test environment without full loop.
    event = Mock()
    event.data = {"new_state": hass.states.get("sensor.source")}
    coordinator._handle_sensor_change(event)
    
    assert coordinator.get_value(PERIOD_DAILY, "start") == 10.0
    assert coordinator.get_value(PERIOD_DAILY, "end") == 15.0
    
    sensor = DeltaSensor(coordinator, entry, "Delta Sensor", PERIOD_DAILY)
    assert sensor.native_value == 5.0

@pytest.mark.asyncio
async def test_delta_sensor_reset(hass):
    """Test that delta sensor resets correctly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.source",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
    )
    hass.states.async_set("sensor.source", "10.0")
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    # Move to 20.0
    hass.states.get.return_value = Mock(state="20.0")
    event = Mock()
    event.data = {"new_state": hass.states.get("sensor.source")}
    coordinator._handle_sensor_change(event)
    
    assert coordinator.get_value(PERIOD_DAILY, "start") == 10.0
    assert coordinator.get_value(PERIOD_DAILY, "end") == 20.0
    
    # Perform Reset
    # Reset uses seed temporarily, re-anchored on first sensor update
    from homeassistant.util import dt as dt_util
    now = dt_util.now()
    coordinator._perform_reset(now, PERIOD_DAILY)
    
    assert coordinator.get_value(PERIOD_DAILY, "start") == 20.0
    assert coordinator.get_value(PERIOD_DAILY, "end") == 20.0
    
    sensor = DeltaSensor(coordinator, entry, "Delta Sensor", PERIOD_DAILY)
    assert sensor.native_value == 0.0

@pytest.mark.asyncio
async def test_delta_negative_change(hass):
    """Test delta with decreasing values."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.source",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
    )
    hass.states.async_set("sensor.source", "10.0")
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    # Drop to 5.0
    hass.states.get.return_value = Mock(state="5.0")
    event = Mock()
    event.data = {"new_state": hass.states.get("sensor.source")}
    coordinator._handle_sensor_change(event)
    
    # Delta should be 5.0 - 10.0 = -5.0
    sensor = DeltaSensor(coordinator, entry, "Delta Sensor", PERIOD_DAILY)
    assert sensor.native_value == -5.0


@pytest.mark.asyncio
async def test_delta_initial_with_comma_decimal(hass):
    """Initial delta accepts localized comma decimal format."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.source",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
        options={
            "daily_initial_delta": "52,3",
        },
    )
    hass.states.get.return_value = Mock(state="100.0")

    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    sensor = DeltaSensor(coordinator, entry, "Delta Sensor", PERIOD_DAILY)

    assert coordinator.get_value(PERIOD_DAILY, "start") == pytest.approx(47.7)
    assert coordinator.get_value(PERIOD_DAILY, "end") == pytest.approx(100.0)
    assert sensor.native_value == pytest.approx(52.3)


@pytest.mark.asyncio
async def test_legacy_migration_does_not_corrupt_after_reset(hass):
    """Legacy migration must NOT re-offset start after a period reset.

    Bug: after a reset, start==end (delta=0). The legacy migration sees
    end-start=0 < initial_delta → subtracts initial_delta from start again,
    corrupting the delta to show initial_delta instead of 0.
    """
    from homeassistant.core import State
    import homeassistant.util.dt as dt_util

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.source",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
        options={
            "daily_initial_delta": 3000.0,
        },
    )

    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    now = dt_util.now()

    # Simulate state after a reset: start==end==343, delta should be 0
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 343.0, "min": 343.0,
        "start": 343.0, "end": 343.0,
        "last_reset": now,
    }

    sensor = DeltaSensor(coordinator, entry, "Delta", PERIOD_DAILY)
    sensor.hass = hass
    sensor.entity_id = "sensor.test_delta"

    # Simulate restore with start==end (just after reset)
    mock_last_state = State(
        "sensor.test_delta",
        "0.0",
        attributes={
            "start_value": 343.0,
            "end_value": 343.0,
            "last_reset": now.isoformat(),
        },
    )

    with patch(
        "custom_components.max_min.sensor.RestoreEntity.async_get_last_state",
        return_value=mock_last_state,
    ):
        await sensor.async_added_to_hass()

    # start must remain 343.0, NOT 343.0 - 3000.0 = -2657.0
    assert coordinator.tracked_data[PERIOD_DAILY]["start"] == 343.0
    assert coordinator.tracked_data[PERIOD_DAILY]["end"] == 343.0
    assert sensor.native_value == 0.0


@pytest.mark.asyncio
async def test_reanchor_respects_initial_delta(hass):
    """After reset + reanchor, initial_delta is one-shot: delta starts at 0."""
    from datetime import datetime

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.source",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
        options={
            "daily_initial_delta": 3000.0,
        },
    )
    hass.states.get.return_value = Mock(state="343.0", attributes={})

    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Perform reset
    now = datetime(2026, 3, 10, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._perform_reset(now, PERIOD_DAILY)

    # Seed is 343.0, delta=0 immediately
    assert coordinator.tracked_data[PERIOD_DAILY]["start"] == 343.0
    assert coordinator.tracked_data[PERIOD_DAILY]["end"] == 343.0

    # First sensor update should re-anchor WITHOUT initial_delta (one-shot)
    event = Mock()
    event.data = {"new_state": Mock(state="343.0", attributes={})}
    coordinator._handle_sensor_change(event)

    # start=343.0, end=343.0, delta=0 (initial_delta not re-applied)
    assert coordinator.tracked_data[PERIOD_DAILY]["start"] == 343.0
    assert coordinator.tracked_data[PERIOD_DAILY]["end"] == 343.0

    sensor = DeltaSensor(coordinator, entry, "Delta", PERIOD_DAILY)
    assert sensor.native_value == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_delta_sensor_restores_start_end(hass):
    """DeltaSensor restores start and end values from state attributes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
        title="Test Sensor",
        unique_id="sensor.test",
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.update_restored_data = Mock(wraps=coordinator.update_restored_data)

    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
    last_state = Mock()
    last_state.state = "5.0"
    last_state.attributes = {
        "config_entry_id": entry.entry_id,
        "start_value": 10.0,
        "end_value": 15.0,
        "last_reset": "2026-02-10T00:00:00+00:00",
    }
    sensor.async_get_last_state = AsyncMock(return_value=last_state)

    await sensor.async_added_to_hass()

    assert coordinator.update_restored_data.call_count == 2
    coordinator.update_restored_data.assert_any_call(
        PERIOD_DAILY, "start", 10.0, "2026-02-10T00:00:00+00:00"
    )
    coordinator.update_restored_data.assert_any_call(
        PERIOD_DAILY, "end", 15.0, "2026-02-10T00:00:00+00:00"
    )


def test_coordinator_restores_start_end_values(hass):
    """Coordinator stores restored delta boundaries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
        title="Test Sensor",
        unique_id="sensor.test",
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)

    coordinator.update_restored_data(PERIOD_DAILY, "start", 100.0)
    coordinator.update_restored_data(PERIOD_DAILY, "end", 150.0)

    assert coordinator.tracked_data[PERIOD_DAILY]["start"] == 100.0
    assert coordinator.tracked_data[PERIOD_DAILY]["end"] == 150.0


@pytest.mark.asyncio
async def test_delta_sensor_available_after_restore(hass):
    """Delta sensor stays available and computes the restored delta."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
        title="Test Sensor",
        unique_id="sensor.test",
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)

    last_state = Mock()
    last_state.state = "5.0"
    last_state.attributes = {
        "config_entry_id": entry.entry_id,
        "start_value": 10.0,
        "end_value": 15.0,
    }
    sensor.async_get_last_state = AsyncMock(return_value=last_state)

    await sensor.async_added_to_hass()

    assert sensor.available is True
    assert sensor.native_value == 5.0


@pytest.mark.asyncio
async def test_delta_sensor_ignores_invalid_restored_values(hass):
    """DeltaSensor gracefully ignores invalid restored boundaries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
        title="Test Sensor",
        unique_id="sensor.test",
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)

    last_state = Mock()
    last_state.state = "5.0"
    last_state.attributes = {
        "start_value": "invalid",
        "end_value": "also_invalid",
    }
    sensor.async_get_last_state = AsyncMock(return_value=last_state)

    await sensor.async_added_to_hass()

    assert sensor.available is True
    assert sensor.native_value is None


@pytest.mark.asyncio
async def test_delta_sensor_restores_unit_and_keeps_it_if_source_unavailable():
    """Delta keeps the restored unit during startup unavailability."""
    ha = Mock()
    ha.states.get.return_value = Mock(state="unavailable", attributes={})

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
        title="Test Sensor",
        unique_id="sensor.test",
    )
    coordinator = MaxMinDataUpdateCoordinator(ha, entry)
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)

    last_state = Mock()
    last_state.state = "5.0"
    last_state.attributes = {
        "config_entry_id": entry.entry_id,
        "unit_of_measurement": "kWh",
        "device_class": "energy",
        "start_value": 10.0,
        "end_value": 15.0,
    }
    sensor.async_get_last_state = AsyncMock(return_value=last_state)

    await sensor.async_added_to_hass()

    assert sensor.native_unit_of_measurement == "kWh"


@pytest.mark.asyncio
async def test_delta_sensor_async_added_to_hass(hass):
    """DeltaSensor.async_added_to_hass completes without error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
        title="Test Sensor",
        unique_id="sensor.test",
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)

    with patch.object(DeltaSensor.__mro__[1], "async_added_to_hass", new_callable=AsyncMock):
        await sensor.async_added_to_hass()


def test_delta_sensor_device_class_with_attributes(hass):
    """DeltaSensor.device_class reads from source entity attributes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
        title="Test Sensor",
        unique_id="sensor.test",
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    hass.states.get.return_value = Mock(
        state="10.0",
        attributes={"device_class": "temperature"},
    )
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
    assert sensor.device_class == "temperature"


def test_delta_sensor_state_class_always_measurement(hass):
    """DeltaSensor.state_class always returns measurement."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
        title="Test Sensor",
        unique_id="sensor.test",
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    hass.states.get.return_value = Mock(
        state="10.0",
        attributes={"state_class": "total_increasing"},
    )
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
    assert sensor.state_class == "measurement"


def test_delta_sensor_device_info_with_device(hass):
    """DeltaSensor.device_info returns info when device exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
            CONF_DEVICE_ID: "dev_123",
        },
        title="Test Sensor",
        unique_id="sensor.test",
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)

    mock_device = Mock()
    mock_device.identifiers = {("test", "123")}
    mock_device.connections = set()

    with patch("custom_components.max_min.sensor.dr.async_get") as mock_dr:
        mock_dr.return_value.async_get.return_value = mock_device
        sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
        info = sensor.device_info

    assert info is not None
    assert info["identifiers"] == {("test", "123")}


def test_delta_sensor_device_info_no_device(hass):
    """DeltaSensor.device_info returns None when no device_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SENSOR_ENTITY: "sensor.test",
            CONF_PERIODS: [PERIOD_DAILY],
            CONF_TYPES: [TYPE_DELTA],
        },
        title="Test Sensor",
        unique_id="sensor.test",
    )
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
    assert sensor.device_info is None
