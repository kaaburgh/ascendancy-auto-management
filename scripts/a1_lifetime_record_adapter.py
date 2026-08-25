"""Project bounded A1 observer transcripts into the existing lifetime-record schema.

The observer transcript intentionally omits raw target bytes and the richer reuse-event
semantics required by a positive lifetime contract. This adapter therefore preserves
what the transcript can prove while always producing an ``incomplete-harness`` record.
The lifetime oracle remains the authority for interpreting the resulting record.
"""
from __future__ import annotations

from typing import Any

try:
    from .a1_lifetime_observer_core import TRANSCRIPT_SCHEMA
    from .a1_sidecar_lifetime_oracle import SCHEMA as LIFETIME_RECORD_SCHEMA
except ImportError:
    from a1_lifetime_observer_core import TRANSCRIPT_SCHEMA
    from a1_sidecar_lifetime_oracle import SCHEMA as LIFETIME_RECORD_SCHEMA


EXPECTED_REPLACEMENTS = ("new-game-reset", "save-load-replacement")


class A1LifetimeRecordAdapterError(ValueError):
    pass


def _nonempty(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise A1LifetimeRecordAdapterError(f"{context} must be a non-empty string")
    return value


def _steps(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    raw = transcript.get("steps")
    if not isinstance(raw, list):
        raise A1LifetimeRecordAdapterError("transcript.steps must be a list")
    steps: list[dict[str, Any]] = []
    for index, value in enumerate(raw):
        if not isinstance(value, dict):
            raise A1LifetimeRecordAdapterError(
                f"transcript.steps[{index}] must be an object"
            )
        steps.append(value)
    return steps


def _replacement_legs(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    raw = transcript.get("replacement_legs")
    if not isinstance(raw, list):
        raise A1LifetimeRecordAdapterError("transcript.replacement_legs must be a list")
    legs: list[dict[str, Any]] = []
    for index, value in enumerate(raw):
        if not isinstance(value, dict):
            raise A1LifetimeRecordAdapterError(
                f"transcript.replacement_legs[{index}] must be an object"
            )
        legs.append(value)
    return legs


def _selection_transition(steps: list[dict[str, Any]], complete: bool) -> dict[str, Any] | None:
    selected = [step for step in steps if step.get("phase") == "selection-control"]
    if complete and len(selected) != 3:
        raise A1LifetimeRecordAdapterError(
            "complete transcript must contain exactly three selection-control qualifications"
        )
    if not selected:
        return None

    source_steps: list[str] = []
    logical_records: list[str] = []
    record_pointers: list[int] = []
    witness_sha256: list[str] = []
    for index, step in enumerate(selected):
        source_steps.append(_nonempty(step.get("step"), f"selection step {index}.step"))
        logical_records.append(
            _nonempty(step.get("logical_record"), f"selection step {index}.logical_record")
        )
        pointer = step.get("record_pointer")
        if not isinstance(pointer, int) or isinstance(pointer, bool) or pointer < 0:
            raise A1LifetimeRecordAdapterError(
                f"selection step {index}.record_pointer must be a non-negative integer"
            )
        record_pointers.append(pointer)
        witness = step.get("qualified_witness")
        if not isinstance(witness, dict):
            raise A1LifetimeRecordAdapterError(
                f"selection step {index}.qualified_witness must be an object"
            )
        witness_sha256.append(
            _nonempty(
                witness.get("metadata_sha256"),
                f"selection step {index}.qualified_witness.metadata_sha256",
            )
        )

    return {
        "label": "selection-control",
        "replacement": False,
        "source_steps": source_steps,
        "logical_records": logical_records,
        "record_pointers": record_pointers,
        "witness_sha256": witness_sha256,
    }


def _replacement_transition(leg: dict[str, Any], index: int) -> dict[str, Any]:
    mechanism = _nonempty(leg.get("mechanism"), f"replacement leg {index}.mechanism")
    if mechanism not in EXPECTED_REPLACEMENTS:
        raise A1LifetimeRecordAdapterError(
            f"replacement leg {index}.mechanism is unsupported: {mechanism!r}"
        )
    source_steps = [
        _nonempty(leg.get("pre_step"), f"replacement leg {index}.pre_step"),
        _nonempty(leg.get("replace_step"), f"replacement leg {index}.replace_step"),
        _nonempty(leg.get("post_step"), f"replacement leg {index}.post_step"),
    ]
    reused = leg.get("pointer_reused_after_replacement")
    if not isinstance(reused, bool):
        raise A1LifetimeRecordAdapterError(
            f"replacement leg {index}.pointer_reused_after_replacement must be boolean"
        )
    return {
        "label": mechanism,
        "replacement": True,
        "source_steps": source_steps,
        "pre_logical_record": _nonempty(
            leg.get("pre_logical_record"), f"replacement leg {index}.pre_logical_record"
        ),
        "post_logical_record": _nonempty(
            leg.get("post_logical_record"), f"replacement leg {index}.post_logical_record"
        ),
        "pointer_reused_after_replacement": reused,
        "lifecycle_signal": leg.get("lifecycle_signal"),
    }


def adapt_transcript(transcript: dict[str, Any]) -> dict[str, Any]:
    """Return a fail-closed lifetime record for one bounded observer transcript.

    A transcript is not sufficient to establish a positive A1 lifetime contract because
    it deliberately omits raw witness bytes and an oracle-shaped observed reuse event.
    Consequently this function never emits a positive outcome.
    """
    if not isinstance(transcript, dict):
        raise A1LifetimeRecordAdapterError("transcript root must be an object")
    if transcript.get("schema") != TRANSCRIPT_SCHEMA:
        raise A1LifetimeRecordAdapterError("unsupported or missing observer transcript schema")
    status = transcript.get("status")
    if status not in {"complete", "incomplete-harness"}:
        raise A1LifetimeRecordAdapterError("unsupported or missing observer transcript status")

    steps = _steps(transcript)
    legs = _replacement_legs(transcript)
    complete = status == "complete"
    if complete:
        if len(legs) != len(EXPECTED_REPLACEMENTS):
            raise A1LifetimeRecordAdapterError(
                "complete transcript must contain exactly two replacement legs"
            )
        mechanisms = [_nonempty(leg.get("mechanism"), "replacement leg mechanism") for leg in legs]
        if set(mechanisms) != set(EXPECTED_REPLACEMENTS):
            raise A1LifetimeRecordAdapterError(
                "complete transcript must cover new-game-reset and save-load-replacement exactly once"
            )

    transitions: list[dict[str, Any]] = []
    selection = _selection_transition(steps, complete)
    if selection is not None:
        transitions.append(selection)
    transitions.extend(_replacement_transition(leg, index) for index, leg in enumerate(legs))

    record: dict[str, Any] = {
        "schema": LIFETIME_RECORD_SCHEMA,
        "outcome": "incomplete-harness",
        "claims": {
            "array_base_established": False,
            "array_count_established": False,
            "stable_index_established": False,
            "reuse_detector_established": False,
            "epoch_boundary_established": False,
            "manual_transition_invalidation_established": False,
        },
        "control": {"passed": complete and selection is not None},
        "transitions": transitions,
        "observer_transcript": {
            "schema": TRANSCRIPT_SCHEMA,
            "status": status,
            "step_count": len(steps),
            "replacement_leg_count": len(legs),
        },
        "adapter_limitation": (
            "observer transcript omits the raw witness bytes and oracle-shaped reuse-event "
            "evidence required for a positive lifetime contract"
        ),
    }
    if status == "incomplete-harness":
        error = transcript.get("error")
        if error is not None:
            record["observer_transcript"]["error"] = _nonempty(error, "transcript.error")
    return record
