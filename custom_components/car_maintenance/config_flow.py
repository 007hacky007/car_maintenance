"""Config flow for the Car Maintenance integration."""

from __future__ import annotations

from datetime import date
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import DistanceConverter
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import (
    CONF_DIRECTION,
    CONF_KM_INTERVAL,
    CONF_LAST_DATE,
    CONF_LAST_ODOMETER,
    CONF_ODOMETER_ENTITY,
    CONF_TEMPLATE,
    CONF_THRESHOLD,
    CONF_TIME_UNIT,
    CONF_TIME_VALUE,
    CONF_UNIT,
    DEFAULT_THRESHOLD,
    DIRECTION_EXHAUSTED,
    DIRECTION_REMAINING,
    DOMAIN,
    SUBENTRY_TYPE_COUNTER,
    TEMPLATES,
    TIME_UNIT_YEARS,
    TIME_UNITS,
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


def _to_km(value: float | None, unit: str) -> float | None:
    if value is None:
        return None
    if unit == UNIT_MI:
        return DistanceConverter.convert(value, "mi", "km")
    return float(value)


def _from_km(value: float | None, unit: str) -> float | None:
    # Display rounding to 0.1 mi: values entered in miles round-trip exactly
    # (the stored km is the product of a 0.1-precision mi value), so a no-op
    # reconfigure is stable; only km-canonical defaults shift once by < 0.2 km.
    if value is None:
        return None
    if unit == UNIT_MI:
        return round(DistanceConverter.convert(value, "km", "mi"), 1)
    return value


def _counter_schema(
    *, has_odometer: bool, defaults: dict[str, Any]
) -> vol.Schema:
    """Schema for the counter details step; km fields only with an odometer."""

    def _suggested(key: str) -> dict[str, Any]:
        return {"suggested_value": defaults.get(key)}

    schema: dict[Any, Any] = {
        vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
        vol.Optional(
            CONF_TIME_VALUE, description=_suggested(CONF_TIME_VALUE)
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, step=1, mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required(
            CONF_TIME_UNIT,
            default=defaults.get(CONF_TIME_UNIT, TIME_UNIT_YEARS),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(TIME_UNITS),
                translation_key="time_unit",
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
    }
    if has_odometer:
        schema[
            vol.Optional(
                CONF_KM_INTERVAL, description=_suggested(CONF_KM_INTERVAL)
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, step=1, mode=selector.NumberSelectorMode.BOX
            )
        )
    schema[
        vol.Required(
            CONF_LAST_DATE,
            default=defaults.get(
                CONF_LAST_DATE, dt_util.now().date().isoformat()
            ),
        )
    ] = selector.DateSelector()
    if has_odometer:
        schema[
            vol.Optional(
                CONF_LAST_ODOMETER, description=_suggested(CONF_LAST_ODOMETER)
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, step=1, mode=selector.NumberSelectorMode.BOX
            )
        )
    schema[
        vol.Required(
            CONF_THRESHOLD,
            default=defaults.get(CONF_THRESHOLD, DEFAULT_THRESHOLD),
        )
    ] = selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, max=100, step=1, mode=selector.NumberSelectorMode.SLIDER
        )
    )
    return vol.Schema(schema)


def _validate_counter(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not user_input.get(CONF_TIME_VALUE) and not user_input.get(
        CONF_KM_INTERVAL
    ):
        errors["base"] = "no_interval"
    last_date = user_input.get(CONF_LAST_DATE)
    if last_date and date.fromisoformat(last_date) > dt_util.now().date():
        errors[CONF_LAST_DATE] = "future_date"
    return errors


class CounterSubentryFlow(ConfigSubentryFlow):
    """Add or reconfigure a maintenance counter."""

    _template: str = "custom"

    @property
    def _vehicle(self) -> ConfigEntry:
        return self._get_entry()

    @property
    def _has_odometer(self) -> bool:
        return self._vehicle.data.get(CONF_ODOMETER_ENTITY) is not None

    @property
    def _unit(self) -> str:
        return self._vehicle.data[CONF_UNIT]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Pick a counter template."""
        if user_input is not None:
            self._template = user_input[CONF_TEMPLATE]
            return await self.async_step_details()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TEMPLATE, default="service"
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(TEMPLATES),
                            translation_key="template",
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Enter counter details."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_counter(user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=self._counter_data(user_input),
                )
            defaults = dict(user_input)
        else:
            template = TEMPLATES[self._template]
            defaults = {
                CONF_NAME: template["name"],
                CONF_THRESHOLD: DEFAULT_THRESHOLD,
            }
            if template["time"]:
                defaults[CONF_TIME_VALUE] = template["time"][0]
                defaults[CONF_TIME_UNIT] = template["time"][1]
            if template["km"] and self._has_odometer:
                defaults[CONF_KM_INTERVAL] = _from_km(
                    template["km"], self._unit
                )
                defaults[CONF_LAST_ODOMETER] = self._current_odometer()
        return self.async_show_form(
            step_id="details",
            data_schema=_counter_schema(
                has_odometer=self._has_odometer, defaults=defaults
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure an existing counter."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_counter(user_input)
            if not errors:
                return self.async_update_and_abort(
                    self._vehicle,
                    subentry,
                    title=user_input[CONF_NAME],
                    data=self._counter_data(user_input),
                )
            defaults = dict(user_input)
        else:
            data = subentry.data
            defaults = {
                CONF_NAME: subentry.title,
                CONF_TIME_VALUE: data.get(CONF_TIME_VALUE),
                CONF_TIME_UNIT: data.get(CONF_TIME_UNIT) or TIME_UNIT_YEARS,
                CONF_KM_INTERVAL: _from_km(
                    data.get(CONF_KM_INTERVAL), self._unit
                ),
                CONF_LAST_DATE: data[CONF_LAST_DATE],
                CONF_LAST_ODOMETER: _from_km(
                    data.get(CONF_LAST_ODOMETER), self._unit
                ),
                CONF_THRESHOLD: data[CONF_THRESHOLD],
            }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_counter_schema(
                has_odometer=self._has_odometer, defaults=defaults
            ),
            errors=errors,
        )

    def _current_odometer(self) -> float | None:
        """Current odometer reading in the vehicle unit, for prefills."""
        coordinator = getattr(self._vehicle, "runtime_data", None)
        if coordinator is None or coordinator.data is None:
            return None
        return _from_km(coordinator.data, self._unit)

    def _counter_data(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Convert form input to canonical subentry data."""
        time_value = user_input.get(CONF_TIME_VALUE)
        km_interval = _to_km(user_input.get(CONF_KM_INTERVAL), self._unit)
        return {
            CONF_TIME_VALUE: int(time_value) if time_value else None,
            CONF_TIME_UNIT: user_input[CONF_TIME_UNIT] if time_value else None,
            CONF_KM_INTERVAL: km_interval,
            CONF_LAST_DATE: user_input[CONF_LAST_DATE],
            CONF_LAST_ODOMETER: (
                _to_km(user_input.get(CONF_LAST_ODOMETER), self._unit)
                if km_interval
                else None
            ),
            CONF_THRESHOLD: int(user_input[CONF_THRESHOLD]),
        }


class CarMaintenanceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the vehicle config flow."""

    VERSION = 1

    _pending_input: dict[str, Any]

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentry flow types supported by this integration."""
        return {SUBENTRY_TYPE_COUNTER: CounterSubentryFlow}

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
            except ValueError:
                new_value = None
            if new_value is not None:
                unit = new_state.attributes.get("unit_of_measurement")
                if unit in DistanceConverter.VALID_UNITS:
                    new_km = DistanceConverter.convert(new_value, unit, "km")
                else:
                    new_km = _to_km(
                        new_value, entry.data[CONF_UNIT]
                    )
                below = [
                    subentry.title
                    for subentry in entry.subentries.values()
                    if subentry.data.get(CONF_KM_INTERVAL)
                    and (subentry.data.get(CONF_LAST_ODOMETER) or 0)
                    > new_km
                ]
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
