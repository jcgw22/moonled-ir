"""The moonLedRemote moon lamp integration.

Supports both YAML (`light: - platform: moonled_ir`, see light.py's
PLATFORM_SCHEMA) and UI-based config entries (see config_flow.py) --
async_setup_entry below just forwards to the light platform, same as any
other config-entry integration. Depends on HA core's `infrared` domain
(declared in manifest.json) for the emitter entity this light sends
commands through -- see light.py and README.md.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a moon lamp from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
