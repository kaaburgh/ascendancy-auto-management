"""Run the bounded A1 observer → lifetime-record pipeline.

The committed synthetic mode exists only to prove that the repository's already-reviewed
pieces form one executable chain. It is not target-runtime evidence.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

try:
    from .a1_lifetime_action_script import ACTION_SCRIPT_SCHEMA
    from .a1_lifetime_observer_core import RuntimeBackend, execute_observer_plan
    from .a1_lifetime_record_adapter import adapt_transcript
    from .a1_observer_witness import SCENARIO_SCHEMA
    from .a1_sidecar_lifetime_oracle import validate_record
except ImportError:
    from a1_lifetime_action_script import ACTION_SCRIPT_SCHEMA
    from a1_lifetime_observer_core import RuntimeBackend, execute_observer_plan
    from a1_lifetime_record_adapter import adapt_transcript
    from a1_observer_witness import SCENARIO_SCHEMA
    from a1_sidecar_lifetime_oracle import validate_record


class SyntheticBackend:
    """Deterministic repository-safe backend for the narrow end-to-end smoke path."""

    def __init__(self, records: dict[str, bytes]) -> None:
        self.records = records
        self.pointers = {"A": 100, "B": 200, "C": 300, "D": 400}
        self.signals = {
            "new-game-reset": {
                "name": "epoch",
                "before": 1,
                "after": 2,
                "changed_before_post_qualification": True,
            },
            "save-load-replacement": {
                "name": "epoch",
                "before": 2,
                "after": 3,
                "changed_before_post_qualification": True,
            },
        }

    def qualify(
        self, *, step_id: str, logical_label: str, timeout_seconds: float
    ) -> dict[str, Any]:
        return {
            "record_pointer": self.pointers[logical_label],
            "record": self.records[logical_label],
            "population_replacement": False,
        }

    def replace(
        self, *, step_id: str, mechanism: str, timeout_seconds: float
    ) -> dict[str, Any]:
        return {"completed": True, "lifecycle_signal": self.signals[mechanism]}


def _record(fill: int, witness: bytes) -> bytes:
    data = bytearray([fill] * 0x7B)
    data[8 : 8 + len(witness)] = witness
    return bytes(data)


def build_synthetic_plan() -> tuple[dict[str, Any], dict[str, Any], SyntheticBackend]:
    """Build the smallest deterministic plan that exercises every pipeline stage."""
    records = {
        "A": _record(1, b"AAAAAAAA"),
        "B": _record(2, b"BBBBBBBB"),
        "C": _record(3, b"CCCCCCCC"),
        "D": _record(4, b"DDDDDDDD"),
    }
    planets: dict[str, str] = {}
    witness_ranges: dict[str, dict[str, Any]] = {}
    for label, record in records.items():
        witness = record[8:16]
        digest = hashlib.sha256(witness).hexdigest()
        planets[label] = digest
        witness_ranges[label] = {
            "metadata_basis": "bounded-record-metadata",
            "record_offset": 8,
            "length": 8,
            "sha256": digest,
            "rationale": "synthetic stable witness for the end-to-end pipeline smoke path",
        }

    manifest = {
        "schema": SCENARIO_SCHEMA,
        "planets": planets,
        "witness_ranges": witness_ranges,
    }
    action_script = {
        "schema": ACTION_SCRIPT_SCHEMA,
        "bounds": {
            "max_action_count": 9,
            "max_qualification_attempts_per_step": 2,
            "per_step_timeout_seconds": 10,
            "total_timeout_seconds": 120,
        },
        "steps": [
            {
                "id": "control-a1",
                "action": "qualify",
                "phase": "selection-control",
                "logical_label": "A",
            },
            {
                "id": "control-b",
                "action": "qualify",
                "phase": "selection-control",
                "logical_label": "B",
            },
            {
                "id": "control-a2",
                "action": "qualify",
                "phase": "selection-control",
                "logical_label": "A",
            },
            {
                "id": "ng-pre",
                "action": "qualify",
                "phase": "pre-replacement",
                "logical_label": "A",
            },
            {"id": "ng", "action": "replace", "mechanism": "new-game-reset"},
            {
                "id": "ng-post",
                "action": "qualify",
                "phase": "post-replacement",
                "logical_label": "C",
            },
            {
                "id": "sl-pre",
                "action": "qualify",
                "phase": "pre-replacement",
                "logical_label": "C",
            },
            {"id": "sl", "action": "replace", "mechanism": "save-load-replacement"},
            {
                "id": "sl-post",
                "action": "qualify",
                "phase": "post-replacement",
                "logical_label": "D",
            },
        ],
    }
    return manifest, action_script, SyntheticBackend(records)


def run_pipeline(
    manifest: dict[str, Any],
    action_script: dict[str, Any],
    backend: RuntimeBackend,
) -> dict[str, Any]:
    """Plan inputs are executed, adapted once, and accepted by the lifetime oracle."""
    transcript = execute_observer_plan(manifest, action_script, backend)
    record = adapt_transcript(transcript)
    validate_record(record)
    return record


def run_synthetic_pipeline() -> dict[str, Any]:
    manifest, action_script, backend = build_synthetic_plan()
    return run_pipeline(manifest, action_script, backend)


def main() -> int:
    print(json.dumps(run_synthetic_pipeline(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
