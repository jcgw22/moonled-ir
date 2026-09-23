"""Light platform for the moonLedRemote moon lamp via HA's core `infrared`.

This is a hand-built variant of Home Assistant core's `led_infrared`
integration (see README.md) for one specific 24-key RGB LED remote whose
top-row function keys don't match the standard layout -- see
HANDOFF-moonled-ir-mate.md for how each command byte was verified.

Like led_infrared, this sends commands through an `infrared.*` emitter
entity (InfraredEmitterConsumerEntity) using the standard NEC encoder --
no bespoke ESPHome service needed, just the `ir_rf_proxy` platform on the
IR Mate node. Unlike led_infrared's ColorMode.ONOFF + effect-list
approach, this models the lamp as a real RGB + brightness light: colour
buttons map to ColorMode.RGB (nearest-match on requested RGB), and the two
relative brightness buttons are exposed as a 4-level brightness attribute
via a calibrate-then-step hack -- see MoonLedIrLight._async_set_level.

Settable via YAML (PLATFORM_SCHEMA/async_setup_platform) or the UI
(config_flow.py/async_setup_entry) -- both end up calling the same
MoonLedIrLight constructor with a plain mapping of the same keys.
"""

from __future__ import annotations

import asyncio
from typing import Any

import probatio

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    BRIGHTNESS_LEVELS,
    CMD_BRIGHTNESS_DOWN,
    CMD_BRIGHTNESS_UP,
    CMD_OFF,
    CMD_ON,
    COLORS,
    CONF_ADDRESS,
    CONF_CARRIER_FREQUENCY,
    CONF_INFRARED_ENTITY_ID,
    CONF_REPEAT_COUNT,
    DEFAULT_ADDRESS,
    DEFAULT_CARRIER_FREQUENCY,
    DEFAULT_NAME,
    DEFAULT_REPEAT_COUNT,
    DOMAIN,
    EFFECTS,
)
from .protocol import build_command

# NOTE: voluptuous was renamed probatio in HA core; `probatio.Required` /
# `probatio.Optional` are the same API voluptuous had, just reimported.
PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_INFRARED_ENTITY_ID): cv.entity_id,
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Optional(CONF_ADDRESS, default=DEFAULT_ADDRESS): cv.positive_int,
        probatio.Optional(
            CONF_CARRIER_FREQUENCY, default=DEFAULT_CARRIER_FREQUENCY
        ): cv.positive_int,
        probatio.Optional(
            CONF_REPEAT_COUNT, default=DEFAULT_REPEAT_COUNT
        ): cv.positive_int,
    }
)

# Evenly spaced HA brightness (0-255) values for the lamp's 4 physical
# brightness steps, e.g. {1: 64, 2: 128, 3: 191, 4: 255}.
LEVEL_TO_BRIGHTNESS = {
    level: round(level * 255 / BRIGHTNESS_LEVELS)
    for level in range(1, BRIGHTNESS_LEVELS + 1)
}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the moonLedRemote light from YAML."""
    name = config[CONF_NAME]
    async_add_entities(
        [MoonLedIrLight(config, unique_id=f"moonled_ir_{name.lower().replace(' ', '_')}")]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the moonLedRemote light from a config entry (the GUI flow)."""
    async_add_entities([MoonLedIrLight(entry.data, unique_id=entry.entry_id)])


