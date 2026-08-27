#!/usr/bin/env python3
"""Public A1 lifetime oracle with selection-control validation on every positive path."""
from __future__ import annotations

from typing import Any

try:
    from scripts import _a1_sidecar_lifetime_oracle_core as _core
    from scripts.a1_selection_control_oracle import A1SelectionControlError, validate_selection_control
    from scripts.a1_v2_witness_binding import (
        A1V2WitnessBindingError,
        SCENARIO_SCHEMA_V2,
        validate_qualified_witness,
    )
except ImportError:
    import _a1_sidecar_lifetime_oracle_core as _core
    from a1_selection_control_oracle import A1SelectionControlError, validate_selection_control
    from a1_v2_witness_binding import (
        A1V2WitnessBindingError,
        SCENARIO_SCHEMA_V2,
        validate_qualified_witness,
    )


for _name in dir(_core):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_core, _name)


# Dynamic test loaders can import this public wrapper more than once while the
# private core module remains cached. Preserve the original core callables once
# so rebinding stays idempotent rather than wrapping a previous wrapper.
if not hasattr(_core, "_public_raw_scenario_planets"):
    _core._public_raw_scenario_planets = _core._scenario_planets
if not hasattr(_core, "_public_raw_require_point"):
    _core._public_raw_require_point = _core._require_point
if not hasattr(_core, "_public_raw_validate_record"):
    _core._public_raw_validate_record = _core.validate_record
_RAW_SCENARIO_PLANETS = _core._public_raw_scenario_planets
_RAW_REQUIRE_POINT = _core._public_raw_require_point
_RAW_VALIDATE_RECORD = _core._public_raw_validate_record


class _ScenarioPlanets(dict[str, str]):
    def __init__(self, values: dict[str, str], witness_ranges: dict[str, Any] | None = None) -> None:
        super().__init__(values)
        self.witness_ranges = witness_ranges


def _scenario_planets(
    record: dict[str, Any],
    scenario_manifest: dict[str, Any] | None,
    expected_source: dict[str, Any] | None,
) -> dict[str, str]:
    if not isinstance(scenario_manifest, dict) or scenario_manifest.get("schema") != SCENARIO_SCHEMA_V2:
        return _RAW_SCENARIO_PLANETS(record, scenario_manifest, expected_source)

    legacy_projection = {
        "schema": _core.SCENARIO_SCHEMA,
        "source": scenario_manifest.get("source"),
        "planets": scenario_manifest.get("planets"),
    }
    validated = _RAW_SCENARIO_PLANETS(record, legacy_projection, expected_source)
    witness_ranges = scenario_manifest.get("witness_ranges")
    if not isinstance(witness_ranges, dict) or not witness_ranges:
        raise _core.A1LifetimeError("scenario qualification v2 manifest requires witness_ranges")
    if set(witness_ranges) != set(validated):
        raise _core.A1LifetimeError("scenario qualification v2 witness_ranges must exactly cover planets")
    return _ScenarioPlanets(validated, witness_ranges)


def _require_point(
    observations: dict[str, Any],
    name: str,
    label: str,
    scenario_planets: dict[str, str],
) -> dict[str, Any]:
    if not isinstance(scenario_planets, _ScenarioPlanets) or scenario_planets.witness_ranges is None:
        return _RAW_REQUIRE_POINT(observations, name, label, scenario_planets)

    point = observations.get(name)
    if not isinstance(point, dict):
        raise _core.A1LifetimeError(f"{label} requires observations.{name}")
    _core._require_seq(point.get("seq"), f"{label} observations.{name}.seq")
    pointer = point.get("record_pointer")
    if not isinstance(pointer, int) or isinstance(pointer, bool) or pointer < 0:
        raise _core.A1LifetimeError(
            f"{label} observations.{name}.record_pointer must be a non-negative integer"
        )
    logical_record = _core._require_nonempty_string(
        point.get("logical_record"), f"{label} observations.{name}.logical_record"
    )
    witness = point.get("qualified_witness")
    context = f"{label} observations.{name}"
    try:
        validate_qualified_witness(
            witness,
            logical_record,
            scenario_planets,
            scenario_planets.witness_ranges,
            context=context,
        )
    except A1V2WitnessBindingError as exc:
        raise _core.A1LifetimeError(str(exc)) from exc
    return point


# The core validator resolves these helpers through its module globals. Rebind only
# the schema/witness boundary; every other lifetime invariant remains in the core.
_core._scenario_planets = _scenario_planets
_core._require_point = _require_point


def validate_record(
    record: dict[str, Any],
    scenario_manifest: dict[str, Any] | None = None,
    expected_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = _RAW_VALIDATE_RECORD(record, scenario_manifest, expected_source)
    if result["positive_contract_accepted"]:
        try:
            validate_selection_control(record, scenario_manifest or {})
        except A1SelectionControlError as exc:
            raise _core.A1LifetimeError(str(exc)) from exc
    return result


# The legacy CLI entry point resolves validate_record through its module globals.
# Bind it to the guarded public validator so direct CLI and imported callers agree.
_core.validate_record = validate_record


if __name__ == "__main__":
    raise SystemExit(_core.main())
