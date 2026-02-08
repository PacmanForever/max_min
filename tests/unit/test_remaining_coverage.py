"""Tests for remaining uncovered lines across coordinator.py and sensor.py."""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from custom_components.max_min.coordinator import MaxMinDataUpdateCoordinator
from custom_components.max_min.sensor import DeltaSensor
from custom_components.max_min.const import (
    CONF_DEVICE_ID,
    CONF_PERIODS,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    PERIOD_DAILY,
    PERIOD_MONTHLY,
    PERIOD_WEEKLY,
    PERIOD_YEARLY,
    TYPE_DELTA,
    TYPE_MAX,
    TYPE_MIN,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hass():
    """Mock hass."""
    hass = Mock()
    hass.config.time_zone = timezone.utc
    hass.data = {"custom_components": {}}
    hass.states.get.return_value = Mock(
        state="10.0", attributes={"friendly_name": "Test Sensor"}
    )
    return hass


def _entry(periods=None, types=None, **extra_options):
    """Create a mock config entry."""
    entry = MagicMock()
    entry.data = {
        CONF_SENSOR_ENTITY: "sensor.test",
        CONF_PERIODS: periods or [PERIOD_DAILY],
        CONF_TYPES: types or [TYPE_MAX, TYPE_MIN],
    }
    entry.options = dict(extra_options)
    entry.entry_id = "test_entry"
    entry.title = "Test"
    return entry


# ---------------------------------------------------------------------------
# coordinator.py — _compute_next_reset direct tests
# ---------------------------------------------------------------------------

def test_compute_next_reset_daily():
    """_compute_next_reset returns next midnight for daily."""
    now = datetime(2026, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
    result = MaxMinDataUpdateCoordinator._compute_next_reset(now, PERIOD_DAILY)
    assert result == datetime(2026, 6, 16, 0, 0, 0, tzinfo=timezone.utc)


def test_compute_next_reset_monthly_non_december():
    """_compute_next_reset returns 1st of next month for non-December."""
    now = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    result = MaxMinDataUpdateCoordinator._compute_next_reset(now, PERIOD_MONTHLY)
    assert result == datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_compute_next_reset_monthly_december():
    """_compute_next_reset wraps to January for December."""
    now = datetime(2026, 12, 15, 10, 0, 0, tzinfo=timezone.utc)
    result = MaxMinDataUpdateCoordinator._compute_next_reset(now, PERIOD_MONTHLY)
    assert result == datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_compute_next_reset_unknown_period():
    """_compute_next_reset returns None for unknown period."""
    now = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
    assert MaxMinDataUpdateCoordinator._compute_next_reset(now, "unknown") is None


# ---------------------------------------------------------------------------
# coordinator.py — line 42: periods as string fallback
# ---------------------------------------------------------------------------

def test_periods_string_fallback(hass):
    """Periods provided as a plain string is coerced to a list."""
    entry = _entry()
    entry.data[CONF_PERIODS] = "daily"   # string instead of list
    entry.options = {}
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    assert coordinator.periods == ["daily"]


# ---------------------------------------------------------------------------
# coordinator.py — line 99: get_value for unknown period
# ---------------------------------------------------------------------------

def test_get_value_unknown_period(hass):
    """get_value returns None for a period not in tracked_data."""
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry())
    assert coordinator.get_value("nonexistent_period", "max") is None


# ---------------------------------------------------------------------------
# coordinator.py — line 117: _get_period_start unknown period → None
# ---------------------------------------------------------------------------

def test_get_period_start_unknown_period(hass):
    """_get_period_start returns None for an unrecognised period string."""
    coordinator = MaxMinDataUpdateCoordinator(hass, _entry())
    now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
    assert coordinator._get_period_start(now, "custom_period") is None


# ---------------------------------------------------------------------------
# coordinator.py — line 222: _handle_sensor_change creates tracked_data
#                  for a period not yet initialised
# ---------------------------------------------------------------------------

def test_handle_sensor_change_creates_missing_period(hass):
    """A sensor change for a period not in tracked_data creates it."""
    entry = _entry(periods=[PERIOD_DAILY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)

    # Remove the period from tracked_data to simulate uninitialised state
    coordinator.tracked_data.pop(PERIOD_DAILY, None)
    coordinator._next_resets = {}

    event = Mock()
    event.data = {"new_state": Mock(state="5.0", attributes={})}

    with patch("custom_components.max_min.coordinator.async_track_point_in_time"):
        coordinator._handle_sensor_change(event)

    assert PERIOD_DAILY in coordinator.tracked_data
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] == 5.0
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] == 5.0


