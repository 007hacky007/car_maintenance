"""Config flow for the Car Maintenance integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import (
    CONF_DIRECTION,
    CONF_ODOMETER_ENTITY,
    CONF_UNIT,
    DIRECTION_EXHAUSTED,
    DIRECTION_REMAINING,
    DOMAIN,
    UNIT_KM,
    UNIT_MI,
)


def _odometer_error(hass: HomeAssistant, entity_id: str | None) -> str | None:
    """Validate that the selected odometer entity has a numeric state."""
    if entity_id is None:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return "odometer_not_numeric"
    try:
        float(state.state)
    except ValueError:
        return "odometer_not_numeric"
    return None


def _vehicle_schema(hass: HomeAssistant, defaults: dict[str, Any]) -> vol.Schema:
    default_unit = UNIT_KM if hass.config.units is METRIC_SYSTEM else UNIT_MI
    schema: dict[Any, Any] = {
        vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
    }
    odometer_key = (
        vol.Optional(
            CONF_ODOMETER_ENTITY,
            description={
                "suggested_value": defaults.get(CONF_ODOMETER_ENTITY)
            },
        )
        if defaults.get(CONF_ODOMETER_ENTITY)
        else vol.Optional(CONF_ODOMETER_ENTITY)
    )
    schema[odometer_key] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor")
    )
    schema[
        vol.Required(
            CONF_UNIT, default=defaults.get(CONF_UNIT, default_unit)
        )
    ] = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[UNIT_KM, UNIT_MI],
            translation_key="unit",
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )
    schema[
        vol.Required(
            CONF_DIRECTION,
            default=defaults.get(CONF_DIRECTION, DIRECTION_EXHAUSTED),
        )
    ] = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[DIRECTION_EXHAUSTED, DIRECTION_REMAINING],
            translation_key="direction",
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )
    return vol.Schema(schema)


class CarMaintenanceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the vehicle config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a new vehicle."""
        errors: dict[str, str] = {}
        if user_input is not None:
            odometer = user_input.get(CONF_ODOMETER_ENTITY)
            if error := _odometer_error(self.hass, odometer):
                errors[CONF_ODOMETER_ENTITY] = error
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_ODOMETER_ENTITY: odometer,
                        CONF_UNIT: user_input[CONF_UNIT],
                        CONF_DIRECTION: user_input[CONF_DIRECTION],
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=_vehicle_schema(self.hass, user_input or {}),
            errors=errors,
        )
