"""Tests for counter calculations."""

from datetime import date

from custom_components.car_maintenance.calc import CounterState, compute


def _compute(**overrides):
    kwargs = {
        "today": date(2026, 6, 11),
        "last_date": None,
        "time_value": None,
        "time_unit": None,
        "last_odometer_km": None,
        "km_interval": None,
        "odometer_km": None,
    }
    kwargs.update(overrides)
    return compute(**kwargs)


def test_time_only_halfway() -> None:
    state = _compute(
        last_date=date(2025, 6, 11), time_value=2, time_unit="years"
    )
    assert state.time_percent == 50.0
    assert state.km_percent is None
    assert state.exhausted_percent == 50.0
    assert state.limiting_factor == "time"
    assert state.due_date == date(2027, 6, 11)
    assert state.remaining_days == 365
    assert state.remaining_km is None


def test_time_overdue_exceeds_100() -> None:
    state = _compute(
        last_date=date(2025, 1, 1), time_value=1, time_unit="years"
    )
    assert state.exhausted_percent > 100
    assert state.remaining_days < 0


def test_time_months_unit() -> None:
    state = _compute(
        last_date=date(2026, 1, 11), time_value=6, time_unit="months"
    )
    assert state.due_date == date(2026, 7, 11)
    assert 0 < state.time_percent < 100


def test_km_only() -> None:
    state = _compute(
        last_odometer_km=10000, km_interval=15000, odometer_km=17500
    )
    assert state.km_percent == 50.0
    assert state.time_percent is None
    assert state.exhausted_percent == 50.0
    assert state.limiting_factor == "km"
    assert state.due_odometer_km == 25000
    assert state.remaining_km == 7500
    assert state.due_date is None


def test_combined_km_limits() -> None:
    state = _compute(
        last_date=date(2026, 3, 11),  # 92 of 365 days ~ 25 %
        time_value=1,
        time_unit="years",
        last_odometer_km=0,
        km_interval=10000,
        odometer_km=9000,
    )
    assert state.km_percent == 90.0
    assert state.limiting_factor == "km"
    assert state.exhausted_percent == 90.0


def test_combined_time_limits() -> None:
    state = _compute(
        last_date=date(2025, 6, 11),
        time_value=1,
        time_unit="years",
        last_odometer_km=0,
        km_interval=10000,
        odometer_km=1000,
    )
    assert state.limiting_factor == "time"
    assert state.exhausted_percent == 100.0


def test_combined_unknown_odometer_falls_back_to_time() -> None:
    state = _compute(
        last_date=date(2025, 6, 11),
        time_value=2,
        time_unit="years",
        last_odometer_km=0,
        km_interval=10000,
        odometer_km=None,
    )
    assert state.km_percent is None
    assert state.exhausted_percent == 50.0
    assert state.limiting_factor == "time"
    assert state.remaining_km is None


def test_exact_tie_is_attributed_to_time() -> None:
    # 50 % elapsed on both components: time wins the tie
    state = _compute(
        last_date=date(2025, 6, 11),
        time_value=2,
        time_unit="years",
        last_odometer_km=0,
        km_interval=10000,
        odometer_km=5000,
    )
    assert state.time_percent == 50.0
    assert state.km_percent == 50.0
    assert state.limiting_factor == "time"


def test_odometer_lower_than_last_service_clamps_to_zero() -> None:
    state = _compute(
        last_odometer_km=20000, km_interval=15000, odometer_km=100
    )
    assert state.km_percent == 0.0
    assert state.remaining_km == 15000


def test_nothing_computable() -> None:
    state = _compute()
    assert state == CounterState(
        time_percent=None,
        km_percent=None,
        exhausted_percent=None,
        limiting_factor=None,
        due_date=None,
        remaining_days=None,
        due_odometer_km=None,
        remaining_km=None,
    )
