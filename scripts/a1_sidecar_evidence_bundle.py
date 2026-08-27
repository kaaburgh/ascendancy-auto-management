#!/usr/bin/env python3
"""Build the qualified A1 scenario manifest and validate one lifetime run record."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterator

try:
    from .a1_scenario_qualification import A1ScenarioQualificationError, build_manifest
    from .a1_selection_control_oracle import A1SelectionControlError, validate_selection_control
    from .a1_sidecar_lifetime_oracle import A1LifetimeError, SCENARIO_SCHEMA, validate_record
    from .a1_v2_witness_binding import A1V2WitnessBindingError, validate_qualified_witness
except ImportError:
    from a1_scenario_qualification import A1ScenarioQualificationError, build_manifest
    from a1_selection_control_oracle import A1SelectionControlError, validate_selection_control
    from a1_sidecar_lifetime_oracle import A1LifetimeError, SCENARIO_SCHEMA, validate_record
    from a1_v2_witness_binding import A1V2WitnessBindingError, validate_qualified_witness


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
    """Project qualification v2 onto the legacy lifetime-oracle v1 input contract."""
    return {
        "schema": SCENARIO_SCHEMA,
        "source": scenario_manifest["source"],
        "planets": scenario_manifest["planets"],
    }


def _qualified_witnesses(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        witness = value.get("qualified_witness")
        if isinstance(witness, dict):
            yield witness
        for child in value.values():
            yield from _qualified_witnesses(child)
    elif isinstance(value, list):
        for child in value:
            yield from _qualified_witnesses(child)


def _validate_v2_witness_range_binding(record: dict[str, Any], scenario_manifest: dict[str, Any]) -> None:
    """Fail closed when a positive record is not bound to the v2 predeclared witness ranges."""
    witness_ranges = scenario_manifest.get("witness_ranges")
    planets = scenario_manifest.get("planets")
    if not isinstance(witness_ranges, dict) or not str(record.get("outcome", "")).startswith("positive-"):
        return
    if not isinstance(planets, dict) or not planets:
        raise A1ScenarioQualificationError("scenario qualification v2 manifest requires planets")

    witnesses = list(_qualified_witnesses(record))
    if not witnesses:
        raise A1ScenarioQualificationError("positive v2 lifetime record requires qualified witnesses")

    for witness in witnesses:
        label = witness.get("scenario_planet")
        if not isinstance(label, str) or label not in witness_ranges:
            raise A1ScenarioQualificationError("qualified witness scenario_planet is not present in v2 witness_ranges")
        try:
            validate_qualified_witness(
                witness,
                label,
                planets,
                witness_ranges,
                context=f"qualified witness {label!r}",
            )
        except A1V2WitnessBindingError as exc:
            raise A1ScenarioQualificationError(str(exc)) from exc


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
    _validate_v2_witness_range_binding(record, scenario_manifest)
    result = validate_record(record, scenario_manifest, expected_source)
    validate_selection_control(record, scenario_manifest)
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
