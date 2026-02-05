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
    CONF_OFFSET,
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
        self.offset = config_entry.options.get(CONF_OFFSET, config_entry.data.get(CONF_OFFSET, 0))


        # Data structure: {period: {"max": value, "min": value, "start": value, "end": value}}
        self.tracked_data = {}

        # Legacy global values (backward compatibility)
        global_initial_max = config_entry.options.get(CONF_INITIAL_MAX, config_entry.data.get(CONF_INITIAL_MAX))
        global_initial_min = config_entry.options.get(CONF_INITIAL_MIN, config_entry.data.get(CONF_INITIAL_MIN))

        for period in self.periods:
            # Try specific period value first, then global
            specific_max_key = f"{period}_{CONF_INITIAL_MAX}"
            specific_min_key = f"{period}_{CONF_INITIAL_MIN}"

            p_initial_max = config_entry.options.get(specific_max_key, config_entry.data.get(specific_max_key, global_initial_max))
            p_initial_min = config_entry.options.get(specific_min_key, config_entry.data.get(specific_min_key, global_initial_min))

            self.tracked_data[period] = {
                "max": p_initial_max,
                "min": p_initial_min,
                "start": None,
                "end": None
            }

        self._reset_listeners = {}
        self._next_resets = {} # Keep track of next reset times for offset logic
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
    
    def _get_period_start(self, now, period):
        """Get the start time of the current period."""
        if period == PERIOD_DAILY:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == PERIOD_WEEKLY:
            start_of_week = now - timedelta(days=now.weekday())
            return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == PERIOD_MONTHLY:
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == PERIOD_YEARLY:
            return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return None

    def update_restored_data(self, period, type_, value, last_reset=None):
        """Update data from restored state."""
        if period not in self.tracked_data:
            self.tracked_data[period] = {"max": None, "min": None, "last_reset": None}
            
        data = self.tracked_data[period]
        
        # Check if the restored data is stale (from previous period)
        # If last_reset is provided, we check against current period start.
        if last_reset:
            if isinstance(last_reset, str):
                last_reset = dt_util.parse_datetime(last_reset)
            
            if last_reset:
                now = dt_util.now()
                period_start = self._get_period_start(now, period)
                
                # If the restored point is older than the current period start, ignore it
                # Unless we are in "All Time" which never expires
                if period != PERIOD_ALL_TIME and period_start and last_reset < period_start:
                    _LOGGER.debug("Ignoring restored data for %s (stale): %s < %s", period, last_reset, period_start)
                    return

                # If the restored last_reset is newer than what we have, take it
                if data.get("last_reset") is None or last_reset > data["last_reset"]:
                    data["last_reset"] = last_reset

        # Only update if the restored value extends the current range (or initializes it)
        # Note: stored data might have been initialized by current sensor state in first_refresh
        # If restored value is "more extreme", we keep it.
        # But we also want to overwrite if the current value is just "current" and the restored is "historical max/min"
        
        # Case Max:
        if type_ == "max":
            if data["max"] is None or value > data["max"]:
                data["max"] = value
        
        # Case Min:
        if type_ == "min":
            if data["min"] is None or value < data["min"]:
                data["min"] = value

    async def async_config_entry_first_refresh(self) -> None:
        """Initialize values and listeners."""
        # Get initial value
        state = self.hass.states.get(self.sensor_entity)
        if state and state.state not in (None, "unknown", "unavailable"):
            try:
                current_value = float(state.state)
                now = dt_util.now()
                # Initialize info for all periods
                for period, data in self.tracked_data.items():
                    if data["max"] is None or current_value > data["max"]:
                        data["max"] = current_value
                    if data["min"] is None or current_value < data["min"]:
                        data["min"] = current_value
                    if data.get("last_reset") is None:
                        data["last_reset"] = self._get_period_start(now, period)
                    # Delta support: initialize start/end
                    if data.get("start") is None:
                        data["start"] = current_value
                    if data.get("end") is None:
                        data["end"] = current_value
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
                now = dt_util.now()

                for period in self.periods:
                    if period not in self.tracked_data:
                        self.tracked_data[period] = {"max": None, "min": None, "start": None, "end": None}

                    data = self.tracked_data[period]
                    is_cumulative = new_state.attributes.get("state_class") in ["total", "total_increasing"]

                    # 1. Early Reset Detection (Offset Window)
                    # If we are in the offset "dead zone" (waiting for reset) and the sensor drops,
                    # we trigger the reset immediately instead of ignoring the data.
                    if period in self._next_resets and self.offset > 0:
                        reset_time = self._next_resets[period]
                        if (now >= reset_time - timedelta(seconds=self.offset) and 
                            now <= reset_time + timedelta(seconds=self.offset)):
                            
                            # If cumulative sensor drops during dead zone, it's a reset
                            if is_cumulative and data["max"] is not None and value < data["max"]:
                                _LOGGER.debug("Early reset detected for %s. Triggering reset now.", period)
                                # Cancel scheduled reset
                                if period in self._reset_listeners:
                                    self._reset_listeners[period]()
                                    del self._reset_listeners[period]
                                self._handle_reset(now, period)
                                return

                            continue
                    
                    # Normal update logic
                    if data["max"] is None or value > data["max"]:
                        data["max"] = value
                        updated = True
                    if data["min"] is None or value < data["min"]:
                        data["min"] = value
                        updated = True
                    # Delta support: update end value
                    data["end"] = value
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
        self._next_resets = {}

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
                self._next_resets[period] = reset_time
                # apply offset to schedule time
                schedule_time = reset_time + timedelta(seconds=self.offset)
                
                # Use a default argument in lambda to capture loop variable 'period' value 
                self._reset_listeners[period] = async_track_point_in_time(
                    self.hass, 
                    lambda now, p=period: self._handle_reset(now, p), 
                    schedule_time
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
            self.tracked_data[period]["last_reset"] = now
            # Delta support: reset start and end to current value
            self.tracked_data[period]["start"] = current_val
            self.tracked_data[period]["end"] = current_val
            
            # Notifica explícitament (redundant safety)
            self.async_set_updated_data({})


            # Notifica explícitament les entitats perquè actualitzin el seu estat
            for entity in getattr(self, "entities", []):
                if hasattr(entity, "period") and entity.period == period:
                    entity.async_write_ha_state()

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
            self._next_resets[period] = next_reset
            schedule_time = next_reset + timedelta(seconds=self.offset)
            self._reset_listeners[period] = async_track_point_in_time(
                self.hass,
                lambda now, p=period: self._handle_reset(now, p),
                schedule_time
            )

    async def async_unload(self):
        """Unload the coordinator."""
        for unsub in self._reset_listeners.values():
            unsub()
        self._reset_listeners = {}
            
        if self._unsub_sensor_state_listener:
            self._unsub_sensor_state_listener()
            self._unsub_sensor_state_listener = None
