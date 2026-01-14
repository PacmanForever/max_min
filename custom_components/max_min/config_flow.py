"""Config flow for Max Min integration."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE_ID,
    CONF_INITIAL_MAX,
    CONF_INITIAL_MIN,
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
)


class MaxMinConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Max Min."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.data = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
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
                        ],
                        multiple=True,
                    )
                ),
            }),
            errors=errors,
        )

    async def async_step_optional_settings(self, user_input=None):
        """Handle optional settings step."""
        errors = {}
        if user_input is not None:
            initial_min = user_input.get(CONF_INITIAL_MIN)
            initial_max = user_input.get(CONF_INITIAL_MAX)

            if initial_min is not None and initial_max is not None and initial_min > initial_max:
                errors["base"] = "min_greater_than_max"
            else:
                final_data = {**self.data, **user_input}
                
                # Create a better title
                sensor_entity = self.data[CONF_SENSOR_ENTITY]
                sensor_name = sensor_entity
                if self.hass:
                    state = self.hass.states.get(sensor_entity)
                    if state and state.name:
                        sensor_name = state.name

                types = self.data.get(CONF_TYPES, [])
                if TYPE_MAX in types and TYPE_MIN in types:
                    suffix = "Max/Min"
                elif TYPE_MAX in types:
                    suffix = "Max"
                elif TYPE_MIN in types:
                    suffix = "Min"
                else:
                    suffix = "Max/Min"

                title = f"{sensor_name} ({suffix})"
                
                return self.async_create_entry(title=title, data=final_data)
        
        # Defaults
        suggested_min = None
        suggested_max = None
        default_device = None

        return self.async_show_form(
            step_id="optional_settings",
            data_schema=vol.Schema({
                vol.Optional(CONF_INITIAL_MIN, description={"suggested_value": suggested_min}): vol.Coerce(float),
                vol.Optional(CONF_INITIAL_MAX, description={"suggested_value": suggested_max}): vol.Coerce(float),
                vol.Optional(CONF_DEVICE_ID, description={"suggested_value": default_device}): selector.DeviceSelector(
                    selector.DeviceSelectorConfig()
                ),
            }),
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
        self.options = {}

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_optional_settings()

        # Defaults for schema
        default_types = self._config_entry.options.get(CONF_TYPES, self._config_entry.data.get(CONF_TYPES, [TYPE_MAX, TYPE_MIN]))
        default_periods = self._config_entry.options.get(CONF_PERIODS, self._config_entry.data.get(CONF_PERIODS, [PERIOD_DAILY]))
        
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
                vol.Optional(
                    CONF_TYPES,
                    default=default_types,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": TYPE_MIN, "label": "Minimum"},
                            {"value": TYPE_MAX, "label": "Maximum"},
                        ],
                        multiple=True,
                    )
                ),
            }),
        )

    async def async_step_optional_settings(self, user_input=None):
        """Manage optional settings."""
        errors = {}
        if user_input is not None:
            initial_min = user_input.get(CONF_INITIAL_MIN)
            initial_max = user_input.get(CONF_INITIAL_MAX)

            if initial_min is not None and initial_max is not None and initial_min > initial_max:
                errors["base"] = "min_greater_than_max"
            else:
                self.options.update(user_input)
                # Ensure device_id is captured as None if cleared/missing to override data
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

                        types = self.options.get(CONF_TYPES, self._config_entry.data.get(CONF_TYPES, []))
                        
                        if TYPE_MAX in types and TYPE_MIN in types:
                            suffix = "Max/Min"
                        elif TYPE_MAX in types:
                            suffix = "Max"
                        elif TYPE_MIN in types:
                            suffix = "Min"
                        else:
                            suffix = "Max/Min"
                        
                        new_title = f"{sensor_name} ({suffix})"
                        self.hass.config_entries.async_update_entry(self._config_entry, title=new_title)

                return self.async_create_entry(title="", data=self.options)

        # Defaults
        default_min = None
        default_max = None
        default_device = self._config_entry.options.get(CONF_DEVICE_ID, self._config_entry.data.get(CONF_DEVICE_ID))

        return self.async_show_form(
            step_id="optional_settings",
            data_schema=vol.Schema({
                vol.Optional(CONF_INITIAL_MIN, description={"suggested_value": default_min}): vol.Coerce(float),
                vol.Optional(CONF_INITIAL_MAX, description={"suggested_value": default_max}): vol.Coerce(float),
                vol.Optional(CONF_DEVICE_ID, description={"suggested_value": default_device}): selector.DeviceSelector(
                    selector.DeviceSelectorConfig()
                ),
            }),
            errors=errors,
        )