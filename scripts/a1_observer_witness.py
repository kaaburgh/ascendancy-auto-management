"""Validate predeclared A1 runtime witness ranges against one selected planet record."""
from __future__ import annotations

import hashlib
from typing import Any

try:
    from .a1_v2_witness_binding import (
        A1V2WitnessBindingError,
        PLANET_RECORD_SIZE,
        PRESENTATION_NAME_LENGTH,
        PRESENTATION_NAME_OFFSET,
        SCENARIO_SCHEMA_V2 as SCENARIO_SCHEMA,
        witness_contract as _shared_witness_contract,
    )
except ImportError:
    from a1_v2_witness_binding import (
        A1V2WitnessBindingError,
        PLANET_RECORD_SIZE,
        PRESENTATION_NAME_LENGTH,
        PRESENTATION_NAME_OFFSET,
        SCENARIO_SCHEMA_V2 as SCENARIO_SCHEMA,
        witness_contract as _shared_witness_contract,
    )


class A1ObserverWitnessError(ValueError):
    pass


def _nonempty_string(value: Any, context: str, *, exact: bool = False) -> str:
    if not isinstance(value, str):
        raise A1ObserverWitnessError(f"{context} must be a non-empty string")
    if (value == "") if exact else (not value.strip()):
        raise A1ObserverWitnessError(f"{context} must be a non-empty string")
    return value


def witness_contract(manifest: dict[str, Any], logical_label: str) -> dict[str, Any]:
    """Return the exact predeclared witness contract for one logical label."""
    if not isinstance(manifest, dict) or manifest.get("schema") != SCENARIO_SCHEMA:
        raise A1ObserverWitnessError("exact-target observer requires scenario qualification v2")
    label = _nonempty_string(logical_label, "logical label", exact=True)
    planets = manifest.get("planets")
    ranges = manifest.get("witness_ranges")
    if not isinstance(planets, dict) or not isinstance(ranges, dict):
        raise A1ObserverWitnessError("scenario manifest requires planets and witness_ranges objects")
    try:
        return _shared_witness_contract(planets, ranges, label)
    except A1V2WitnessBindingError as exc:
        raise A1ObserverWitnessError(str(exc)) from exc


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
