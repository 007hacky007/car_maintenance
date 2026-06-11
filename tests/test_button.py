"""Tests for the reset button."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.car_maintenance.const import (
    CONF_LAST_DATE,
    CONF_LAST_ODOMETER,
    DOMAIN,
)

from .conftest import ODOMETER_ENTITY, make_counter_subentry, make_vehicle_entry


@pytest.fixture
def frozen_time(freezer):
    freezer.move_to("2026-06-11 12:00:00+00:00")
    return freezer


async def _setup(hass: HomeAssistant, entry) -> str:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    sub_id = next(iter(entry.subentries))
    entity_id = er.async_get(hass).async_get_entity_id(
        "button", DOMAIN, f"{entry.entry_id}-{sub_id}-reset"
    )
    assert entity_id is not None
    return entity_id


async def _press(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()


async def test_reset_updates_date_and_odometer(
    hass: HomeAssistant, frozen_time
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    entity_id = await _setup(hass, entry)

    await _press(hass, entity_id)
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data[CONF_LAST_DATE] == "2026-06-11"
    assert subentry.data[CONF_LAST_ODOMETER] == 12000.0


async def test_reset_time_only_counter_updates_date_only(
    hass: HomeAssistant, frozen_time
) -> None:
    entry = make_vehicle_entry(
        odometer_entity=None,
        subentries=[
            make_counter_subentry(
                "STK", km_interval=None, last_odometer=None
            )
        ],
    )
    entity_id = await _setup(hass, entry)
    await _press(hass, entity_id)
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data[CONF_LAST_DATE] == "2026-06-11"
    assert subentry.data[CONF_LAST_ODOMETER] is None


async def test_reset_km_counter_without_reading_fails(
    hass: HomeAssistant, frozen_time
) -> None:
    # odometer entity configured but never had a state, nothing persisted
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    entity_id = await _setup(hass, entry)
    with pytest.raises(HomeAssistantError):
        await _press(hass, entity_id)
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data[CONF_LAST_DATE] == "2026-01-01"
