"""Sensor platform for Max Min integration."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
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
from .coordinator import MaxMinDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data["max_min"][config_entry.entry_id]
    types = config_entry.options.get(CONF_TYPES, config_entry.data.get(CONF_TYPES, [TYPE_MAX, TYPE_MIN]))
    period = config_entry.options.get(CONF_PERIOD, config_entry.data.get(CONF_PERIOD, PERIOD_DAILY))

    entities = []
    sensor_state = hass.states.get(config_entry.data[CONF_SENSOR_ENTITY])
    sensor_name = sensor_state.attributes.get("friendly_name", config_entry.data[CONF_SENSOR_ENTITY]) if sensor_state else config_entry.data[CONF_SENSOR_ENTITY]

    period_labels = {
        PERIOD_DAILY: "Daily",
        PERIOD_WEEKLY: "Weekly",
        PERIOD_MONTHLY: "Monthly",
        PERIOD_YEARLY: "Yearly",
    }
    period_label = period_labels.get(period, period)

    if TYPE_MAX in types:
        entities.append(MaxSensor(coordinator, config_entry, f"Max {sensor_name} {period_label}"))
    if TYPE_MIN in types:
        entities.append(MinSensor(coordinator, config_entry, f"Min {sensor_name} {period_label}"))

    async_add_entities(entities)


class MaxSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Max sensor."""

    def __init__(self, coordinator: MaxMinDataUpdateCoordinator, config_entry: ConfigEntry, name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_max"
        self._attr_device_class = "measurement"
        self._attr_state_class = "measurement"
        # Inherit unit from source sensor
        source_entity = config_entry.data[CONF_SENSOR_ENTITY]
        if coordinator.hass:
            source_state = coordinator.hass.states.get(source_entity)
            if source_state and source_state.attributes.get("unit_of_measurement"):
                self._attr_unit_of_measurement = source_state.attributes["unit_of_measurement"]

    @property
    def device_info(self):
        """Return device info."""
        device_id = self._config_entry.data.get(CONF_DEVICE_ID)
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
        return self.coordinator.max_value

    @property
    def available(self):
        """Return if the sensor is available."""
        return self.coordinator.max_value is not None


class MinSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Min sensor."""

    def __init__(self, coordinator: MaxMinDataUpdateCoordinator, config_entry: ConfigEntry, name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_min"
        self._attr_device_class = "measurement"
        self._attr_state_class = "measurement"
        # Inherit unit from source sensor
        source_entity = config_entry.data[CONF_SENSOR_ENTITY]
        if coordinator.hass:
            source_state = coordinator.hass.states.get(source_entity)
            if source_state and source_state.attributes.get("unit_of_measurement"):
                self._attr_unit_of_measurement = source_state.attributes["unit_of_measurement"]

    @property
    def device_info(self):
        """Return device info."""
        device_id = self._config_entry.data.get(CONF_DEVICE_ID)
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
        return self.coordinator.min_value

    @property
    def available(self):
        """Return if the sensor is available."""
        return self.coordinator.min_value is not None