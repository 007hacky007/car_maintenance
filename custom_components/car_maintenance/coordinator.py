"""Vehicle coordinator holding the current odometer reading in km."""

from __future__ import annotations

import logging
from datetime import date

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import DistanceConverter

from .calc import CounterState, compute
from .const import (
    CONF_KM_INTERVAL,
    CONF_LAST_DATE,
    CONF_LAST_ODOMETER,
    CONF_ODOMETER_ENTITY,
    CONF_TIME_UNIT,
    CONF_TIME_VALUE,
    CONF_UNIT,
    DOMAIN,
    STORAGE_VERSION,
    UNIT_MI,
)

_LOGGER = logging.getLogger(__name__)

SAVE_DELAY = 10


def vehicle_store(hass: HomeAssistant, entry_id: str) -> Store[dict]:
    """Return the storage object for a vehicle's persisted odometer reading."""
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")


class VehicleCoordinator(DataUpdateCoordinator[float | None]):
    """Tracks the odometer entity; data is the reading in canonical km."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass, _LOGGER, name=f"{DOMAIN} {entry.title}", config_entry=entry
        )
        self.entry = entry
        self._store = vehicle_store(hass, entry.entry_id)

    @property
    def vehicle_unit(self) -> str:
        return self.entry.data[CONF_UNIT]

    async def async_setup(self) -> None:
        """Load the persisted reading and start listeners."""
        stored = await self._store.async_load()
        self.async_set_updated_data(
            stored.get("odometer_km") if stored else None
        )

        issue_id = f"odometer_missing_{self.entry.entry_id}"
        entity_id: str | None = self.entry.data.get(CONF_ODOMETER_ENTITY)
        if entity_id:
            state = self.hass.states.get(entity_id)
            if state is None:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="odometer_missing",
                    translation_placeholders={
                        "entity_id": entity_id,
                        "vehicle": self.entry.title,
                    },
                )
            else:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
                self._handle_state(state)
            self.entry.async_on_unload(
                async_track_state_change_event(
                    self.hass, [entity_id], self._odometer_changed
                )
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

        self.entry.async_on_unload(
            async_track_time_change(
                self.hass, self._midnight_tick, hour=0, minute=0, second=10
            )
        )

    @callback
    def _odometer_changed(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state is None:
            # entity removed from the registry at runtime
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"odometer_missing_{self.entry.entry_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="odometer_missing",
                translation_placeholders={
                    "entity_id": self.entry.data[CONF_ODOMETER_ENTITY],
                    "vehicle": self.entry.title,
                },
            )
            self.async_set_updated_data(None)
            return
        self._handle_state(new_state)

    @callback
    def _handle_state(self, state: State | None) -> None:
        """Update data from an odometer state; ignore unusable states."""
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        try:
            value = float(state.state)
        except ValueError:
            _LOGGER.warning(
                "Odometer entity %s has non-numeric state: %s",
                state.entity_id,
                state.state,
            )
            return
        unit = state.attributes.get("unit_of_measurement")
        if unit not in DistanceConverter.VALID_UNITS:
            unit = "mi" if self.vehicle_unit == UNIT_MI else "km"
        km = DistanceConverter.convert(value, unit, "km")
        ir.async_delete_issue(
            self.hass, DOMAIN, f"odometer_missing_{self.entry.entry_id}"
        )
        self.async_set_updated_data(km)
        self._store.async_delay_save(lambda: {"odometer_km": km}, SAVE_DELAY)

    async def async_flush(self) -> None:
        """Persist the current reading immediately, cancelling delayed saves."""
        if self.data is not None:
            await self._store.async_save({"odometer_km": self.data})

    @callback
    def _midnight_tick(self, _now) -> None:
        """Refresh time-based percentages once a day."""
        self.async_update_listeners()

    def compute_counter(self, subentry: ConfigSubentry) -> CounterState:
        """Compute the current state of one counter subentry."""
        data = subentry.data
        last_date = (
            date.fromisoformat(data[CONF_LAST_DATE])
            if data.get(CONF_LAST_DATE)
            else None
        )
        return compute(
            today=dt_util.now().date(),
            last_date=last_date,
            time_value=data.get(CONF_TIME_VALUE),
            time_unit=data.get(CONF_TIME_UNIT),
            last_odometer_km=data.get(CONF_LAST_ODOMETER),
            km_interval=data.get(CONF_KM_INTERVAL),
            odometer_km=self.data,
        )
