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


def _sha256(value: Any, context: str) -> str:
    text = _nonempty(value, context).lower()
    if len(text) != 64:
        raise A1LifetimeRecordAdapterError(f"{context} must be a 64-hex SHA-256 digest")
    try:
        int(text, 16)
    except ValueError as exc:
        raise A1LifetimeRecordAdapterError(
            f"{context} must be a 64-hex SHA-256 digest"
        ) from exc
    return text


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


def _step_index(steps: list[dict[str, Any]]) -> dict[str, tuple[int, dict[str, Any]]]:
    indexed: dict[str, tuple[int, dict[str, Any]]] = {}
    for index, step in enumerate(steps):
        step_id = _nonempty(step.get("step"), f"transcript.steps[{index}].step")
        if step_id in indexed:
            raise A1LifetimeRecordAdapterError(
                f"transcript step id {step_id!r} is duplicated"
            )
        indexed[step_id] = (index, step)
    return indexed


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
            _sha256(
                witness.get("metadata_sha256"),
                f"selection step {index}.qualified_witness.metadata_sha256",
            )
        )

    if complete:
        if logical_records[0] == logical_records[1]:
            raise A1LifetimeRecordAdapterError(
                "complete selection control must observe two distinct logical records"
            )
        if record_pointers[0] == record_pointers[1]:
            raise A1LifetimeRecordAdapterError(
                "complete selection control must observe two distinct record pointers"
            )
        if logical_records[2] != logical_records[0]:
            raise A1LifetimeRecordAdapterError(
                "complete selection control must return to the first logical record"
            )
        if record_pointers[2] != record_pointers[0]:
            raise A1LifetimeRecordAdapterError(
                "complete selection control must return to the first record pointer"
            )
        if witness_sha256[2] != witness_sha256[0]:
            raise A1LifetimeRecordAdapterError(
                "complete selection control must return to the first qualified witness"
            )

    return {
        "label": "selection-control",
        "replacement": False,
        "source_steps": source_steps,
        "logical_records": logical_records,
        "record_pointers": record_pointers,
        "witness_sha256": witness_sha256,
    }


def _replacement_transition(
    leg: dict[str, Any],
    index: int,
    steps_by_id: dict[str, tuple[int, dict[str, Any]]],
) -> dict[str, Any]:
    context = f"replacement leg {index}"
    mechanism = _nonempty(leg.get("mechanism"), f"{context}.mechanism")
    if mechanism not in EXPECTED_REPLACEMENTS:
        raise A1LifetimeRecordAdapterError(
            f"{context}.mechanism is unsupported: {mechanism!r}"
        )
    source_steps = [
        _nonempty(leg.get("pre_step"), f"{context}.pre_step"),
        _nonempty(leg.get("replace_step"), f"{context}.replace_step"),
        _nonempty(leg.get("post_step"), f"{context}.post_step"),
    ]
    try:
        resolved = [steps_by_id[step_id] for step_id in source_steps]
    except KeyError as exc:
        raise A1LifetimeRecordAdapterError(
            f"{context} references missing transcript step {exc.args[0]!r}"
        ) from exc
    positions = [position for position, _ in resolved]
    if positions != list(range(positions[0], positions[0] + 3)):
        raise A1LifetimeRecordAdapterError(
            f"{context} steps must be one consecutive pre/action/post sequence"
        )
    pre, action, post = [step for _, step in resolved]
    if pre.get("phase") != "pre-replacement" or post.get("phase") != "post-replacement":
        raise A1LifetimeRecordAdapterError(
            f"{context} must reference pre-replacement and post-replacement qualifications"
        )
    if action.get("mechanism") != mechanism:
        raise A1LifetimeRecordAdapterError(
            f"{context}.mechanism does not match its replacement action step"
        )

    pre_pointer = pre.get("record_pointer")
    post_pointer = post.get("record_pointer")
    for label, pointer in (("pre", pre_pointer), ("post", post_pointer)):
        if not isinstance(pointer, int) or isinstance(pointer, bool) or pointer < 0:
            raise A1LifetimeRecordAdapterError(
                f"{context} {label} step record_pointer must be a non-negative integer"
            )
    expected_fields = {
        "pre_record_pointer": pre_pointer,
        "post_record_pointer": post_pointer,
        "pre_logical_record": _nonempty(pre.get("logical_record"), f"{context} pre logical_record"),
        "post_logical_record": _nonempty(post.get("logical_record"), f"{context} post logical_record"),
        "pointer_reused_after_replacement": pre_pointer == post_pointer,
        "lifecycle_signal": action.get("lifecycle_signal"),
    }
    for field, expected in expected_fields.items():
        if leg.get(field) != expected:
            raise A1LifetimeRecordAdapterError(
                f"{context}.{field} does not match referenced transcript steps"
            )

    reused = expected_fields["pointer_reused_after_replacement"]
    assert isinstance(reused, bool)
    return {
        "label": mechanism,
        "replacement": True,
        "source_steps": source_steps,
        "pre_logical_record": expected_fields["pre_logical_record"],
        "post_logical_record": expected_fields["post_logical_record"],
        "pointer_reused_after_replacement": reused,
        "lifecycle_signal": expected_fields["lifecycle_signal"],
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
    steps_by_id = _step_index(steps)
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
    transitions.extend(
        _replacement_transition(leg, index, steps_by_id) for index, leg in enumerate(legs)
    )

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
