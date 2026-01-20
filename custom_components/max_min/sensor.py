"""Sensor platform for Max Min integration."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .coordinator import MaxMinDataUpdateCoordinator
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
    TYPE_DELTA,
)
class DeltaSensor(CoordinatorEntity, SensorEntity, RestoreEntity):
    """Representation of a Delta sensor (end - start)."""

    def __init__(self, coordinator: MaxMinDataUpdateCoordinator, config_entry: ConfigEntry, name: str, period: str) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = name
        self.period = period
        self._attr_unique_id = f"{config_entry.entry_id}_{period}_delta"
        self._source_entity = config_entry.data[CONF_SENSOR_ENTITY]
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None
        self._attr_state_class = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # No restore logic needed for delta, as coordinator manages start/end

    @property
    def extra_state_attributes(self):
        attrs = {}
        last_reset = self.coordinator.get_value(self.period, "last_reset")
        if last_reset:
            attrs["last_reset"] = last_reset.isoformat()
        start = self.coordinator.get_value(self.period, "start")
        end = self.coordinator.get_value(self.period, "end")
        if start is not None:
            attrs["start_value"] = start
        if end is not None:
            attrs["end_value"] = end
        return attrs

    @property
    def native_unit_of_measurement(self):
        if self.coordinator.hass:
            state = self.coordinator.hass.states.get(self._source_entity)
            if state and "unit_of_measurement" in state.attributes:
                self._attr_native_unit_of_measurement = state.attributes.get("unit_of_measurement")
        return self._attr_native_unit_of_measurement

    @property
    def device_class(self):
        if self.coordinator.hass:
            state = self.coordinator.hass.states.get(self._source_entity)
            if state and "device_class" in state.attributes:
                self._attr_device_class = state.attributes.get("device_class")
        return self._attr_device_class

    @property
    def state_class(self):
        if self.coordinator.hass:
            state = self.coordinator.hass.states.get(self._source_entity)
            if state and "state_class" in state.attributes:
                self._attr_state_class = state.attributes.get("state_class")
        return self._attr_state_class

    @property
    def device_info(self):
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
        start = self.coordinator.get_value(self.period, "start")
        end = self.coordinator.get_value(self.period, "end")
        if start is not None and end is not None:
            return end - start
        return None

    @property
    def available(self):
        start = self.coordinator.get_value(self.period, "start")
        end = self.coordinator.get_value(self.period, "end")
        return start is not None and end is not None

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

    # Identify and remove stale entities
    # Calculate all expected unique IDs for the current configuration
    expected_unique_ids = set()
    for period in periods:
        if TYPE_MAX in types:
            expected_unique_ids.add(f"{config_entry.entry_id}_{period}_max")
        if TYPE_MIN in types:
            expected_unique_ids.add(f"{config_entry.entry_id}_{period}_min")

    ent_reg = er.async_get(hass)
    entity_entries = er.async_entries_for_config_entry(ent_reg, config_entry.entry_id)
    for entity_entry in entity_entries:
        if entity_entry.unique_id not in expected_unique_ids:
            ent_reg.async_remove(entity_entry.entity_id)

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
        if TYPE_DELTA in types:
            entities.append(DeltaSensor(coordinator, config_entry, f"{sensor_name} {period_label} Delta", period))

    async_add_entities(entities)


class MaxSensor(CoordinatorEntity, SensorEntity, RestoreEntity):
    """Representation of a Max sensor."""

    def __init__(self, coordinator: MaxMinDataUpdateCoordinator, config_entry: ConfigEntry, name: str, period: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = name
        self.period = period
        self._attr_unique_id = f"{config_entry.entry_id}_{period}_max"
        self._source_entity = config_entry.data[CONF_SENSOR_ENTITY]
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None
        self._attr_state_class = None

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            # Restore attributes if available
            self._attr_native_unit_of_measurement = last_state.attributes.get("unit_of_measurement")
            self._attr_device_class = last_state.attributes.get("device_class")
            self._attr_state_class = last_state.attributes.get("state_class")

            if last_state.state not in (None, "unknown", "unavailable"):
                try:
                    value = float(last_state.state)
                    last_reset = last_state.attributes.get("last_reset")
                    self.coordinator.update_restored_data(self.period, "max", value, last_reset)
                except ValueError:
                    pass

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        last_reset = self.coordinator.get_value(self.period, "last_reset")
        if last_reset:
            attrs["last_reset"] = last_reset.isoformat()
        return attrs

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        if self.coordinator.hass:
            state = self.coordinator.hass.states.get(self._source_entity)
            if state and "unit_of_measurement" in state.attributes:
                self._attr_native_unit_of_measurement = state.attributes.get("unit_of_measurement")
        return self._attr_native_unit_of_measurement

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self.coordinator.hass:
            state = self.coordinator.hass.states.get(self._source_entity)
            if state and "device_class" in state.attributes:
                self._attr_device_class = state.attributes.get("device_class")
        return self._attr_device_class

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        if self.coordinator.hass:
            state = self.coordinator.hass.states.get(self._source_entity)
            if state and "state_class" in state.attributes:
                self._attr_state_class = state.attributes.get("state_class")
        return self._attr_state_class

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


class MinSensor(CoordinatorEntity, SensorEntity, RestoreEntity):
    """Representation of a Min sensor."""

    def __init__(self, coordinator: MaxMinDataUpdateCoordinator, config_entry: ConfigEntry, name: str, period: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = name
        self.period = period
        self._attr_unique_id = f"{config_entry.entry_id}_{period}_min"
        self._source_entity = config_entry.data[CONF_SENSOR_ENTITY]
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None
        self._attr_state_class = None

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            # Restore attributes if available
            self._attr_native_unit_of_measurement = last_state.attributes.get("unit_of_measurement")
            self._attr_device_class = last_state.attributes.get("device_class")
            self._attr_state_class = last_state.attributes.get("state_class")

            if last_state.state not in (None, "unknown", "unavailable"):
                try:
                    value = float(last_state.state)
                    last_reset = last_state.attributes.get("last_reset")
                    self.coordinator.update_restored_data(self.period, "min", value, last_reset)
                except ValueError:
                    pass

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        last_reset = self.coordinator.get_value(self.period, "last_reset")
        if last_reset:
            attrs["last_reset"] = last_reset.isoformat()
        return attrs

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        if self.coordinator.hass:
            state = self.coordinator.hass.states.get(self._source_entity)
            if state and "unit_of_measurement" in state.attributes:
                self._attr_native_unit_of_measurement = state.attributes.get("unit_of_measurement")
        return self._attr_native_unit_of_measurement

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self.coordinator.hass:
            state = self.coordinator.hass.states.get(self._source_entity)
            if state and "device_class" in state.attributes:
                self._attr_device_class = state.attributes.get("device_class")
        return self._attr_device_class

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        if self.coordinator.hass:
            state = self.coordinator.hass.states.get(self._source_entity)
            if state and "state_class" in state.attributes:
                self._attr_state_class = state.attributes.get("state_class")
        return self._attr_state_class

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
