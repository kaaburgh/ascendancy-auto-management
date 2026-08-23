#!/usr/bin/env python3
"""Run a bounded A1 lifetime observer and validate its detached evidence immediately."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
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


def run_observer(
    qualification_input: Path,
    expected_source: Path,
    observer: Path,
    observer_args: list[str],
    timeout_seconds: float,
    record_output: Path,
    manifest_output: Path | None = None,
) -> dict[str, Any]:
    if timeout_seconds <= 0:
        raise A1RuntimeObserverError("timeout must be positive")
    if not observer.is_file():
        raise A1RuntimeObserverError(f"observer does not exist: {observer}")
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

        command = [
            str(observer),
            "--scenario-manifest", str(manifest_path),
            "--record-output", str(record_output),
            *observer_args,
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                timeout=timeout_seconds,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise A1RuntimeObserverError(f"observer timed out after {timeout_seconds:g}s") from exc

        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            detail = f": {stderr}" if stderr else ""
            raise A1RuntimeObserverError(f"observer exited with {completed.returncode}{detail}")
        if not record_output.is_file():
            raise A1RuntimeObserverError("observer exited successfully without producing the record")

        # Re-read the independently supplied inputs after the observer ran. The observer never
        # receives their paths, but this also fails closed on unrelated concurrent mutation.
        if _sha256_file(qualification_input) != qualification_sha:
            raise A1RuntimeObserverError("qualification input changed during observer execution")
        if _sha256_file(expected_source) != expected_sha:
            raise A1RuntimeObserverError("expected source changed during observer execution")
        if _sha256_file(observer) != observer_sha:
            raise A1RuntimeObserverError("observer executable changed during execution")
        if _sha256_file(manifest_path) != manifest_sha:
            raise A1RuntimeObserverError("scenario manifest changed during observer execution")

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
        "oracle_result": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-input", type=Path, required=True)
    parser.add_argument("--expected-source", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--record-output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("observer_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    observer_args = args.observer_args
    if observer_args[:1] == ["--"]:
        observer_args = observer_args[1:]
    try:
        result = run_observer(
            args.qualification_input,
            args.expected_source,
            args.observer,
            observer_args,
            args.timeout,
            args.record_output,
            args.manifest_output,
        )
    except (OSError, ValueError, A1RuntimeObserverError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
