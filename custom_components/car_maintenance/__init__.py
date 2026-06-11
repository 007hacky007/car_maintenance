"""The Car Maintenance integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import VehicleCoordinator, vehicle_store

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]

type CarMaintenanceConfigEntry = ConfigEntry[VehicleCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: CarMaintenanceConfigEntry
) -> bool:
    """Set up a vehicle from a config entry."""
    coordinator = VehicleCoordinator(hass, entry)
    await coordinator.async_setup()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: CarMaintenanceConfigEntry
) -> None:
    """Reload the entry when the entry or any subentry changes."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: CarMaintenanceConfigEntry
) -> bool:
    """Unload a vehicle config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove the persisted odometer reading with the entry."""
    await vehicle_store(hass, entry.entry_id).async_remove()
