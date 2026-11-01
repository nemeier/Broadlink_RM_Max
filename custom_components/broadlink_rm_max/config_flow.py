"""Configuration flow for Broadlink RM Max."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from .connection import ConnectionFailure, test_connection
from .const import DOMAIN


class BroadlinkRMMaxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Allow a single independent installation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle installation from the integrations menu."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self._async_test_and_configure(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Connect a legacy entry or change the address of the same device."""
        return await self._async_test_and_configure(
            user_input, self._get_reconfigure_entry()
        )

    async def _async_test_and_configure(
        self,
        user_input: dict[str, Any] | None,
        entry: config_entries.ConfigEntry | None = None,
    ) -> FlowResult:
        """Test discovery and authentication before saving any configuration."""
        errors: dict[str, str] = {}
        host = entry.data.get(CONF_HOST, "") if entry else ""
        if user_input is not None:
            host = user_input.get(CONF_HOST, "").strip()
            try:
                device = await self.hass.async_add_executor_job(test_connection, host)
            except ConnectionFailure as err:
                errors[
                    CONF_HOST
                    if err.reason in ("invalid_host", "cannot_resolve")
                    else "base"
                ] = err.reason
            else:
                if entry and entry.data.get("mac") not in (None, device.mac):
                    return self.async_abort(reason="wrong_device")
                await self.async_set_unique_id(device.mac)
                data = {
                    CONF_HOST: host,
                    "mac": device.mac,
                    "devtype": device.devtype,
                    "name": device.name,
                }
                if entry:
                    return self.async_update_reload_and_abort(
                        entry, unique_id=device.mac, data_updates=data
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Broadlink RM Max", data=data)

        return self.async_show_form(
            step_id="reconfigure" if entry else "user",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=host): str}),
            errors=errors,
        )
