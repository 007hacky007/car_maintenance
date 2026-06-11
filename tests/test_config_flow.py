"""Tests for the vehicle config flow."""

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.car_maintenance.const import (
    CONF_DIRECTION,
    CONF_KM_INTERVAL,
    CONF_LAST_DATE,
    CONF_LAST_ODOMETER,
    CONF_ODOMETER_ENTITY,
    CONF_TEMPLATE,
    CONF_THRESHOLD,
    CONF_TIME_UNIT,
    CONF_TIME_VALUE,
    CONF_UNIT,
    DIRECTION_EXHAUSTED,
    DOMAIN,
    UNIT_KM,
)

from .conftest import ODOMETER_ENTITY, make_counter_subentry, make_vehicle_entry

OTHER_ODOMETER = "sensor.other_odometer"

VEHICLE_INPUT = {
    CONF_NAME: "Octavia",
    CONF_ODOMETER_ENTITY: ODOMETER_ENTITY,
    CONF_UNIT: UNIT_KM,
    CONF_DIRECTION: DIRECTION_EXHAUSTED,
}


async def _finish(hass: HomeAssistant, result):
    """Select 'finish' in the counters menu and pass the summary page."""
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "finish"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {}
    )


async def _start_reconfigure(hass: HomeAssistant, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return await entry.start_reconfigure_flow(hass)


async def test_user_flow_with_odometer(hass: HomeAssistant) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VEHICLE_INPUT
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "counters_menu"
    assert result["description_placeholders"]["counters"] == "-"

    result = await _finish(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Octavia"
    assert result["data"] == {
        CONF_ODOMETER_ENTITY: ODOMETER_ENTITY,
        CONF_UNIT: UNIT_KM,
        CONF_DIRECTION: DIRECTION_EXHAUSTED,
    }
    assert result["result"].subentries == {}


async def test_user_flow_without_odometer(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Old car",
            CONF_UNIT: UNIT_KM,
            CONF_DIRECTION: DIRECTION_EXHAUSTED,
        },
    )
    result = await _finish(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ODOMETER_ENTITY] is None


async def test_user_flow_adds_counters_during_setup(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VEHICLE_INPUT
    )
    assert result["step_id"] == "counters_menu"

    # first counter
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add_counter"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_counter"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TEMPLATE: "service"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "counter_details"
    result = await hass.config_entries.flow.async_configure(
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
    assert result["type"] is FlowResultType.MENU
    # the menu lists what was already added
    assert (
        result["description_placeholders"]["counters"]
        == "Service inspection"
    )

    # second counter, time only
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add_counter"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TEMPLATE: "vehicle_inspection"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "STK",
            CONF_TIME_VALUE: 2,
            CONF_TIME_UNIT: "years",
            CONF_LAST_DATE: "2026-01-01",
            CONF_THRESHOLD: 90,
        },
    )
    assert result["type"] is FlowResultType.MENU
    assert (
        result["description_placeholders"]["counters"]
        == "Service inspection, STK"
    )

    # the summary page lists the counters as well
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "finish"
    assert (
        result["description_placeholders"]["counters"]
        == "Service inspection, STK"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    subentries = list(entry.subentries.values())
    assert len(subentries) == 2
    assert subentries[0].title == "Service inspection"
    assert subentries[0].data[CONF_KM_INTERVAL] == 15000
    assert subentries[0].data[CONF_LAST_ODOMETER] == 10000
    assert subentries[1].title == "STK"
    assert subentries[1].data[CONF_KM_INTERVAL] is None
    await hass.async_block_till_done()


async def test_setup_counter_details_validates(hass: HomeAssistant) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VEHICLE_INPUT
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add_counter"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TEMPLATE: "custom"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Broken",
            CONF_LAST_DATE: "2026-01-01",
            CONF_THRESHOLD: 90,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "counter_details"
    assert result["errors"] == {"base": "no_interval"}


async def test_user_flow_rejects_non_numeric_odometer(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "not_a_number")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Octavia",
            CONF_ODOMETER_ENTITY: ODOMETER_ENTITY,
            CONF_UNIT: UNIT_KM,
            CONF_DIRECTION: DIRECTION_EXHAUSTED,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ODOMETER_ENTITY: "odometer_not_numeric"}

    # the flow recovers once the entity reports a numeric state
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Octavia",
            CONF_ODOMETER_ENTITY: ODOMETER_ENTITY,
            CONF_UNIT: UNIT_KM,
            CONF_DIRECTION: DIRECTION_EXHAUSTED,
        },
    )
    assert result["type"] is FlowResultType.MENU
    result = await _finish(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reconfigure_blocks_odometer_removal_with_km_counters(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    result = await _start_reconfigure(hass, entry)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Car",
            CONF_UNIT: UNIT_KM,
            CONF_DIRECTION: DIRECTION_EXHAUSTED,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_ODOMETER_ENTITY: "odometer_required_by_counters"
    }


async def test_reconfigure_allows_odometer_removal_without_km_counters(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(
        subentries=[
            make_counter_subentry(
                "STK", km_interval=None, last_odometer=None
            )
        ]
    )
    result = await _start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Car",
            CONF_UNIT: UNIT_KM,
            CONF_DIRECTION: DIRECTION_EXHAUSTED,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_ODOMETER_ENTITY] is None


async def test_reconfigure_odometer_change_requires_confirmation(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    hass.states.async_set(OTHER_ODOMETER, "11500")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    result = await _start_reconfigure(hass, entry)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Car",
            CONF_ODOMETER_ENTITY: OTHER_ODOMETER,
            CONF_UNIT: UNIT_KM,
            CONF_DIRECTION: DIRECTION_EXHAUSTED,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm_odometer"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_ODOMETER_ENTITY] == OTHER_ODOMETER


async def test_confirmation_warns_about_counters_above_new_reading(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    hass.states.async_set(OTHER_ODOMETER, "9000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    result = await _start_reconfigure(hass, entry)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Car",
            CONF_ODOMETER_ENTITY: OTHER_ODOMETER,
            CONF_UNIT: UNIT_KM,
            CONF_DIRECTION: DIRECTION_EXHAUSTED,
        },
    )
    assert result["step_id"] == "confirm_odometer"
    # counter's last service reading (10000) is above the new value (9000)
    placeholders = result["description_placeholders"]
    assert placeholders["below_counters"] == "Service inspection"
    assert placeholders["old_reading"] == "12000"
    assert placeholders["new_reading"] == "9000"


async def test_reconfigure_same_odometer_skips_confirmation(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    result = await _start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Renamed Car",
            CONF_ODOMETER_ENTITY: ODOMETER_ENTITY,
            CONF_UNIT: UNIT_KM,
            CONF_DIRECTION: DIRECTION_EXHAUSTED,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == "Renamed Car"


async def test_unit_change_does_not_rescale_stored_km(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    result = await _start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Car",
            CONF_ODOMETER_ENTITY: ODOMETER_ENTITY,
            CONF_UNIT: "mi",
            CONF_DIRECTION: DIRECTION_EXHAUSTED,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data["km_interval"] == 15000
    assert subentry.data["last_odometer"] == 10000


async def test_confirmation_converts_new_reading_units(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(ODOMETER_ENTITY, "12000")
    # 7000 mi = 11265 km, above the counter's 10000 km -> no warning
    hass.states.async_set(
        OTHER_ODOMETER, "7000", {"unit_of_measurement": "mi"}
    )
    entry = make_vehicle_entry(subentries=[make_counter_subentry()])
    result = await _start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Car",
            CONF_ODOMETER_ENTITY: OTHER_ODOMETER,
            CONF_UNIT: UNIT_KM,
            CONF_DIRECTION: DIRECTION_EXHAUSTED,
        },
    )
    assert result["step_id"] == "confirm_odometer"
    assert result["description_placeholders"]["below_counters"] == "-"
