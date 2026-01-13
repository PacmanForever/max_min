"""Data coordinator for Max Min integration."""

import inspect
from datetime import datetime, timedelta
import logging

from homeassistant.util import dt as dt_util
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_INITIAL_MAX,
    CONF_INITIAL_MIN,
    CONF_PERIOD,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    PERIOD_DAILY,
    PERIOD_MONTHLY,
    PERIOD_WEEKLY,
    PERIOD_YEARLY,
    TYPE_MAX,
    TYPE_MIN,
)

_LOGGER = logging.getLogger(__name__)


class MaxMinDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the sensor."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry
        self.sensor_entity = config_entry.data[CONF_SENSOR_ENTITY]
        self.period = config_entry.options.get(CONF_PERIOD, config_entry.data.get(CONF_PERIOD, PERIOD_DAILY))
        self.types = config_entry.options.get(CONF_TYPES, config_entry.data.get(CONF_TYPES, [TYPE_MAX, TYPE_MIN]))

        self.max_value = config_entry.options.get(CONF_INITIAL_MAX, config_entry.data.get(CONF_INITIAL_MAX))
        self.min_value = config_entry.options.get(CONF_INITIAL_MIN, config_entry.data.get(CONF_INITIAL_MIN))
        self._reset_listener = None

        # Check if DataUpdateCoordinator accepts config_entry (HA 2024.2+)
        sig = inspect.signature(DataUpdateCoordinator.__init__)
        kwargs = {
            'hass': hass,
            'logger': _LOGGER,
            'name': f"{config_entry.title} Coordinator",
            'update_interval': None,  # Manual updates
        }
        if 'config_entry' in sig.parameters:
            kwargs['config_entry'] = config_entry

        super().__init__(**kwargs)

    async def async_config_entry_first_refresh(self) -> None:
        """Initialize values and listeners."""
        # Get initial value
        state = self.hass.states.get(self.sensor_entity)
        if state and state.state not in (None, "unknown", "unavailable"):
            try:
                current_value = float(state.state)
                self.max_value = current_value
                self.min_value = current_value
            except ValueError:
                _LOGGER.warning("Sensor %s has non-numeric state: %s", self.sensor_entity, state.state)
        else:
            _LOGGER.warning("Sensor %s is not available", self.sensor_entity)

        # Schedule reset
        self._schedule_reset()

        # Listen to sensor changes
        async_track_state_change_event(
            self.hass, [self.sensor_entity], self._handle_sensor_change
        )

    @callback
    def _handle_sensor_change(self, event):
        """Handle sensor state change."""
        new_state = event.data.get("new_state")
        if new_state and new_state.state not in (None, "unknown", "unavailable"):
            try:
                value = float(new_state.state)
                if self.max_value is None or value > self.max_value:
                    self.max_value = value
                if self.min_value is None or value < self.min_value:
                    self.min_value = value
                self.async_set_updated_data({})
            except ValueError:
                _LOGGER.warning("Invalid sensor value: %s", new_state.state)

    def _schedule_reset(self):
        """Schedule the next reset."""
        now = dt_util.now()
        if self.period == PERIOD_DAILY:
            reset_time = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.period == PERIOD_WEEKLY:
            days_ahead = (7 - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            reset_time = (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.period == PERIOD_MONTHLY:
            if now.month == 12:
                reset_time = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                reset_time = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif self.period == PERIOD_YEARLY:
            reset_time = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

        # Cancel previous listener if exists
        if self._reset_listener:
            self._reset_listener()
            self._reset_listener = None

        self._reset_listener = async_track_point_in_time(
            self.hass, self._handle_reset, reset_time
        )

    @callback
    def _handle_reset(self, now):
        """Handle period reset."""
        state = self.hass.states.get(self.sensor_entity)
        if state and state.state not in (None, "unknown", "unavailable"):
            try:
                current_value = float(state.state)
                self.max_value = current_value
                self.min_value = current_value
            except ValueError:
                self.max_value = None
                self.min_value = None
        else:
            self.max_value = None
            self.min_value = None

        self.async_set_updated_data({})
        self._schedule_reset()

    async def async_unload(self):
        """Unload the coordinator."""
        if self._reset_listener:
            self._reset_listener()