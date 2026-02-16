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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data
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
    expected_unique_ids = set()
    for period in periods:
        if TYPE_MAX in types:
            expected_unique_ids.add(f"{config_entry.entry_id}_{period}_max")
        if TYPE_MIN in types:
            expected_unique_ids.add(f"{config_entry.entry_id}_{period}_min")
        if TYPE_DELTA in types:
            expected_unique_ids.add(f"{config_entry.entry_id}_{period}_delta")

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


# ---------------------------------------------------------------------------
# Base class — shared logic for Max / Min / Delta sensors
# ---------------------------------------------------------------------------

class _BaseMaxMinSensor(CoordinatorEntity, SensorEntity, RestoreEntity):
    """Base class with shared properties for Max/Min/Delta sensors."""

    _value_key: str  # Subclasses set this to "max", "min", or override native_value

    def __init__(self, coordinator: MaxMinDataUpdateCoordinator, config_entry: ConfigEntry, name: str, period: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = name
        self.period = period
        self._attr_unique_id = f"{config_entry.entry_id}_{period}_{self._value_key}"
        self._source_entity = config_entry.data[CONF_SENSOR_ENTITY]
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None
        self._attr_state_class = None

    # -- Source-sensor mirrored properties ----------------------------------

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement mirrored from the source sensor."""
        if self.coordinator.hass:
            state = self.coordinator.hass.states.get(self._source_entity)
            # Only update if source is available and has a unit.
            # If source is unavailable (e.g. startup), keep the restored/last known unit.
            if state and state.state not in (None, "unknown", "unavailable") and "unit_of_measurement" in state.attributes:
                self._attr_native_unit_of_measurement = state.attributes.get("unit_of_measurement")
        return self._attr_native_unit_of_measurement

    @property
    def device_class(self):
        """Return the device class mirrored from the source sensor.
        
        We avoid mirroring classes that enforce state_class: total/total_increasing
        because our sensors are all snapshots/measurements of periods.
        """
        if self.coordinator.hass:
            state = self.coordinator.hass.states.get(self._source_entity)
            if state and "device_class" in state.attributes:
                dev_cls = state.attributes.get("device_class")
                if dev_cls in ("energy", "gas", "water", "monetary", "data_size", "data_rate"):
                    return None
                return dev_cls
        return self._attr_device_class

    @property
    def state_class(self):
        """Return the state class. Always measurement to avoid reset issues with statistics."""
        return "measurement"

    @property
    def device_info(self):
        """Return device info linking this entity to the configured device."""
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
    def extra_state_attributes(self):
        """Return the state attributes including last_reset."""
        attrs = {}
        last_reset = self.coordinator.get_value(self.period, "last_reset")
        if last_reset:
            attrs["last_reset"] = last_reset.isoformat()
        return attrs


# ---------------------------------------------------------------------------
# Concrete sensor classes
# ---------------------------------------------------------------------------

class MaxSensor(_BaseMaxMinSensor):
    """Representation of a Max sensor."""

    _value_key = "max"

    async def async_added_to_hass(self) -> None:
        """Restore previous state on startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self._attr_native_unit_of_measurement = last_state.attributes.get("unit_of_measurement")
            self._attr_device_class = last_state.attributes.get("device_class")

            if last_state.state not in (None, "unknown", "unavailable"):
                try:
                    value = float(last_state.state)
                    last_reset = last_state.attributes.get("last_reset")
                    self.coordinator.update_restored_data(self.period, self._value_key, value, last_reset)
                except ValueError:
                    pass

    @property
    def native_value(self):
        """Return the current maximum."""
        return self.coordinator.get_value(self.period, self._value_key)

    @property
    def available(self):
        """Return True when a max value has been recorded."""
        return self.coordinator.get_value(self.period, self._value_key) is not None


class MinSensor(_BaseMaxMinSensor):
    """Representation of a Min sensor."""

    _value_key = "min"

    async def async_added_to_hass(self) -> None:
        """Restore previous state on startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self._attr_native_unit_of_measurement = last_state.attributes.get("unit_of_measurement")
            self._attr_device_class = last_state.attributes.get("device_class")

            if last_state.state not in (None, "unknown", "unavailable"):
                try:
                    value = float(last_state.state)
                    last_reset = last_state.attributes.get("last_reset")
                    self.coordinator.update_restored_data(self.period, self._value_key, value, last_reset)
                except ValueError:
                    pass

    @property
    def native_value(self):
        """Return the current minimum."""
        return self.coordinator.get_value(self.period, self._value_key)

    @property
    def available(self):
        """Return True when a min value has been recorded."""
        return self.coordinator.get_value(self.period, self._value_key) is not None


class DeltaSensor(_BaseMaxMinSensor):
    """Representation of a Delta sensor (end - start)."""

    _value_key = "delta"

    async def async_added_to_hass(self) -> None:
        """Restore previous state on startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self._attr_native_unit_of_measurement = last_state.attributes.get("unit_of_measurement")
            self._attr_device_class = last_state.attributes.get("device_class")

            # Restore start/end from attributes
            start = last_state.attributes.get("start_value")
            end = last_state.attributes.get("end_value")
            last_reset = last_state.attributes.get("last_reset")
            
            if start is not None:
                try:
                    self.coordinator.update_restored_data(self.period, "start", float(start), last_reset)
                except ValueError:
                    pass
            if end is not None:
                try:
                    self.coordinator.update_restored_data(self.period, "end", float(end), last_reset)
                except ValueError:
                    pass

    @property
    def extra_state_attributes(self):
        """Return delta-specific attributes (start, end, last_reset)."""
        attrs = super().extra_state_attributes
        start = self.coordinator.get_value(self.period, "start")
        end = self.coordinator.get_value(self.period, "end")
        if start is not None:
            attrs["start_value"] = start
        if end is not None:
            attrs["end_value"] = end
        return attrs

    @property
    def native_value(self):
        """Return end - start."""
        start = self.coordinator.get_value(self.period, "start")
        end = self.coordinator.get_value(self.period, "end")
        if start is not None and end is not None:
            return end - start
        return None

    @property
    def available(self):
        """Return True when both start and end values exist."""
        start = self.coordinator.get_value(self.period, "start")
        end = self.coordinator.get_value(self.period, "end")
        return start is not None and end is not None
