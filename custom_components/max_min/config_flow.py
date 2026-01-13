"""Config flow for Max Min integration."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE_ID,
    CONF_INITIAL_MAX,
    CONF_INITIAL_MIN,
    CONF_PERIOD,
    CONF_SENSOR_ENTITY,
    CONF_TYPES,
    DOMAIN,
    PERIOD_DAILY,
    PERIOD_MONTHLY,
    PERIOD_WEEKLY,
    PERIOD_YEARLY,
    TYPE_MAX,
    TYPE_MIN,
)


class MaxMinConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Max Min."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            initial_min = user_input.get(CONF_INITIAL_MIN)
            initial_max = user_input.get(CONF_INITIAL_MAX)

            if initial_min is not None and initial_max is not None and initial_min > initial_max:
                errors["base"] = "min_greater_than_max"
            else:
                # Set unique ID based on sensor and period to allow multiple periods per sensor
                sensor_entity = user_input[CONF_SENSOR_ENTITY]
                period = user_input[CONF_PERIOD]
                await self.async_set_unique_id(f"{sensor_entity}_{period}")
                abort_result = self._abort_if_unique_id_configured()
                if abort_result:
                    return abort_result

                # Create a better title
                period_label = period.capitalize()
                sensor_name = sensor_entity
                if self.hass:
                    state = self.hass.states.get(sensor_entity)
                    if state and state.name:
                        sensor_name = state.name

                title = f"{sensor_name} - {period_label}"
                
                return self.async_create_entry(title=title, data=user_input)

        # Defaults for schema
        default_sensor = user_input.get(CONF_SENSOR_ENTITY) if user_input else vol.UNDEFINED
        default_period = user_input.get(CONF_PERIOD, PERIOD_DAILY) if user_input else PERIOD_DAILY
        default_types = user_input.get(CONF_TYPES, [TYPE_MAX, TYPE_MIN]) if user_input else [TYPE_MAX, TYPE_MIN]
        suggested_min = user_input.get(CONF_INITIAL_MIN) if user_input else None
        suggested_max = user_input.get(CONF_INITIAL_MAX) if user_input else None
        default_device = user_input.get(CONF_DEVICE_ID) if user_input else None

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_SENSOR_ENTITY, default=default_sensor): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_DEVICE_ID, description={"suggested_value": default_device}): selector.DeviceSelector(
                    selector.DeviceSelectorConfig()
                ),
                vol.Required(CONF_PERIOD, default=default_period): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": PERIOD_DAILY, "label": "Daily"},
                            {"value": PERIOD_WEEKLY, "label": "Weekly"},
                            {"value": PERIOD_MONTHLY, "label": "Monthly"},
                            {"value": PERIOD_YEARLY, "label": "Yearly"},
                        ]
                    )
                ),
                vol.Required(CONF_TYPES, default=default_types): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": TYPE_MAX, "label": "Maximum"},
                            {"value": TYPE_MIN, "label": "Minimum"},
                        ],
                        multiple=True,
                    )
                ),
                vol.Optional(CONF_INITIAL_MIN, description={"suggested_value": suggested_min}): vol.Coerce(float),
                vol.Optional(CONF_INITIAL_MAX, description={"suggested_value": suggested_max}): vol.Coerce(float),
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

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}
        if user_input is not None:
            initial_min = user_input.get(CONF_INITIAL_MIN)
            initial_max = user_input.get(CONF_INITIAL_MAX)

            if initial_min is not None and initial_max is not None and initial_min > initial_max:
                errors["base"] = "min_greater_than_max"
            else:
                return self.async_create_entry(title="", data=user_input)

        # Defaults for schema
        default_types = self._config_entry.options.get(CONF_TYPES, [TYPE_MAX, TYPE_MIN])
        # In options flow, we don't pre-fill initial values to allow user to keep existing logic
        # or input new values only when needed
        default_min = None
        default_max = None

        if user_input:
             default_types = user_input.get(CONF_TYPES, default_types)
             default_min = user_input.get(CONF_INITIAL_MIN, default_min)
             default_max = user_input.get(CONF_INITIAL_MAX, default_max)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_TYPES,
                    default=default_types,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": TYPE_MAX, "label": "Maximum"},
                            {"value": TYPE_MIN, "label": "Minimum"},
                        ],
                        multiple=True,
                    )
                ),
                vol.Optional(CONF_INITIAL_MIN, description={"suggested_value": default_min}): vol.Coerce(float),
                vol.Optional(CONF_INITIAL_MAX, description={"suggested_value": default_max}): vol.Coerce(float),
            }),
            errors=errors
        )