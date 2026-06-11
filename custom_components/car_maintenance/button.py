"""Reset button for maintenance counters."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import CarMaintenanceConfigEntry
from .const import (
    CONF_KM_INTERVAL,
    CONF_LAST_DATE,
    CONF_LAST_ODOMETER,
    DOMAIN,
    SUBENTRY_TYPE_COUNTER,
)
from .coordinator import VehicleCoordinator
from .entity import CounterEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CarMaintenanceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a reset button per counter."""
    coordinator = entry.runtime_data
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_COUNTER:
            continue
        async_add_entities(
            [ResetButton(coordinator, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class ResetButton(CounterEntity, ButtonEntity):
    """Mark the counter as done today at the current odometer reading."""

    _attr_icon = "mdi:check-circle-outline"

    def __init__(
        self, coordinator: VehicleCoordinator, subentry: ConfigSubentry
    ) -> None:
        super().__init__(coordinator, subentry, "reset")
        self._attr_name = f"{subentry.title} done"

    async def async_press(self) -> None:
        """Reset the counter; the subentry update reloads the entry."""
        data = dict(self.subentry.data)
        if data.get(CONF_KM_INTERVAL):
            odometer_km = self.coordinator.data
            if odometer_km is None:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="no_odometer_reading",
                )
            data[CONF_LAST_ODOMETER] = odometer_km
        data[CONF_LAST_DATE] = dt_util.now().date().isoformat()
        self.hass.config_entries.async_update_subentry(
            self.coordinator.entry, self.subentry, data=data
        )
