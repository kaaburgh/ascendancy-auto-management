#!/usr/bin/env python3
"""Run the bounded A1 sidecar lifetime selection-control leg."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import a1_scenario_qualification as qualification  # noqa: E402
import a1_sidecar_lifetime_oracle as lifetime  # noqa: E402
import run_re4_runtime_state as re4  # noqa: E402
import run_t3_multi_planet_fixture as t3  # noqa: E402

ARTIFACT_SCHEMA = lifetime.SCHEMA
CONTROL_CONTRACT = "a1/sidecar-selection-control/v1"
WITNESS_OFFSET = 0
WITNESS_SIZE = 0x52
ROW_A = 0
ROW_B = 1
ACTION_SCRIPT = (
    ("select", ROW_A),
    ("identify-toggle-restore", ROW_A),
    ("select", ROW_B),
    ("identify-toggle-restore", ROW_B),
    ("select", ROW_A),
    ("identify-toggle-restore", ROW_A),
)


class A1SelectionControlError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise A1SelectionControlError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise A1SelectionControlError(f"{label} must be a JSON object")
    return value


def validate_qualification_inputs(
    qualification_input: Path,
    expected_source_path: Path,
    scenario_manifest_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    raw = qualification_input.read_bytes()
    expected = load_json_object(expected_source_path, "expected source")
    manifest = load_json_object(scenario_manifest_path, "scenario qualification manifest")
    try:
        qualification.validate_manifest(raw, expected, manifest)
    except qualification.A1ScenarioQualificationError as exc:
        raise A1SelectionControlError(f"scenario qualification rejected: {exc}") from exc
    return expected, manifest, raw


def _qualified_witness(
    snapshot: bytes,
    base: int,
    logical_label: str,
    expected_digests: dict[str, str],
) -> dict[str, Any]:
    end = base + WITNESS_OFFSET + WITNESS_SIZE
    if base < 0 or end > len(snapshot):
        raise A1SelectionControlError("selected record witness range is outside runtime snapshot")
    metadata = snapshot[base + WITNESS_OFFSET:end]
    digest = sha256_bytes(metadata)
    expected = expected_digests.get(logical_label)
    if expected is None:
        raise A1SelectionControlError(
            f"logical label {logical_label!r} is absent from scenario qualification manifest"
        )
    if digest != expected:
        raise A1SelectionControlError(
            f"runtime metadata for {logical_label!r} does not match independent qualification"
        )
    return {
        "scenario_planet": logical_label,
        "metadata_basis": "bounded-record-metadata",
        "metadata_offset": WITNESS_OFFSET,
        "metadata_size": WITNESS_SIZE,
        "metadata_hex": metadata.hex(),
        "metadata_sha256": digest,
    }


def evaluate_selection_control(points: list[dict[str, Any]]) -> dict[str, Any]:
    if len(points) != 3:
        raise A1SelectionControlError("selection control requires exactly A, B, A observations")
    first_a, b, second_a = points
    if first_a.get("logical_record") != second_a.get("logical_record"):
        raise A1SelectionControlError("selection control did not return to the first logical record")
    if first_a.get("logical_record") == b.get("logical_record"):
        raise A1SelectionControlError("selection control requires two distinct logical records")
    if first_a.get("record_pointer") != second_a.get("record_pointer"):
        raise A1SelectionControlError("first logical record pointer changed within unchanged population")
    if first_a.get("record_pointer") == b.get("record_pointer"):
        raise A1SelectionControlError("two logical records resolved to the same record pointer")
    first_digest = first_a.get("qualified_witness", {}).get("metadata_sha256")
    second_digest = second_a.get("qualified_witness", {}).get("metadata_sha256")
    b_digest = b.get("qualified_witness", {}).get("metadata_sha256")
    if not all(isinstance(value, str) and value for value in (first_digest, second_digest, b_digest)):
        raise A1SelectionControlError("selection control requires qualified witness digests")
    if first_digest != second_digest:
        raise A1SelectionControlError("first logical record witness changed within unchanged population")
    if first_digest == b_digest:
        raise A1SelectionControlError("independent qualification does not distinguish the two control records")
    return {
        "passed": True,
        "sequence": [first_a["logical_record"], b["logical_record"], second_a["logical_record"]],
        "same_first_record_pointer_on_return": True,
        "distinct_control_record_pointers": True,
        "same_first_record_witness_on_return": True,
        "distinct_control_record_witnesses": True,
        "population_replacement_observed": False,
    }


def _observe_selected_record(
    *,
    process: subprocess.Popen[Any],
    inp: re4.XInput,
    anchor: dict[str, Any],
    row: int,
    logical_label: str,
    expected_digests: dict[str, str],
    seq: int,
) -> dict[str, Any]:
    re4.select_planet_list_row(inp, row)
    time.sleep(0.35)
    before = re4.snapshot_anchor_map(process.pid, anchor)
    inp.key("m")
    time.sleep(0.08)
    managed = re4.snapshot_anchor_map(process.pid, anchor)
    inp.key("m")
    time.sleep(0.08)
    restored = re4.snapshot_anchor_map(process.pid, anchor)
    record = re4.find_transition_record(before, managed, restored)
    base = int(record["record_offset_in_snapshot"])
    field_host = anchor["map_start"] + int(record["field_offset_in_snapshot"])
    if re4.read_process(process.pid, field_host, 4) != re4.MANUAL:
        raise A1SelectionControlError("selected record was not restored to Manual after identification")
    return {
        "seq": seq,
        "record_pointer": anchor["map_start"] + base,
        "logical_record": logical_label,
        "presentation_name": record["planet_name"],
        "compatibility_mirror_0x5a": record["restored"],
        "qualified_witness": _qualified_witness(before, base, logical_label, expected_digests),
    }


def _checkout_sha() -> str:
    candidate = os.environ.get("GITHUB_SHA", "").strip().lower()
    if not candidate:
        cp = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if cp.returncode == 0:
            candidate = cp.stdout.strip().lower()
    if len(candidate) != 40:
        raise A1SelectionControlError("cannot establish 40-hex repository checkout SHA")
    try:
        int(candidate, 16)
    except ValueError as exc:
        raise A1SelectionControlError("repository checkout SHA is not hexadecimal") from exc
    return candidate


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = args.game_dir.expanduser().resolve()
    if not root.is_dir():
        raise A1SelectionControlError("game-dir must exist")
    candidate_path = args.candidate_save.expanduser().resolve()
    if not candidate_path.is_file():
        raise A1SelectionControlError("candidate-save must exist")
    fixture_manifest = args.fixture_manifest.expanduser().resolve()
    if not fixture_manifest.is_file():
        raise A1SelectionControlError("fixture-manifest must exist")
    candidate = candidate_path.read_bytes()
    expected_candidate_hash = args.candidate_sha256.lower()
    if sha256_bytes(candidate) != expected_candidate_hash:
        raise A1SelectionControlError("candidate-save identity mismatch")

    expected_source, scenario_manifest, qualification_raw = validate_qualification_inputs(
        args.qualification_input.expanduser().resolve(),
        args.expected_source.expanduser().resolve(),
        args.scenario_manifest.expanduser().resolve(),
    )
    expected_digests = scenario_manifest.get("planets")
    if not isinstance(expected_digests, dict):
        raise A1SelectionControlError("scenario qualification manifest requires planets map")
    qualification_document = json.loads(qualification_raw.decode("utf-8"))
    entries = qualification_document.get("planets") if isinstance(qualification_document, dict) else None
    if not isinstance(entries, list):
        raise A1SelectionControlError("qualification input requires planets list")
    by_label = {entry.get("logical_label"): entry for entry in entries if isinstance(entry, dict)}
    if args.planet_a_label == args.planet_b_label:
        raise A1SelectionControlError("control labels must be distinct")
    for label in (args.planet_a_label, args.planet_b_label):
        if label not in expected_digests:
            raise A1SelectionControlError(f"control label {label!r} is not independently qualified")
        entry = by_label.get(label)
        if not isinstance(entry, dict):
            raise A1SelectionControlError(f"control label {label!r} is absent from qualification input")
        if entry.get("metadata_basis") != "bounded-record-metadata":
            raise A1SelectionControlError(f"control label {label!r} has unsupported metadata basis")
        try:
            metadata = bytes.fromhex(str(entry.get("metadata_hex", "")))
        except ValueError as exc:
            raise A1SelectionControlError(f"control label {label!r} metadata is not hex") from exc
        if len(metadata) != WITNESS_SIZE:
            raise A1SelectionControlError(
                f"control label {label!r} qualification metadata must be exactly {WITNESS_SIZE} bytes"
            )

    fixture = re4.verify_fixture(root, fixture_manifest)
    dosbox = t3.resolve_executable(args.dosbox)
    for tool in ("Xvfb", "xwininfo"):
        t3.resolve_executable(tool)

    temp, mount, xvfb, process, inp = t3._launch(root, dosbox, candidate)
    try:
        target = re4._casefold_file_map(mount)["antag.exe"]
        anchor = re4.find_unique_runtime_anchor(process.pid)
        import run_re5_override_witness as override_witness
        override_witness.validate_mapping(process.pid, anchor, target)
        re4.scenario_steps(inp, "resume")
        time.sleep(0.8)
        points = [
            _observe_selected_record(
                process=process,
                inp=inp,
                anchor=anchor,
                row=ROW_A,
                logical_label=args.planet_a_label,
                expected_digests=expected_digests,
                seq=1,
            ),
            _observe_selected_record(
                process=process,
                inp=inp,
                anchor=anchor,
                row=ROW_B,
                logical_label=args.planet_b_label,
                expected_digests=expected_digests,
                seq=2,
            ),
            _observe_selected_record(
                process=process,
                inp=inp,
                anchor=anchor,
                row=ROW_A,
                logical_label=args.planet_a_label,
                expected_digests=expected_digests,
                seq=3,
            ),
        ]
        control = evaluate_selection_control(points)
    finally:
        t3._teardown(temp, xvfb, process, inp)

    if candidate_path.read_bytes() != candidate:
        raise A1SelectionControlError("source candidate changed during runtime experiment")

    source = scenario_manifest["source"]
    action_digest = sha256_bytes(json.dumps(ACTION_SCRIPT, separators=(",", ":")).encode("ascii"))
    record = {
        "schema": ARTIFACT_SCHEMA,
        "outcome": "incomplete-harness",
        "claims": {
            "array_base_established": False,
            "array_count_established": False,
            "stable_index_established": False,
            "reuse_detector_established": False,
            "epoch_boundary_established": False,
            "manual_transition_invalidation_established": False,
        },
        "control": control,
        "transitions": [
            {
                "label": "selection-control",
                "replacement": False,
                "identity_basis": "independently-qualified-bounded-record-metadata",
                "observations": {"first_a": points[0], "b": points[1], "second_a": points[2]},
            }
        ],
        "inputs": {
            "target_sha256": source["target_sha256"],
            "retail_manifest_identity": source["retail_manifest_identity"],
            "scenario_identity": source["scenario_identity"],
            "qualification_source_sha256": source["qualification_source_sha256"],
            "candidate_save_sha256": expected_candidate_hash,
        },
        "provenance": {
            "checkout_sha": _checkout_sha(),
            "runner_sha256": t3.sha256_file(Path(__file__)),
            "qualification_input_sha256": sha256_bytes(qualification_raw),
            "action_script_sha256": action_digest,
            "control_contract": CONTROL_CONTRACT,
            "blind_re_provenance": "clean",
            "evidence_class": "runtime",
            "runtime_environment": {
                "host": {
                    "system": platform.system(),
                    "release": platform.release(),
                    "machine": platform.machine(),
                    "python": platform.python_version(),
                },
                "dosbox": t3.executable_identity(dosbox),
            },
            "retail_fixture": fixture,
            "source_candidate_unchanged": True,
            "guest_code_writes": False,
            "guest_data_writes": "ordinary in-game Manual/Managed toggle restored immediately for record identification",
        },
    }
    validated = lifetime.validate_record(record, scenario_manifest, expected_source)
    if validated["positive_contract_accepted"] or validated["coverage_complete"]:
        raise A1SelectionControlError("selection-control-only record escaped incomplete-harness boundary")
    return record


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game-dir", type=Path, required=True)
    ap.add_argument("--dosbox", required=True)
    ap.add_argument("--fixture-manifest", type=Path, required=True)
    ap.add_argument("--candidate-save", type=Path, required=True)
    ap.add_argument("--candidate-sha256", required=True)
    ap.add_argument("--qualification-input", type=Path, required=True)
    ap.add_argument("--expected-source", type=Path, required=True)
    ap.add_argument("--scenario-manifest", type=Path, required=True)
    ap.add_argument("--planet-a-label", required=True)
    ap.add_argument("--planet-b-label", required=True)
    ap.add_argument("--artifact", type=Path, required=True)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    artifact = args.artifact.expanduser().resolve(strict=False)
    try:
        if artifact.exists() and artifact.is_dir():
            raise A1SelectionControlError("artifact path names a directory")
        if artifact.is_relative_to(args.game_dir.expanduser().resolve()):
            raise A1SelectionControlError("artifact path must not be inside source game tree")
        result = run(args)
        artifact.parent.mkdir(parents=True, exist_ok=True)
        t3.write_json_atomic(artifact, result)
    except Exception as exc:
        failure = {
            "schema": ARTIFACT_SCHEMA,
            "outcome": "incomplete-harness",
            "claims": {
                "array_base_established": False,
                "array_count_established": False,
                "stable_index_established": False,
                "reuse_detector_established": False,
                "epoch_boundary_established": False,
                "manual_transition_invalidation_established": False,
            },
            "control": {"passed": False},
            "transitions": [],
            "failure": f"{type(exc).__name__}: {exc}",
        }
        try:
            artifact.parent.mkdir(parents=True, exist_ok=True)
            t3.write_json_atomic(artifact, failure)
        except Exception:
            pass
        print(f"A1 selection control: FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        "A1 selection control: PASS "
        f"sequence={' -> '.join(result['control']['sequence'])}; "
        "lifecycle coverage intentionally incomplete"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
