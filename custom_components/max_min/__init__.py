"""Max Min integration for Home Assistant.

Setup ordering contract (CRITICAL — update if behaviour changes)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The startup sequence is intentionally ordered to avoid a race condition
that wipes delta sensor values after a HA restart:

  1. Create coordinator and run first_refresh (seeds data, schedules
     reset timers, but does NOT start the watchdog or state listener).
  2. Forward platform setup — RestoreEntity restores saved state.
  3. start_listeners() — runs startup catch-up and starts listeners.
  4. apply_pending_initials() — enforces configured initial values.

If step 3 runs before step 2, the watchdog sees last_reset=None,
triggers a false period reset, and the first state change after boot
overwrites restored start/end with the current value → delta=0.

See coordinator.py module docstring for full details.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, CONF_RESET_HISTORY
from .coordinator import MaxMinDataUpdateCoordinator


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Max Min integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Max Min from a config entry."""
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start state tracking AFTER platform setup so that RestoreEntity
    # has already restored state.  Running the watchdog before restore
    # causes false resets that wipe delta values on restart.
    coordinator.start_listeners()

    # Apply initial values AFTER platform setup (i.e. after RestoreEntity
    # has had a chance to restore state).  This ensures user-configured
    # initials always win over stale restored values.
    coordinator.apply_pending_initials()

    # Surgical Reset Cleanup:
    # Clear the one-shot reset list BEFORE registering the update listener so
    # that async_update_entry does NOT trigger a second reload.  The coordinator
    # already captured reset_history in its __init__, and sensors have already
    # skipped restore for the affected period/type combos above.
    if entry.options.get(CONF_RESET_HISTORY):
        new_options = dict(entry.options)
        new_options.pop(CONF_RESET_HISTORY)
        hass.config_entries.async_update_entry(entry, options=new_options)

    # Register update listener (after cleanup to avoid spurious reload)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = entry.runtime_data
        await coordinator.async_unload()
            
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
