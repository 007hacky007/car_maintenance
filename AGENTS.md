# Car Maintenance - project specification

This file preserves the original design spec the integration was built from.
It is intentionally not committed (see .gitignore). Status: implemented
(2026-06-11), 54 tests passing.

## Goal

A HACS custom integration for tracking vehicle maintenance. For every counter
(service inspection, vehicle inspection / STK, highway vignette, ...) it provides
sensors suitable for display as a horizontal progress bar. A custom Lovelace card
is NOT part of the project - the README shows examples using the existing,
actively maintained entity-progress-card (HACS).

## Architecture

- Custom integration, domain `car_maintenance`, type `device` (one config entry
  = one vehicle = one device; makes the UI button say "Add device"),
  `iot_class: calculated`.
- Each vehicle = config entry. Each counter = config subentry (HA >= 2025.3).
- No cloud, no polling API. Recalculation on odometer entity state change
  (`async_track_state_change_event`) and on a midnight tick
  (`async_track_time_change`).
- Repository structure for a HACS custom repository:
  - `custom_components/car_maintenance/` (`__init__.py` with entry setup/unload,
    platform forwarding and listener cleanup; manifest.json, config_flow.py,
    sensor.py, binary_sensor.py, button.py, coordinator/calculations,
    translations/en.json + cs.json)
  - `hacs.json`, `README.md`, MIT `LICENSE`
- Minimum HA version: 2025.3 (required for subentries).
- Entities are registered with the `config_subentry_id` of their counter so that
  deleting a subentry automatically cleans up its entities from the registry and
  no orphans remain.
- Entity unique_ids are stable and derived from config entry id + subentry id +
  entity kind (e.g. `<entry_id>-<subentry_id>-progress`). Entity IDs shown below
  are illustrative slugs only; renaming a vehicle or counter must not change
  unique_ids.

## Units

Single canonical rule: all distances are stored and calculated in kilometers.
Conversions happen only at boundaries:

- config flow inputs (km interval, last service odometer) are entered in the
  vehicle's configured unit (km or miles) and converted to km on save
- the odometer entity state is converted to km using its own unit of
  measurement via HA unit conversion; if the entity has no distance unit, the
  value is interpreted in the vehicle's configured unit
- `remaining_distance` sensors have device_class `distance` with native unit km;
  HA handles display conversion according to the user's unit system
- attributes carrying distances (`last_service_odometer`, `due_odometer`) are
  always in km
- changing the vehicle's unit setting only changes how flow inputs are
  interpreted and displayed; stored canonical km values are not rescaled

## Configuration

### Vehicle (config entry)

- vehicle name
- optional odometer entity (entity selector, sensor domain); when not set,
  counters work on time only and km fields are not offered in the UI
  - validation on save: the entity state must be numeric, otherwise a form error
  - if the entity has a distance unit, the value is converted via HA unit
    conversion; without a unit it is interpreted in the vehicle's unit
  - a hard filter on device_class `distance` is intentionally not applied - many
    real-world odometers (MQTT, template, OBD) have no device_class
- distance unit: km / miles (default follows the HA unit system) - defines the
  unit in which the user enters intervals and km values
- progress bar direction: "exhausted" 0 -> 100 (default) or "remaining"
  100 -> 0; applies to all counters of the vehicle, both raw values are always
  available as attributes

### Counter (subentry)

- name
- optional time interval: number + unit (days / months / years)
- optional km interval (only when the vehicle has an odometer; default 15000 km)
- validation: at least one interval must be set; intervals > 0
- date of last service (default today; future dates are rejected with a form
  error)
- odometer at last service (km counters only; default current odometer; >= 0)
- warning threshold in % (default 90; range 1-100)

### Counter templates

When adding a subentry the user picks a template that prefills values
(everything can be edited afterwards):

| Template              | Time     | Km     |
|-----------------------|----------|--------|
| Service inspection    | 1 year   | 15 000 |
| Vehicle inspection    | 2 years  | -      |
| Highway vignette      | 1 year   | -      |
| Oil change            | 1 year   | 15 000 |
| Brake fluid           | 2 years  | -      |
| Coolant               | 4 years  | -      |
| Timing belt           | 5 years  | 90 000 |
| Battery               | 5 years  | -      |
| Insurance             | 1 year   | -      |
| Tire change (seasonal)| 6 months | -      |
| First aid kit expiry  | 4 years  | -      |
| Custom                | -        | -      |

## Entities

All entities of a vehicle live under one device. Per counter:

