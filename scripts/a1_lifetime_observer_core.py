"""Execute the bounded A1 lifetime-observer action plan against a supplied runtime backend."""
from __future__ import annotations

import time
from typing import Any, Protocol

try:
    from .a1_lifetime_action_script import validate_action_script
    from .a1_observer_witness import A1ObserverWitnessError, qualify_selected_record
except ImportError:
    from a1_lifetime_action_script import validate_action_script
    from a1_observer_witness import A1ObserverWitnessError, qualify_selected_record

TRANSCRIPT_SCHEMA = "ascendancy.a1-lifetime-observer-transcript/v1"
STATE_OFFSET = 0x5A
STATE_SIZE = 4


class A1ObserverExecutionError(RuntimeError):
    pass


class RuntimeBackend(Protocol):
    def qualify(
        self, *, step_id: str, logical_label: str, timeout_seconds: float
    ) -> dict[str, Any]:
        """Return record_pointer:int, record:bytes, population_replacement:bool."""

    def replace(
        self, *, step_id: str, mechanism: str, timeout_seconds: float
    ) -> dict[str, Any]:
        """Perform one bounded replacement action and return optional lifecycle_signal."""


def _remaining(deadline: float, per_step: float, clock: Any) -> float:
    remaining = deadline - float(clock())
    if remaining <= 0:
        raise A1ObserverExecutionError("observer exceeded total runtime bound")
    return min(per_step, remaining)


