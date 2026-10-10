"""Config flow for Booyood Parking Heater BLE integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_EXTERNAL_TEMP_SENSOR,
    CONF_MAC,
    CONF_NAME,
    CONF_PIN,
    CONF_PROTOCOL_VERSION,
    DEFAULT_NAME,
    DEFAULT_PIN,
    DOMAIN,
    PROTOCOL_AUTO,
    PROTOCOL_V1,
    PROTOCOL_V21,
)

_LOGGER = logging.getLogger(__name__)


class BooyoodConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Booyood Parking Heater BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle bluetooth discovery flow."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        device_name = discovery_info.name or discovery_info.address
        self.context["title_placeholders"] = {"name": device_name}

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery and enter PIN."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, self._discovery_info.name or DEFAULT_NAME),
                data={
                    CONF_MAC: self._discovery_info.address,
                    CONF_NAME: user_input.get(CONF_NAME, self._discovery_info.name or DEFAULT_NAME),
                    CONF_PIN: user_input.get(CONF_PIN, DEFAULT_PIN),
                    CONF_PROTOCOL_VERSION: user_input.get(
                        CONF_PROTOCOL_VERSION, PROTOCOL_AUTO
                    ),
                    CONF_EXTERNAL_TEMP_SENSOR: user_input.get(CONF_EXTERNAL_TEMP_SENSOR),
                },
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME,
                    default=self._discovery_info.name or DEFAULT_NAME,
                ): str,
                vol.Required(CONF_PIN, default=DEFAULT_PIN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(
                    CONF_PROTOCOL_VERSION, default=PROTOCOL_AUTO
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=PROTOCOL_AUTO, label="Auto Detect (Recommended)"
                            ),
                            SelectOptionDict(
                                value=PROTOCOL_V21,
                                label="Protocol v2.1 (Booyood 2.2+ Encrypted)",
                            ),
                            SelectOptionDict(
                                value=PROTOCOL_V1,
                                label="Protocol v1.0 (Classic Unencrypted)",
                            ),
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_EXTERNAL_TEMP_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                ),
            }
        )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=schema,
            description_placeholders={"name": self._discovery_info.name or self._discovery_info.address},
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual user initiation."""
        errors: dict[str, str] = {}

        # Scan for available BLE devices
        current_addresses = self._async_current_ids()
        for discovery in async_discovered_service_info(self.hass):
            address = discovery.address
            if address not in current_addresses:
                name = discovery.name or "Unknown"
                self._discovered_devices[address] = f"{name} ({address})"

        if user_input is not None:
            address = user_input[CONF_MAC]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input.get(CONF_NAME, DEFAULT_NAME),
                data={
                    CONF_MAC: address,
                    CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
                    CONF_PIN: user_input.get(CONF_PIN, DEFAULT_PIN),
                    CONF_PROTOCOL_VERSION: user_input.get(
                        CONF_PROTOCOL_VERSION, PROTOCOL_AUTO
                    ),
                    CONF_EXTERNAL_TEMP_SENSOR: user_input.get(CONF_EXTERNAL_TEMP_SENSOR),
                },
            )

        # Build schema
        device_selector: Any
        if self._discovered_devices:
            device_selector = vol.In(self._discovered_devices)
        else:
            device_selector = str

        schema = vol.Schema(
            {
                vol.Required(CONF_MAC): device_selector,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_PIN, default=DEFAULT_PIN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(
                    CONF_PROTOCOL_VERSION, default=PROTOCOL_AUTO
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=PROTOCOL_AUTO, label="Auto Detect (Empfohlen)"
                            ),
                            SelectOptionDict(
                                value=PROTOCOL_V21,
                                label="Protocol v2.1 (Booyood 2.2+ Verschlüsselt)",
                            ),
                            SelectOptionDict(
                                value=PROTOCOL_V1,
                                label="Protocol v1.0 (Klassisch Unverschlüsselt)",
                            ),
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_EXTERNAL_TEMP_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return BooyoodOptionsFlowHandler(config_entry)


class BooyoodOptionsFlowHandler(OptionsFlow):
    """Handle options for Booyood integration (e.g. change external temperature sensor)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_sensor = self.config_entry.options.get(
            CONF_EXTERNAL_TEMP_SENSOR,
            self.config_entry.data.get(CONF_EXTERNAL_TEMP_SENSOR),
        )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_EXTERNAL_TEMP_SENSOR,
                    description={"suggested_value": current_sensor},
                ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
