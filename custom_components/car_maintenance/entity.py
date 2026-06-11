"""Base entity for counter entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .calc import CounterState
from .const import DOMAIN
from .coordinator import VehicleCoordinator


class CounterEntity(CoordinatorEntity[VehicleCoordinator]):
    """Entity belonging to one counter subentry of a vehicle."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VehicleCoordinator,
        subentry: ConfigSubentry,
        kind: str,
    ) -> None:
        super().__init__(coordinator)
        self.subentry = subentry
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}-{subentry.subentry_id}-{kind}"
        )
        self._attr_translation_key = kind
        self._attr_translation_placeholders = {"counter": subentry.title}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
        )

    @property
    def counter_state(self) -> CounterState:
        """Freshly computed state of this counter."""
        return self.coordinator.compute_counter(self.subentry)
