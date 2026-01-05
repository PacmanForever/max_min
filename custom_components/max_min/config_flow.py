"""Config flow for Max Min integration."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
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
        if user_input is not None:
            return self.async_create_entry(title="Max Min", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_SENSOR_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_PERIOD, default=PERIOD_DAILY): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": PERIOD_DAILY, "label": "Daily"},
                            {"value": PERIOD_WEEKLY, "label": "Weekly"},
                            {"value": PERIOD_MONTHLY, "label": "Monthly"},
                            {"value": PERIOD_YEARLY, "label": "Yearly"},
                        ]
                    )
                ),
                vol.Required(CONF_TYPES, default=[TYPE_MAX, TYPE_MIN]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": TYPE_MAX, "label": "Maximum"},
                            {"value": TYPE_MIN, "label": "Minimum"},
                        ],
                        multiple=True,
                    )
                ),
            }),
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
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_PERIOD,
                    default=self._config_entry.options.get(CONF_PERIOD, PERIOD_DAILY),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": PERIOD_DAILY, "label": "Daily"},
                            {"value": PERIOD_WEEKLY, "label": "Weekly"},
                            {"value": PERIOD_MONTHLY, "label": "Monthly"},
                            {"value": PERIOD_YEARLY, "label": "Yearly"},
                        ]
                    )
                ),
                vol.Optional(
                    CONF_TYPES,
                    default=self._config_entry.options.get(CONF_TYPES, [TYPE_MAX, TYPE_MIN]),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": TYPE_MAX, "label": "Maximum"},
                            {"value": TYPE_MIN, "label": "Minimum"},
                        ],
                        multiple=True,
                    )
                ),
            }),
        )