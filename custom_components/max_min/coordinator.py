"""Data coordinator for Max Min integration."""

import inspect
from datetime import timedelta
import logging

from homeassistant.util import dt as dt_util
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_INITIAL_MAX,
    CONF_INITIAL_MIN,
    CONF_PERIODS,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    PERIOD_DAILY,
    PERIOD_MONTHLY,
    PERIOD_WEEKLY,
    PERIOD_YEARLY,
    PERIOD_ALL_TIME,
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
        self.periods = config_entry.options.get(CONF_PERIODS, config_entry.data.get(CONF_PERIODS, [PERIOD_DAILY]))
        # Fallback to verify single list
        if isinstance(self.periods, str):
            self.periods = [self.periods]
            
        self.types = config_entry.options.get(CONF_TYPES, config_entry.data.get(CONF_TYPES, [TYPE_MAX, TYPE_MIN]))

        # Data structure: {period: {"max": value, "min": value}}
        self.tracked_data = {}
        initial_max = config_entry.options.get(CONF_INITIAL_MAX, config_entry.data.get(CONF_INITIAL_MAX))
        initial_min = config_entry.options.get(CONF_INITIAL_MIN, config_entry.data.get(CONF_INITIAL_MIN))

        for period in self.periods:
            self.tracked_data[period] = {
                "max": initial_max,
                "min": initial_min
            }

        self._reset_listeners = {}
        self._unsub_sensor_state_listener = None

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
        # Ensure config_entry is set (some HA versions might overwrite it with None if not in kwargs)
        self.config_entry = config_entry

    def get_value(self, period, type_):
        """Get value for specific period and type."""
        if period in self.tracked_data:
            return self.tracked_data[period].get(type_)
        return None

    async def async_config_entry_first_refresh(self) -> None:
        """Initialize values and listeners."""
        # Get initial value
        state = self.hass.states.get(self.sensor_entity)
        if state and state.state not in (None, "unknown", "unavailable"):
            try:
                current_value = float(state.state)
                # Initialize info for all periods
                for period, data in self.tracked_data.items():
                    if data["max"] is None or current_value > data["max"]:
                        data["max"] = current_value
                    if data["min"] is None or current_value < data["min"]:
                        data["min"] = current_value
            except ValueError:
                _LOGGER.warning("Sensor %s has non-numeric state: %s", self.sensor_entity, state.state)
        else:
            _LOGGER.warning("Sensor %s is not available", self.sensor_entity)

        # Schedule resets
        self._schedule_resets()

        # Listen to sensor changes
        self._unsub_sensor_state_listener = async_track_state_change_event(
            self.hass, [self.sensor_entity], self._handle_sensor_change
        )

    @callback
    def _handle_sensor_change(self, event):
        """Handle sensor state change."""
        new_state = event.data.get("new_state")
        if new_state and new_state.state not in (None, "unknown", "unavailable"):
            try:
                value = float(new_state.state)
                updated = False
                
                for period in self.periods:
                    if period not in self.tracked_data:
                        self.tracked_data[period] = {"max": None, "min": None}
                        
                    data = self.tracked_data[period]
                    if data["max"] is None or value > data["max"]:
                        data["max"] = value
                        updated = True
                    if data["min"] is None or value < data["min"]:
                        data["min"] = value
                        updated = True
                
                if updated:
                    _LOGGER.debug("Sensor updated: %s. Data: %s", value, self.tracked_data)
                    self.async_set_updated_data({})
            except ValueError:
                _LOGGER.warning("Invalid sensor value: %s", new_state.state)

    def _schedule_resets(self):
        """Schedule the next reset for all periods."""
        # Cancel previous listeners
        for unsub in self._reset_listeners.values():
            unsub()
        self._reset_listeners = {}

        for period in self.periods:
            if period == PERIOD_ALL_TIME:
                continue

            now = dt_util.now()
            reset_time = None
            
            if period == PERIOD_DAILY:
                reset_time = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == PERIOD_WEEKLY:
                days_ahead = (7 - now.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                reset_time = (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == PERIOD_MONTHLY:
                if now.month == 12:
                    reset_time = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                else:
                    reset_time = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
            elif period == PERIOD_YEARLY:
                reset_time = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

            if reset_time:
                # Use a default argument in lambda to capture loop variable 'period' value 
                self._reset_listeners[period] = async_track_point_in_time(
                    self.hass, 
                    lambda now, p=period: self._handle_reset(now, p), 
                    reset_time
                )

    @callback
    def _handle_reset(self, now, period):
        """Handle period reset."""
        _LOGGER.debug("Handling period reset for %s - %s", self.config_entry.title, period)
        
        current_val = None
        state = self.hass.states.get(self.sensor_entity)
        if state and state.state not in (None, "unknown", "unavailable"):
            try:
                current_val = float(state.state)
            except ValueError:
                pass
        
        if period in self.tracked_data:
            self.tracked_data[period]["max"] = current_val
            self.tracked_data[period]["min"] = current_val
            self.async_set_updated_data({})
        
        # Reschedule only this period
        now = dt_util.now()
        next_reset = None
        if period == PERIOD_DAILY:
            next_reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == PERIOD_WEEKLY:
            days_ahead = (7 - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            next_reset = (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == PERIOD_MONTHLY:
            if now.month == 12:
                next_reset = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                next_reset = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == PERIOD_YEARLY:
            next_reset = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            
        if next_reset:
             self._reset_listeners[period] = async_track_point_in_time(
                self.hass, 
                lambda now, p=period: self._handle_reset(now, p), 
                next_reset
            )

    async def async_unload(self):
        """Unload the coordinator."""
        for unsub in self._reset_listeners.values():
            unsub()
        self._reset_listeners = {}
            
        if self._unsub_sensor_state_listener:
            self._unsub_sensor_state_listener()
            self._unsub_sensor_state_listener = None
