"""Validate predeclared A1 runtime witness ranges against one selected planet record."""
from __future__ import annotations

import hashlib
from typing import Any

SCENARIO_SCHEMA = "ascendancy.a1-sidecar-scenario-qualification/v2"
PLANET_RECORD_SIZE = 0x7B
METADATA_BASIS = "bounded-record-metadata"


class A1ObserverWitnessError(ValueError):
    pass


def _nonempty_string(value: Any, context: str, *, exact: bool = False) -> str:
    if not isinstance(value, str):
        raise A1ObserverWitnessError(f"{context} must be a non-empty string")
    if (value == "") if exact else (not value.strip()):
        raise A1ObserverWitnessError(f"{context} must be a non-empty string")
    return value


def _sha256(value: Any, context: str) -> str:
    text = _nonempty_string(value, context)
    if len(text) != 64:
        raise A1ObserverWitnessError(f"{context} must be a 64-hex SHA-256 digest")
    try:
        int(text, 16)
    except ValueError as exc:
        raise A1ObserverWitnessError(f"{context} must be a 64-hex SHA-256 digest") from exc
    return text.lower()


def _nonnegative_int(value: Any, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise A1ObserverWitnessError(f"{context} must be a non-negative integer")
    return value


def _positive_int(value: Any, context: str) -> int:
    result = _nonnegative_int(value, context)
    if result == 0:
        raise A1ObserverWitnessError(f"{context} must be positive")
    return result


def witness_contract(manifest: dict[str, Any], logical_label: str) -> dict[str, Any]:
    """Return the exact predeclared witness contract for one logical label."""
    if not isinstance(manifest, dict) or manifest.get("schema") != SCENARIO_SCHEMA:
        raise A1ObserverWitnessError("exact-target observer requires scenario qualification v2")

    label = _nonempty_string(logical_label, "logical label", exact=True)
    planets = manifest.get("planets")
    ranges = manifest.get("witness_ranges")
    if not isinstance(planets, dict) or not isinstance(ranges, dict):
        raise A1ObserverWitnessError("scenario manifest requires planets and witness_ranges objects")
    if label not in planets or label not in ranges:
        raise A1ObserverWitnessError(f"logical label {label!r} is not independently qualified")

    expected = _sha256(planets[label], f"planets[{label!r}]")
    entry = ranges[label]
    if not isinstance(entry, dict):
        raise A1ObserverWitnessError(f"witness_ranges[{label!r}] must be an object")
    if entry.get("metadata_basis") != METADATA_BASIS:
        raise A1ObserverWitnessError(
            f"witness_ranges[{label!r}].metadata_basis must be {METADATA_BASIS!r}"
        )
    offset = _nonnegative_int(entry.get("record_offset"), f"witness_ranges[{label!r}].record_offset")
    length = _positive_int(entry.get("length"), f"witness_ranges[{label!r}].length")
    digest = _sha256(entry.get("sha256"), f"witness_ranges[{label!r}].sha256")
    _nonempty_string(entry.get("rationale"), f"witness_ranges[{label!r}].rationale")
    if digest != expected:
        raise A1ObserverWitnessError(
            f"witness_ranges[{label!r}].sha256 must match planets[{label!r}]"
        )
    if offset + length > PLANET_RECORD_SIZE:
        raise A1ObserverWitnessError(
            f"witness range for {label!r} exceeds established 0x{PLANET_RECORD_SIZE:x}-byte record"
        )

    return {
        "logical_record": label,
        "metadata_basis": METADATA_BASIS,
        "record_offset": offset,
        "length": length,
        "sha256": digest,
    }


def qualify_selected_record(
    manifest: dict[str, Any], logical_label: str, record: bytes
) -> dict[str, Any]:
    """Verify one exact 0x7b selected-record snapshot without returning proprietary bytes."""
    if not isinstance(record, bytes) or len(record) != PLANET_RECORD_SIZE:
        raise A1ObserverWitnessError(
            f"selected record must be exactly 0x{PLANET_RECORD_SIZE:x} bytes"
        )
    contract = witness_contract(manifest, logical_label)
    start = contract["record_offset"]
    end = start + contract["length"]
    observed = hashlib.sha256(record[start:end]).hexdigest()
    if observed != contract["sha256"]:
        raise A1ObserverWitnessError(
            f"selected record does not match independently qualified witness for {logical_label!r}"
        )
    return {
        **contract,
        "record_size": PLANET_RECORD_SIZE,
        "observed_sha256": observed,
        "matched": True,
    }
