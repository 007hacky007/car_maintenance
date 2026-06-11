"""Shared fixtures for car_maintenance tests."""

import pytest
from homeassistant.config_entries import ConfigSubentryData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.car_maintenance.const import (
    CONF_DIRECTION,
    CONF_KM_INTERVAL,
    CONF_LAST_DATE,
    CONF_LAST_ODOMETER,
    CONF_ODOMETER_ENTITY,
    CONF_THRESHOLD,
    CONF_TIME_UNIT,
    CONF_TIME_VALUE,
    CONF_UNIT,
    DIRECTION_EXHAUSTED,
    DOMAIN,
    SUBENTRY_TYPE_COUNTER,
    UNIT_KM,
)

ODOMETER_ENTITY = "sensor.test_car_odometer"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in all tests."""
    return


def make_counter_subentry(
    title: str = "Service inspection",
    *,
    time_value: int | None = 1,
    time_unit: str | None = "years",
    km_interval: float | None = 15000,
    last_date: str = "2026-01-01",
    last_odometer: float | None = 10000,
    threshold: int = 90,
) -> ConfigSubentryData:
    """Build subentry data for a counter."""
    return ConfigSubentryData(
        data={
            CONF_TIME_VALUE: time_value,
            CONF_TIME_UNIT: time_unit,
            CONF_KM_INTERVAL: km_interval,
            CONF_LAST_DATE: last_date,
            CONF_LAST_ODOMETER: last_odometer,
            CONF_THRESHOLD: threshold,
        },
        subentry_type=SUBENTRY_TYPE_COUNTER,
        title=title,
        unique_id=None,
    )


def make_vehicle_entry(
    *,
    odometer_entity: str | None = ODOMETER_ENTITY,
    unit: str = UNIT_KM,
    direction: str = DIRECTION_EXHAUSTED,
    subentries: list[ConfigSubentryData] | None = None,
) -> MockConfigEntry:
    """Build a vehicle config entry with counter subentries."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Car",
        data={
            CONF_ODOMETER_ENTITY: odometer_entity,
            CONF_UNIT: unit,
            CONF_DIRECTION: direction,
        },
        subentries_data=subentries or [],
    )
