#!/usr/bin/env python3
"""Validate the bounded A1 A→B→A selection-control observations."""
from __future__ import annotations

import hashlib
from typing import Any

try:
    from .a1_v2_witness_binding import (
        A1V2WitnessBindingError,
        SCENARIO_SCHEMA_V2,
        validate_qualified_witness,
    )
except ImportError:
    from a1_v2_witness_binding import (
        A1V2WitnessBindingError,
        SCENARIO_SCHEMA_V2,
        validate_qualified_witness,
    )

MAX_METADATA_BYTES = 512


class A1SelectionControlError(ValueError):
    pass


def _nonnegative_int(value: Any, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise A1SelectionControlError(f"{context} must be a non-negative integer")
    return value


def _nonempty_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise A1SelectionControlError(f"{context} must be a non-empty string")
    return value


def _sha256(value: Any, context: str) -> str:
    text = _nonempty_string(value, context)
    if len(text) != 64:
        raise A1SelectionControlError(f"{context} must be a 64-hex SHA-256 digest")
    try:
        int(text, 16)
    except ValueError as exc:
        raise A1SelectionControlError(f"{context} must be a 64-hex SHA-256 digest") from exc
    return text.lower()


def _legacy_witness(
    witness: dict[str, Any], logical: str, scenario_planets: dict[str, Any], context: str
) -> str:
    basis = _nonempty_string(
        witness.get("metadata_basis"), f"{context}.qualified_witness.metadata_basis"
    )
    if basis == "presentation-name":
        raise A1SelectionControlError("presentation name cannot qualify a selection-control witness")
    metadata_hex = _nonempty_string(
        witness.get("metadata_hex"), f"{context}.qualified_witness.metadata_hex"
    )
    if len(metadata_hex) % 2:
        raise A1SelectionControlError(f"{context}.qualified_witness.metadata_hex must be even-length hex")
    try:
        metadata = bytes.fromhex(metadata_hex)
    except ValueError as exc:
        raise A1SelectionControlError(f"{context}.qualified_witness.metadata_hex must be hex") from exc
    if not metadata:
        raise A1SelectionControlError(f"{context}.qualified_witness.metadata_hex must not be empty")
    if len(metadata) > MAX_METADATA_BYTES:
        raise A1SelectionControlError(
            f"{context}.qualified_witness.metadata_hex exceeds {MAX_METADATA_BYTES} byte bound"
        )
    digest = hashlib.sha256(metadata).hexdigest()
    declared = _sha256(
        witness.get("metadata_sha256"), f"{context}.qualified_witness.metadata_sha256"
    )
    if declared != digest:
        raise A1SelectionControlError(
            f"{context}.qualified_witness.metadata_sha256 must match bounded metadata bytes"
        )
    expected = _sha256(scenario_planets.get(logical), f"scenario qualification digest for {logical}")
    if expected != digest:
        raise A1SelectionControlError(
            f"{context} bounded metadata does not match independent scenario qualification"
        )
    witness["metadata_sha256"] = digest
    return digest


def _point(
    observations: dict[str, Any],
    name: str,
    scenario_planets: dict[str, Any],
    witness_ranges: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = f"selection-control observations.{name}"
    point = observations.get(name)
    if not isinstance(point, dict):
        raise A1SelectionControlError(f"selection-control requires observations.{name}")
    _nonnegative_int(point.get("seq"), f"{context}.seq")
    _nonnegative_int(point.get("record_pointer"), f"{context}.record_pointer")
    logical = _nonempty_string(point.get("logical_record"), f"{context}.logical_record")
    witness = point.get("qualified_witness")
    if not isinstance(witness, dict):
        raise A1SelectionControlError(f"{context} requires qualified_witness")
    scenario_planet = _nonempty_string(
        witness.get("scenario_planet"), f"{context}.qualified_witness.scenario_planet"
    )
    if scenario_planet != logical:
        raise A1SelectionControlError(
            f"{context}.qualified_witness.scenario_planet must bind to logical_record"
        )

    if witness_ranges is None:
        _legacy_witness(witness, logical, scenario_planets, context)
        return point

    try:
        validate_qualified_witness(
            witness,
            logical,
            scenario_planets,
            witness_ranges,
            context=context,
        )
    except A1V2WitnessBindingError as exc:
        raise A1SelectionControlError(str(exc)) from exc
    return point


def validate_selection_control(record: dict[str, Any], scenario_manifest: dict[str, Any]) -> None:
    outcome = record.get("outcome")
    if not isinstance(outcome, str) or not outcome.startswith("positive-"):
        return
    planets = scenario_manifest.get("planets")
    if not isinstance(planets, dict) or not planets:
        raise A1SelectionControlError("selection-control requires scenario qualification planets")

    witness_ranges: dict[str, Any] | None = None
    if scenario_manifest.get("schema") == SCENARIO_SCHEMA_V2:
        candidate = scenario_manifest.get("witness_ranges")
        if not isinstance(candidate, dict) or not candidate:
            raise A1SelectionControlError("scenario qualification v2 manifest requires witness_ranges")
        if set(candidate) != set(planets):
            raise A1SelectionControlError("scenario qualification v2 witness_ranges must exactly cover planets")
        witness_ranges = candidate

    transitions = record.get("transitions")
    if not isinstance(transitions, list):
        raise A1SelectionControlError("selection-control requires transitions list")
    matches = [step for step in transitions if isinstance(step, dict) and step.get("label") == "selection-control"]
    if len(matches) != 1:
        raise A1SelectionControlError("positive outcome requires exactly one selection-control transition")
    step = matches[0]
    if step.get("replacement") is not False:
        raise A1SelectionControlError(
            "positive selection-control must explicitly report replacement=false"
        )
    observations = step.get("observations")
    if not isinstance(observations, dict):
        raise A1SelectionControlError(
            "positive outcome requires bounded observations for selection-control"
        )

    first = _point(observations, "first", planets, witness_ranges)
    second = _point(observations, "second", planets, witness_ranges)
    returned = _point(observations, "return", planets, witness_ranges)
    first_seq = first["seq"]
    second_seq = second["seq"]
    return_seq = returned["seq"]
    if not (first_seq < second_seq < return_seq):
        raise A1SelectionControlError(
            "selection-control observations must be ordered first < second < return"
        )
    if first["logical_record"] == second["logical_record"]:
        raise A1SelectionControlError("selection-control must observe two distinct logical records")
    if first["record_pointer"] == second["record_pointer"]:
        raise A1SelectionControlError("selection-control must observe two distinct record pointers")
    if returned["logical_record"] != first["logical_record"]:
        raise A1SelectionControlError("selection-control return must bind to the first logical record")
    if returned["record_pointer"] != first["record_pointer"]:
        raise A1SelectionControlError("selection-control return must reproduce the first record pointer")
    first_digest = first["qualified_witness"]["metadata_sha256"].lower()
    return_digest = returned["qualified_witness"]["metadata_sha256"].lower()
    if return_digest != first_digest:
        raise A1SelectionControlError("selection-control return must reproduce the first qualified witness")
