#!/usr/bin/env python3
"""Build the qualified A1 scenario manifest and validate one lifetime run record."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .a1_scenario_qualification import A1ScenarioQualificationError, build_manifest
    from .a1_selection_control_oracle import A1SelectionControlError, validate_selection_control
    from .a1_sidecar_lifetime_oracle import A1LifetimeError, SCENARIO_SCHEMA, validate_record
except ImportError:
    from a1_scenario_qualification import A1ScenarioQualificationError, build_manifest
    from a1_selection_control_oracle import A1SelectionControlError, validate_selection_control
    from a1_sidecar_lifetime_oracle import A1LifetimeError, SCENARIO_SCHEMA, validate_record


def _read_json_object(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} root must be an object")
    return value


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _oracle_manifest(scenario_manifest: dict) -> dict:
    """Project qualification v2 onto the unchanged lifetime-oracle v1 input contract."""
    return {
        "schema": SCENARIO_SCHEMA,
        "source": scenario_manifest["source"],
        "planets": scenario_manifest["planets"],
    }


def validate_bundle(
    qualification_input: Path,
    expected_source_path: Path,
    record_path: Path,
    manifest_output: Path | None = None,
) -> dict:
    expected_source = _read_json_object(expected_source_path, "expected source")
    record = _read_json_object(record_path, "lifetime record")
    try:
        raw = qualification_input.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read qualification input: {exc}") from exc

    scenario_manifest = build_manifest(raw, expected_source)
    oracle_manifest = _oracle_manifest(scenario_manifest)
    result = validate_record(record, oracle_manifest, expected_source)
    validate_selection_control(record, oracle_manifest)
    if manifest_output is not None:
        _write_json(manifest_output, scenario_manifest)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-input", type=Path, required=True)
    parser.add_argument("--expected-source", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path)
    args = parser.parse_args()

    try:
        result = validate_bundle(
            args.qualification_input,
            args.expected_source,
            args.record,
            args.manifest_output,
        )
    except (ValueError, A1ScenarioQualificationError, A1SelectionControlError, A1LifetimeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
