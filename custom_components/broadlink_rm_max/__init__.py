"""Set up the independent Broadlink RM Max integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .connection import ConnectionFailure, test_connection
from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Verify connectivity and register the device without control entities."""
    if not entry.data.get(CONF_HOST):
        raise ConfigEntryError(
            "Reconfigure Broadlink RM Max and enter its IP address or hostname."
        )
    try:
        device = await hass.async_add_executor_job(
            test_connection, entry.data[CONF_HOST]
        )
    except ConnectionFailure as err:
        if err.reason in ("cannot_connect", "cannot_resolve"):
            raise ConfigEntryNotReady(err.reason) from err
        raise ConfigEntryError(err.reason) from err
    if device.mac != entry.data.get("mac"):
        raise ConfigEntryError(
            "The address now belongs to a different device; reconfigure the integration."
        )
    entry.runtime_data = device
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device.mac)},
        manufacturer="Broadlink",
        model="RM Max",
        name="Broadlink RM Max",
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry without allocated resources."""
    return True