class MoonLedIrLight(InfraredEmitterConsumerEntity, LightEntity):
    """A moonLedRemote-controlled lamp, sent via an `infrared` emitter entity.

    assumed_state: there is no feedback path from the lamp itself (only the
    IR Mate's receiver, which isn't wired to this entity), so every
    attribute here is Home Assistant's best guess based on what it has
    sent. Using the physical remote in parallel will drift this entity's
    state until the next command re-syncs it.
    """

    _attr_assumed_state = True
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = list(EFFECTS)

    def __init__(self, config: ConfigType, unique_id: str) -> None:
        """Initialize the entity from a YAML or config-entry mapping.

        `unique_id` is passed in rather than derived from the name, since a
        config-entry-created entity must key off the entry's own (renameable
        -safe) entry_id, not the user-visible name.
        """
        self._attr_name = config[CONF_NAME]
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)}, name=config[CONF_NAME]
        )
        self._infrared_emitter_entity_id = config[CONF_INFRARED_ENTITY_ID]
        # int(): the GUI config flow's NumberSelector fields come back as
        # floats (even for entries created before that was fixed at the
        # source in config_flow.py) -- NECCommand does bitwise ops on
        # address/command that floats don't support.
        self._address = int(config[CONF_ADDRESS])
        self._carrier_frequency = int(config[CONF_CARRIER_FREQUENCY])
        self._repeat_count = int(config[CONF_REPEAT_COUNT])

        self._attr_is_on = False
        self._attr_rgb_color = next(iter(COLORS.values()))
        self._attr_effect = None
        # Physical brightness step, 1..BRIGHTNESS_LEVELS. None = never set
        # from HA this session -- see _async_set_level.
        self._level: int | None = None
        self._attr_brightness = LEVEL_TO_BRIGHTNESS[BRIGHTNESS_LEVELS]

    async def _async_send(self, command_byte: int) -> None:
        """Send one IR button press and wait for it to fully transmit.

        The underlying remote_transmitter is non_blocking, so back-to-back
        sends (e.g. several brightness steps) can otherwise overlap on the
        RMT peripheral -- wait out the command's own duration before the
        next one.
        """
        command = build_command(
            command_byte, self._address, self._repeat_count, self._carrier_frequency
        )
        duration = sum(abs(t) for t in command.get_raw_timings()) / 1_000_000
        await self._send_command(command)
        await asyncio.sleep(duration + 0.05)

    async def _async_set_level(self, target: int) -> None:
        """Step the lamp's relative brightness to `target` (1..N).

        There's no feedback path, so on the first brightness change this
        session we first force the lamp to the bottom step with N-1 DOWN
        presses, then step up to the target. After that we trust our own
        tracked `_level` and just send the delta.
        """
        if self._level is None:
            for _ in range(BRIGHTNESS_LEVELS - 1):
                await self._async_send(CMD_BRIGHTNESS_DOWN)
            self._level = 1

        delta = target - self._level
        command_byte = CMD_BRIGHTNESS_UP if delta > 0 else CMD_BRIGHTNESS_DOWN
        for _ in range(abs(delta)):
            await self._async_send(command_byte)
        self._level = target

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the lamp on and apply any requested colour/effect/brightness.

        ON is sent unconditionally on every call (confirmed harmless while
        already on) rather than gated on tracked state, since this is an
        assumed_state entity and the physical remote can desync it.
        """
        await self._async_send(CMD_ON)
        self._attr_is_on = True

        if ATTR_RGB_COLOR in kwargs:
            requested = kwargs[ATTR_RGB_COLOR]
            command_byte, matched = min(
                COLORS.items(),
                key=lambda item: sum(
                    (a - b) ** 2 for a, b in zip(item[1], requested)
                ),
            )
            await self._async_send(command_byte)
            self._attr_rgb_color = matched
            self._attr_effect = None

        if ATTR_EFFECT in kwargs:
            effect = kwargs[ATTR_EFFECT]
            if effect in EFFECTS:
                await self._async_send(EFFECTS[effect])
                self._attr_effect = effect

        if ATTR_BRIGHTNESS in kwargs:
            requested = kwargs[ATTR_BRIGHTNESS]
            target = min(
                LEVEL_TO_BRIGHTNESS,
                key=lambda level: abs(LEVEL_TO_BRIGHTNESS[level] - requested),
            )
            await self._async_set_level(target)
            self._attr_brightness = LEVEL_TO_BRIGHTNESS[target]

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the lamp off. Sent unconditionally, same reasoning as turn_on."""
        await self._async_send(CMD_OFF)
        self._attr_is_on = False
        self.async_write_ha_state()
