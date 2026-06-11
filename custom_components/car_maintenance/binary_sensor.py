"""Warning binary sensor for maintenance counters."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CarMaintenanceConfigEntry
from .const import CONF_THRESHOLD, SUBENTRY_TYPE_COUNTER
from .coordinator import VehicleCoordinator
from .entity import CounterEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CarMaintenanceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a warning binary sensor per counter."""
    coordinator = entry.runtime_data
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_COUNTER:
            continue
        async_add_entities(
            [WarningBinarySensor(coordinator, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class WarningBinarySensor(CounterEntity, BinarySensorEntity):
    """On when counter exhaustion reaches the warning threshold."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self, coordinator: VehicleCoordinator, subentry: ConfigSubentry
    ) -> None:
        super().__init__(coordinator, subentry, "warning")
        self._attr_name = f"{subentry.title} warning"

    @property
    def is_on(self) -> bool | None:
        exhausted = self.counter_state.exhausted_percent
        if exhausted is None:
            return None
        return exhausted >= self.subentry.data[CONF_THRESHOLD]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        exhausted = self.counter_state.exhausted_percent
        return {
            "overdue": exhausted is not None and exhausted >= 100
        }
