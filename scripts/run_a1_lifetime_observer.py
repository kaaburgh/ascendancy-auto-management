#!/usr/bin/env python3
"""Run a bounded A1 lifetime observer and validate its detached evidence immediately."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
from typing import Any

try:
    from .a1_scenario_qualification import build_manifest
    from .a1_sidecar_evidence_bundle import validate_bundle
except ImportError:
    from a1_scenario_qualification import build_manifest
    from a1_sidecar_evidence_bundle import validate_bundle


class A1RuntimeObserverError(RuntimeError):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A1RuntimeObserverError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise A1RuntimeObserverError(f"{label} root must be an object")
    return value


def _resolved(path: Path) -> Path:
    return path.resolve(strict=False)


def _validate_manifest_output_path(
    manifest_output: Path | None,
    qualification_input: Path,
    expected_source: Path,
    observer: Path,
    record_output: Path,
    immutable_inputs: dict[str, Path],
) -> None:
    if manifest_output is None:
        return
    manifest_resolved = _resolved(manifest_output)
    protected = {
        "qualification input": _resolved(qualification_input),
        "expected source": _resolved(expected_source),
        "observer": _resolved(observer),
        "record output": _resolved(record_output),
        **{f"immutable input {name!r}": _resolved(path) for name, path in immutable_inputs.items()},
    }
    for label, path in protected.items():
        if manifest_resolved == path:
            raise A1RuntimeObserverError(f"manifest output must not alias {label}")


def _snapshot_immutable_inputs(immutable_inputs: dict[str, Path]) -> dict[str, str]:
    snapshots: dict[str, str] = {}
    for name, path in immutable_inputs.items():
        if not isinstance(name, str) or not name.strip():
            raise A1RuntimeObserverError("immutable input names must be non-empty")
        if name in snapshots:
            raise A1RuntimeObserverError(f"duplicate immutable input name: {name}")
        if not path.is_file():
            raise A1RuntimeObserverError(f"immutable input {name!r} does not exist: {path}")
        snapshots[name] = _sha256_file(path)
    return snapshots


def _validate_immutable_input_bindings(
    observer_args: list[str], immutable_inputs: dict[str, Path]
) -> None:
    for name, path in immutable_inputs.items():
        flag = f"--{name}"
        bound_values: list[str] = []
        index = 0
        while index < len(observer_args):
            arg = observer_args[index]
            if arg == flag:
                if index + 1 >= len(observer_args):
                    raise A1RuntimeObserverError(f"immutable input {name!r} observer argument has no value")
                bound_values.append(observer_args[index + 1])
                index += 2
                continue
            prefix = flag + "="
            if arg.startswith(prefix):
                bound_values.append(arg[len(prefix):])
            index += 1

        if len(bound_values) != 1:
            raise A1RuntimeObserverError(
                f"immutable input {name!r} must bind exactly one observer argument {flag}"
            )
        if _resolved(Path(bound_values[0])) != _resolved(path):
            raise A1RuntimeObserverError(
                f"immutable input {name!r} does not match observer argument {flag}"
            )


def _recheck_immutable_inputs(immutable_inputs: dict[str, Path], snapshots: dict[str, str]) -> None:
    for name, path in immutable_inputs.items():
        if not path.is_file() or _sha256_file(path) != snapshots[name]:
            raise A1RuntimeObserverError(f"immutable input {name!r} changed during observer execution")


def _bind_orchestration_provenance(
    record_output: Path,
    *,
    observer_sha: str,
    qualification_sha: str,
    expected_sha: str,
    manifest_sha: str,
    immutable_snapshots: dict[str, str],
) -> None:
    record = _read_json_object(record_output, "lifetime record")
    if "orchestration_provenance" in record:
        raise A1RuntimeObserverError("observer record must not pre-populate orchestration_provenance")
    record["orchestration_provenance"] = {
        "schema": "ascendancy.a1-observer-orchestration-provenance/v1",
        "observer_sha256": observer_sha,
        "qualification_input_sha256": qualification_sha,
        "expected_source_sha256": expected_sha,
        "scenario_manifest_sha256": manifest_sha,
        "immutable_inputs": dict(sorted(immutable_snapshots.items())),
    }
    record_output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_immutable_input(value: str) -> tuple[str, Path]:
    name, sep, raw_path = value.partition("=")
    if not sep or not name.strip() or not raw_path:
        raise argparse.ArgumentTypeError("immutable input must use NAME=PATH")
    return name, Path(raw_path)


def _run_bounded_process(command: list[str], timeout_seconds: float) -> subprocess.CompletedProcess[str]:
    if not hasattr(os, "killpg"):
        raise A1RuntimeObserverError("observer process-group cleanup requires POSIX process groups")

    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        raise A1RuntimeObserverError(f"observer timed out after {timeout_seconds:g}s") from exc

    return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)


def run_observer(
    qualification_input: Path,
    expected_source: Path,
    observer: Path,
    observer_args: list[str],
    timeout_seconds: float,
    record_output: Path,
    manifest_output: Path | None = None,
    immutable_inputs: dict[str, Path] | None = None,
) -> dict[str, Any]:
    if timeout_seconds <= 0:
        raise A1RuntimeObserverError("timeout must be positive")
    if not observer.is_file():
        raise A1RuntimeObserverError(f"observer does not exist: {observer}")
    immutable_inputs = immutable_inputs or {}
    _validate_immutable_input_bindings(observer_args, immutable_inputs)
    immutable_snapshots = _snapshot_immutable_inputs(immutable_inputs)
    _validate_manifest_output_path(
        manifest_output,
        qualification_input,
        expected_source,
        observer,
        record_output,
        immutable_inputs,
    )
    if record_output.exists():
        raise A1RuntimeObserverError("record output must not already exist")

    qualification_raw = qualification_input.read_bytes()
    expected = _read_json_object(expected_source, "expected source")
    scenario_manifest = build_manifest(qualification_raw, expected)
    qualification_sha = _sha256_bytes(qualification_raw)
    expected_sha = _sha256_file(expected_source)
    observer_sha = _sha256_file(observer)

    with tempfile.TemporaryDirectory(prefix="a1-lifetime-observer-") as tmp:
        tmp_path = Path(tmp)
        manifest_path = tmp_path / "scenario-manifest.json"
        manifest_path.write_text(json.dumps(scenario_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest_sha = _sha256_file(manifest_path)

        # The observer must not begin target interaction until every declared file-backed
        # immutable input still matches the pre-launch snapshot.
        _recheck_immutable_inputs(immutable_inputs, immutable_snapshots)

        command = [
            str(observer),
            "--scenario-manifest", str(manifest_path),
            "--record-output", str(record_output),
            *observer_args,
        ]
        completed = _run_bounded_process(command, timeout_seconds)

        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            detail = f": {stderr}" if stderr else ""
            raise A1RuntimeObserverError(f"observer exited with {completed.returncode}{detail}")
        if not record_output.is_file():
            raise A1RuntimeObserverError("observer exited successfully without producing the record")

        # Re-read every independently supplied immutable input after the observer ran. This
        # fails closed on concurrent mutation even when the observer itself cannot see the
        # protected source paths.
        if _sha256_file(qualification_input) != qualification_sha:
            raise A1RuntimeObserverError("qualification input changed during observer execution")
        if _sha256_file(expected_source) != expected_sha:
            raise A1RuntimeObserverError("expected source changed during observer execution")
        if _sha256_file(observer) != observer_sha:
            raise A1RuntimeObserverError("observer executable changed during execution")
        if _sha256_file(manifest_path) != manifest_sha:
            raise A1RuntimeObserverError("scenario manifest changed during observer execution")
        _recheck_immutable_inputs(immutable_inputs, immutable_snapshots)

        _bind_orchestration_provenance(
            record_output,
            observer_sha=observer_sha,
            qualification_sha=qualification_sha,
            expected_sha=expected_sha,
            manifest_sha=manifest_sha,
            immutable_snapshots=immutable_snapshots,
        )

        result = validate_bundle(
            qualification_input,
            expected_source,
            record_output,
            manifest_output,
        )

    return {
        "observer_sha256": observer_sha,
        "qualification_input_sha256": qualification_sha,
        "expected_source_sha256": expected_sha,
        "scenario_manifest_sha256": manifest_sha,
        "immutable_inputs": dict(sorted(immutable_snapshots.items())),
        "oracle_result": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-input", type=Path, required=True)
    parser.add_argument("--expected-source", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--record-output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument(
        "--immutable-input",
        action="append",
        type=_parse_immutable_input,
        default=[],
        metavar="NAME=PATH",
        help="hash/recheck one file-backed immutable observer input and bind it into the record",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("observer_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    observer_args = args.observer_args
    if observer_args[:1] == ["--"]:
        observer_args = observer_args[1:]
    immutable_inputs: dict[str, Path] = {}
    for name, path in args.immutable_input:
        if name in immutable_inputs:
            parser.error(f"duplicate immutable input name: {name}")
        immutable_inputs[name] = path
    try:
        result = run_observer(
            args.qualification_input,
            args.expected_source,
            args.observer,
            observer_args,
            args.timeout,
            args.record_output,
            args.manifest_output,
            immutable_inputs,
        )
    except (OSError, ValueError, A1RuntimeObserverError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
