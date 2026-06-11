"""Tests for integration setup and the vehicle coordinator."""

import os
from datetime import timedelta

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.car_maintenance.const import DOMAIN

from .conftest import ODOMETER_ENTITY, make_counter_subentry, make_vehicle_entry


async def _setup(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_and_unload(hass: HomeAssistant) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.data == 12000.0

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_odometer_state_change_updates_coordinator(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    await _setup(hass, entry)

    hass.states.async_set(ODOMETER_ENTITY, "12500")
    await hass.async_block_till_done()
    assert entry.runtime_data.data == 12500.0


async def test_unavailable_odometer_keeps_last_value(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    await _setup(hass, entry)

    hass.states.async_set(ODOMETER_ENTITY, "unavailable")
    await hass.async_block_till_done()
    assert entry.runtime_data.data == 12000.0


async def test_odometer_in_miles_converted_to_km(hass: HomeAssistant) -> None:
    hass.states.async_set(
        ODOMETER_ENTITY, "100", {"unit_of_measurement": "mi"}
    )
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    await _setup(hass, entry)
    assert round(entry.runtime_data.data, 1) == 160.9


async def test_odometer_without_unit_uses_vehicle_unit(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "100")
    entry = make_vehicle_entry(
        unit="mi", subentries=[make_counter_subentry()]
    )
    await _setup(hass, entry)
    assert round(entry.runtime_data.data, 1) == 160.9


async def test_reading_persists_across_reload(hass: HomeAssistant) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    await _setup(hass, entry)

    # flush the delayed Store save before reloading
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    hass.states.async_remove(ODOMETER_ENTITY)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.data == 12000.0


async def test_startup_without_reading_is_unknown(
    hass: HomeAssistant,
) -> None:
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    await _setup(hass, entry)
    assert entry.runtime_data.data is None


async def test_missing_odometer_entity_raises_repair_issue(
    hass: HomeAssistant,
) -> None:
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    await _setup(hass, entry)
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"odometer_missing_{entry.entry_id}"
    )
    assert issue is not None


async def test_present_odometer_entity_clears_repair_issue(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    await _setup(hass, entry)
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"odometer_missing_{entry.entry_id}"
    )
    assert issue is None


async def test_entity_appearing_after_startup_clears_repair_issue(
    hass: HomeAssistant,
) -> None:
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    await _setup(hass, entry)
    issue_id = f"odometer_missing_{entry.entry_id}"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None

    hass.states.async_set(ODOMETER_ENTITY, "12000")
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
    assert entry.runtime_data.data == 12000.0


async def test_runtime_odometer_removal_raises_issue_and_clears_reading(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    await _setup(hass, entry)
    assert entry.runtime_data.data == 12000.0

    hass.states.async_remove(ODOMETER_ENTITY)
    await hass.async_block_till_done()
    assert entry.runtime_data.data is None
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"odometer_missing_{entry.entry_id}"
    )
    assert issue is not None


async def test_remove_entry_deletes_persisted_reading(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    await _setup(hass, entry)

    store_path = hass.config.path(
        ".storage", f"{DOMAIN}.{entry.entry_id}"
    )
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert not os.path.exists(store_path)
