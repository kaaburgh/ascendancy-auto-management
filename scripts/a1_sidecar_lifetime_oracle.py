#!/usr/bin/env python3
"""Public A1 lifetime oracle with selection-control validation on every positive path."""
from __future__ import annotations

from typing import Any

try:
    from scripts import _a1_sidecar_lifetime_oracle_core as _core
    from scripts.a1_selection_control_oracle import A1SelectionControlError, validate_selection_control
except ImportError:
    import _a1_sidecar_lifetime_oracle_core as _core
    from a1_selection_control_oracle import A1SelectionControlError, validate_selection_control


for _name in dir(_core):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_core, _name)


SCENARIO_SCHEMA_V2 = "ascendancy.a1-sidecar-scenario-qualification/v2"
PLANET_RECORD_SIZE = 0x7B

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


def _require_nonnegative_int(value: Any, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise _core.A1LifetimeError(f"{context} must be a non-negative integer")
    return value


def _require_positive_int(value: Any, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise _core.A1LifetimeError(f"{context} must be a positive integer")
    return value


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
    if not isinstance(witness, dict):
        raise _core.A1LifetimeError(f"{label} observations.{name} requires qualified_witness")

    context = f"{label} observations.{name}.qualified_witness"
    scenario_planet = _core._require_nonempty_string(
        witness.get("scenario_planet"), f"{context}.scenario_planet"
    )
    if scenario_planet != logical_record:
        raise _core.A1LifetimeError(f"{context}.scenario_planet must bind to logical_record")
    expected_range = scenario_planets.witness_ranges.get(scenario_planet)
    if not isinstance(expected_range, dict):
        raise _core.A1LifetimeError(
            f"{label} observations.{name} logical record is not independently qualified by v2 witness_ranges"
        )
    if "metadata_hex" in witness:
        raise _core.A1LifetimeError(f"{context} v2 witness must not contain metadata_hex")

    basis = _core._require_nonempty_string(witness.get("metadata_basis"), f"{context}.metadata_basis")
    expected_basis = _core._require_nonempty_string(
        expected_range.get("metadata_basis"), f"scenario qualification witness range for {scenario_planet} metadata_basis"
    )
    if basis == "presentation-name" or expected_basis == "presentation-name":
        raise _core.A1LifetimeError("presentation name cannot qualify a logical-record witness")
    if basis != expected_basis:
        raise _core.A1LifetimeError(f"{context}.metadata_basis must match predeclared v2 witness range")

    record_offset = _require_nonnegative_int(witness.get("record_offset"), f"{context}.record_offset")
    length = _require_positive_int(witness.get("length"), f"{context}.length")
    expected_offset = _require_nonnegative_int(
        expected_range.get("record_offset"), f"scenario qualification witness range for {scenario_planet} record_offset"
    )
    expected_length = _require_positive_int(
        expected_range.get("length"), f"scenario qualification witness range for {scenario_planet} length"
    )
    if expected_length > _core.MAX_METADATA_BYTES or expected_offset + expected_length > PLANET_RECORD_SIZE:
        raise _core.A1LifetimeError(
            f"scenario qualification witness range for {scenario_planet} exceeds bounded planet record"
        )
    if record_offset != expected_offset:
        raise _core.A1LifetimeError(f"{context}.record_offset must match predeclared v2 witness range")
    if length != expected_length:
        raise _core.A1LifetimeError(f"{context}.length must match predeclared v2 witness range")

    declared_digest = _core._require_sha256(witness.get("metadata_sha256"), f"{context}.metadata_sha256")
    expected_range_digest = _core._require_sha256(
        expected_range.get("sha256"), f"scenario qualification witness range for {scenario_planet} sha256"
    )
    expected_planet_digest = scenario_planets.get(scenario_planet)
    if expected_planet_digest is None:
        raise _core.A1LifetimeError(
            f"{label} observations.{name} logical record is not independently qualified by scenario manifest"
        )
    if expected_range_digest != expected_planet_digest:
        raise _core.A1LifetimeError(
            f"scenario qualification witness range for {scenario_planet} must match planets digest"
        )
    if declared_digest != expected_range_digest:
        raise _core.A1LifetimeError(f"{context}.metadata_sha256 must match predeclared v2 witness range")
    witness["metadata_sha256"] = declared_digest
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
