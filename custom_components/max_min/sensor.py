"""Sensor platform for Max Min integration."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
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
from .coordinator import MaxMinDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data["max_min"][config_entry.entry_id]
    types = config_entry.options.get(CONF_TYPES, config_entry.data.get(CONF_TYPES, [TYPE_MAX, TYPE_MIN]))
    periods = config_entry.options.get(CONF_PERIODS, config_entry.data.get(CONF_PERIODS, [PERIOD_DAILY]))
    # Fallback to verify single list
    if isinstance(periods, str):
        periods = [periods]

    # Clean up device association if device is removed
    device_id = config_entry.options.get(CONF_DEVICE_ID, config_entry.data.get(CONF_DEVICE_ID))
    if not device_id:
        # Unlink entities from device
        ent_reg = er.async_get(hass)
        # We need to find all entities related to this config entry
        # The period is part of unique_id now, so we can't strict predict suffix easily without knowing old periods
        # But we can iterate over registry entries
        entity_entries = er.async_entries_for_config_entry(ent_reg, config_entry.entry_id)
        for entity_entry in entity_entries:
            if entity_entry.device_id:
                 ent_reg.async_update_entity(entity_entry.entity_id, device_id=None)
        
        # Unlink config entry from device
        dev_reg = dr.async_get(hass)
        devices_to_unlink = [
            dev.id for dev in dev_reg.devices.values() 
            if config_entry.entry_id in dev.config_entries
        ]
        for dev_id in devices_to_unlink:
            dev_reg.async_update_device(dev_id, remove_config_entry_id=config_entry.entry_id)

    entities = []
    source_entity = config_entry.data[CONF_SENSOR_ENTITY]
    sensor_name = source_entity

    # Try to get valid name from registry or state
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(source_entity)
    if entry and (entry.name or entry.original_name):
        sensor_name = entry.name or entry.original_name
    else:
        sensor_state = hass.states.get(source_entity)
        if sensor_state and sensor_state.attributes.get("friendly_name"):
            sensor_name = sensor_state.attributes.get("friendly_name")

    period_labels = {
        PERIOD_DAILY: "Daily",
        PERIOD_WEEKLY: "Weekly",
        PERIOD_MONTHLY: "Monthly",
        PERIOD_YEARLY: "Yearly",
        PERIOD_ALL_TIME: "All time",
    }
    
    for period in periods:
        period_label = period_labels.get(period, period)
        if TYPE_MAX in types:
            entities.append(MaxSensor(coordinator, config_entry, f"{sensor_name} {period_label} Max", period))
        if TYPE_MIN in types:
            entities.append(MinSensor(coordinator, config_entry, f"{sensor_name} {period_label} Min", period))

    async_add_entities(entities)


class MaxSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Max sensor."""

    def __init__(self, coordinator: MaxMinDataUpdateCoordinator, config_entry: ConfigEntry, name: str, period: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = name
        self.period = period
        self._attr_unique_id = f"{config_entry.entry_id}_{period}_max"
        
        # Inherit attributes from source sensor
        source_entity = config_entry.data[CONF_SENSOR_ENTITY]
        if coordinator.hass:
            source_state = coordinator.hass.states.get(source_entity)
            if source_state:
                if source_state.attributes.get("unit_of_measurement"):
                    self._attr_native_unit_of_measurement = source_state.attributes["unit_of_measurement"]
                if source_state.attributes.get("device_class"):
                    self._attr_device_class = source_state.attributes["device_class"]
                if source_state.attributes.get("state_class"):
                    self._attr_state_class = source_state.attributes["state_class"]

    @property
    def device_info(self):
        """Return device info."""
        device_id = self._config_entry.options.get(CONF_DEVICE_ID, self._config_entry.data.get(CONF_DEVICE_ID))
        if device_id and self.coordinator.hass:
            device_registry = dr.async_get(self.coordinator.hass)
            device = device_registry.async_get(device_id)
            if device:
                return {
                    "identifiers": device.identifiers,
                    "connections": device.connections,
                }
        return None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.get_value(self.period, "max")

    @property
    def available(self):
        """Return if the sensor is available."""
        return self.coordinator.get_value(self.period, "max") is not None


class MinSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Min sensor."""

    def __init__(self, coordinator: MaxMinDataUpdateCoordinator, config_entry: ConfigEntry, name: str, period: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = name
        self.period = period
        self._attr_unique_id = f"{config_entry.entry_id}_{period}_min"
        
        # Inherit attributes from source sensor
        source_entity = config_entry.data[CONF_SENSOR_ENTITY]
        if coordinator.hass:
            source_state = coordinator.hass.states.get(source_entity)
            if source_state:
                if source_state.attributes.get("unit_of_measurement"):
                    self._attr_native_unit_of_measurement = source_state.attributes["unit_of_measurement"]
                if source_state.attributes.get("device_class"):
                    self._attr_device_class = source_state.attributes["device_class"]
                if source_state.attributes.get("state_class"):
                    self._attr_state_class = source_state.attributes["state_class"]

    @property
    def device_info(self):
        """Return device info."""
        device_id = self._config_entry.options.get(CONF_DEVICE_ID, self._config_entry.data.get(CONF_DEVICE_ID))
        if device_id and self.coordinator.hass:
            device_registry = dr.async_get(self.coordinator.hass)
            device = device_registry.async_get(device_id)
            if device:
                return {
                    "identifiers": device.identifiers,
                    "connections": device.connections,
                }
        return None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.get_value(self.period, "min")

    @property
    def available(self):
        """Return if the sensor is available."""
        return self.coordinator.get_value(self.period, "min") is not None
