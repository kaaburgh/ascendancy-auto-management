#!/usr/bin/env python3
"""Validate/classify detached A1 sidecar lifetime observations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "ascendancy.a1-sidecar-runtime-lifetime/v1"
OUTCOMES = {
    "positive-epoch-pointer",
    "positive-epoch-index",
    "positive-other",
    "negative-no-safe-seam",
    "incomplete-harness",
}
REQUIRED_TRANSITIONS = {"selection-control", "new-game-reset", "save-load-replacement"}
REPLACEMENT_TRANSITIONS = {"new-game-reset", "save-load-replacement"}
ACCEPTED_INVALIDATION_BASIS = {
    "positive-epoch-pointer": {"epoch", "reuse-detector", "epoch+reuse-detector"},
    "positive-epoch-index": {"epoch"},
    "positive-other": {"other"},
}
REUSE_EVENT_KIND = {
    "positive-epoch-pointer": "record-pointer-reuse",
    "positive-epoch-index": "index-reassignment",
    "positive-other": "other-identity-reuse",
}


class A1LifetimeError(ValueError):
    pass


def _require_bool(claims: dict[str, Any], key: str) -> bool:
    value = claims.get(key)
    if not isinstance(value, bool):
        raise A1LifetimeError(f"claim {key!r} must be boolean")
    return value


def _require_seq(value: Any, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise A1LifetimeError(f"{context} must be a non-negative integer")
    return value


def _require_nonempty_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise A1LifetimeError(f"{context} must be a non-empty string")
    return value


def _require_point(observations: dict[str, Any], name: str, label: str) -> dict[str, Any]:
    point = observations.get(name)
    if not isinstance(point, dict):
        raise A1LifetimeError(f"{label} requires observations.{name}")
    _require_seq(point.get("seq"), f"{label} observations.{name}.seq")
    pointer = point.get("record_pointer")
    if not isinstance(pointer, int) or isinstance(pointer, bool) or pointer < 0:
        raise A1LifetimeError(f"{label} observations.{name}.record_pointer must be a non-negative integer")
    return point


def _validate_signal(
    observations: dict[str, Any],
    name: str,
    label: str,
    pre_seq: int,
    reuse_event_seq: int,
) -> None:
    signal = observations.get(name)
    if not isinstance(signal, dict):
        raise A1LifetimeError(f"{label} requires observations.{name}")
    if "before" not in signal or "after" not in signal:
        raise A1LifetimeError(f"{label} observations.{name} requires before and after values")
    if signal["before"] == signal["after"]:
        raise A1LifetimeError(f"{label} observations.{name} did not change")
    signal_seq = _require_seq(signal.get("seq"), f"{label} observations.{name}.seq")
    if not (pre_seq < signal_seq < reuse_event_seq):
        raise A1LifetimeError(
            f"{label} observations.{name} must be observed after pre-state and before observed reuse event"
        )


def _validate_index_point(point: dict[str, Any], label: str, name: str) -> None:
    base = point.get("array_base")
    count = point.get("array_count")
    index = point.get("index")
    if not isinstance(base, int) or isinstance(base, bool) or base < 0:
        raise A1LifetimeError(f"{label} observations.{name}.array_base must be a non-negative integer")
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise A1LifetimeError(f"{label} observations.{name}.array_count must be a positive integer")
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < count:
        raise A1LifetimeError(f"{label} observations.{name}.index must be within observed array_count")


def _validate_reuse_event(
    observations: dict[str, Any],
    label: str,
    outcome: str,
    pre: dict[str, Any],
    post: dict[str, Any],
    pre_seq: int,
    post_seq: int,
) -> int:
    event = observations.get("reuse_event")
    if not isinstance(event, dict):
        raise A1LifetimeError(f"{label} requires observations.reuse_event")
    event_seq = _require_seq(event.get("seq"), f"{label} observations.reuse_event.seq")
    if not (pre_seq < event_seq <= post_seq):
        raise A1LifetimeError(
            f"{label} observations.reuse_event.seq must be after pre-state and no later than post-state"
        )
    expected_kind = REUSE_EVENT_KIND[outcome]
    if event.get("kind") != expected_kind:
        raise A1LifetimeError(
            f"{label} observations.reuse_event.kind must be {expected_kind!r} for {outcome}"
        )
    before_logical = _require_nonempty_string(
        event.get("before_logical_record"), f"{label} observations.reuse_event.before_logical_record"
    )
    after_logical = _require_nonempty_string(
        event.get("after_logical_record"), f"{label} observations.reuse_event.after_logical_record"
    )
    if before_logical == after_logical:
        raise A1LifetimeError(f"{label} observed reuse event must distinguish two logical records")

    if outcome == "positive-epoch-pointer":
        pointer = event.get("record_pointer")
        if not isinstance(pointer, int) or isinstance(pointer, bool) or pointer < 0:
            raise A1LifetimeError(
                f"{label} observations.reuse_event.record_pointer must be a non-negative integer"
            )
        if pointer != pre["record_pointer"] or pointer != post["record_pointer"]:
            raise A1LifetimeError(
                f"{label} observed pointer-reuse event must bind to both pre/post record_pointer values"
            )
    elif outcome == "positive-epoch-index":
        event_base = event.get("array_base")
        event_index = event.get("index")
        if event_base != pre.get("array_base") or event_base != post.get("array_base"):
            raise A1LifetimeError(f"{label} observed index-reuse event must bind to pre/post array_base")
        if event_index != pre.get("index") or event_index != post.get("index"):
            raise A1LifetimeError(f"{label} observed index-reuse event must bind to pre/post index")
    else:
        _require_nonempty_string(
            event.get("identity_subject"), f"{label} observations.reuse_event.identity_subject"
        )
    return event_seq


def _validate_replacement_observations(
    step: dict[str, Any],
    label: str,
    outcome: str,
) -> None:
    observations = step.get("observations")
    if not isinstance(observations, dict):
        raise A1LifetimeError(f"positive outcome requires bounded observations for {label}")

    pre = _require_point(observations, "pre", label)
    post = _require_point(observations, "post", label)
    pre_seq = _require_seq(pre["seq"], f"{label} observations.pre.seq")
    post_seq = _require_seq(post["seq"], f"{label} observations.post.seq")
    if pre_seq >= post_seq:
        raise A1LifetimeError(f"{label} observations must order pre before post")

    if outcome == "positive-epoch-index":
        _validate_index_point(pre, label, "pre")
        _validate_index_point(post, label, "post")

    reuse_event_seq = _validate_reuse_event(
        observations, label, outcome, pre, post, pre_seq, post_seq
    )

    basis = step.get("invalidation_basis")
    if basis == "epoch":
        _validate_signal(observations, "epoch_signal", label, pre_seq, reuse_event_seq)
    elif basis == "reuse-detector":
        _validate_signal(observations, "reuse_detector_signal", label, pre_seq, reuse_event_seq)
    elif basis == "epoch+reuse-detector":
        _validate_signal(observations, "epoch_signal", label, pre_seq, reuse_event_seq)
        _validate_signal(observations, "reuse_detector_signal", label, pre_seq, reuse_event_seq)
    elif basis == "other":
        _validate_signal(observations, "other_invalidation_signal", label, pre_seq, reuse_event_seq)


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("schema") != SCHEMA:
        raise A1LifetimeError("unsupported or missing schema")
    outcome = record.get("outcome")
    if outcome not in OUTCOMES:
        raise A1LifetimeError("unsupported or missing outcome")

    claims = record.get("claims")
    if not isinstance(claims, dict):
        raise A1LifetimeError("claims must be an object")
    array_base = _require_bool(claims, "array_base_established")
    array_count = _require_bool(claims, "array_count_established")
    stable_index = _require_bool(claims, "stable_index_established")
    reuse_detector = _require_bool(claims, "reuse_detector_established")
    epoch = _require_bool(claims, "epoch_boundary_established")
    manual = _require_bool(claims, "manual_transition_invalidation_established")
    if manual:
        raise A1LifetimeError("this experiment must not establish Manual-transition invalidation")
    if stable_index and not (array_base and array_count):
        raise A1LifetimeError("stable index requires independently established array base and count")

    control = record.get("control")
    if not isinstance(control, dict) or not isinstance(control.get("passed"), bool):
        raise A1LifetimeError("control.passed must be boolean")

    transitions = record.get("transitions")
    if not isinstance(transitions, list):
        raise A1LifetimeError("transitions must be a list")
    by_label: dict[str, dict[str, Any]] = {}
    for step in transitions:
        if not isinstance(step, dict):
            raise A1LifetimeError("transition entries must be objects")
        label = step.get("label")
        if not isinstance(label, str):
            raise A1LifetimeError("transition label must be a string")
        if label in by_label:
            raise A1LifetimeError(f"duplicate transition label {label!r}")
        by_label[label] = step
        if step.get("identity_basis") == "presentation-name":
            raise A1LifetimeError("presentation name cannot be promoted to identity")
        if step.get("index_basis") == "stride-only":
            raise A1LifetimeError("0x7b stride alone cannot establish a stable index")
        if step.get("replacement") is True and step.get("signal_order") == "post-hoc":
            raise A1LifetimeError("post-hoc replacement signal cannot establish lossless invalidation")

    coverage_complete = REQUIRED_TRANSITIONS.issubset(by_label)
    positive = outcome.startswith("positive-")
    if positive:
        if not control["passed"]:
            raise A1LifetimeError("positive outcome requires passed selection control")
        if not coverage_complete:
            raise A1LifetimeError("positive outcome requires all predeclared transitions")
        accepted_basis = ACCEPTED_INVALIDATION_BASIS[outcome]
        for label in REPLACEMENT_TRANSITIONS:
            step = by_label[label]
            if step.get("replacement") is not True:
                raise A1LifetimeError(
                    f"positive outcome requires observed replacement for {label}"
                )
            if step.get("invalidation_basis") not in accepted_basis:
                raise A1LifetimeError(
                    f"positive outcome has incompatible invalidation basis for {label}"
                )
            _validate_replacement_observations(step, label, outcome)
        if outcome == "positive-epoch-pointer" and not (epoch and reuse_detector):
            raise A1LifetimeError("epoch+pointer outcome requires epoch and reuse detector")
        if outcome == "positive-epoch-index" and not (epoch and stable_index and array_base and array_count):
            raise A1LifetimeError("epoch+index outcome requires epoch plus independently established index")
        if outcome == "positive-other":
            other = record.get("other_identity_contract")
            if not isinstance(other, dict) or not other.get("fails_closed_on_reuse"):
                raise A1LifetimeError("positive-other requires an explicit fail-closed reuse contract")

    return {
        "schema": SCHEMA,
        "outcome": outcome,
        "control_passed": control["passed"],
        "coverage_complete": coverage_complete,
        "positive_contract_accepted": positive,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("record", type=Path)
    ns = ap.parse_args()
    try:
        data = json.loads(ns.record.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise A1LifetimeError("record root must be an object")
        result = validate_record(data)
    except (OSError, json.JSONDecodeError, A1LifetimeError) as exc:
        ap.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
