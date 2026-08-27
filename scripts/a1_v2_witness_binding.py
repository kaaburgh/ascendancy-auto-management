"""Shared validation for A1 v2 predeclared witness-range binding."""
from __future__ import annotations

from typing import Any

SCENARIO_SCHEMA_V2 = "ascendancy.a1-sidecar-scenario-qualification/v2"
PLANET_RECORD_SIZE = 0x7B
MAX_METADATA_BYTES = 512
PRESENTATION_NAME_OFFSET = 0x24
PRESENTATION_NAME_LENGTH = 32
METADATA_BASIS = "bounded-record-metadata"


class A1V2WitnessBindingError(ValueError):
    pass


def _nonempty_string(value: Any, context: str, *, exact: bool = False) -> str:
    if not isinstance(value, str) or (value == "" if exact else not value.strip()):
        raise A1V2WitnessBindingError(f"{context} must be a non-empty string")
    return value


def _sha256(value: Any, context: str) -> str:
    text = _nonempty_string(value, context)
    if len(text) != 64:
        raise A1V2WitnessBindingError(f"{context} must be a 64-hex SHA-256 digest")
    try:
        int(text, 16)
    except ValueError as exc:
        raise A1V2WitnessBindingError(f"{context} must be a 64-hex SHA-256 digest") from exc
    return text.lower()


def _nonnegative_int(value: Any, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise A1V2WitnessBindingError(f"{context} must be a non-negative integer")
    return value


def _positive_int(value: Any, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise A1V2WitnessBindingError(f"{context} must be a positive integer")
    return value


def _reject_presentation_name_overlap(offset: int, length: int, logical_label: str) -> None:
    end = offset + length
    name_end = PRESENTATION_NAME_OFFSET + PRESENTATION_NAME_LENGTH
    if offset < name_end and end > PRESENTATION_NAME_OFFSET:
        raise A1V2WitnessBindingError(
            f"witness range for {logical_label!r} overlaps established presentation-name window "
            f"0x{PRESENTATION_NAME_OFFSET:x}..0x{name_end:x}; presentation name cannot establish identity"
        )


def witness_contract(
    planets: dict[str, Any], witness_ranges: dict[str, Any], logical_label: str
) -> dict[str, Any]:
    """Return one fully validated v2 predeclared witness-range contract."""
    label = _nonempty_string(logical_label, "logical label", exact=True)
    if label not in planets or label not in witness_ranges:
        raise A1V2WitnessBindingError(f"logical label {label!r} is not independently qualified")

    expected = _sha256(planets[label], f"planets[{label!r}]")
    entry = witness_ranges[label]
    if not isinstance(entry, dict):
        raise A1V2WitnessBindingError(f"witness_ranges[{label!r}] must be an object")
    if entry.get("metadata_basis") != METADATA_BASIS:
        raise A1V2WitnessBindingError(
            f"witness_ranges[{label!r}].metadata_basis must be {METADATA_BASIS!r}"
        )
    offset = _nonnegative_int(entry.get("record_offset"), f"witness_ranges[{label!r}].record_offset")
    length = _positive_int(entry.get("length"), f"witness_ranges[{label!r}].length")
    digest = _sha256(entry.get("sha256"), f"witness_ranges[{label!r}].sha256")
    _nonempty_string(entry.get("rationale"), f"witness_ranges[{label!r}].rationale")
    if digest != expected:
        raise A1V2WitnessBindingError(
            f"witness_ranges[{label!r}].sha256 must match planets[{label!r}]"
        )
    if length > MAX_METADATA_BYTES or offset + length > PLANET_RECORD_SIZE:
        raise A1V2WitnessBindingError(
            f"witness range for {label!r} exceeds established 0x{PLANET_RECORD_SIZE:x}-byte record"
        )
    _reject_presentation_name_overlap(offset, length, label)
    return {
        "logical_record": label,
        "metadata_basis": METADATA_BASIS,
        "record_offset": offset,
        "length": length,
        "sha256": digest,
    }


def validate_qualified_witness(
    witness: dict[str, Any],
    logical_record: str,
    planets: dict[str, Any],
    witness_ranges: dict[str, Any],
    *,
    context: str,
) -> str:
    """Validate one digest-only runtime witness against its v2 range; return its digest."""
    if not isinstance(witness, dict):
        raise A1V2WitnessBindingError(f"{context} requires qualified_witness")
    logical = _nonempty_string(logical_record, f"{context}.logical_record")
    scenario_planet = _nonempty_string(
        witness.get("scenario_planet"), f"{context}.qualified_witness.scenario_planet"
    )
    if scenario_planet != logical:
        raise A1V2WitnessBindingError(
            f"{context}.qualified_witness.scenario_planet must bind to logical_record"
        )
    if "metadata_hex" in witness:
        raise A1V2WitnessBindingError(
            f"{context}.qualified_witness v2 witness must not contain metadata_hex"
        )

    contract = witness_contract(planets, witness_ranges, logical)
    basis = _nonempty_string(
        witness.get("metadata_basis"), f"{context}.qualified_witness.metadata_basis"
    )
    if basis != contract["metadata_basis"]:
        raise A1V2WitnessBindingError(
            f"{context}.qualified_witness.metadata_basis must match predeclared v2 witness range"
        )
    offset = _nonnegative_int(
        witness.get("record_offset"), f"{context}.qualified_witness.record_offset"
    )
    length = _positive_int(witness.get("length"), f"{context}.qualified_witness.length")
    if offset != contract["record_offset"]:
        raise A1V2WitnessBindingError(
            f"{context}.qualified_witness.record_offset must match predeclared v2 witness range"
        )
    if length != contract["length"]:
        raise A1V2WitnessBindingError(
            f"{context}.qualified_witness.length must match predeclared v2 witness range"
        )
    declared = _sha256(
        witness.get("metadata_sha256"), f"{context}.qualified_witness.metadata_sha256"
    )
    if declared != contract["sha256"]:
        raise A1V2WitnessBindingError(
            f"{context}.qualified_witness.metadata_sha256 must match predeclared v2 witness range"
        )
    witness["metadata_sha256"] = declared
    return declared
