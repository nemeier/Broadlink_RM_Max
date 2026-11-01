"""Configuration flow for Broadlink RM Max."""

from typing import Any

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

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

        if user_input is not None:
            return self.async_create_entry(title="Broadlink RM Max", data={})

        return self.async_show_form(step_id="user")