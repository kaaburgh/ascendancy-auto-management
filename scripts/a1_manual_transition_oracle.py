#!/usr/bin/env python3
"""Validate detached evidence for lossless A1 Manual-transition invalidation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "ascendancy.a1-manual-transition-invalidation/v1"
EXPECTED_COVERAGE_SCHEMA = "ascendancy.a1-manual-transition-expected-coverage/v1"
COVERAGE_EVIDENCE_SCHEMA = "ascendancy.a1-manual-transition-coverage-evidence/v1"
CANONICAL_TARGET = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
OUTCOMES = {"positive-lossless-invalidation", "negative-missed-transition", "incomplete-harness"}
COVERAGE_BASES = {"all-relevant-zero-write-paths", "equivalent-lossless-boundary"}


class A1ManualInvalidationError(ValueError):
    pass


def _seq(value: Any, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise A1ManualInvalidationError(f"{context} must be a non-negative integer")
    return value


def _nonempty(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise A1ManualInvalidationError(f"{context} must be a non-empty string")
    return value


def _sha256(value: Any, context: str) -> str:
    text = _nonempty(value, context).lower()
    if len(text) != 64:
        raise A1ManualInvalidationError(f"{context} must be a 64-hex SHA-256 digest")
    try:
        int(text, 16)
    except ValueError as exc:
        raise A1ManualInvalidationError(f"{context} must be a 64-hex SHA-256 digest") from exc
    return text


def _canonical_json_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_expected_coverage(
    record: dict[str, Any],
    expected: dict[str, Any] | None,
    evidence: dict[str, Any] | None,
) -> tuple[str, str]:
    if not isinstance(expected, dict):
        raise A1ManualInvalidationError(
            "positive outcome requires independently supplied expected coverage provenance"
        )
    if expected.get("schema") != EXPECTED_COVERAGE_SCHEMA:
        raise A1ManualInvalidationError("unsupported or missing expected coverage schema")
    if not isinstance(evidence, dict):
        raise A1ManualInvalidationError(
            "positive outcome requires independently supplied coverage evidence manifest"
        )
    if evidence.get("schema") != COVERAGE_EVIDENCE_SCHEMA:
        raise A1ManualInvalidationError("unsupported or missing coverage evidence schema")

    evidence_digest = _canonical_json_sha256(evidence)
    trusted_digest = _sha256(
        expected.get("coverage_evidence_sha256"),
        "expected coverage coverage_evidence_sha256",
    )
    if evidence_digest != trusted_digest:
        raise A1ManualInvalidationError(
            "coverage evidence manifest must match independently supplied expected digest"
        )

    inputs = record["inputs"]
    for field in ("target_sha256", "harness_sha256"):
        trusted = _sha256(expected.get(field), f"expected coverage {field}")
        observed = _sha256(inputs.get(field), f"inputs.{field}")
        manifest = _sha256(evidence.get(field), f"coverage evidence {field}")
        if observed != trusted:
            raise A1ManualInvalidationError(
                f"inputs.{field} must bind to independently supplied expected coverage"
            )
        if manifest != trusted:
            raise A1ManualInvalidationError(
                f"coverage evidence {field} must bind to independently supplied expected coverage"
            )

    trusted_scenario = _nonempty(expected.get("scenario_identity"), "expected coverage scenario_identity")
    observed_scenario = _nonempty(inputs.get("scenario_identity"), "inputs.scenario_identity")
    manifest_scenario = _nonempty(evidence.get("scenario_identity"), "coverage evidence scenario_identity")
    if observed_scenario != trusted_scenario:
        raise A1ManualInvalidationError(
            "inputs.scenario_identity must bind to independently supplied expected coverage"
        )
    if manifest_scenario != trusted_scenario:
        raise A1ManualInvalidationError(
            "coverage evidence scenario_identity must bind to independently supplied expected coverage"
        )

    basis = expected.get("coverage_basis")
    if basis not in COVERAGE_BASES:
        raise A1ManualInvalidationError("expected coverage coverage_basis is unsupported")
    if evidence.get("coverage_basis") != basis:
        raise A1ManualInvalidationError(
            "coverage evidence coverage_basis must match independently supplied expected coverage"
        )

    mechanism = _nonempty(
        evidence.get("write_source_mechanism"),
        "coverage evidence write_source_mechanism",
    )
    _sha256(
        evidence.get("qualification_artifact_sha256"),
        "coverage evidence qualification_artifact_sha256",
    )
    _nonempty(evidence.get("qualification_method"), "coverage evidence qualification_method")

    if basis == "all-relevant-zero-write-paths":
        if evidence.get("all_relevant_zero_write_paths_established") is not True:
            raise A1ManualInvalidationError(
                "coverage evidence must establish all relevant zero-write paths"
            )
        if evidence.get("equivalent_lossless_boundary_established") is not False:
            raise A1ManualInvalidationError(
                "all-relevant-zero-write-path evidence must not also claim equivalent lossless boundary"
            )
    else:
        if evidence.get("equivalent_lossless_boundary_established") is not True:
            raise A1ManualInvalidationError(
                "coverage evidence must establish an equivalent lossless boundary"
            )
        if evidence.get("all_relevant_zero_write_paths_established") is not False:
            raise A1ManualInvalidationError(
                "equivalent-lossless-boundary evidence must not also claim all relevant zero-write paths"
            )

    if evidence.get("periodic_sampling_only") is not False:
        raise A1ManualInvalidationError(
            "coverage evidence based only on periodic sampling cannot establish losslessness"
        )
    return basis, mechanism


def validate_record(
    record: dict[str, Any],
    expected_coverage: dict[str, Any] | None = None,
    coverage_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if record.get("schema") != SCHEMA:
        raise A1ManualInvalidationError("unsupported or missing schema")

    outcome = record.get("outcome")
    if outcome not in OUTCOMES:
        raise A1ManualInvalidationError("unsupported outcome")

    inputs = record.get("inputs")
    if not isinstance(inputs, dict):
        raise A1ManualInvalidationError("inputs must be an object")
    if _sha256(inputs.get("target_sha256"), "inputs.target_sha256") != CANONICAL_TARGET:
        raise A1ManualInvalidationError("record is not bound to the canonical target")
    _sha256(inputs.get("harness_sha256"), "inputs.harness_sha256")
    _nonempty(inputs.get("scenario_identity"), "inputs.scenario_identity")

    claims = record.get("claims")
    if not isinstance(claims, dict):
        raise A1ManualInvalidationError("claims must be an object")
    established = claims.get("manual_transition_invalidation_established")
    if not isinstance(established, bool):
        raise A1ManualInvalidationError("claims.manual_transition_invalidation_established must be boolean")

    transitions = record.get("transitions")
    if not isinstance(transitions, list):
        raise A1ManualInvalidationError("transitions must be an array")

    if outcome != "positive-lossless-invalidation":
        if established:
            raise A1ManualInvalidationError("non-positive outcome cannot establish Manual-transition invalidation")
        return {"outcome": outcome, "manual_transition_invalidation_established": False}

    coverage_basis, expected_mechanism = _validate_expected_coverage(
        record, expected_coverage, coverage_evidence
    )
    if not established:
        raise A1ManualInvalidationError("positive outcome requires established Manual-transition invalidation claim")
    if not transitions:
        raise A1ManualInvalidationError("positive outcome requires at least one observed Manual round trip")

    for index, transition in enumerate(transitions):
        label = f"transitions[{index}]"
        if not isinstance(transition, dict):
            raise A1ManualInvalidationError(f"{label} must be an object")
        if transition.get("kind") != "managed-manual-managed":
            raise A1ManualInvalidationError(f"{label}.kind must be 'managed-manual-managed'")
        managed_before = _seq(transition.get("managed_before_seq"), f"{label}.managed_before_seq")
        manual_write = _seq(transition.get("manual_write_seq"), f"{label}.manual_write_seq")
        invalidation = _seq(transition.get("invalidation_seq"), f"{label}.invalidation_seq")
        managed_after = _seq(transition.get("managed_after_seq"), f"{label}.managed_after_seq")
        if not (managed_before < manual_write <= invalidation < managed_after):
            raise A1ManualInvalidationError(
                f"{label} must order Managed -> Manual write -> invalidation -> Managed"
            )
        if transition.get("manual_value") != 0:
            raise A1ManualInvalidationError(f"{label}.manual_value must be 0")
        if transition.get("managed_before_value") != 0xFFFFFFFF or transition.get("managed_after_value") != 0xFFFFFFFF:
            raise A1ManualInvalidationError(f"{label} Managed values must be 0xffffffff")
        source = transition.get("write_source")
        if not isinstance(source, dict):
            raise A1ManualInvalidationError(f"{label}.write_source must be an object")
        mechanism = _nonempty(source.get("mechanism"), f"{label}.write_source.mechanism")
        if mechanism != expected_mechanism:
            raise A1ManualInvalidationError(
                f"{label}.write_source.mechanism must match qualified coverage evidence"
            )
        if source.get("lossless") is not True:
            raise A1ManualInvalidationError(f"{label}.write_source.lossless must be true")
        if transition.get("stale_profile_visible_after_manual") is not False:
            raise A1ManualInvalidationError(f"{label} must prove stale profile is not visible after Manual invalidation")

    coverage = record.get("coverage")
    if not isinstance(coverage, dict):
        raise A1ManualInvalidationError("positive outcome requires coverage object")
    if coverage.get("periodic_sampling_only") is not False:
        raise A1ManualInvalidationError("periodic sampling cannot establish a lossless Manual-transition boundary")
    if coverage_basis == "all-relevant-zero-write-paths":
        if coverage.get("all_relevant_zero_write_paths_established") is not True:
            raise A1ManualInvalidationError(
                "record must match independently supplied all-relevant-zero-write-path coverage"
            )
    elif coverage.get("equivalent_lossless_boundary_established") is not True:
        raise A1ManualInvalidationError(
            "record must match independently supplied equivalent-lossless-boundary coverage"
        )

    return {
        "outcome": outcome,
        "manual_transition_invalidation_established": True,
        "validated_round_trips": len(transitions),
        "coverage_basis": coverage_basis,
        "coverage_evidence_sha256": _canonical_json_sha256(coverage_evidence),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("--expected-coverage", type=Path)
    parser.add_argument("--coverage-evidence", type=Path)
    args = parser.parse_args()
    try:
        value = json.loads(args.record.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise A1ManualInvalidationError("record root must be an object")
        expected = None
        if args.expected_coverage is not None:
            expected = json.loads(args.expected_coverage.read_text(encoding="utf-8"))
            if not isinstance(expected, dict):
                raise A1ManualInvalidationError("expected coverage root must be an object")
        evidence = None
        if args.coverage_evidence is not None:
            evidence = json.loads(args.coverage_evidence.read_text(encoding="utf-8"))
            if not isinstance(evidence, dict):
                raise A1ManualInvalidationError("coverage evidence root must be an object")
        result = validate_record(value, expected, evidence)
    except (OSError, json.JSONDecodeError, A1ManualInvalidationError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
