"""Tests for the counter subentry flow."""

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.car_maintenance.const import (
    CONF_KM_INTERVAL,
    CONF_LAST_DATE,
    CONF_LAST_ODOMETER,
    CONF_TEMPLATE,
    CONF_THRESHOLD,
    CONF_TIME_UNIT,
    CONF_TIME_VALUE,
    DOMAIN,
    SUBENTRY_TYPE_COUNTER,
    UNIT_MI,
)

from .conftest import ODOMETER_ENTITY, make_counter_subentry, make_vehicle_entry


async def _setup_entry(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _start_details(hass: HomeAssistant, entry, template: str):
    """Start the subentry flow and pass the template step."""
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_COUNTER),
        context={"source": SOURCE_USER},
    )
    assert result["step_id"] == "user"
    return await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_TEMPLATE: template}
    )


async def test_add_counter_from_service_template(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry()
    await _setup_entry(hass, entry)

    result = await _start_details(hass, entry, "service")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "details"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Service inspection",
            CONF_TIME_VALUE: 1,
            CONF_TIME_UNIT: "years",
            CONF_KM_INTERVAL: 15000,
            CONF_LAST_DATE: "2026-01-01",
            CONF_LAST_ODOMETER: 10000,
            CONF_THRESHOLD: 90,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(iter(entry.subentries.values()))
    assert subentry.title == "Service inspection"
    assert subentry.data[CONF_KM_INTERVAL] == 15000
    assert subentry.data[CONF_LAST_ODOMETER] == 10000
    assert subentry.data[CONF_TIME_VALUE] == 1


async def test_time_only_counter_on_vehicle_without_odometer(
    hass: HomeAssistant,
) -> None:
    entry = make_vehicle_entry(odometer_entity=None)
    await _setup_entry(hass, entry)

    result = await _start_details(hass, entry, "vehicle_inspection")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "STK",
            CONF_TIME_VALUE: 2,
            CONF_TIME_UNIT: "years",
            CONF_LAST_DATE: "2026-01-01",
            CONF_THRESHOLD: 90,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data[CONF_KM_INTERVAL] is None
    assert subentry.data[CONF_LAST_ODOMETER] is None


async def test_counter_requires_at_least_one_interval(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry()
    await _setup_entry(hass, entry)

    result = await _start_details(hass, entry, "custom")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Broken",
            CONF_LAST_DATE: "2026-01-01",
            CONF_THRESHOLD: 90,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_interval"}


async def test_counter_rejects_future_last_date(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry()
    await _setup_entry(hass, entry)

    result = await _start_details(hass, entry, "vignette")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Vignette",
            CONF_TIME_VALUE: 1,
            CONF_TIME_UNIT: "years",
            CONF_LAST_DATE: "2099-01-01",
            CONF_THRESHOLD: 90,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_LAST_DATE: "future_date"}


async def test_km_values_entered_in_miles_are_stored_as_km(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "10000")
    entry = make_vehicle_entry(unit=UNIT_MI)
    await _setup_entry(hass, entry)

    result = await _start_details(hass, entry, "custom")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Miles counter",
            CONF_KM_INTERVAL: 100,
            CONF_LAST_DATE: "2026-01-01",
            CONF_LAST_ODOMETER: 50,
            CONF_THRESHOLD: 90,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(iter(entry.subentries.values()))
    assert round(subentry.data[CONF_KM_INTERVAL], 1) == 160.9
    assert round(subentry.data[CONF_LAST_ODOMETER], 1) == 80.5


async def test_reconfigure_counter_updates_values(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    await _setup_entry(hass, entry)
    subentry = next(iter(entry.subentries.values()))

    result = await entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Service inspection",
            CONF_TIME_VALUE: 1,
            CONF_TIME_UNIT: "years",
            CONF_KM_INTERVAL: 20000,
            CONF_LAST_DATE: "2026-03-01",
            CONF_LAST_ODOMETER: 11000,
            CONF_THRESHOLD: 80,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data[CONF_KM_INTERVAL] == 20000
    assert subentry.data[CONF_LAST_DATE] == "2026-03-01"
    assert subentry.data[CONF_THRESHOLD] == 80


async def test_reconfigure_counter_validates(hass: HomeAssistant) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    await _setup_entry(hass, entry)
    subentry = next(iter(entry.subentries.values()))

    result = await entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Service inspection",
            CONF_LAST_DATE: "2026-03-01",
            CONF_THRESHOLD: 80,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_interval"}
