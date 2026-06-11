"""Constants for the Car Maintenance integration."""

from typing import Any

DOMAIN = "car_maintenance"

STORAGE_VERSION = 1

# Vehicle (config entry) keys
CONF_ODOMETER_ENTITY = "odometer_entity"
CONF_UNIT = "unit"
CONF_DIRECTION = "direction"

UNIT_KM = "km"
UNIT_MI = "mi"

DIRECTION_EXHAUSTED = "exhausted"
DIRECTION_REMAINING = "remaining"

# Counter (subentry) keys
SUBENTRY_TYPE_COUNTER = "counter"
CONF_TEMPLATE = "template"
CONF_TIME_VALUE = "time_value"
CONF_TIME_UNIT = "time_unit"
CONF_KM_INTERVAL = "km_interval"  # canonical km
CONF_LAST_DATE = "last_date"  # ISO date string
CONF_LAST_ODOMETER = "last_odometer"  # canonical km
CONF_THRESHOLD = "threshold"

TIME_UNIT_DAYS = "days"
TIME_UNIT_MONTHS = "months"
TIME_UNIT_YEARS = "years"
TIME_UNITS = [TIME_UNIT_DAYS, TIME_UNIT_MONTHS, TIME_UNIT_YEARS]

DEFAULT_THRESHOLD = 90
DEFAULT_KM_INTERVAL = 15000

# Counter templates: prefill values for the subentry flow.
# name: default counter title, time: (value, unit), km: km interval or None.
TEMPLATES: dict[str, dict[str, Any]] = {
    "service": {"name": "Service inspection", "time": (1, TIME_UNIT_YEARS), "km": 15000},
    "vehicle_inspection": {"name": "Vehicle inspection", "time": (2, TIME_UNIT_YEARS), "km": None},
    "vignette": {"name": "Highway vignette", "time": (1, TIME_UNIT_YEARS), "km": None},
    "oil": {"name": "Oil change", "time": (1, TIME_UNIT_YEARS), "km": 15000},
    "brake_fluid": {"name": "Brake fluid", "time": (2, TIME_UNIT_YEARS), "km": None},
    "coolant": {"name": "Coolant", "time": (4, TIME_UNIT_YEARS), "km": None},
    "timing_belt": {"name": "Timing belt", "time": (5, TIME_UNIT_YEARS), "km": 90000},
    "battery": {"name": "Battery", "time": (5, TIME_UNIT_YEARS), "km": None},
    "insurance": {"name": "Insurance", "time": (1, TIME_UNIT_YEARS), "km": None},
    "tires": {"name": "Tire change", "time": (6, TIME_UNIT_MONTHS), "km": None},
    "first_aid_kit": {"name": "First aid kit", "time": (4, TIME_UNIT_YEARS), "km": None},
    "custom": {"name": "", "time": None, "km": None},
}
