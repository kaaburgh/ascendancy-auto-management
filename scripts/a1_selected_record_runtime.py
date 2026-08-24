"""Fail-closed selected-record resolver for the A1 exact-target lifetime observer."""
from __future__ import annotations

from typing import Any, Callable

try:
    from .a1_observer_witness import (
        A1ObserverWitnessError,
        PLANET_RECORD_SIZE,
        qualify_selected_record,
    )
except ImportError:
    from a1_observer_witness import (
        A1ObserverWitnessError,
        PLANET_RECORD_SIZE,
        qualify_selected_record,
    )

DATA_OBJECT_BASE_VA = 0x90000
SELECTED_PLANET_DS_OFFSET = 0x43664
SELECTED_PLANET_STATIC_VA = DATA_OBJECT_BASE_VA + SELECTED_PLANET_DS_OFFSET
POINTER_SIZE = 4


class A1SelectedRecordResolutionError(RuntimeError):
    pass


def resolve_selected_record(
    pid: int,
    anchor: dict[str, Any],
    data_bias: int,
    manifest: dict[str, Any],
    logical_label: str,
    *,
    read_process: Callable[[int, int, int], bytes] | None = None,
    data_host: Callable[[dict[str, Any], int, int, int], int] | None = None,
) -> dict[str, Any]:
    """Resolve and qualify the currently selected planet without serializing record bytes.

    The canonical target stores the selected-object pointer at DS:0x43664. The
    validated RE5 data-object mapping resolves that global to the DOSBox host
    mapping. The pointer value itself is treated only as a candidate offset in
    the bounded guest-memory mapping: the predeclared v2 witness must qualify
    the exact 0x7b bytes at that candidate before the relation is accepted.
    """
    if read_process is None or data_host is None:
        try:
            import run_re4_runtime_state as re4
            import run_re5_override_witness as override_witness
        except ImportError as exc:
            raise A1SelectedRecordResolutionError(
                f"runtime mapping helpers unavailable: {exc}"
            ) from exc
        read_process = read_process or re4.read_process
        data_host = data_host or override_witness.data_host

    try:
        map_start = int(anchor["map_start"])
        map_end = int(anchor["map_end"])
    except (KeyError, TypeError, ValueError) as exc:
        raise A1SelectedRecordResolutionError(
            "runtime anchor lacks a valid mapping range"
        ) from exc
    if map_start < 0 or map_end <= map_start:
        raise A1SelectedRecordResolutionError("runtime anchor mapping range is invalid")

    global_host = data_host(
        anchor, data_bias, SELECTED_PLANET_STATIC_VA, POINTER_SIZE
    )
    raw_pointer = read_process(pid, global_host, POINTER_SIZE)
    if not isinstance(raw_pointer, bytes) or len(raw_pointer) != POINTER_SIZE:
        raise A1SelectedRecordResolutionError("short selected-planet pointer read")
    guest_pointer = int.from_bytes(raw_pointer, "little")
    if guest_pointer == 0:
        raise A1SelectedRecordResolutionError("selected-planet pointer is null")

    record_host = map_start + guest_pointer
    if record_host < map_start or record_host + PLANET_RECORD_SIZE > map_end:
        raise A1SelectedRecordResolutionError(
            "selected-planet pointer resolves outside bounded runtime mapping"
        )
    record = read_process(pid, record_host, PLANET_RECORD_SIZE)
    if not isinstance(record, bytes) or len(record) != PLANET_RECORD_SIZE:
        raise A1SelectedRecordResolutionError("short selected-planet record read")
    try:
        witness = qualify_selected_record(manifest, logical_label, record)
    except A1ObserverWitnessError as exc:
        raise A1SelectedRecordResolutionError(
            "selected-planet pointer candidate failed the predeclared logical-record witness"
        ) from exc
    return {
        "record_pointer": guest_pointer,
        "record": record,
        "qualified_witness": witness,
        "pointer_mapping_relation": "dosbox-mapping-offset-qualified-by-v2-witness",
    }
