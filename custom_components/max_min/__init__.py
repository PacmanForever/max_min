"""Max Min integration for Home Assistant."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, CONF_RESET_HISTORY
from .coordinator import MaxMinDataUpdateCoordinator


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Max Min integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Max Min from a config entry."""
    coordinator = MaxMinDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    # Register update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Surgical Reset Cleanup:
    # If the entry was reloaded with a reset list, clear it now so it doesn't
    # reset again on the next HA restart. 
    # This will trigger ONE more reload, but it's the only way to persist the clear.
    if entry.options.get(CONF_RESET_HISTORY):
        new_options = dict(entry.options)
        new_options.pop(CONF_RESET_HISTORY)
        hass.config_entries.async_update_entry(entry, options=new_options)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    if unload_ok:
        coordinator = entry.runtime_data
        await coordinator.async_unload()
            
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
