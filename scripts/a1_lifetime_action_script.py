"""Validate bounded A1 exact-target lifetime observer action scripts."""
from __future__ import annotations

from typing import Any

ACTION_SCRIPT_SCHEMA = "ascendancy.a1-lifetime-action-script/v1"
_REQUIRED_REPLACEMENT_MECHANISMS = ("new-game-reset", "save-load-replacement")
_ALLOWED_PHASES = ("selection-control", "pre-replacement", "post-replacement")


class A1LifetimeActionScriptError(ValueError):
    pass


def _object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise A1LifetimeActionScriptError(f"{context} must be an object")
    return value


def _nonempty_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise A1LifetimeActionScriptError(f"{context} must be a non-empty string")
    return value


def _positive_int(value: Any, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise A1LifetimeActionScriptError(f"{context} must be a positive integer")
    return value


def validate_action_script(document: Any) -> dict[str, Any]:
    """Validate the predeclared bounded action sequence and return normalized metadata."""
    root = _object(document, "action script")
    if root.get("schema") != ACTION_SCRIPT_SCHEMA:
        raise A1LifetimeActionScriptError(
            f"action script schema must be {ACTION_SCRIPT_SCHEMA!r}"
        )

    bounds = _object(root.get("bounds"), "bounds")
    max_action_count = _positive_int(bounds.get("max_action_count"), "bounds.max_action_count")
    max_attempts = _positive_int(
        bounds.get("max_qualification_attempts_per_step"),
        "bounds.max_qualification_attempts_per_step",
    )
    per_step_timeout = _positive_int(
        bounds.get("per_step_timeout_seconds"), "bounds.per_step_timeout_seconds"
    )
    total_timeout = _positive_int(
        bounds.get("total_timeout_seconds"), "bounds.total_timeout_seconds"
    )
    if per_step_timeout > total_timeout:
        raise A1LifetimeActionScriptError(
            "bounds.per_step_timeout_seconds must not exceed bounds.total_timeout_seconds"
        )

    steps = root.get("steps")
    if not isinstance(steps, list) or not steps:
        raise A1LifetimeActionScriptError("steps must be a non-empty array")
    if len(steps) > max_action_count:
        raise A1LifetimeActionScriptError("steps exceed bounds.max_action_count")

    normalized: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for index, raw_step in enumerate(steps):
        step = _object(raw_step, f"steps[{index}]")
        step_id = _nonempty_string(step.get("id"), f"steps[{index}].id")
        if step_id in seen_ids:
            raise A1LifetimeActionScriptError(f"duplicate step id: {step_id}")
        seen_ids.add(step_id)

        action = _nonempty_string(step.get("action"), f"steps[{index}].action")
        if action == "qualify":
            label = _nonempty_string(
                step.get("logical_label"), f"steps[{index}].logical_label"
            )
            phase = _nonempty_string(step.get("phase"), f"steps[{index}].phase")
            if phase not in _ALLOWED_PHASES:
                raise A1LifetimeActionScriptError(
                    f"steps[{index}].phase must be one of {_ALLOWED_PHASES}"
                )
            if "mechanism" in step:
                raise A1LifetimeActionScriptError(
                    f"steps[{index}] qualify step must not declare mechanism"
                )
            normalized.append(
                {"id": step_id, "action": action, "logical_label": label, "phase": phase}
            )
        elif action == "replace":
            mechanism = _nonempty_string(
                step.get("mechanism"), f"steps[{index}].mechanism"
            )
            if mechanism not in _REQUIRED_REPLACEMENT_MECHANISMS:
                raise A1LifetimeActionScriptError(
                    f"steps[{index}].mechanism must be one of {_REQUIRED_REPLACEMENT_MECHANISMS}"
                )
            if "logical_label" in step or "phase" in step:
                raise A1LifetimeActionScriptError(
                    f"steps[{index}] replace step must not declare logical_label or phase"
                )
            normalized.append({"id": step_id, "action": action, "mechanism": mechanism})
        else:
            raise A1LifetimeActionScriptError(
                f"steps[{index}].action must be 'qualify' or 'replace'"
            )

    if len(normalized) < 9:
        raise A1LifetimeActionScriptError(
            "action script must contain A→B→A control plus both replacement legs"
        )

    control = normalized[:3]
    if any(step["action"] != "qualify" or step["phase"] != "selection-control" for step in control):
        raise A1LifetimeActionScriptError(
            "first three steps must be selection-control qualifications"
        )
    labels = [step["logical_label"] for step in control]
    if labels[0] != labels[2] or labels[0] == labels[1]:
        raise A1LifetimeActionScriptError(
            "selection control must use A→B→A logical labels with A != B"
        )

    cursor = 3
    observed_mechanisms: list[str] = []
    while cursor < len(normalized):
        if cursor + 2 >= len(normalized):
            raise A1LifetimeActionScriptError(
                "replacement leg must contain pre qualification, replacement, and post qualification"
            )
        pre, replace, post = normalized[cursor : cursor + 3]
        if (
            pre["action"] != "qualify"
            or pre["phase"] != "pre-replacement"
            or replace["action"] != "replace"
            or post["action"] != "qualify"
            or post["phase"] != "post-replacement"
        ):
            raise A1LifetimeActionScriptError(
                "replacement legs must be contiguous pre-replacement → replace → post-replacement triples"
            )
        observed_mechanisms.append(replace["mechanism"])
        cursor += 3

    if tuple(observed_mechanisms) != _REQUIRED_REPLACEMENT_MECHANISMS:
        raise A1LifetimeActionScriptError(
            "replacement legs must occur exactly once in order: "
            + " → ".join(_REQUIRED_REPLACEMENT_MECHANISMS)
        )

    return {
        "schema": ACTION_SCRIPT_SCHEMA,
        "step_count": len(normalized),
        "selection_control_labels": labels,
        "replacement_mechanisms": observed_mechanisms,
        "bounds": {
            "max_action_count": max_action_count,
            "max_qualification_attempts_per_step": max_attempts,
            "per_step_timeout_seconds": per_step_timeout,
            "total_timeout_seconds": total_timeout,
        },
    }
