#!/usr/bin/env python3
"""Build and validate detached A1 scenario-qualification manifests."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

INPUT_SCHEMA = "ascendancy.a1-sidecar-scenario-qualification-input/v2"
OUTPUT_SCHEMA = "ascendancy.a1-sidecar-scenario-qualification/v2"
LEGACY_INPUT_SCHEMA = "ascendancy.a1-sidecar-scenario-qualification-input/v1"
LEGACY_OUTPUT_SCHEMA = "ascendancy.a1-sidecar-scenario-qualification/v1"
EXPECTED_SOURCE_SCHEMA = "ascendancy.a1-sidecar-expected-source/v1"
MAX_METADATA_BYTES = 512
PLANET_RECORD_SIZE = 0x7B
PRESENTATION_NAME_OFFSET = 0x24
PRESENTATION_NAME_LENGTH = 32
ALLOWED_METADATA_BASES = frozenset({"bounded-record-metadata"})


class A1ScenarioQualificationError(ValueError):
    pass


def _require_nonempty_string(value: Any, context: str, *, exact: bool = False) -> str:
    if not isinstance(value, str):
        raise A1ScenarioQualificationError(f"{context} must be a non-empty string")
    if exact:
        if value == "":
            raise A1ScenarioQualificationError(f"{context} must be a non-empty string")
    elif not value.strip():
        raise A1ScenarioQualificationError(f"{context} must be a non-empty string")
    return value


def _require_nonnegative_int(value: Any, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise A1ScenarioQualificationError(f"{context} must be a non-negative integer")
    return value


def _require_sha256(value: Any, context: str) -> str:
    text = _require_nonempty_string(value, context)
    if len(text) != 64:
        raise A1ScenarioQualificationError(f"{context} must be a 64-hex SHA-256 digest")
    try:
        int(text, 16)
    except ValueError as exc:
        raise A1ScenarioQualificationError(f"{context} must be a 64-hex SHA-256 digest") from exc
    return text.lower()


def _require_hex_bytes(value: Any, context: str) -> bytes:
    text = _require_nonempty_string(value, context)
    if len(text) % 2:
        raise A1ScenarioQualificationError(f"{context} must be even-length hex")
    try:
        raw = bytes.fromhex(text)
    except ValueError as exc:
        raise A1ScenarioQualificationError(f"{context} must be hex") from exc
    if not raw:
        raise A1ScenarioQualificationError(f"{context} must not be empty")
    if len(raw) > MAX_METADATA_BYTES:
        raise A1ScenarioQualificationError(f"{context} exceeds {MAX_METADATA_BYTES} byte bound")
    return raw


def _reject_presentation_name_overlap(offset: int, length: int, context: str) -> None:
    """Reject a witness range by its geometry, not by the basis label it declares."""
    name_end = PRESENTATION_NAME_OFFSET + PRESENTATION_NAME_LENGTH
    if offset < name_end and offset + length > PRESENTATION_NAME_OFFSET:
        raise A1ScenarioQualificationError(
            f"{context} metadata range 0x{offset:x}..0x{offset + length:x} overlaps the established "
            f"presentation-name window 0x{PRESENTATION_NAME_OFFSET:x}..0x{name_end:x}; "
            "presentation name cannot establish record identity"
        )


def _load_json_bytes(raw: bytes, context: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise A1ScenarioQualificationError(f"{context} must be UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise A1ScenarioQualificationError(f"{context} must be a JSON object")
    return value


def _validated_expected_source(expected: dict[str, Any]) -> dict[str, str]:
    if expected.get("schema") != EXPECTED_SOURCE_SCHEMA:
        raise A1ScenarioQualificationError("unsupported or missing expected source schema")
    return {
        "target_sha256": _require_sha256(expected.get("target_sha256"), "expected source target_sha256"),
        "retail_manifest_identity": _require_nonempty_string(
            expected.get("retail_manifest_identity"), "expected source retail_manifest_identity"
        ),
        "scenario_identity": _require_nonempty_string(
            expected.get("scenario_identity"), "expected source scenario_identity"
        ),
        "qualification_source_sha256": _require_sha256(
            expected.get("qualification_source_sha256"), "expected source qualification_source_sha256"
        ),
    }


def _validated_input(
    raw: bytes, expected: dict[str, Any]
) -> tuple[dict[str, str], dict[str, str], dict[str, dict[str, Any]] | None]:
    document = _load_json_bytes(raw, "qualification input")
    input_schema = document.get("schema")
    if input_schema not in {INPUT_SCHEMA, LEGACY_INPUT_SCHEMA}:
        raise A1ScenarioQualificationError("unsupported or missing qualification input schema")

    trusted = _validated_expected_source(expected)
    observed_source_sha256 = hashlib.sha256(raw).hexdigest()
    if observed_source_sha256 != trusted["qualification_source_sha256"]:
        raise A1ScenarioQualificationError(
            "qualification input bytes do not match expected source qualification_source_sha256"
        )

    source = document.get("source")
    if not isinstance(source, dict):
        raise A1ScenarioQualificationError("qualification input requires source object")
    input_source = {
        "target_sha256": _require_sha256(source.get("target_sha256"), "qualification input target_sha256"),
        "retail_manifest_identity": _require_nonempty_string(
            source.get("retail_manifest_identity"), "qualification input retail_manifest_identity"
        ),
        "scenario_identity": _require_nonempty_string(
            source.get("scenario_identity"), "qualification input scenario_identity"
        ),
    }
    for field in ("target_sha256", "retail_manifest_identity", "scenario_identity"):
        if input_source[field] != trusted[field]:
            raise A1ScenarioQualificationError(
                f"qualification input {field} must bind to independently supplied expected source"
            )

    planets = document.get("planets")
    if not isinstance(planets, list) or not planets:
        raise A1ScenarioQualificationError("qualification input requires non-empty planets list")

    digests: dict[str, str] = {}
    witness_ranges: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(planets):
        context = f"qualification input planets[{index}]"
        if not isinstance(entry, dict):
            raise A1ScenarioQualificationError(f"{context} must be an object")
        label = _require_nonempty_string(entry.get("logical_label"), f"{context}.logical_label", exact=True)
        if label in digests:
            raise A1ScenarioQualificationError(f"duplicate logical label {label!r}")
        basis = _require_nonempty_string(entry.get("metadata_basis"), f"{context}.metadata_basis")
        if basis not in ALLOWED_METADATA_BASES:
            raise A1ScenarioQualificationError(
                f"{context}.metadata_basis must be one of {sorted(ALLOWED_METADATA_BASES)!r}; "
                "presentation-name-only qualification is not allowed"
            )
        metadata = _require_hex_bytes(entry.get("metadata_hex"), f"{context}.metadata_hex")
        digest = hashlib.sha256(metadata).hexdigest()
        digests[label] = digest
        if input_schema == INPUT_SCHEMA:
            record_offset = _require_nonnegative_int(entry.get("record_offset"), f"{context}.record_offset")
            if record_offset + len(metadata) > PLANET_RECORD_SIZE:
                raise A1ScenarioQualificationError(
                    f"{context} metadata range must fit within the established 0x{PLANET_RECORD_SIZE:x}-byte planet record"
                )
            _reject_presentation_name_overlap(record_offset, len(metadata), context)
            rationale = _require_nonempty_string(entry.get("metadata_rationale"), f"{context}.metadata_rationale")
            witness_ranges[label] = {
                "metadata_basis": basis,
                "record_offset": record_offset,
                "length": len(metadata),
                "sha256": digest,
                "rationale": rationale,
            }

    source_out = {**input_source, "qualification_source_sha256": observed_source_sha256}
    return source_out, digests, witness_ranges if input_schema == INPUT_SCHEMA else None


def build_manifest(raw: bytes, expected: dict[str, Any]) -> dict[str, Any]:
    source, planets, witness_ranges = _validated_input(raw, expected)
    if witness_ranges is None:
        return {"schema": LEGACY_OUTPUT_SCHEMA, "source": source, "planets": planets}
    return {
        "schema": OUTPUT_SCHEMA,
        "source": source,
        "planets": planets,
        "witness_ranges": witness_ranges,
    }


def validate_manifest(raw: bytes, expected: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    generated = build_manifest(raw, expected)
    if manifest.get("schema") != generated["schema"]:
        raise A1ScenarioQualificationError("unsupported or missing scenario qualification schema")
    if manifest != generated:
        raise A1ScenarioQualificationError(
            "scenario qualification manifest does not match supplied bounded metadata/source bytes"
        )
    return generated


def _read_json(path: Path, context: str) -> dict[str, Any]:
    return _load_json_bytes(path.read_bytes(), context)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    produce = sub.add_parser("produce", help="build a qualification manifest from bounded input")
    produce.add_argument("--input", type=Path, required=True)
    produce.add_argument("--expected-source", type=Path, required=True)
    produce.add_argument("--output", type=Path, required=True)

    validate = sub.add_parser("validate", help="validate a manifest against exact bounded input")
    validate.add_argument("--input", type=Path, required=True)
    validate.add_argument("--expected-source", type=Path, required=True)
    validate.add_argument("--manifest", type=Path, required=True)

    args = parser.parse_args()
    try:
        raw = args.input.read_bytes()
        expected = _read_json(args.expected_source, "expected source")
        if args.command == "produce":
            _write_json(args.output, build_manifest(raw, expected))
        else:
            manifest = _read_json(args.manifest, "scenario qualification manifest")
            validate_manifest(raw, expected, manifest)
    except (OSError, A1ScenarioQualificationError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