| Entity                                | Description |
|---------------------------------------|-------------|
| `sensor.<car>_<counter>_progress`     | % according to the vehicle's direction setting; base = max(time %, km %); state capped to 0-100, uncapped values in attributes |
| `sensor..._remaining_days`            | remaining days (integer, may be negative) |
| `sensor..._remaining_distance`        | remaining distance; km counters only; device_class `distance`, native unit km (HA converts for display) |
| `sensor..._due_date`                  | next due date (device_class `date`); for km counters from the time component when present |
| `binary_sensor..._warning`            | on when exhaustion >= threshold; attribute `overdue` (exhaustion >= 100) |
| `button..._reset`                     | "Done" - sets date = today and, only for counters with a km interval, odometer at last service = current odometer (or the persisted last valid reading when the odometer entity is unavailable); if neither is available, the press fails with a translated `HomeAssistantError` and nothing is written. Persists via `async_update_subentry` and immediately recalculates the counter's entity states |

Progress sensor attributes: `exhausted_percent` (uncapped, may exceed 100),
`remaining_percent` (100 - exhausted, uncapped, may be negative),
`limiting_factor` (time/km), `time_percent`, `km_percent`, `last_service_date`,
`last_service_odometer`, `due_odometer`.

Sensors are created only for the components a counter has: `remaining_days` and
`due_date` only with a time interval, `remaining_distance` only with a km
interval. Progress, binary_sensor and button always exist.

## Calculations

- time % = days elapsed since last service / interval length in days * 100
  (months/years via `dateutil.relativedelta` - due_date = last date + interval,
  percentage linear between them)
- km % = (current odometer - odometer at last service) / km interval * 100
- exhaustion = max(available components); direction "remaining" = 100 - exhaustion
- the progress sensor state is capped to 0-100 (in both directions); uncapped
  values live in the `exhausted_percent` / `remaining_percent` attributes, and
  overdue state is also carried by `remaining_days` (negative), `due_date` and
  the `overdue` attribute

## Edge cases

- Odometer `unavailable` / `unknown`: the integration persists its own last
  valid odometer reading per vehicle (canonical km, `helpers.storage` Store)
  and keeps using it; the value survives an HA restart. On startup with no
  stored value and an unavailable odometer, km components report `unknown`
  until the first valid reading arrives; time components work normally.
- Combined time+km counter while the km value is unknown: progress and the
  warning binary sensor fall back to the components that can be computed
  (exhaustion = max of available components, here time only); the `km_percent`
  attribute is unknown and `limiting_factor` reflects the used component. Only
  when no component is computable do progress and the binary sensor report
  `unknown`.
- Odometer reporting miles (or another distance unit): converted to km via HA
  unit conversion, see Units.
- Odometer lower than odometer at last service (e.g. control unit replaced):
  km component = 0 % and a warning is logged.
- Retroactive service entry: reconfigure the subentry (date and km can be
  edited manually).
- Vehicle without odometer + template containing km: the km field is ignored,
  time only is used.
- Removing or changing the odometer entity on a vehicle that has counters with
  a km interval:
  - reconfigure flow blocks removing the odometer with a form error listing the
    affected counters; the user must first edit or delete those counters
  - changing to a different odometer entity is allowed but requires an explicit
    confirmation step showing the current and the new entity reading; stored
    last_service_odometer values are kept because canonical km values describe
    the physical vehicle. If the new reading is lower than a counter's
    last_service_odometer, the standard "odometer lower than last service" edge
    case applies and the confirmation step warns about it.
  - if the odometer entity disappears at runtime (deleted from the registry),
    km components become unavailable, time-only components keep working, and a
    repair issue is raised pointing the user to reconfigure the vehicle

## Tests

`pytest-homeassistant-custom-component` (run with `.venv/bin/python -m pytest tests`):

- config flow: vehicle creation, adding/editing a subentry, "at least one
  interval" validation, range validation (interval > 0, km >= 0, threshold
  1-100), rejection of a non-numeric odometer entity, rejection of a future
  last service date, odometer entity change confirmation step
- calculations: time %, km %, combination, direction "remaining" (capped state
  and uncapped attributes), overdue, odometer unavailable, odometer lower than
  last service
- units: odometer in miles, odometer without a unit (vehicle unit
  interpretation), flow input conversion in miles mode, vehicle unit change
  does not rescale stored km
- odometer lifecycle: blocked removal while km counters exist, runtime
  disappearance raises a repair issue and km components go unavailable,
  startup with no persisted reading and unavailable odometer reports `unknown`
- reset button: subentry data update and immediate recalculation; time-only
  counter reset updates the date only; km counter reset with unavailable
  odometer uses the persisted reading, and with no persisted reading raises a
  translated error without writing
- combined counter fallback: time+km counter with unknown km computes progress
  from time only; progress is `unknown` only when no component is computable

## Dashboard (README)

YAML examples with entity-progress-card for a single bar and for an overview of
all counters, including a "remaining" direction variant. Recommend installing
the card via HACS.
