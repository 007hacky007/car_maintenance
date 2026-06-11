"""Pure calculation functions for maintenance counters.

All distances are canonical kilometers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from dateutil.relativedelta import relativedelta

_LOGGER = logging.getLogger(__name__)

FACTOR_TIME = "time"
FACTOR_KM = "km"


@dataclass(frozen=True)
class CounterState:
    """Computed state of one maintenance counter."""

    time_percent: float | None
    km_percent: float | None
    exhausted_percent: float | None
    limiting_factor: str | None
    due_date: date | None
    remaining_days: int | None
    due_odometer_km: float | None
    remaining_km: float | None


def compute(
    *,
    today: date,
    last_date: date | None,
    time_value: int | None,
    time_unit: str | None,
    last_odometer_km: float | None,
    km_interval: float | None,
    odometer_km: float | None,
) -> CounterState:
    """Compute the counter state from its configuration and current inputs."""
    time_percent: float | None = None
    due_date: date | None = None
    remaining_days: int | None = None
    if last_date is not None and time_value and time_unit:
        due_date = last_date + relativedelta(**{time_unit: time_value})
        total_days = (due_date - last_date).days
        if total_days > 0:
            time_percent = (today - last_date).days / total_days * 100
            remaining_days = (due_date - today).days

    km_percent: float | None = None
    due_odometer_km: float | None = None
    remaining_km: float | None = None
    if km_interval and last_odometer_km is not None:
        due_odometer_km = last_odometer_km + km_interval
        if odometer_km is not None:
            driven = odometer_km - last_odometer_km
            if driven < 0:
                _LOGGER.warning(
                    "Odometer reading %.0f km is lower than the reading at last"
                    " service (%.0f km); km progress clamped to 0",
                    odometer_km,
                    last_odometer_km,
                )
                driven = 0
            km_percent = driven / km_interval * 100
            remaining_km = km_interval - driven

    if time_percent is None and km_percent is None:
        exhausted = None
        limiting = None
    elif km_percent is None or (
        time_percent is not None and time_percent >= km_percent
    ):
        exhausted = time_percent
        limiting = FACTOR_TIME
    else:
        exhausted = km_percent
        limiting = FACTOR_KM

    return CounterState(
        time_percent=time_percent,
        km_percent=km_percent,
        exhausted_percent=exhausted,
        limiting_factor=limiting,
        due_date=due_date,
        remaining_days=remaining_days,
        due_odometer_km=due_odometer_km,
        remaining_km=remaining_km,
    )