# ---------------------------------------------------------------------------
# coordinator.py — _handle_reset reschedule branches for monthly (Dec),
# yearly, and the schedule_time assignment line
# ---------------------------------------------------------------------------

def test_handle_reset_reschedule_monthly_december(hass):
    """_handle_reset reschedules monthly correctly in December (→ Jan next year)."""
    entry = _entry(periods=[PERIOD_MONTHLY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_MONTHLY] = {
        "max": 20.0, "min": 5.0, "start": 5.0, "end": 20.0, "last_reset": None,
    }
    coordinator._next_resets = {}
    coordinator._reset_listeners = {}

    dec_now = datetime(2026, 12, 31, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track, \
         patch("custom_components.max_min.coordinator.dt_util.now", return_value=dec_now):
        coordinator._handle_reset(dec_now, PERIOD_MONTHLY)

        # Next reset should be Jan 1 2027
        assert PERIOD_MONTHLY in coordinator._next_resets
        nr = coordinator._next_resets[PERIOD_MONTHLY]
        assert nr.year == 2027 and nr.month == 1 and nr.day == 1
        mock_track.assert_called()


def test_handle_reset_reschedule_monthly_non_december(hass):
    """_handle_reset reschedules monthly correctly outside December."""
    entry = _entry(periods=[PERIOD_MONTHLY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_MONTHLY] = {
        "max": 20.0, "min": 5.0, "start": 5.0, "end": 20.0, "last_reset": None,
    }
    coordinator._next_resets = {}
    coordinator._reset_listeners = {}

    jun_now = datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"), \
         patch("custom_components.max_min.coordinator.dt_util.now", return_value=jun_now):
        coordinator._handle_reset(jun_now, PERIOD_MONTHLY)
        nr = coordinator._next_resets[PERIOD_MONTHLY]
        assert nr.month == 7 and nr.day == 1


def test_handle_reset_reschedule_yearly(hass):
    """_handle_reset reschedules yearly correctly."""
    entry = _entry(periods=[PERIOD_YEARLY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_YEARLY] = {
        "max": 20.0, "min": 5.0, "start": 5.0, "end": 20.0, "last_reset": None,
    }
    coordinator._next_resets = {}
    coordinator._reset_listeners = {}

    feb_now = datetime(2026, 2, 8, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track, \
         patch("custom_components.max_min.coordinator.dt_util.now", return_value=feb_now):
        coordinator._handle_reset(feb_now, PERIOD_YEARLY)

        nr = coordinator._next_resets[PERIOD_YEARLY]
        assert nr.year == 2027 and nr.month == 1 and nr.day == 1
        mock_track.assert_called()


# ---------------------------------------------------------------------------
# sensor.py — DeltaSensor.async_added_to_hass (line 41)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delta_sensor_async_added_to_hass(hass):
    """DeltaSensor.async_added_to_hass completes without error."""
    entry = _entry()
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)

    # Patch the parent async_added_to_hass
    with patch.object(
        DeltaSensor.__mro__[1], "async_added_to_hass", new_callable=AsyncMock
    ):
        await sensor.async_added_to_hass()
    # No assertion needed — just ensures the method runs without error


# ---------------------------------------------------------------------------
# sensor.py — DeltaSensor.device_class with hass + device_class attr (L68-72)
# ---------------------------------------------------------------------------

def test_delta_sensor_device_class_with_attributes(hass):
    """DeltaSensor.device_class reads from source entity attributes."""
    entry = _entry()
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    hass.states.get.return_value = Mock(
        state="10.0",
        attributes={"device_class": "temperature"},
    )
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
    assert sensor.device_class == "temperature"


# ---------------------------------------------------------------------------
# sensor.py — DeltaSensor.state_class with hass + state_class attr (L76-80)
# ---------------------------------------------------------------------------

def test_delta_sensor_state_class_with_attributes(hass):
    """DeltaSensor.state_class reads from source entity attributes."""
    entry = _entry()
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    hass.states.get.return_value = Mock(
        state="10.0",
        attributes={"state_class": "measurement"},
    )
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
    assert sensor.state_class == "measurement"


# ---------------------------------------------------------------------------
# sensor.py — DeltaSensor.device_info with device_id (L84-93)
# ---------------------------------------------------------------------------

def test_delta_sensor_device_info_with_device(hass):
    """DeltaSensor.device_info returns info when device exists."""
    entry = _entry()
    entry.data[CONF_DEVICE_ID] = "dev_123"
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)

    mock_device = Mock()
    mock_device.identifiers = {("test", "123")}
    mock_device.connections = set()

    with patch(
        "custom_components.max_min.sensor.dr.async_get"
    ) as mock_dr:
        mock_dr.return_value.async_get.return_value = mock_device
        sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
        info = sensor.device_info

    assert info is not None
    assert info["identifiers"] == {("test", "123")}


def test_delta_sensor_device_info_no_device(hass):
    """DeltaSensor.device_info returns None when no device_id."""
    entry = _entry()
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    sensor = DeltaSensor(coordinator, entry, "Test Delta", PERIOD_DAILY)
    assert sensor.device_info is None


# ---------------------------------------------------------------------------
# coordinator.py — L117: update_restored_data for unknown period creates dict
# ---------------------------------------------------------------------------

def test_update_restored_data_unknown_period(hass):
    """update_restored_data creates tracked_data for a period not yet present."""
    entry = _entry(periods=[PERIOD_DAILY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)

    # Ensure "weekly" is NOT in tracked_data
    assert PERIOD_WEEKLY not in coordinator.tracked_data

    # Restore data for an unknown period (no last_reset in data → never initialised)
    coordinator.update_restored_data(PERIOD_WEEKLY, "max", 42.0)

    assert PERIOD_WEEKLY in coordinator.tracked_data
    assert coordinator.tracked_data[PERIOD_WEEKLY]["max"] == 42.0


# ---------------------------------------------------------------------------
# coordinator.py — _schedule_resets yearly branch (L309)
# ---------------------------------------------------------------------------

def test_schedule_resets_yearly(hass):
    """_schedule_resets covers the yearly period branch."""
    entry = _entry(periods=[PERIOD_YEARLY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_YEARLY] = {
        "max": 10.0, "min": 10.0, "start": 10.0, "end": 10.0, "last_reset": None,
    }

    feb_now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track, \
         patch("custom_components.max_min.coordinator.dt_util.now", return_value=feb_now):
        coordinator._schedule_resets()

        assert PERIOD_YEARLY in coordinator._next_resets
        nr = coordinator._next_resets[PERIOD_YEARLY]
        assert nr.year == 2027 and nr.month == 1 and nr.day == 1
        mock_track.assert_called()


def test_schedule_resets_monthly_december(hass):
    """_schedule_resets covers the monthly/December branch."""
    entry = _entry(periods=[PERIOD_MONTHLY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_MONTHLY] = {
        "max": 10.0, "min": 10.0, "start": 10.0, "end": 10.0, "last_reset": None,
    }

    dec_now = datetime(2026, 12, 15, 12, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track, \
         patch("custom_components.max_min.coordinator.dt_util.now", return_value=dec_now):
        coordinator._schedule_resets()

        assert PERIOD_MONTHLY in coordinator._next_resets
        nr = coordinator._next_resets[PERIOD_MONTHLY]
        assert nr.year == 2027 and nr.month == 1 and nr.day == 1
        mock_track.assert_called()


# ---------------------------------------------------------------------------
# coordinator.py — L337-338: _handle_reset with invalid sensor state
# ---------------------------------------------------------------------------

def test_handle_reset_with_invalid_sensor_value(hass):
    """_handle_reset handles ValueError when sensor state is not a float."""
    entry = _entry(periods=[PERIOD_DAILY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 20.0, "min": 5.0, "start": 5.0, "end": 20.0, "last_reset": None,
    }
    coordinator._next_resets = {}
    coordinator._reset_listeners = {}

    # Sensor returns a non-numeric state
    hass.states.get.return_value = Mock(
        state="not_a_number",
        attributes={"friendly_name": "Test"},
    )

    now = datetime(2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"), \
         patch("custom_components.max_min.coordinator.dt_util.now", return_value=now):
        coordinator._handle_reset(now, PERIOD_DAILY)

    # current_val should be None (ValueError caught), so max/min reset to None
    assert coordinator.tracked_data[PERIOD_DAILY]["max"] is None
    assert coordinator.tracked_data[PERIOD_DAILY]["min"] is None


# ---------------------------------------------------------------------------
# coordinator.py — L354-355: _handle_reset notifies entities
# ---------------------------------------------------------------------------

def test_handle_reset_notifies_entities(hass):
    """_handle_reset calls async_write_ha_state on matching entities."""
    entry = _entry(periods=[PERIOD_DAILY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_DAILY] = {
        "max": 20.0, "min": 5.0, "start": 5.0, "end": 20.0, "last_reset": None,
    }
    coordinator._next_resets = {}
    coordinator._reset_listeners = {}

    # Create mock entities
    entity_matching = Mock()
    entity_matching.period = PERIOD_DAILY

    entity_other = Mock()
    entity_other.period = PERIOD_WEEKLY

    entity_no_period = Mock(spec=[])  # no 'period' attribute

    coordinator.entities = [entity_matching, entity_other, entity_no_period]

    now = datetime(2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time"), \
         patch("custom_components.max_min.coordinator.dt_util.now", return_value=now):
        coordinator._handle_reset(now, PERIOD_DAILY)

    entity_matching.async_write_ha_state.assert_called_once()
    entity_other.async_write_ha_state.assert_not_called()


# ---------------------------------------------------------------------------
# coordinator.py — L365: weekly reschedule when days_ahead == 0
# ---------------------------------------------------------------------------

def test_handle_reset_reschedule_weekly_same_weekday(hass):
    """_handle_reset reschedules weekly when today is the reset day (days_ahead=0→7)."""
    entry = _entry(periods=[PERIOD_WEEKLY])
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    coordinator.tracked_data[PERIOD_WEEKLY] = {
        "max": 20.0, "min": 5.0, "start": 5.0, "end": 20.0, "last_reset": None,
    }
    coordinator._next_resets = {}
    coordinator._reset_listeners = {}

    # Monday 2026-02-09 → weekday()=0, (7-0)%7=0 → days_ahead set to 7
    monday = datetime(2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc)
    with patch("custom_components.max_min.coordinator.async_track_point_in_time") as mock_track, \
         patch("custom_components.max_min.coordinator.dt_util.now", return_value=monday):
        coordinator._handle_reset(monday, PERIOD_WEEKLY)

    nr = coordinator._next_resets[PERIOD_WEEKLY]
    # Should schedule 7 days later = 2026-02-16 (next Monday)
    assert nr == datetime(2026, 2, 16, 0, 0, 0, tzinfo=timezone.utc)
    mock_track.assert_called()


# ---------------------------------------------------------------------------
# sensor.py — L123: periods as string fallback in async_setup_entry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sensor_async_setup_entry_periods_string(hass):
    """async_setup_entry coerces periods from string to list."""
    from custom_components.max_min.sensor import async_setup_entry
    from custom_components.max_min import DOMAIN

    entry = _entry(periods=[PERIOD_DAILY], types=[TYPE_MAX])
    # Override data so periods is a plain string (not a list)
    entry.data[CONF_PERIODS] = "daily"
    entry.options = {}

    coordinator = Mock(spec=MaxMinDataUpdateCoordinator)
    coordinator.get_value.return_value = 10.0
    coordinator.hass = hass
    hass.data = {DOMAIN: {entry.entry_id: coordinator}}

    async_add_entities = Mock()

    with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get, \
         patch("homeassistant.helpers.device_registry.async_get") as mock_dr_get, \
         patch("homeassistant.helpers.entity_registry.async_entries_for_config_entry", return_value=[]):
        mock_registry = Mock()
        mock_registry.async_get.return_value = Mock(name="Temp", original_name="Temp Orig")
        mock_er_get.return_value = mock_registry

        mock_dev_reg = Mock()
        mock_dev_reg.devices = {}
        mock_dr_get.return_value = mock_dev_reg

        await async_setup_entry(hass, entry, async_add_entities)

    assert async_add_entities.called
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 1  # one period, one type


# ---------------------------------------------------------------------------
# sensor.py — L191: friendly_name fallback for sensor_name
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sensor_async_setup_entry_friendly_name_fallback(hass):
    """async_setup_entry uses friendly_name when entity registry has no name."""
    from custom_components.max_min.sensor import async_setup_entry
    from custom_components.max_min import DOMAIN

    entry = _entry(periods=[PERIOD_DAILY], types=[TYPE_MAX])
    entry.options = {}

    coordinator = Mock(spec=MaxMinDataUpdateCoordinator)
    coordinator.get_value.return_value = 10.0
    coordinator.hass = hass
    hass.data = {DOMAIN: {entry.entry_id: coordinator}}

    # State machine returns friendly_name
    hass.states.get.return_value = Mock(
        state="10.0",
        attributes={"friendly_name": "My Friendly Sensor"},
    )

    async_add_entities = Mock()

    with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get, \
         patch("homeassistant.helpers.device_registry.async_get") as mock_dr_get, \
         patch("homeassistant.helpers.entity_registry.async_entries_for_config_entry", return_value=[]):
        mock_registry = Mock()
        # async_get returns None → falls through to state machine
        mock_registry.async_get.return_value = None
        mock_er_get.return_value = mock_registry

        mock_dev_reg = Mock()
        mock_dev_reg.devices = {}
        mock_dr_get.return_value = mock_dev_reg

        await async_setup_entry(hass, entry, async_add_entities)

    assert async_add_entities.called
    entities = async_add_entities.call_args[0][0]
    assert entities[0].name == "My Friendly Sensor Daily Max"


# ---------------------------------------------------------------------------
# sensor.py — L191: DeltaSensor creation in async_setup_entry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sensor_async_setup_entry_delta_type(hass):
    """async_setup_entry creates DeltaSensor when TYPE_DELTA is in types."""
    from custom_components.max_min.sensor import async_setup_entry
    from custom_components.max_min import DOMAIN

    entry = _entry(periods=[PERIOD_DAILY], types=[TYPE_DELTA])
    entry.options = {}

    coordinator = Mock(spec=MaxMinDataUpdateCoordinator)
    coordinator.get_value.return_value = 0.0
    coordinator.hass = hass
    hass.data = {DOMAIN: {entry.entry_id: coordinator}}

    async_add_entities = Mock()

    with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get, \
         patch("homeassistant.helpers.device_registry.async_get") as mock_dr_get, \
         patch("homeassistant.helpers.entity_registry.async_entries_for_config_entry", return_value=[]):
        mock_registry = Mock()
        mock_registry.async_get.return_value = Mock(name="Temp", original_name="Temp Orig")
        mock_er_get.return_value = mock_registry

        mock_dev_reg = Mock()
        mock_dev_reg.devices = {}
        mock_dr_get.return_value = mock_dev_reg

        await async_setup_entry(hass, entry, async_add_entities)

    assert async_add_entities.called
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 1
    assert isinstance(entities[0], DeltaSensor)
