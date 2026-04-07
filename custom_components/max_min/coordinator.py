"""Data coordinator for Max Min integration.

Startup ordering (CRITICAL — update if behaviour changes)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
At HA restart the source sensor is usually *unavailable* when our
integration loads.  The setup sequence MUST be:

  1. __init__          — build tracked_data, NO timers, NO listeners.
  2. first_refresh     — seed tracked_data from source (if available),
                         schedule reset timers.  Does NOT run catch-up
                         and does NOT register the state listener.
  3. forward_entry_setups → RestoreEntity restores start/end/last_reset
                            into tracked_data via update_restored_data().
  4. start_listeners() — run startup catch-up (_check_watchdog), start
                         the periodic watchdog, and register the state
                         change listener.  ONLY called AFTER step 3.
  5. apply_pending_initials() — enforce configured initial values for
                                periods that had no valid restore.

If step 4 runs before step 3, a false reset fires (last_reset is still
None → _is_reset_due returns True), _pending_start_reanchor is set,
and the first real state change wipes start/end → delta drops to 0.

Safety nets:
  - update_restored_data() clears _pending_start_reanchor when it
    accepts valid start/end data, so even if ordering is violated the
    restored values survive.
  - async_unload() cancels the periodic watchdog timer.
"""

from datetime import datetime, timedelta
import logging

from homeassistant.util import dt as dt_util
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_point_in_time, async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_INITIAL_MAX,
    CONF_INITIAL_MIN,
    CONF_INITIAL_DELTA,
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

WATCHDOG_INTERVAL = timedelta(minutes=1)
BACKUP_RESET_DELAY = timedelta(seconds=30)


