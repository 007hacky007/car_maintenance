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
    CONF_KM_INTERVAL,
    CONF_LAST_ODOMETER,
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
    odometer_key = vol.Optional(
        CONF_ODOMETER_ENTITY,
        description={"suggested_value": defaults.get(CONF_ODOMETER_ENTITY)},
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

    _pending_input: dict[str, Any]

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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure a vehicle."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            new_odometer = user_input.get(CONF_ODOMETER_ENTITY)
            old_odometer = entry.data.get(CONF_ODOMETER_ENTITY)
            km_counters = [
                subentry.title
                for subentry in entry.subentries.values()
                if subentry.data.get(CONF_KM_INTERVAL)
            ]
            if new_odometer is None and km_counters:
                errors[CONF_ODOMETER_ENTITY] = "odometer_required_by_counters"
            elif error := _odometer_error(self.hass, new_odometer):
                errors[CONF_ODOMETER_ENTITY] = error
            elif (
                new_odometer != old_odometer
                and old_odometer is not None
                and km_counters
            ):
                self._pending_input = user_input
                return await self.async_step_confirm_odometer()
            else:
                return self._finish_reconfigure(user_input)
        defaults = dict(entry.data)
        defaults[CONF_NAME] = entry.title
        if user_input is not None:
            defaults.update(user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_vehicle_schema(self.hass, defaults),
            errors=errors,
            description_placeholders={
                "counters": ", ".join(
                    subentry.title
                    for subentry in entry.subentries.values()
                    if subentry.data.get(CONF_KM_INTERVAL)
                )
            },
        )

    async def async_step_confirm_odometer(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm switching to a different odometer entity."""
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            return self._finish_reconfigure(self._pending_input)

        def _reading(entity_id: str | None) -> str:
            state = self.hass.states.get(entity_id) if entity_id else None
            return state.state if state else "unknown"

        new_odometer = self._pending_input[CONF_ODOMETER_ENTITY]
        new_state = self.hass.states.get(new_odometer)
        below = []
        if new_state:
            try:
                new_value = float(new_state.state)
                below = [
                    subentry.title
                    for subentry in entry.subentries.values()
                    if subentry.data.get(CONF_KM_INTERVAL)
                    and (subentry.data.get(CONF_LAST_ODOMETER) or 0)
                    > new_value
                ]
            except ValueError:
                pass
        return self.async_show_form(
            step_id="confirm_odometer",
            data_schema=vol.Schema({}),
            description_placeholders={
                "old_reading": _reading(
                    entry.data.get(CONF_ODOMETER_ENTITY)
                ),
                "new_reading": _reading(new_odometer),
                "below_counters": ", ".join(below) or "-",
            },
        )

    def _finish_reconfigure(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        return self.async_update_reload_and_abort(
            entry,
            title=user_input[CONF_NAME],
            data={
                CONF_ODOMETER_ENTITY: user_input.get(CONF_ODOMETER_ENTITY),
                CONF_UNIT: user_input[CONF_UNIT],
                CONF_DIRECTION: user_input[CONF_DIRECTION],
            },
        )
