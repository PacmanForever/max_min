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
    CONF_RESET_HISTORY,
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
        
        # Surgical reset list: list of "period_type" to ignore during restore
        self.reset_history = config_entry.options.get(CONF_RESET_HISTORY, [])
        if isinstance(self.reset_history, bool):
            # Backward compatibility with v0.3.21 global flag
            self.reset_history = ["all"] if self.reset_history else []


        # Data structure: {period: {"max": value, "min": value, "start": value, "end": value}}
        self.tracked_data = {}
        # Store configured initial values so they can be enforced after restore
        self._configured_initials = {}

        # Legacy global values (backward compatibility)
        global_initial_max = config_entry.options.get(CONF_INITIAL_MAX, config_entry.data.get(CONF_INITIAL_MAX))
        global_initial_min = config_entry.options.get(CONF_INITIAL_MIN, config_entry.data.get(CONF_INITIAL_MIN))

        for period in self.periods:
            # Try specific period value first, then global
            specific_max_key = f"{period}_{CONF_INITIAL_MAX}"
            specific_min_key = f"{period}_{CONF_INITIAL_MIN}"

            p_initial_max = config_entry.options.get(specific_max_key, config_entry.data.get(specific_max_key, global_initial_max))
            p_initial_min = config_entry.options.get(specific_min_key, config_entry.data.get(specific_min_key, global_initial_min))

            # Ensure we coerce to float if they came from somewhere weird
            if p_initial_max is not None:
                try:
                    p_initial_max = float(p_initial_max)
                except (ValueError, TypeError):
                    p_initial_max = None
            if p_initial_min is not None:
                try:
                    p_initial_min = float(p_initial_min)
                except (ValueError, TypeError):
                    p_initial_min = None

            _LOGGER.debug("Period %s: Initial Max=%s, Min=%s", period, p_initial_max, p_initial_min)

            self.tracked_data[period] = {
                "max": p_initial_max,
                "min": p_initial_min,
                "start": None,
                "end": None
            }
            self._configured_initials[period] = {
                "max": p_initial_max,
                "min": p_initial_min,
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
        _LOGGER.debug("[%s] Coordinator initialized. Reset history: %s. Options: %s", config_entry.title, self.reset_history, config_entry.options)

    def get_value(self, period, type_):
        """Get value for specific period and type."""
        # Force a look at the latest config entry data/options to be absolutely sure
        if self.config_entry:
            key = f"{period}_initial_{type_}"
            # Check options first (from OptionsFlow), then data (from ConfigFlow)
            # Use explicit None check to handle potential empty dict entry properly
            init_val = self.config_entry.options.get(key)
            if init_val is None:
                init_val = self.config_entry.data.get(key)
                
            if init_val is not None:
                try:
                    init_val = float(init_val)
                    current_val = self.tracked_data.get(period, {}).get(type_)
                    if type_ == "max":
                        if current_val is None or current_val < init_val:
                            _LOGGER.debug("get_value(%s, %s) returning initial %s over current %s", period, type_, init_val, current_val)
                            return init_val
                    elif type_ == "min":
                        if current_val is None or current_val > init_val:
                            _LOGGER.debug("get_value(%s, %s) returning initial %s over current %s", period, type_, init_val, current_val)
                            return init_val
                except (ValueError, TypeError):
                    pass

        if period in self.tracked_data:
            return self.tracked_data[period].get(type_)
        return None
    
    @staticmethod
    def _get_period_start(now, period):
        """Get the start time of the current period."""
        if period == PERIOD_DAILY:
            return dt_util.start_of_local_day(now)
        elif period == PERIOD_WEEKLY:
            start_of_week = now - timedelta(days=now.weekday())
            return dt_util.start_of_local_day(start_of_week)
        elif period == PERIOD_MONTHLY:
            return dt_util.start_of_local_day(now.replace(day=1))
        elif period == PERIOD_YEARLY:
            return dt_util.start_of_local_day(now.replace(month=1, day=1))
        return None

    @staticmethod
    def _compute_next_reset(now, period):
        """Compute the next reset time for a given period."""
        if period == PERIOD_DAILY:
            return dt_util.start_of_local_day(now + timedelta(days=1))
        elif period == PERIOD_WEEKLY:
            days_ahead = (7 - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return dt_util.start_of_local_day(now + timedelta(days=days_ahead))
        elif period == PERIOD_MONTHLY:
            # Safely compute next month start using local time boundaries
            if now.month == 12:
                next_check = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_check = now.replace(month=now.month + 1, day=1)
            return dt_util.start_of_local_day(next_check)
        elif period == PERIOD_YEARLY:
            return dt_util.start_of_local_day(now.replace(year=now.year + 1, month=1, day=1))
        return None

    def update_restored_data(self, period, type_, value, last_reset=None):
        """Update data from restored state."""
        # Check if this specific sensor or all sensors should skip history restore
        if "all" in self.reset_history or f"{period}_{type_}" in self.reset_history:
            _LOGGER.debug("[%s] Skipping restore for %s %s (surgical reset triggered by config change)", self.config_entry.title, period, type_)
            return

        if period not in self.tracked_data:
            self.tracked_data[period] = {
                "max": None, 
                "min": None, 
                "start": None, 
                "end": None, 
                "last_reset": None
            }
            
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
        else:
            # No last_reset info from restored state.
            # We used to be conservative here, but that caused data loss during updates.
            # Now we allow restoration if the value is more extreme or data is empty.
            _LOGGER.debug("[%s] Restoring %s %s without last_reset info", self.config_entry.title, period, type_)

        # Only update if the restored value extends the current range (or initializes it)
        # Note: stored data might have been initialized by current sensor state in first_refresh
        # If restored value is "more extreme", we keep it.
        # But we also want to overwrite if the current value is just "current" and the restored is "historical max/min"
        
        # Case Max:
        if type_ == "max":
            if data["max"] is None or value > data["max"]:
                data["max"] = value
            # Enforce configured initial max as floor (user explicitly set it)
            configured = self._configured_initials.get(period, {}).get("max")
            if configured is not None and (data["max"] is None or data["max"] < configured):
                data["max"] = configured
        
        # Case Min:
        if type_ == "min":
            if data["min"] is None or value < data["min"]:
                data["min"] = value
            # Enforce configured initial min as ceiling (user explicitly set it)
            configured = self._configured_initials.get(period, {}).get("min")
            if configured is not None and (data["min"] is None or data["min"] > configured):
                data["min"] = configured

        # Case Start/End (Delta support):
        if type_ in ("start", "end"):
            # We always trust restored start/end values if they passed the staleness check
            # because they represent the true period boundaries from before the restart.
            data[type_] = value

        self._check_consistency()

    async def async_config_entry_first_refresh(self) -> None:
        """Initialize values and listeners."""
        # Get initial value
        state = self.hass.states.get(self.sensor_entity)
        if state and state.state not in (None, "unknown", "unavailable"):
            try:
                raw_value = float(state.state)
                # Avoid float precision noise by rounding to 4 decimals
                # but we'll try to be more surgical in the update loop
                current_value = round(raw_value, 4)
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
                    
                    # Enforce configured initial values as floor/ceiling
                    initials = self._configured_initials.get(period, {})
                    initial_max = initials.get("max")
                    initial_min = initials.get("min")
                    if initial_max is not None and (data["max"] is None or data["max"] < initial_max):
                        data["max"] = initial_max
                    if initial_min is not None and (data["min"] is None or data["min"] > initial_min):
                        data["min"] = initial_min

                self._check_consistency()
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
                # Round to 4 decimals to avoid float precision noise (0.9999999999998)
                value = round(float(new_state.state), 4)
                updated = False
                now = dt_util.now()

                for period in self.periods:
                    if period not in self.tracked_data:
                        self.tracked_data[period] = {"max": None, "min": None, "start": None, "end": None}

                    data = self.tracked_data[period]
                    is_cumulative = new_state.attributes.get("state_class") in ["total", "total_increasing"]

                    # 0. Inline period-boundary reset detection
                    # If a sensor update arrives after the period boundary but before the
                    # scheduled async_track_point_in_time fires, we must reset first so
                    # old max/min values don't bleed into the new period.
                    # When offset > 0 (cumulative sensors), defer to the scheduled reset
                    # unless the offset window has already passed.
                    if period != PERIOD_ALL_TIME:
                        period_start = self._get_period_start(now, period)
                        last_reset = data.get("last_reset")
                        if period_start and last_reset and last_reset < period_start and (
                            self.offset == 0 or now >= period_start + timedelta(seconds=self.offset)
                        ):
                            _LOGGER.debug(
                                "Inline reset for %s: last_reset %s < period_start %s",
                                period, last_reset, period_start,
                            )
                            # Cancel the scheduled reset if pending
                            if period in self._reset_listeners:
                                self._reset_listeners[period]()
                                del self._reset_listeners[period]
                            self._handle_reset(now, period)
                            # After reset, data has been re-initialised with current_val
                            # from self.hass.states – refresh local reference
                            data = self.tracked_data[period]

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
                                # This period is reset; continue to process remaining periods

                            continue
                    
                    # Normal update logic
                    if data["max"] is None or value > data["max"]:
                        data["max"] = value
                        updated = True
                    if data["min"] is None or value < data["min"]:
                        data["min"] = value
                        updated = True

                    # Delta support: update end value
                    if data.get("end") != value:
                        data["end"] = value
                        updated = True

                if updated:
                    self._check_consistency()
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

        now = dt_util.now()
        for period in self.periods:
            if period == PERIOD_ALL_TIME:
                continue

            reset_time = self._compute_next_reset(now, period)
            if reset_time:
                self._schedule_single_reset(period, reset_time)

    def _schedule_single_reset(self, period, reset_time):
        """Schedule (or reschedule) the reset timer for a single period."""
        self._next_resets[period] = reset_time
        schedule_time = reset_time + timedelta(seconds=self.offset)
        
        _LOGGER.debug(
            "Scheduling %s reset for %s (Offset: %ss). Target: %s", 
            period, self.config_entry.title, self.offset, schedule_time
        )

        # Default arg p=period captures the loop variable by value
        self._reset_listeners[period] = async_track_point_in_time(
            self.hass,
            lambda now, p=period: self._handle_reset(now, p),
            schedule_time,
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
            # Apply configured initial values as floor/ceiling after reset
            initials = self._configured_initials.get(period, {})
            initial_max = initials.get("max")
            initial_min = initials.get("min")

            # Max: use whichever is higher between current value and configured initial
            if current_val is not None and initial_max is not None:
                self.tracked_data[period]["max"] = max(current_val, initial_max)
            elif initial_max is not None:
                self.tracked_data[period]["max"] = initial_max
            else:
                self.tracked_data[period]["max"] = current_val

            # Min: use whichever is lower between current value and configured initial
            if current_val is not None and initial_min is not None:
                self.tracked_data[period]["min"] = min(current_val, initial_min)
            elif initial_min is not None:
                self.tracked_data[period]["min"] = initial_min
            else:
                self.tracked_data[period]["min"] = current_val

            self.tracked_data[period]["last_reset"] = now
            self.tracked_data[period]["start"] = current_val
            self.tracked_data[period]["end"] = current_val

            self.async_set_updated_data({})

            # Notify entities so they refresh their HA state immediately
            for entity in getattr(self, "entities", []):
                if hasattr(entity, "period") and entity.period == period:
                    entity.async_write_ha_state()

        # Reschedule only this period
        current_time = dt_util.now()
        next_reset = self._compute_next_reset(current_time, period)
        if next_reset:
            self._schedule_single_reset(period, next_reset)

    async def async_unload(self):
        """Unload the coordinator."""
        for unsub in self._reset_listeners.values():
            unsub()
        self._reset_listeners = {}
            
        if self._unsub_sensor_state_listener:
            self._unsub_sensor_state_listener()
            self._unsub_sensor_state_listener = None

    def _check_consistency(self):
        """Ensure broader periods encapsulate more extreme values from narrower ones.
        
        This propagates extreme values 'outwards' (e.g. if Daily Min is -5, 
        then Weekly, Monthly, Yearly and All-time must be at least -5).
        
        NOTE: Respects surgical reset - will not propagate to periods in reset_history.
        """
        # Hierarchy: indices allow relative comparison
        hierarchy = [
            PERIOD_DAILY,
            PERIOD_WEEKLY,
            PERIOD_MONTHLY,
            PERIOD_YEARLY,
            PERIOD_ALL_TIME
        ]
        
        # We process from narrowest to broadest to propagate extremes outwards
        for i in range(len(hierarchy) - 1):
            narrower_p = hierarchy[i]
            if narrower_p not in self.tracked_data:
                continue
                
            n_max = self.tracked_data[narrower_p].get("max")
            n_min = self.tracked_data[narrower_p].get("min")
            
            # Compare with all broader periods
            for j in range(i + 1, len(hierarchy)):
                broader_p = hierarchy[j]
                if broader_p not in self.tracked_data:
                    continue
                
                # Skip propagation to periods undergoing surgical reset
                if "all" in self.reset_history or f"{broader_p}_max" in self.reset_history:
                    # Don't propagate max to this period
                    n_max_propagate = None
                else:
                    n_max_propagate = n_max
                    
                if "all" in self.reset_history or f"{broader_p}_min" in self.reset_history:
                    # Don't propagate min to this period
                    n_min_propagate = None
                else:
                    n_min_propagate = n_min
                
                b_data = self.tracked_data[broader_p]
                
                if n_max_propagate is not None:
                    if b_data.get("max") is None or n_max_propagate > b_data["max"]:
                        b_data["max"] = n_max_propagate
                        
                if n_min_propagate is not None:
                    if b_data.get("min") is None or n_min_propagate < b_data["min"]:
                        b_data["min"] = n_min_propagate

        # After applying consistency, re-enforce configured initial values as absolute floors/ceilings.
        # This prevents consistency propagation from Daily (e.g. 13.0) overriding 
        # a user-configured Yearly Initial (e.g. 45.0).
        updated_any = False
        for period, initials in self._configured_initials.items():
            if period not in self.tracked_data:
                continue
            data = self.tracked_data[period]
            initial_max = initials.get("max")
            initial_min = initials.get("min")

            if initial_max is not None and (data.get("max") is None or data["max"] < initial_max):
                data["max"] = initial_max
                updated_any = True
                _LOGGER.info("Initial value enforcement: %s Max floor set to %s (current was %s)", period, initial_max, data.get("max"))
            if initial_min is not None and (data.get("min") is None or data["min"] > initial_min):
                data["min"] = initial_min
                updated_any = True
                _LOGGER.info("Initial value enforcement: %s Min ceiling set to %s (current was %s)", period, initial_min, data.get("min"))
        
        if updated_any:
            self.async_set_updated_data({})