def _as_float(value):
    """Convert value to float accepting comma decimal separator."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
    return float(value)


class MaxMinDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the sensor."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"MaxMin {config_entry.data[CONF_SENSOR_ENTITY]}",
            update_interval=None,
            config_entry=config_entry,
        )
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
            specific_delta_key = f"{period}_{CONF_INITIAL_DELTA}"

            p_initial_max = config_entry.options.get(specific_max_key, config_entry.data.get(specific_max_key, global_initial_max))
            p_initial_min = config_entry.options.get(specific_min_key, config_entry.data.get(specific_min_key, global_initial_min))
            p_initial_delta = config_entry.options.get(specific_delta_key, config_entry.data.get(specific_delta_key))

            # Ensure we coerce to float if they came from somewhere weird
            if p_initial_max is not None:
                try:
                    p_initial_max = _as_float(p_initial_max)
                except (ValueError, TypeError):
                    p_initial_max = None
            if p_initial_min is not None:
                try:
                    p_initial_min = _as_float(p_initial_min)
                except (ValueError, TypeError):
                    p_initial_min = None
            if p_initial_delta is not None:
                try:
                    p_initial_delta = _as_float(p_initial_delta)
                except (ValueError, TypeError):
                    p_initial_delta = None

            _LOGGER.debug("Period %s: Initial Max=%s, Min=%s, Delta=%s", period, p_initial_max, p_initial_min, p_initial_delta)

            self.tracked_data[period] = {
                "max": None,
                "min": None,
                "start": None,
                "end": None,
                "last_reset_reason": None,
                "last_reset_triggered_at": None,
            }
            self._configured_initials[period] = {
                "max": p_initial_max,
                "min": p_initial_min,
                "delta": p_initial_delta,
            }

        self._reset_listeners = {}
        self._backup_reset_listeners = {}
        self._next_resets = {} # Keep track of next reset times for offset logic
        self._unsub_sensor_state_listener = None
        self._watchdog_unsub = None
        self._source_is_cumulative = False
        # Periods whose start/end need re-anchoring on the first sensor update
        # after a reset.  Avoids race conditions with sensors that also reset at
        # midnight while keeping delta=0 (not unavailable) immediately after reset.
        self._pending_start_reanchor: set[str] = set()
        # Periods that received valid restored data from RestoreEntity.
        # Used by apply_pending_initials to skip initial enforcement for
        # periods that already have correct restored state.
        self._restore_accepted: set[str] = set()

    @callback
    def _check_watchdog(self, now):
        """Periodic check to ensure no resets were missed."""
        _LOGGER.debug("Watchdog checking for missed resets...")
        changes = False
        for period in self.periods:
            try:
                if self.ensure_period_current(period, now, reason="watchdog"):
                    changes = True
            except Exception as err:
                _LOGGER.exception("Watchdog failed for period %s: %s", period, err)
                
        if changes:
            _LOGGER.info("Watchdog forced missed resets successfully.")

    def get_value(self, period, type_):
        """Get value for specific period and type."""
        if period in self.tracked_data:
            return self.tracked_data[period].get(type_)
        return None

    @staticmethod
    def _is_cumulative_state(state) -> bool:
        """Return True when the source state uses a cumulative class."""
        if not state:
            return False
        state_class = state.attributes.get("state_class") if hasattr(state, "attributes") else None
        return state_class in ("total", "total_increasing")

    def _sync_source_cumulative_mode(self, state) -> None:
        """Update cumulative mode and reschedule when it changes."""
        is_cumulative = self._is_cumulative_state(state)
        if is_cumulative == self._source_is_cumulative:
            return

        self._source_is_cumulative = is_cumulative
        _LOGGER.debug(
            "Source %s cumulative mode changed to %s; rescheduling resets",
            self.sensor_entity,
            is_cumulative,
        )
        self._schedule_resets()
    
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

    @staticmethod
    def _normalize_last_reset(last_reset, reference_tz):
        """Normalize restored/stored last_reset to a timezone-aware datetime."""
        if isinstance(last_reset, str):
            last_reset = dt_util.parse_datetime(last_reset)

        if not isinstance(last_reset, datetime):
            return None

        if last_reset.tzinfo is None and reference_tz is not None:
            return last_reset.replace(tzinfo=reference_tz)

        return last_reset

    @staticmethod
    def _is_timestamp_in_period(timestamp: datetime, now: datetime, period: str) -> bool:
        """Return True when timestamp belongs to the current period of now."""
        if period == PERIOD_ALL_TIME:
            return True

        period_start = MaxMinDataUpdateCoordinator._get_period_start(now, period)
        if period_start is None:
            return True

        next_period_start = MaxMinDataUpdateCoordinator._compute_next_reset(period_start, period)
        if next_period_start is None:
            return timestamp >= period_start

        return period_start <= timestamp < next_period_start

    def _compute_reset_seed(self, period) -> float | None:
        """Compute the seed value for a period reset.

        Always tries the live sensor value first.  When the source is
        unavailable (e.g. a solar sensor at night), falls back to the
        last recorded end value so that entities keep a numeric state
        and the HA history graph shows a clean break at the period
        boundary instead of a flat line of the previous maximum.
        """
        state = self.hass.states.get(self.sensor_entity)
        if state and state.state not in (None, "unknown", "unavailable"):
            try:
                return round(float(state.state), 4)
            except ValueError:
                pass
        # Fallback: use last known end value regardless of sensor type.
        # For cumulative sensors this preserves the meter reading.
        # For measurement sensors this avoids a None seed that would
        # make the entity unavailable in HA (graph shows stale line).
        end_val = self.tracked_data.get(period, {}).get("end")
        if isinstance(end_val, (int, float)):
            return round(float(end_val), 4)
        if isinstance(end_val, str):
            try:
                return round(float(end_val), 4)
            except ValueError:
                pass
        return None

    def _is_reset_due(self, now, period) -> bool:
        """Check if a period reset is due based on last_reset and period boundaries."""
        if period == PERIOD_ALL_TIME:
            return False

        data = self.tracked_data.get(period)
        if not data:
            return False

        period_start = self._get_period_start(now, period)
        if not period_start:
            return False

        last_reset = self._normalize_last_reset(data.get("last_reset"), period_start.tzinfo)
        if last_reset:
            try:
                if last_reset >= period_start:
                    return False
            except TypeError:
                _LOGGER.warning(
                    "Invalid last_reset %s for period %s; treating as missing",
                    last_reset,
                    period,
                )

        if self.offset > 0 and self._source_is_cumulative:
            if now < period_start + timedelta(seconds=self.offset):
                return False

        return True

    @callback
    def ensure_period_current(self, period, now, reason="check") -> bool:
        """Ensure the given period has been reset for the current boundary.

        Single entry point for all reset triggers (scheduler, watchdog,
        inline, backup).  Returns True if a reset was performed.
        """
        if not self._is_reset_due(now, period):
            return False

        _LOGGER.warning("Reset triggered by %s for %s at %s", reason, period, now)
        self._perform_reset(now, period, reason=reason)
        return True

    def update_restored_data(self, period, type_, value, last_reset=None):
        """Update data from restored state."""
        # Check if this specific sensor or all sensors should skip history restore
        check_type = "delta" if type_ in ("start", "end") else type_
        if "all" in self.reset_history or f"{period}_{check_type}" in self.reset_history:
            _LOGGER.debug("[%s] Skipping restore for %s %s (surgical reset triggered by config change)", self.config_entry.title, period, type_)
            return

        if period not in self.tracked_data:
            self.tracked_data[period] = {
                "max": None, 
                "min": None, 
                "start": None, 
                "end": None, 
                "last_reset": None,
                "last_reset_reason": None,
                "last_reset_triggered_at": None,
            }
            
        data = self.tracked_data[period]
        
        # Check if the restored data is stale (from previous period)
        # Accept if last_reset is within the same period (year, month, week, day)
        if last_reset:
            now_local = dt_util.as_local(dt_util.now())
            last_reset = self._normalize_last_reset(last_reset, now_local.tzinfo)
            if last_reset:
                last_reset_local = dt_util.as_local(last_reset)
                same_period = self._is_timestamp_in_period(last_reset_local, now_local, period)

                if not same_period:
                    _LOGGER.warning(
                        "Ignoring restored data for %s: last_reset %s is from a previous period (now=%s)",
                        period,
                        last_reset_local,
                        now_local,
                    )
                    return

                # If the restored last_reset is newer than what we have, take it
                current_last_reset = self._normalize_last_reset(data.get("last_reset"), now_local.tzinfo)
                if current_last_reset is None or last_reset_local > current_last_reset:
                    data["last_reset"] = last_reset_local
        else:
            # No last_reset info from restored state.
            # We used to be conservative here, but that caused data loss during updates.
            # Now we allow restoration if the value is more extreme or data is empty.
            _LOGGER.debug("[%s] Restoring %s %s without last_reset info", self.config_entry.title, period, type_)

        # Mark this period as having received valid restore data.
        # apply_pending_initials() will skip periods with valid restores.
        self._restore_accepted.add(period)

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

        # Case Start/End (Delta support):
        if type_ in ("start", "end"):
            # We always trust restored start/end values if they passed the staleness check
            # because they represent the true period boundaries from before the restart.
            data[type_] = value
            # Safety net: if a premature reset marked this period for
            # re-anchoring, the valid restored data takes precedence.
            self._pending_start_reanchor.discard(period)

        self._check_consistency()

    async def async_config_entry_first_refresh(self) -> None:
        """Initialize values and listeners."""
        # Get initial value
        state = self.hass.states.get(self.sensor_entity)
        self._sync_source_cumulative_mode(state)
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
                        initial_delta = self._configured_initials.get(period, {}).get("delta")
                        if initial_delta is not None:
                            data["start"] = current_value - initial_delta
                        else:
                            data["start"] = current_value
                    if data.get("end") is None:
                        data["end"] = current_value

                self._check_consistency()
            except ValueError:
                _LOGGER.warning("Sensor %s has non-numeric state: %s", self.sensor_entity, state.state)
        else:
            _LOGGER.warning("Sensor %s is not available", self.sensor_entity)

        # Schedule resets
        self._schedule_resets()

        # NOTE: startup catch-up and state listener are deferred to
        # start_listeners(), called from __init__.py AFTER platform
        # setup so that RestoreEntity has already restored state.

    @callback
    def start_listeners(self):
        """Start state tracking and run startup catch-up.

        Must be called AFTER platform setup so that RestoreEntity has
        already restored start/end/last_reset.  Running the watchdog
        before restore causes false resets that wipe delta values.
        """
        # Startup catch-up: if a period reset was missed while HA/integration
        # was down, enforce it immediately.
        self._check_watchdog(dt_util.now())

        # Start periodic watchdog (every 1 minute) to catch missed resets.
        # Must be started here (not in __init__) to avoid false resets
        # before RestoreEntity has restored state.
        self._watchdog_unsub = async_track_time_interval(
            self.hass, self._check_watchdog, WATCHDOG_INTERVAL
        )

        # Listen to sensor changes
        self._unsub_sensor_state_listener = async_track_state_change_event(
            self.hass, [self.sensor_entity], self._handle_sensor_change
        )

    @callback
    def apply_pending_initials(self):
        """Apply configured initial values for periods that had NO valid restore.

        Called from async_setup_entry AFTER platform setup (i.e. after
        RestoreEntity has had a chance to restore state).  Only applies
        initials for periods where no valid state was restored — this makes
        initials truly one-shot: they seed a brand-new entry but never
        override correctly restored data on restart.
        """
        state = self.hass.states.get(self.sensor_entity)
        current_value = None
        if state and state.state not in (None, "unknown", "unavailable"):
            try:
                current_value = round(float(state.state), 4)
            except ValueError:
                pass

        applied = False
        for period, initials in self._configured_initials.items():
            if period in self._restore_accepted:
                continue  # Valid restore ran; don't override with initials

            data = self.tracked_data.get(period)
            if data is None:
                continue

            initial_max = initials.get("max")
            initial_min = initials.get("min")
            initial_delta = initials.get("delta")

            if initial_max is not None and (data["max"] is None or data["max"] < initial_max):
                data["max"] = initial_max
                applied = True
            if initial_min is not None and (data["min"] is None or data["min"] > initial_min):
                data["min"] = initial_min
                applied = True
            if initial_delta is not None and current_value is not None:
                data["start"] = current_value - initial_delta
                data["end"] = current_value
                applied = True

        # One-shot: clear so they never interfere again
        self._configured_initials = {}

        if applied:
            self._check_consistency()
            self.async_set_updated_data({})

    @callback
    def _handle_sensor_change(self, event):
        """Handle sensor state change."""
        new_state = event.data.get("new_state")
        self._sync_source_cumulative_mode(new_state)
        if new_state and new_state.state not in (None, "unknown", "unavailable"):
            try:
                # Round to 4 decimals to avoid float precision noise (0.9999999999998)
                value = round(float(new_state.state), 4)
                updated = False
                now = dt_util.now()

                for period in self.periods:
                    if period not in self.tracked_data:
                        self.tracked_data[period] = {
                            "max": None, "min": None, "start": None, "end": None,
                            "last_reset": self._get_period_start(now, period),
                            "last_reset_reason": None,
                            "last_reset_triggered_at": None,
                        }

                    data = self.tracked_data[period]
                    is_cumulative = self._source_is_cumulative

                    # 0. Inline period-boundary reset detection
                    # If a sensor update arrives after the period boundary but before
                    # the scheduled timer fires, we must reset first so old values
                    # don't bleed into the new period.  ensure_period_current
                    # respects cumulative offset.
                    if period != PERIOD_ALL_TIME:
                        if self.ensure_period_current(period, now, reason="inline"):
                            # After reset, data has been re-initialised – refresh ref
                            data = self.tracked_data[period]

                    # 1. Early Reset Detection (Offset Window)
                    # If we are in the offset "dead zone" (waiting for reset) and the sensor drops,
                    # we trigger the reset immediately instead of ignoring the data.
                    if period in self._next_resets and self.offset > 0 and is_cumulative:
                        reset_time = self._next_resets[period]
                        if (now >= reset_time - timedelta(seconds=self.offset) and 
                            now <= reset_time + timedelta(seconds=self.offset)):
                            
                            # If cumulative sensor drops during dead zone, it's a reset
                            if data["max"] is not None and value < data["max"]:
                                _LOGGER.debug("Early reset detected for %s. Triggering reset now.", period)
                                self._perform_reset(now, period, reason="early_offset")
                                continue

                            # No drop: update max/min/end so values stay accurate
                            if data["max"] is None or value > data["max"]:
                                data["max"] = value
                                updated = True
                            if data["min"] is None or value < data["min"]:
                                data["min"] = value
                                updated = True
                            if data.get("end") != value:
                                data["end"] = value
                                updated = True
                            continue
                    
                    # Normal update logic
                    if data["max"] is None or value > data["max"]:
                        data["max"] = value
                        updated = True
                    if data["min"] is None or value < data["min"]:
                        data["min"] = value
                        updated = True

                    # Delta support: re-anchor start after reset
                    # Initial delta is one-shot (creation only), so reanchor
                    # always starts fresh: start=value, delta=0.
                    if period in self._pending_start_reanchor:
                        data["start"] = value
                        data["end"] = value
                        self._pending_start_reanchor.discard(period)
                        updated = True

                    # Delta support: initialize start if missing
                    elif data.get("start") is None:
                        initial_delta = self._configured_initials.get(period, {}).get("delta")
                        if initial_delta is not None:
                            data["start"] = value - initial_delta
                        else:
                            data["start"] = value
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
        for unsub in self._backup_reset_listeners.values():
            unsub()
        self._reset_listeners = {}
        self._backup_reset_listeners = {}
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
        # Cancel previous listeners for this period before re-scheduling
        if period in self._reset_listeners:
            self._reset_listeners[period]()
        if period in self._backup_reset_listeners:
            self._backup_reset_listeners[period]()

        self._next_resets[period] = reset_time
        effective_offset = self.offset if self._source_is_cumulative else 0
        schedule_time = reset_time + timedelta(seconds=effective_offset)
        
        _LOGGER.debug(
            "Scheduling %s reset for %s (Offset: %ss). Target: %s", 
            period, self.config_entry.title, effective_offset, schedule_time
        )

        # Inner functions decorated with @callback so that HA's HassJob
        # classifies them as event-loop callbacks (not executor jobs).
        # Without this, async_write_ha_state runs outside the event loop
        # and the HA state machine is never updated at reset time.
        @callback
        def on_reset(now, _period=period):
            self.ensure_period_current(_period, now, reason="scheduler")

        @callback
        def on_backup(now, _period=period):
            self.ensure_period_current(_period, now, reason="backup")

        self._reset_listeners[period] = async_track_point_in_time(
            self.hass, on_reset, schedule_time,
        )

        # Backup guard: if the main timer is missed, force verification shortly after.
        backup_time = schedule_time + BACKUP_RESET_DELAY
        self._backup_reset_listeners[period] = async_track_point_in_time(
            self.hass, on_backup, backup_time,
        )

    @callback
    def _perform_reset(self, now, period, reason="scheduler"):
        """Handle period reset.

        Uses _compute_reset_seed for seed policy and records last_reset as
        the canonical period_start (not wall-clock ``now``) so that
        _is_reset_due becomes fully idempotent.
        """
        _LOGGER.debug("Handling period reset for %s - %s (source=%s)", self.config_entry.title, period, reason)

        try:
            reset_seed = self._compute_reset_seed(period)

            if period in self.tracked_data:
                # Log seed provenance when source is unavailable
                state = self.hass.states.get(self.sensor_entity)
                source_available = (
                    state and state.state not in (None, "unknown", "unavailable")
                )
                if not source_available and reset_seed is not None:
                    _LOGGER.debug(
                        "Reset fallback for %s: source unavailable, using last end value %s",
                        period, reset_seed,
                    )
                elif not source_available:
                    _LOGGER.debug(
                        "Reset for %s: source unavailable, seed is None",
                        period,
                    )

                # Reset max/min to seed — initial values are one-shot
                # (only applied at entry creation, not on period resets)
                self.tracked_data[period]["max"] = reset_seed
                self.tracked_data[period]["min"] = reset_seed

                # Canonical: last_reset is the period start, not the wall-clock moment
                self.tracked_data[period]["last_reset"] = self._get_period_start(now, period)
                self.tracked_data[period]["last_reset_reason"] = reason
                self.tracked_data[period]["last_reset_triggered_at"] = now
                # Mark the period for re-anchoring BEFORE start/end assignment
                # so that if anything below throws, the reanchor is still pending.
                self._pending_start_reanchor.add(period)
                # Use seed so delta=0 immediately (never unavailable), but the
                # reanchor mark ensures the first real sensor update will
                # overwrite start/end with the truly current value.  This avoids
                # a race condition when the source also resets at midnight.
                self.tracked_data[period]["start"] = reset_seed
                self.tracked_data[period]["end"] = reset_seed

                self.async_set_updated_data({})

        except Exception as e:
            _LOGGER.exception("Error during reset for %s: %s", period, e)
        finally:
            # Reschedule only this period - GUARANTEED
            # We use try/finally to ensure that even if the reset logic crashes,
            # the next reset is still scheduled. This prevents "broken chains".
            next_reset = self._compute_next_reset(now, period)
            if next_reset:
                self._schedule_single_reset(period, next_reset)

    async def async_unload(self):
        """Unload the coordinator."""
        for unsub in self._reset_listeners.values():
            unsub()
        for unsub in self._backup_reset_listeners.values():
            unsub()
        self._reset_listeners = {}
        self._backup_reset_listeners = {}

        if self._watchdog_unsub:
            self._watchdog_unsub()
            self._watchdog_unsub = None

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

        # Initial values are one-shot (applied at entry creation only),
        # so no re-enforcement after consistency propagation.