def _qualify(
    manifest: dict[str, Any],
    backend: RuntimeBackend,
    step: dict[str, Any],
    *,
    timeout: float,
    attempts: int,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            raw = backend.qualify(
                step_id=step["id"],
                logical_label=step["logical_label"],
                timeout_seconds=timeout,
            )
            if not isinstance(raw, dict):
                raise A1ObserverExecutionError("runtime qualification result must be an object")
            pointer = raw.get("record_pointer")
            record = raw.get("record")
            replacement = raw.get("population_replacement")
            if not isinstance(pointer, int) or isinstance(pointer, bool) or pointer < 0:
                raise A1ObserverExecutionError("record_pointer must be a non-negative integer")
            if not isinstance(replacement, bool):
                raise A1ObserverExecutionError("population_replacement must be boolean")
            witness = qualify_selected_record(manifest, step["logical_label"], record)
            managed = int.from_bytes(record[STATE_OFFSET:STATE_OFFSET + STATE_SIZE], "little")
            return {
                "step": step["id"],
                "logical_record": step["logical_label"],
                "phase": step["phase"],
                "record_pointer": pointer,
                "population_replacement": replacement,
                "managed_field_value": managed,
                "qualified_witness": {
                    "scenario_planet": witness["logical_record"],
                    "metadata_basis": witness["metadata_basis"],
                    "record_offset": witness["record_offset"],
                    "length": witness["length"],
                    "metadata_sha256": witness["observed_sha256"],
                },
                "attempt": attempt,
            }
        except (A1ObserverWitnessError, A1ObserverExecutionError, KeyError, TypeError) as exc:
            last_error = exc
    assert last_error is not None
    raise A1ObserverExecutionError(
        f"qualification {step['id']!r} failed after {attempts} attempt(s): {last_error}"
    ) from last_error


def _signal(result: dict[str, Any]) -> dict[str, Any] | None:
    signal = result.get("lifecycle_signal")
    if signal is None:
        return None
    if not isinstance(signal, dict):
        raise A1ObserverExecutionError("lifecycle_signal must be an object or null")
    name = signal.get("name")
    changed_before_post = signal.get("changed_before_post_qualification")
    if not isinstance(name, str) or not name.strip():
        raise A1ObserverExecutionError("lifecycle_signal.name must be non-empty")
    if "before" not in signal or "after" not in signal:
        raise A1ObserverExecutionError("lifecycle_signal requires before and after")
    if signal["before"] == signal["after"]:
        raise A1ObserverExecutionError("lifecycle_signal did not change")
    if not isinstance(changed_before_post, bool):
        raise A1ObserverExecutionError(
            "lifecycle_signal.changed_before_post_qualification must be boolean"
        )
    return {
        "name": name,
        "before": signal["before"],
        "after": signal["after"],
        "changed_before_post_qualification": changed_before_post,
    }


def execute_observer_plan(
    manifest: dict[str, Any],
    action_script: dict[str, Any],
    backend: RuntimeBackend,
    *,
    clock: Any = time.monotonic,
) -> dict[str, Any]:
    """Execute the predeclared plan without serializing target record bytes."""
    validated = validate_action_script(action_script)
    bounds = validated["bounds"]
    per_step = float(bounds["per_step_timeout_seconds"])
    attempts = int(bounds["max_qualification_attempts_per_step"])
    deadline = float(clock()) + float(bounds["total_timeout_seconds"])

    transcript: dict[str, Any] = {
        "schema": TRANSCRIPT_SCHEMA,
        "status": "incomplete-harness",
        "steps": [],
        "replacement_legs": [],
    }

    try:
        raw_steps = action_script["steps"]
        control: list[dict[str, Any]] = []
        pending_replacement: dict[str, Any] | None = None

        for step in raw_steps:
            timeout = _remaining(deadline, per_step, clock)
            if step["action"] == "qualify":
                point = _qualify(
                    manifest, backend, step, timeout=timeout, attempts=attempts
                )
                transcript["steps"].append(point)

                if step["phase"] == "selection-control":
                    if point["population_replacement"]:
                        raise A1ObserverExecutionError(
                            "selection control reported population replacement"
                        )
                    control.append(point)
                    if len(control) == 3:
                        a1, b, a2 = control
                        if a1["record_pointer"] == b["record_pointer"]:
                            raise A1ObserverExecutionError(
                                "selection control A and B must have distinct record pointers"
                            )
                        if a2["record_pointer"] != a1["record_pointer"]:
                            raise A1ObserverExecutionError(
                                "selection control did not return to the original A pointer"
                            )
                        if (
                            a2["qualified_witness"]["metadata_sha256"]
                            != a1["qualified_witness"]["metadata_sha256"]
                        ):
                            raise A1ObserverExecutionError(
                                "selection control did not return to the original A witness"
                            )

                elif step["phase"] == "pre-replacement":
                    if pending_replacement is not None:
                        raise A1ObserverExecutionError("replacement leg already pending")
                    pending_replacement = {"pre": point}

                elif step["phase"] == "post-replacement":
                    if pending_replacement is None or "action" not in pending_replacement:
                        raise A1ObserverExecutionError(
                            "post-replacement qualification has no completed replacement action"
                        )
                    pre = pending_replacement["pre"]
                    action = pending_replacement["action"]
                    signal = action["lifecycle_signal"]
                    pointer_reused_for_new_logical = (
                        pre["record_pointer"] == point["record_pointer"]
                        and pre["logical_record"] != point["logical_record"]
                    )
                    if pointer_reused_for_new_logical and signal is None:
                        raise A1ObserverExecutionError(
                            "record pointer was reused for a different logical record without a lifecycle signal"
                        )
                    if (
                        pointer_reused_for_new_logical
                        and not signal["changed_before_post_qualification"]
                    ):
                        raise A1ObserverExecutionError(
                            "lifecycle signal was first observed too late to guard pointer reuse"
                        )
                    leg = {
                        "mechanism": action["mechanism"],
                        "pre_step": pre["step"],
                        "replace_step": action["step"],
                        "post_step": point["step"],
                        "pre_record_pointer": pre["record_pointer"],
                        "post_record_pointer": point["record_pointer"],
                        "pre_logical_record": pre["logical_record"],
                        "post_logical_record": point["logical_record"],
                        "pointer_reused_for_new_logical_record": pointer_reused_for_new_logical,
                        "lifecycle_signal": signal,
                    }
                    transcript["replacement_legs"].append(leg)
                    pending_replacement = None
                else:
                    raise A1ObserverExecutionError(f"unexpected qualification phase: {step['phase']}")
            else:
                if pending_replacement is None or "action" in pending_replacement:
                    raise A1ObserverExecutionError(
                        "replacement action requires one immediately preceding pre-replacement qualification"
                    )
                result = backend.replace(
                    step_id=step["id"],
                    mechanism=step["mechanism"],
                    timeout_seconds=timeout,
                )
                if not isinstance(result, dict):
                    raise A1ObserverExecutionError("replacement result must be an object")
                if result.get("completed") is not True:
                    raise A1ObserverExecutionError(
                        f"replacement action {step['id']!r} did not complete"
                    )
                action = {
                    "step": step["id"],
                    "mechanism": step["mechanism"],
                    "lifecycle_signal": _signal(result),
                }
                transcript["steps"].append(action)
                pending_replacement["action"] = action

        if pending_replacement is not None:
            raise A1ObserverExecutionError("replacement leg did not reach post qualification")
        if len(transcript["replacement_legs"]) != 2:
            raise A1ObserverExecutionError("both replacement legs were not observed")
        transcript["status"] = "complete"
        return transcript
    except Exception as exc:
        transcript["error"] = str(exc)
        return transcript
