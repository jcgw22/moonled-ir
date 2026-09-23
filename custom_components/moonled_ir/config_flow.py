"""Config flow for the moonLedRemote moon lamp integration.

Modelled on HA core's own led_infrared/config_flow.py: pick an infrared
emitter entity from the ones `infrared` already knows about (created by
ir_rf_proxy or similar), plus this lamp's NEC address/timing knobs.
"""

from __future__ import annotations

from typing import Any

import probatio

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_ADDRESS,
    CONF_CARRIER_FREQUENCY,
    CONF_INFRARED_ENTITY_ID,
    CONF_REPEAT_COUNT,
    DEFAULT_ADDRESS,
    DEFAULT_CARRIER_FREQUENCY,
    DEFAULT_NAME,
    DEFAULT_REPEAT_COUNT,
    DOMAIN,
)


def _schema(emitter_entity_ids: list[str]) -> probatio.Schema:
    """Build the (identical) schema used by both the initial and reconfigure steps."""
    return probatio.Schema(
        {
            probatio.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
            probatio.Required(CONF_INFRARED_ENTITY_ID): EntitySelector(
                EntitySelectorConfig(
                    domain=INFRARED_DOMAIN, include_entities=emitter_entity_ids
                )
            ),
            probatio.Optional(CONF_ADDRESS, default=DEFAULT_ADDRESS): NumberSelector(
                NumberSelectorConfig(min=0, max=0xFFFF, mode=NumberSelectorMode.BOX)
            ),
            probatio.Optional(
                CONF_CARRIER_FREQUENCY, default=DEFAULT_CARRIER_FREQUENCY
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1000, max=100000, mode=NumberSelectorMode.BOX
                )
            ),
            probatio.Optional(
                CONF_REPEAT_COUNT, default=DEFAULT_REPEAT_COUNT
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=10, mode=NumberSelectorMode.BOX)
            ),
        }
    )


class MoonLedIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the moon lamp."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_infrared_emitters")

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_INFRARED_ENTITY_ID: user_input[CONF_INFRARED_ENTITY_ID]}
            )
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=_schema(emitter_entity_ids)
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle changing an existing entry's settings."""
        entry = self._get_reconfigure_entry()
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_infrared_emitters")

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_INFRARED_ENTITY_ID: user_input[CONF_INFRARED_ENTITY_ID]}
            )
            return self.async_update_reload_and_abort(entry, data=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _schema(emitter_entity_ids), entry.data
            ),
        )
