#!/usr/bin/env python3
"""Produce one target-written T3 save through bounded ordinary UI actions.

The source retail tree and seed save are immutable evidence. Execution happens
only in the isolated work tree created by ``run_t3_multi_planet_fixture``. The
resulting proprietary save is copied only to an explicit operator path outside
the repository; the committed/detached artifact contains identities and oracle
results, never payload bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))

import run_re4_runtime_state as re4  # noqa: E402
import run_t3_multi_planet_fixture as t3  # noqa: E402

ARTIFACT_SCHEMA = "ascendancy.validation-fixture-producer/v1"
SCENARIO_CONTRACT = "validation-fixture/canonical-target-exact-byte-producer/v1"
ACTION_SCHEMA = 1
MAX_STEPS = 32
MAX_RUNTIME_SECONDS = 180.0
NUMBERED_SAVE_RE = re.compile(r"^[0-9]{2}\.sav$", re.IGNORECASE)


class ProducerError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return t3.sha256_file(path)


def _bounded_number(value: Any, *, low: float, high: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= float(value) <= high:
        raise ProducerError(f"{label} must be between {low:g} and {high:g}")
    return float(value)


def load_action_scenario(path: Path) -> dict[str, Any]:
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProducerError(f"cannot read action scenario: {exc}") from exc
    if not isinstance(cfg, dict) or cfg.get("schema") != ACTION_SCHEMA:
        raise ProducerError(f"action scenario schema must be {ACTION_SCHEMA}")
    for field in ("name", "ordinary_game_method"):
        if not isinstance(cfg.get(field), str) or not cfg[field].strip():
            raise ProducerError(f"action scenario requires non-empty {field}")
    slot = cfg.get("output_slot")
    if isinstance(slot, bool) or not isinstance(slot, int) or not 1 <= slot <= 99:
        raise ProducerError("output_slot must be an integer in 1..99")
    max_runtime = _bounded_number(
        cfg.get("max_runtime_seconds", 90), low=5, high=MAX_RUNTIME_SECONDS,
        label="max_runtime_seconds",
    )
    steps = cfg.get("steps")
    if not isinstance(steps, list) or not steps or len(steps) > MAX_STEPS:
        raise ProducerError(f"steps must contain 1..{MAX_STEPS} actions")
    active = 0
    estimated_wait = 0.0
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ProducerError(f"step {i} must be an object")
        action = step.get("action")
        if action == "wait":
            estimated_wait += _bounded_number(step.get("seconds"), low=0, high=10, label=f"step {i} seconds")
        elif action == "move_to":
            x, y = step.get("x"), step.get("y")
            if any(isinstance(v, bool) or not isinstance(v, int) for v in (x, y)):
                raise ProducerError(f"step {i} move_to requires integer x/y")
            if not (0 <= x < 640 and 0 <= y < 480):
                raise ProducerError(f"step {i} move_to is outside 640x480")
            active += 1
        elif action == "click":
            active += 1
        elif action == "key":
            name = step.get("name")
            if not isinstance(name, str) or not name.strip() or len(name) > 64:
                raise ProducerError(f"step {i} key requires a bounded key name")
            active += 1
        else:
            raise ProducerError(f"step {i} has unsupported action {action!r}")
    if active == 0:
        raise ProducerError("action scenario must contain at least one UI input action")
    if estimated_wait >= max_runtime:
        raise ProducerError("declared waits consume the entire runtime budget")
    cfg["max_runtime_seconds"] = max_runtime
    return cfg


def validate_repo_scenario_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    try:
        relative = resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ProducerError("action scenario must be a repository file") from exc
    if relative.parts[:1] not in (("tools",), ("docs",)) or resolved.suffix.lower() != ".json":
        raise ProducerError("action scenario must be JSON under tools/ or docs/")
    if not resolved.is_file():
        raise ProducerError("action scenario does not exist")
    return resolved


def validate_operator_output_path(path: Path, game_dir: Path) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    if resolved.exists():
        raise ProducerError("operator output path already exists; refusing to overwrite")
    for forbidden, label in ((ROOT.resolve(), "repository"), (game_dir.resolve(), "source game tree")):
        try:
            resolved.relative_to(forbidden)
        except ValueError:
            pass
        else:
            raise ProducerError(f"operator output path must be outside the {label}")
    return resolved


def validate_artifact_path(path: Path) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    experiments = (ROOT / "docs" / "experiments").resolve()
    try:
        resolved.relative_to(experiments)
    except ValueError as exc:
        raise ProducerError("producer artifact must be under docs/experiments") from exc
    if resolved.suffix.lower() != ".json":
        raise ProducerError("producer artifact must be JSON")
    return resolved


def validate_snapshot_path(path: Path) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    experiments = (ROOT / "docs" / "experiments").resolve()
    try:
        resolved.relative_to(experiments)
    except ValueError as exc:
        raise ProducerError("harness source snapshot must be under docs/experiments") from exc
    if resolved.suffix != ".py":
        raise ProducerError("harness source snapshot must be a Python source file")
    return resolved


def execute_steps(inp: re4.XInput, steps: list[dict[str, Any]], deadline: float) -> None:
    for i, step in enumerate(steps):
        if time.monotonic() >= deadline:
            raise ProducerError(f"runtime deadline exceeded before step {i}")
        action = step["action"]
        if action == "wait":
            seconds = float(step["seconds"])
            if time.monotonic() + seconds > deadline:
                raise ProducerError(f"runtime deadline would be exceeded during step {i}")
            time.sleep(seconds)
        elif action == "move_to":
            inp.move_to(step["x"], step["y"])
        elif action == "click":
            inp.click()
        elif action == "key":
            inp.key(step["name"])


def numbered_saves(mount: Path) -> list[Path]:
    return sorted(
        (p for p in mount.iterdir() if p.is_file() and NUMBERED_SAVE_RE.fullmatch(p.name)),
        key=lambda p: p.name.casefold(),
    )


def read_unambiguous_output(mount: Path, output_slot: int) -> tuple[str, bytes]:
    saves = numbered_saves(mount)
    expected = f"{output_slot:02d}.SAV"
    if len(saves) != 1:
        raise ProducerError(f"expected exactly one numbered save output, found {[p.name for p in saves]}")
    if saves[0].name.casefold() != expected.casefold():
        raise ProducerError(f"only numbered save is {saves[0].name}, expected {expected}")
    payload = saves[0].read_bytes()
    if not payload:
        raise ProducerError("target-written save output is empty")
    return saves[0].name, payload


def wait_for_output(mount: Path, output_slot: int, deadline: float) -> tuple[str, bytes]:
    expected = f"{output_slot:02d}.SAV"
    previous: tuple[int, int] | None = None
    stable_since: float | None = None
    while time.monotonic() < deadline:
        path = next((p for p in numbered_saves(mount) if p.name.casefold() == expected.casefold()), None)
        if path is not None:
            stat = path.stat()
            state = (stat.st_size, stat.st_mtime_ns)
            if stat.st_size > 0 and state == previous:
                stable_since = stable_since or time.monotonic()
                if time.monotonic() - stable_since >= 0.25:
                    return read_unambiguous_output(mount, output_slot)
            else:
                previous, stable_since = state, None
        time.sleep(0.05)
    raise ProducerError(f"timed out waiting for stable {expected}")


def preserve_harness_snapshot(snapshot: Path) -> tuple[str, str]:
    source = Path(__file__).resolve()
    data = source.read_bytes()
    digest = sha256_bytes(data)
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    if snapshot.exists() and snapshot.read_bytes() != data:
        raise ProducerError("harness source snapshot exists with different bytes")
    if not snapshot.exists():
        fd, temp_name = tempfile.mkstemp(prefix=f".{snapshot.name}.", suffix=".part", dir=snapshot.parent)
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, snapshot)
        finally:
            temp.unlink(missing_ok=True)
    return digest, snapshot.relative_to(ROOT.resolve()).as_posix()


def build_artifact(
    *, fixture_id: str, output_name: str, payload: bytes, retail_fixture: dict[str, Any],
    dosbox_identity: dict[str, Any], scenario: dict[str, Any], scenario_path: Path,
    harness_sha256: str, snapshot_relative: str,
) -> dict[str, Any]:
    digest = sha256_bytes(payload)
    return {
        "artifact_schema": ARTIFACT_SCHEMA,
        "scenario_contract": SCENARIO_CONTRACT,
        "roadmap_item": "T3",
        "status": "passed",
        "evidence_class": "runtime",
        "blind_re_provenance": "clean",
        "target": {"filename": "ANTAG.EXE", "size": re4.TARGET_SIZE, "sha256": re4.TARGET_SHA256},
        "retail_fixture": retail_fixture,
        "fixture": {
            "id": fixture_id,
            "filename": output_name,
            "size": len(payload),
            "sha256": digest,
            "target_written_exact_bytes": True,
            "storage": "operator-supplied",
        },
        "runtime_environment": {
            "dosbox": dosbox_identity,
            "configuration": {
                "cpu_core": "normal",
                "cycles": "max",
                "sdl_fullscreen": False,
                "sdl_audio_driver": "dummy",
                "xvfb_screen": "1024x768x24",
                "action_schema": ACTION_SCHEMA,
                "action_scenario": scenario_path.relative_to(ROOT.resolve()).as_posix(),
                "action_scenario_sha256": sha256_file(scenario_path),
                "action_scenario_name": scenario["name"],
                "output_slot": scenario["output_slot"],
                "max_runtime_seconds": scenario["max_runtime_seconds"],
            },
        },
        "harness": {
            "source": "scripts/run_t3_target_written_fixture.py",
            "source_sha256": harness_sha256,
            "source_snapshot": snapshot_relative,
        },
        "execution": {
            "ordinary_game_method": scenario["ordinary_game_method"],
            "diagnostic_guest_code_writes": False,
            "diagnostic_guest_data_writes": False,
            "source_inputs_modified": False,
            "termination": {
                "status": "completed",
                "save_write_completed": True,
                "output_observed_after_save": True,
            },
        },
        "oracle": {
            "status": "passed",
            "exact_byte_match": True,
            "output_sha256": digest,
            "output_size": len(payload),
        },
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = args.game_dir.expanduser().resolve()
    if not root.is_dir():
        raise ProducerError("game-dir must exist")
    manifest = args.fixture_manifest.expanduser().resolve()
    seed_path = args.seed_save.expanduser().resolve()
    if not seed_path.is_file():
        raise ProducerError("seed-save must exist")
    seed = seed_path.read_bytes()
    expected_seed = args.seed_sha256.lower()
    if sha256_bytes(seed) != expected_seed:
        raise ProducerError("seed-save identity mismatch")

    scenario_path = validate_repo_scenario_path(args.actions)
    scenario = load_action_scenario(scenario_path)
    output_save = validate_operator_output_path(args.output_save, root)
    artifact_path = validate_artifact_path(args.artifact)
    snapshot_path = validate_snapshot_path(args.harness_snapshot)
    if artifact_path == snapshot_path:
        raise ProducerError("artifact and harness snapshot paths must differ")

    retail_fixture = re4.verify_fixture(root, manifest)
    files = re4._casefold_file_map(root)
    target = files.get("antag.exe")
    if target is None or target.stat().st_size != re4.TARGET_SIZE or sha256_file(target) != re4.TARGET_SHA256:
        raise ProducerError("canonical ANTAG.EXE identity mismatch")
    dosbox = t3.resolve_executable(args.dosbox)
    dosbox_identity = t3.executable_identity(dosbox)

    temp, mount, xvfb, process, inp = t3._launch(root, dosbox, seed)
    payload: bytes | None = None
    output_name: str | None = None
    try:
        re4.scenario_steps(inp, "resume")
        deadline = time.monotonic() + float(scenario["max_runtime_seconds"])
        execute_steps(inp, scenario["steps"], deadline)
        output_name, payload = wait_for_output(mount, scenario["output_slot"], deadline)
    finally:
        t3._teardown(temp, xvfb, process, inp)

    assert payload is not None and output_name is not None
    if seed_path.read_bytes() != seed:
        raise ProducerError("source seed changed during producer experiment")
    output_save.parent.mkdir(parents=True, exist_ok=True)
    output_save.write_bytes(payload)
    if output_save.read_bytes() != payload:
        raise ProducerError("operator output copy does not match target-written bytes")

    harness_sha256, snapshot_relative = preserve_harness_snapshot(snapshot_path)
    artifact = build_artifact(
        fixture_id=args.fixture_id,
        output_name=output_name,
        payload=payload,
        retail_fixture=retail_fixture,
        dosbox_identity=dosbox_identity,
        scenario=scenario,
        scenario_path=scenario_path,
        harness_sha256=harness_sha256,
        snapshot_relative=snapshot_relative,
    )
    t3.write_json_atomic(artifact_path, artifact)
    return artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--fixture-manifest", type=Path, required=True)
    parser.add_argument("--seed-save", type=Path, required=True)
    parser.add_argument("--seed-sha256", required=True)
    parser.add_argument("--fixture-id", required=True)
    parser.add_argument("--actions", type=Path, required=True)
    parser.add_argument("--output-save", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--harness-snapshot", type=Path, required=True)
    parser.add_argument("--dosbox", default="dosbox")
    args = parser.parse_args(argv)
    try:
        artifact = run(args)
    except (ProducerError, re4.RE4Error, t3.T3Error, OSError, ValueError) as exc:
        print(f"t3-target-written-producer: FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        "t3-target-written-producer: PASS "
        f"fixture={artifact['fixture']['sha256']} size={artifact['fixture']['size']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
