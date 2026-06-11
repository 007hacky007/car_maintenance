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

from .conftest import ODOMETER_ENTITY


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
