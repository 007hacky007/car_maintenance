"""Tests for the warning binary sensor."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.car_maintenance.const import DOMAIN

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
        "binary_sensor", DOMAIN, f"{entry.entry_id}-{sub_id}-warning"
    )
    assert entity_id is not None
    return entity_id


async def test_warning_off_below_threshold(
    hass: HomeAssistant, frozen_time
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    entity_id = await _setup(hass, entry)
    state = hass.states.get(entity_id)
    assert state.state == "off"
    assert state.attributes["overdue"] is False


async def test_warning_on_at_threshold(
    hass: HomeAssistant, frozen_time
) -> None:
    # 2025-07-01 + 1 year -> 94.5 % elapsed on 2026-06-11
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(
        subentries=[make_counter_subentry(last_date="2025-07-01")]
    )
    entity_id = await _setup(hass, entry)
    state = hass.states.get(entity_id)
    assert state.state == "on"
    assert state.attributes["overdue"] is False


async def test_warning_overdue(hass: HomeAssistant, frozen_time) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(
        subentries=[make_counter_subentry(last_date="2024-01-01")]
    )
    entity_id = await _setup(hass, entry)
    state = hass.states.get(entity_id)
    assert state.state == "on"
    assert state.attributes["overdue"] is True


async def test_warning_unknown_without_any_component(
    hass: HomeAssistant, frozen_time
) -> None:
    # km-only counter with no odometer reading: nothing computable
    entry = make_vehicle_entry(
        subentries=[
            make_counter_subentry(
                "Oil", time_value=None, time_unit=None
            )
        ]
    )
    entity_id = await _setup(hass, entry)
    assert hass.states.get(entity_id).state == "unknown"
