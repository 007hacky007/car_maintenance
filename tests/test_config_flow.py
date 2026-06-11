"""Tests for the vehicle config flow."""

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.car_maintenance.const import (
    CONF_DIRECTION,
    CONF_ODOMETER_ENTITY,
    CONF_UNIT,
    DIRECTION_EXHAUSTED,
    DOMAIN,
    UNIT_KM,
)

from .conftest import ODOMETER_ENTITY, make_counter_subentry, make_vehicle_entry

OTHER_ODOMETER = "sensor.other_odometer"


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
        result["flow_id"],
        {
            CONF_NAME: "Octavia",
            CONF_ODOMETER_ENTITY: ODOMETER_ENTITY,
            CONF_UNIT: UNIT_KM,
            CONF_DIRECTION: DIRECTION_EXHAUSTED,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Octavia"
    assert result["data"] == {
        CONF_ODOMETER_ENTITY: ODOMETER_ENTITY,
        CONF_UNIT: UNIT_KM,
        CONF_DIRECTION: DIRECTION_EXHAUSTED,
    }


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
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ODOMETER_ENTITY] is None


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
