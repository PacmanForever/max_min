"""Config flow for Max Min integration."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE_ID,
    CONF_INITIAL_MAX,
    CONF_INITIAL_MIN,
    CONF_OFFSET,
    CONF_RESET_HISTORY,
    CONF_PERIODS,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    DOMAIN,
    PERIOD_DAILY,
    PERIOD_MONTHLY,
    PERIOD_WEEKLY,
    PERIOD_YEARLY,
    PERIOD_ALL_TIME,
    TYPE_MAX,
    TYPE_MIN,
    TYPE_DELTA,
)


class MaxMinConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Max Min."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.data = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            if not user_input.get(CONF_PERIODS):
                errors[CONF_PERIODS] = "periods_required"
            
            if not user_input.get(CONF_TYPES):
                errors[CONF_TYPES] = "types_required"

            if not errors:
                # Set unique ID based on sensor 
                # Now we allow only one entry per sensor, managing multiple periods
                sensor_entity = user_input[CONF_SENSOR_ENTITY]
                await self.async_set_unique_id(f"{sensor_entity}")
                abort_result = self._abort_if_unique_id_configured()
                if abort_result:
                    return abort_result

                self.data = user_input
                return await self.async_step_optional_settings()

        # Defaults for schema
        default_sensor = user_input.get(CONF_SENSOR_ENTITY) if user_input else vol.UNDEFINED
        default_periods = user_input.get(CONF_PERIODS, [PERIOD_DAILY]) if user_input else [PERIOD_DAILY]
        default_types = user_input.get(CONF_TYPES, [TYPE_MAX, TYPE_MIN]) if user_input else [TYPE_MAX, TYPE_MIN]
        default_offset = user_input.get(CONF_OFFSET, 0) if user_input else 0

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_SENSOR_ENTITY, default=default_sensor): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_PERIODS, default=default_periods): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": PERIOD_DAILY, "label": "Daily"},
                            {"value": PERIOD_WEEKLY, "label": "Weekly"},
                            {"value": PERIOD_MONTHLY, "label": "Monthly"},
                            {"value": PERIOD_YEARLY, "label": "Yearly"},
                            {"value": PERIOD_ALL_TIME, "label": "All time"},
                        ],
                        multiple=True,
                    )
                ),
                vol.Required(CONF_TYPES, default=default_types): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": TYPE_MIN, "label": "Minimum"},
                            {"value": TYPE_MAX, "label": "Maximum"},
                            {"value": TYPE_DELTA, "label": "Delta"},
                        ],
                        multiple=True,
                    )
                ),
                vol.Optional(CONF_DEVICE_ID): selector.DeviceSelector(
                    selector.DeviceSelectorConfig()
                ),
                vol.Optional(CONF_OFFSET, default=default_offset): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=300,
                        step=1,
                        unit_of_measurement="seconds",
                    )
                ),
            }),
            errors=errors,
        )

    async def async_step_optional_settings(self, user_input=None):
        """Handle optional settings step."""
        errors = {}
        periods = self.data.get(CONF_PERIODS, [PERIOD_DAILY])
        types = self.data.get(CONF_TYPES, [TYPE_MAX, TYPE_MIN])

        if user_input is not None:
             # Validate min < max for each period
            for period in periods:
                initial_min = user_input.get(f"{period}_{CONF_INITIAL_MIN}")
                initial_max = user_input.get(f"{period}_{CONF_INITIAL_MAX}")

                if initial_min is not None and initial_max is not None and initial_min > initial_max:
                    errors["base"] = "min_greater_than_max"
                    errors[f"{period}_{CONF_INITIAL_MIN}"] = "min_greater_than_max"

            if not errors:
                # Filter out None/empty values so they don't overwrite if not intentional
                # But for ConfigFlow (new entry), we just merge everything
                final_data = {**self.data, **{k: v for k, v in user_input.items() if v is not None}}
                
                # Create a better title
                sensor_entity = self.data[CONF_SENSOR_ENTITY]
                sensor_name = sensor_entity
                if self.hass:
                    state = self.hass.states.get(sensor_entity)
                    if state and state.name:
                        sensor_name = state.name

                suffixes = []
                if TYPE_MAX in types:
                    suffixes.append("Max")
                if TYPE_MIN in types:
                    suffixes.append("Min")
                if TYPE_DELTA in types:
                    suffixes.append("Delta")
                
                suffix = "/".join(suffixes) if suffixes else "Max/Min"

                title = f"{sensor_name} ({suffix})"
                
                return self.async_create_entry(title=title, data=final_data)
        
        # Build schema
        schema = {}
        for period in periods:
            if TYPE_MIN in types:
                key = f"{period}_{CONF_INITIAL_MIN}"
                schema[vol.Optional(key)] = vol.Coerce(float)
            if TYPE_MAX in types:
                key = f"{period}_{CONF_INITIAL_MAX}"
                schema[vol.Optional(key)] = vol.Coerce(float)
        
        # If no settings are relevant (e.g. only Delta selected), skip this step
        if not schema:
            return await self.async_step_optional_settings({})

        return self.async_show_form(
            step_id="optional_settings",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return MaxMinOptionsFlow(config_entry)


class MaxMinOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self._config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}
        if user_input is not None:
            if not user_input.get(CONF_PERIODS):
                errors[CONF_PERIODS] = "periods_required"

            if not user_input.get(CONF_TYPES):
                errors[CONF_TYPES] = "types_required"
            
            if not errors:
                self.options.update(user_input)
                return await self.async_step_optional_settings()

        # Defaults for schema
        default_types = self._config_entry.options.get(CONF_TYPES, self._config_entry.data.get(CONF_TYPES, [TYPE_MAX, TYPE_MIN]))
        default_periods = self._config_entry.options.get(CONF_PERIODS, self._config_entry.data.get(CONF_PERIODS, [PERIOD_DAILY]))
        default_device = self._config_entry.options.get(CONF_DEVICE_ID, self._config_entry.data.get(CONF_DEVICE_ID))
        default_offset = self._config_entry.options.get(CONF_OFFSET, self._config_entry.data.get(CONF_OFFSET, 0))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_PERIODS,
                    default=default_periods,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": PERIOD_DAILY, "label": "Daily"},
                            {"value": PERIOD_WEEKLY, "label": "Weekly"},
                            {"value": PERIOD_MONTHLY, "label": "Monthly"},
                            {"value": PERIOD_YEARLY, "label": "Yearly"},
                            {"value": PERIOD_ALL_TIME, "label": "All time"},
                        ],
                        multiple=True,
                    )
                ),
                vol.Required(
                    CONF_TYPES,
                    default=default_types,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": TYPE_MIN, "label": "Minimum"},
                            {"value": TYPE_MAX, "label": "Maximum"},
                            {"value": TYPE_DELTA, "label": "Delta"},
                        ],
                        multiple=True,
                    )
                ),
                vol.Optional(CONF_DEVICE_ID, description={"suggested_value": default_device}): selector.DeviceSelector(
                    selector.DeviceSelectorConfig()
                ),
                vol.Optional(
                    CONF_OFFSET, 
                    default=default_offset,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=300,
                        step=1,
                        unit_of_measurement="seconds",
                    )
                ),
            }),
            errors=errors,
        )

    async def async_step_optional_settings(self, user_input=None):
        """Manage optional settings."""
        errors = {}
        # Get current configuration (merging existing + new from init step)
        periods = self.options.get(CONF_PERIODS, self._config_entry.options.get(CONF_PERIODS, self._config_entry.data.get(CONF_PERIODS, [PERIOD_DAILY])))
        types = self.options.get(CONF_TYPES, self._config_entry.options.get(CONF_TYPES, self._config_entry.data.get(CONF_TYPES, [TYPE_MAX, TYPE_MIN])))

        if user_input is not None:
             # Validate min < max for each period
            for period in periods:
                initial_min = user_input.get(f"{period}_{CONF_INITIAL_MIN}")
                initial_max = user_input.get(f"{period}_{CONF_INITIAL_MAX}")

                if initial_min is not None and initial_max is not None and initial_min > initial_max:
                    errors["base"] = "min_greater_than_max"
                    errors[f"{period}_{CONF_INITIAL_MIN}"] = "min_greater_than_max"
            
            if not errors:
                # Detect changes in initial values to trigger surgical history resets
                reset_list = []
                for period in periods:
                    for type_ in [TYPE_MIN, TYPE_MAX]:
                        key = f"{period}_initial_{type_}"
                        if key in user_input:
                            new_val = user_input[key]
                            old_val = self.options.get(key, self._config_entry.options.get(key, self._config_entry.data.get(key)))
                            
                            # Normalize for comparison
                            try:
                                n_val = float(new_val) if new_val is not None else None
                                o_val = float(old_val) if old_val is not None else None
                                if n_val != o_val:
                                    reset_list.append(f"{period}_{type_}")
                            except (ValueError, TypeError):
                                if new_val != old_val:
                                    reset_list.append(f"{period}_{type_}")

                # Filter out None/empty values so they don't overwrite existing settings
                filtered_input = {k: v for k, v in user_input.items() if v is not None}
                self.options.update(filtered_input)
                
                if reset_list:
                    self.options[CONF_RESET_HISTORY] = reset_list

                # Ensure device_id is captured as None if cleared/missing to override data
                if CONF_DEVICE_ID not in self.options:
                    # It should be in options based on prev step, but if not we might inherit it or set to None
                    # Actually if user_input (this step) is mostly empty, we rely on self.options from step_init
                    # to carry the device_id.
                    if CONF_DEVICE_ID not in self.options:
                        self.options[CONF_DEVICE_ID] = None
                
                # Update title based on selected types
                if self.hass:
                    sensor_entity = self._config_entry.data.get(CONF_SENSOR_ENTITY)
                    if sensor_entity:
                        sensor_name = sensor_entity
                        state = self.hass.states.get(sensor_entity)
                        if state and state.name:
                            sensor_name = state.name

                        if TYPE_MAX in types and TYPE_MIN in types:
                            suffix = "Max/Min"
                        elif TYPE_MAX in types:
                            suffix = "Max"
                        elif TYPE_MIN in types:
                            suffix = "Min"
                        else:
                            suffix = "Max/Min"
                        
                        new_title = f"{sensor_name} ({suffix})"
                        if new_title != self._config_entry.title:
                            self.hass.config_entries.async_update_entry(self._config_entry, title=new_title)

                return self.async_create_entry(title="", data=self.options)

        # Build schema
        schema = {}
        for period in periods:
            # Try to find specific value, fallback to global legacy value
            if TYPE_MIN in types:
                key = f"{period}_{CONF_INITIAL_MIN}"
                schema[vol.Optional(key)] = vol.Coerce(float)
                
            if TYPE_MAX in types:
                key = f"{period}_{CONF_INITIAL_MAX}"
                schema[vol.Optional(key)] = vol.Coerce(float)

        return self.async_show_form(
            step_id="optional_settings",
            data_schema=vol.Schema(schema),
            errors=errors,
        )