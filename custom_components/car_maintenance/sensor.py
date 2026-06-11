"""Sensors for maintenance counters."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CarMaintenanceConfigEntry
from .const import (
    CONF_DIRECTION,
    CONF_KM_INTERVAL,
    CONF_LAST_DATE,
    CONF_LAST_ODOMETER,
    CONF_TIME_VALUE,
    DIRECTION_REMAINING,
    SUBENTRY_TYPE_COUNTER,
)
from .coordinator import VehicleCoordinator
from .entity import CounterEntity


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CarMaintenanceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up counter sensors for each subentry."""
    coordinator = entry.runtime_data
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_COUNTER:
            continue
        entities: list[SensorEntity] = [
            ProgressSensor(coordinator, subentry)
        ]
        if subentry.data.get(CONF_TIME_VALUE):
            entities.append(RemainingDaysSensor(coordinator, subentry))
            entities.append(DueDateSensor(coordinator, subentry))
        if subentry.data.get(CONF_KM_INTERVAL):
            entities.append(RemainingDistanceSensor(coordinator, subentry))
        async_add_entities(
            entities, config_subentry_id=subentry.subentry_id
        )


class ProgressSensor(CounterEntity, SensorEntity):
    """Progress of a counter, capped 0-100, direction-aware."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:car-wrench"

    def __init__(
        self, coordinator: VehicleCoordinator, subentry: ConfigSubentry
    ) -> None:
        super().__init__(coordinator, subentry, "progress")
        self._attr_name = f"{subentry.title} progress"

    @property
    def native_value(self) -> float | None:
        state = self.counter_state
        if state.exhausted_percent is None:
            return None
        percent = state.exhausted_percent
        if (
            self.coordinator.entry.data[CONF_DIRECTION]
            == DIRECTION_REMAINING
        ):
            percent = 100 - percent
        return round(min(100.0, max(0.0, percent)), 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.counter_state
        exhausted = state.exhausted_percent
        return {
            "exhausted_percent": _round(exhausted),
            "remaining_percent": (
                None if exhausted is None else round(100 - exhausted, 1)
            ),
            "limiting_factor": state.limiting_factor,
            "time_percent": _round(state.time_percent),
            "km_percent": _round(state.km_percent),
            "last_service_date": self.subentry.data.get(CONF_LAST_DATE),
            "last_service_odometer": self.subentry.data.get(
                CONF_LAST_ODOMETER
            ),
            "due_odometer": state.due_odometer_km,
        }


class RemainingDaysSensor(CounterEntity, SensorEntity):
    """Days until the counter is due (negative when overdue)."""

    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self, coordinator: VehicleCoordinator, subentry: ConfigSubentry
    ) -> None:
        super().__init__(coordinator, subentry, "remaining_days")
        self._attr_name = f"{subentry.title} remaining days"

    @property
    def native_value(self) -> int | None:
        return self.counter_state.remaining_days


class DueDateSensor(CounterEntity, SensorEntity):
    """Date when the counter is due."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(
        self, coordinator: VehicleCoordinator, subentry: ConfigSubentry
    ) -> None:
        super().__init__(coordinator, subentry, "due_date")
        self._attr_name = f"{subentry.title} due date"

    @property
    def native_value(self) -> date | None:
        return self.counter_state.due_date


class RemainingDistanceSensor(CounterEntity, SensorEntity):
    """Distance until the counter is due."""

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_suggested_display_precision = 0

    def __init__(
        self, coordinator: VehicleCoordinator, subentry: ConfigSubentry
    ) -> None:
        super().__init__(coordinator, subentry, "remaining_distance")
        self._attr_name = f"{subentry.title} remaining distance"

    @property
    def native_value(self) -> float | None:
        return self.counter_state.remaining_km
