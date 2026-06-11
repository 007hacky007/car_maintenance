"""Tests for counter sensors."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.car_maintenance.const import (
    DIRECTION_REMAINING,
    DOMAIN,
)

from .conftest import ODOMETER_ENTITY, make_counter_subentry, make_vehicle_entry


@pytest.fixture
def frozen_time(freezer):
    freezer.move_to("2026-06-11 12:00:00+00:00")
    return freezer


async def _setup(hass: HomeAssistant, entry) -> str:
    """Set up the entry, return the subentry_id of its first counter."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return next(iter(entry.subentries))


def _eid(hass: HomeAssistant, entry, subentry_id: str, kind: str) -> str:
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}-{subentry_id}-{kind}"
    )
    assert entity_id is not None
    return entity_id


async def test_progress_and_component_sensors(
    hass: HomeAssistant, frozen_time
) -> None:
    # last service 2026-01-01 at 10000 km, interval 1 year / 15000 km
    # today 2026-06-11, odometer 12000 km
    # time: 161/365 days = 44.1 %, km: 2000/15000 = 13.3 % -> time limits
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    sub_id = await _setup(hass, entry)

    progress = hass.states.get(_eid(hass, entry, sub_id, "progress"))
    assert progress.state == "44.1"
    assert progress.attributes["limiting_factor"] == "time"
    assert progress.attributes["km_percent"] == 13.3
    assert progress.attributes["exhausted_percent"] == 44.1
    assert progress.attributes["remaining_percent"] == 55.9
    assert progress.attributes["last_service_odometer"] == 10000
    assert progress.attributes["due_odometer"] == 25000

    days = hass.states.get(_eid(hass, entry, sub_id, "remaining_days"))
    assert days.state == "204"

    due = hass.states.get(_eid(hass, entry, sub_id, "due_date"))
    assert due.state == "2027-01-01"

    distance = hass.states.get(
        _eid(hass, entry, sub_id, "remaining_distance")
    )
    assert float(distance.state) == 13000.0


async def test_progress_direction_remaining(
    hass: HomeAssistant, frozen_time
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(
        direction=DIRECTION_REMAINING,
        subentries=[make_counter_subentry()],
    )
    sub_id = await _setup(hass, entry)
    progress = hass.states.get(_eid(hass, entry, sub_id, "progress"))
    assert progress.state == "55.9"
    assert progress.attributes["exhausted_percent"] == 44.1


async def test_progress_state_capped_at_100_when_overdue(
    hass: HomeAssistant, frozen_time
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(
        subentries=[make_counter_subentry(last_date="2024-01-01")]
    )
    sub_id = await _setup(hass, entry)
    progress = hass.states.get(_eid(hass, entry, sub_id, "progress"))
    assert progress.state == "100.0"
    assert progress.attributes["exhausted_percent"] > 100
    days = hass.states.get(_eid(hass, entry, sub_id, "remaining_days"))
    assert int(days.state) < 0


async def test_time_only_counter_creates_no_distance_sensor(
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
    sub_id = await _setup(hass, entry)
    ent_reg = er.async_get(hass)
    assert (
        ent_reg.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}-{sub_id}-remaining_distance"
        )
        is None
    )
    progress = hass.states.get(_eid(hass, entry, sub_id, "progress"))
    assert progress.state == "44.1"


async def test_combined_counter_with_unknown_odometer_uses_time(
    hass: HomeAssistant, frozen_time
) -> None:
    # odometer entity configured but no state and no persisted reading
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    sub_id = await _setup(hass, entry)
    progress = hass.states.get(_eid(hass, entry, sub_id, "progress"))
    assert progress.state == "44.1"
    assert progress.attributes["km_percent"] is None
    assert progress.attributes["limiting_factor"] == "time"
    distance = hass.states.get(
        _eid(hass, entry, sub_id, "remaining_distance")
    )
    assert distance.state == "unknown"


async def test_odometer_update_refreshes_sensors(
    hass: HomeAssistant, frozen_time
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    sub_id = await _setup(hass, entry)

    hass.states.async_set(ODOMETER_ENTITY, "24000")
    await hass.async_block_till_done()
    progress = hass.states.get(_eid(hass, entry, sub_id, "progress"))
    # km: 14000/15000 = 93.3 % now limits over time 44.1 %
    assert progress.state == "93.3"
    assert progress.attributes["limiting_factor"] == "km"
