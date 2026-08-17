#!/usr/bin/env python3
"""Runtime-qualify the exact operator-supplied T3 multi-planet save fixture.

The candidate save is an immutable, hash-pinned external input. The runner
copies the verified retail tree to a temporary work directory, installs the
candidate there as ``resume.gam``, loads it with the exact canonical ANTAG.EXE,
and derives the current player's planet set from a coherent stopped-process
snapshot of the established 0x7b planet-record sequence.

No guest code or data is patched. The source retail tree and candidate save are
never modified. The detached JSON artifact contains only bounded identities,
runtime/environment provenance, and the semantic role oracle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_re4_runtime_state as re4  # noqa: E402
import run_re5_override_witness as override_witness  # noqa: E402
import run_re5_runtime_turn_path as re5  # noqa: E402

ARTIFACT_SCHEMA = "ascendancy.t3-multi-planet-fixture/v2"
SCENARIO_CONTRACT = "t3/operator-save-runtime-verify/v2"
EXPECTED_PLANET_RECORD_COUNT = 305
MIN_PLAYER_OWNED_PLANETS = 2
MIN_EMPTY_ACTION_PLANETS = 1


class T3Error(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_executable(command: str | Path) -> Path:
    """Resolve an executable while preserving ordinary PATH lookup semantics."""
    text = str(command)
    found = shutil.which(text)
    if found is not None:
        return Path(found).resolve()
    candidate = Path(text).expanduser()
    if candidate.is_file():
        return candidate.resolve()
    raise T3Error(f"required executable not found: {text}")


def executable_identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise T3Error(f"runtime executable missing: {resolved.name}")
    cp = subprocess.run(
        [str(resolved), "-version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=5,
        check=False,
    )
    output = cp.stdout.strip()
    if cp.returncode != 0 or not output:
        raise T3Error(
            f"cannot identify runtime executable {resolved.name}: rc={cp.returncode}"
        )
    if len(output) > 4096:
        raise T3Error("runtime version output exceeds 4096 bytes")
    return {
        "filename": resolved.name,
        "size": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
        "version_output": output,
    }


def _resolved_output(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def validate_output_paths(
    *, artifact: Path, candidate: Path, fixture_manifest: Path, game_dir: Path
) -> Path:
    """Reject any artifact path that could mutate an immutable experiment input."""
    artifact_resolved = _resolved_output(artifact)
    candidate_resolved = candidate.expanduser().resolve()
    manifest_resolved = fixture_manifest.expanduser().resolve()
    game_resolved = game_dir.expanduser().resolve()
    if artifact_resolved in (candidate_resolved, manifest_resolved):
        raise T3Error("artifact path aliases an immutable experiment input")
    if _is_within(artifact_resolved, game_resolved):
        raise T3Error("artifact path must not be inside the source game tree")
    if artifact_resolved.exists() and artifact_resolved.is_dir():
        raise T3Error("artifact path names a directory")
    return artifact_resolved


def write_json_atomic(path: Path, document: dict[str, Any]) -> None:
    """Atomically replace a detached JSON artifact in its destination directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, indent=2, sort_keys=True) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _record_name(snapshot: bytes, base: int) -> str | None:
    if base < 0 or base + re4.RECORD_SIZE > len(snapshot):
        return None
    return re4._record_name(snapshot[base:base + re4.RECORD_SIZE])


def discover_planet_record_sequence(snapshot: bytes) -> list[tuple[int, str]]:
    """Find the unique 305-record 0x7b runtime sequence without trusting ownership."""
    candidates: dict[int, str] = {}
    for match in re.finditer(rb"(?<![ -~])[ -~]{3,31}\x00", snapshot):
        base = match.start() - re4.NAME_OFFSET
        name = _record_name(snapshot, base)
        if name is not None:
            candidates[base] = name

    runs: list[list[tuple[int, str]]] = []
    bases = set(candidates)
    for base in sorted(bases):
        if base - re4.RECORD_SIZE in bases:
            continue
        run: list[tuple[int, str]] = []
        cursor = base
        while cursor in bases:
            name = candidates[cursor]
            if _record_name(snapshot, cursor) != name:
                break
            run.append((cursor, name))
            cursor += re4.RECORD_SIZE
        if run:
            runs.append(run)

    exact = [run for run in runs if len(run) == EXPECTED_PLANET_RECORD_COUNT]
    if len(exact) != 1:
        lengths = sorted((len(run) for run in runs), reverse=True)[:8]
        raise T3Error(
            f"expected exactly one {EXPECTED_PLANET_RECORD_COUNT}-record 0x{re4.RECORD_SIZE:x} "
            f"runtime sequence, got {len(exact)}; longest={lengths}"
        )
    sequence = exact[0]
    names = [name for _, name in sequence]
    if len(set(names)) != len(names):
        raise T3Error("runtime planet sequence contains duplicate names")
    return sequence


def describe_record(snapshot: bytes, base: int, name: str) -> dict[str, Any]:
    record = snapshot[base:base + re4.RECORD_SIZE]
    return {
        "name": name,
        "owner_0x57": record[re5.OWNER_OFFSET],
        "slot_0x52": record[re5.SLOT_OFFSET:re5.SLOT_OFFSET + 2].hex(),
        "action_0x54": f"{record[re5.ACTION_OFFSET]:02x}",
        "managed_0x5a": record[re4.STATE_OFFSET:re4.STATE_OFFSET + 4].hex(),
    }


def evaluate_fixture_records(records: list[dict[str, Any]], current_player_id: int) -> dict[str, Any]:
    names = [str(record["name"]) for record in records]
    player_owned = [record for record in records if record["owner_0x57"] == current_player_id]
    empty = [
        record for record in player_owned
        if record["slot_0x52"] == "ffff" and record["action_0x54"] == "ff"
    ]
    checks = {
        "runtime_record_count_matches_contract": len(records) == EXPECTED_PLANET_RECORD_COUNT,
        "runtime_planet_names_unique": len(names) == len(set(names)),
        "at_least_two_player_owned_planets": len(player_owned) >= MIN_PLAYER_OWNED_PLANETS,
        "at_least_one_player_planet_has_empty_current_action": len(empty) >= MIN_EMPTY_ACTION_PLANETS,
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "current_player_id": current_player_id,
        "runtime_planet_record_count": len(records),
        "runtime_planet_name_sequence_sha256": sha256_bytes("\0".join(names).encode("ascii")),
        "player_owned_planet_count": len(player_owned),
        "player_planet_names": [record["name"] for record in player_owned],
        "planets_with_empty_current_action_at_load": [record["name"] for record in empty],
        "player_planets": player_owned,
    }


def _prepare_mount(root: Path, save_bytes: bytes) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temp = tempfile.TemporaryDirectory(prefix="t3-multi-planet-")
    mount = Path(temp.name) / "game"
    shutil.copytree(root, mount)
    for path in list(mount.iterdir()):
        if not path.is_file():
            continue
        folded = path.name.casefold()
        if folded == "resume.gam" or re.fullmatch(r"\d\d\.sav", folded):
            path.unlink()
    (mount / "resume.gam").write_bytes(save_bytes)
    return temp, mount


def _launch(root: Path, dosbox: Path, save_bytes: bytes) -> tuple[
    tempfile.TemporaryDirectory[str], Path, subprocess.Popen[Any], subprocess.Popen[Any], re4.XInput
]:
    temp, mount = _prepare_mount(root, save_bytes)
    display = re4.choose_display()
    config = Path(temp.name) / "dosbox.conf"
    config.write_text("[cpu]\ncore=normal\ncycles=max\n[sdl]\nfullscreen=false\n", encoding="utf-8")
    env = os.environ.copy()
    env.update({"DISPLAY": display, "SDL_AUDIODRIVER": "dummy"})
    xvfb = subprocess.Popen(
        ["Xvfb", display, "-screen", "0", "1024x768x24", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    process: subprocess.Popen[Any] | None = None
    inp: re4.XInput | None = None
    try:
        time.sleep(0.35)
        process = subprocess.Popen(
            [
                str(dosbox), "-conf", str(config), "-noconsole",
                "-c", f"mount c {mount}", "-c", "c:", "-c", "ANTAG.EXE",
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        window = re4.wait_window(display, env, process)
        inp = re4.XInput(display, window)
        time.sleep(5.0)
        inp.key("space")
        re4.wait_game_geometry(window, env, process)
        time.sleep(4.2)
        return temp, mount, xvfb, process, inp
    except Exception:
        if inp is not None:
            inp.close()
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
        if xvfb.poll() is None:
            xvfb.terminate()
            try:
                xvfb.wait(timeout=2)
            except subprocess.TimeoutExpired:
                xvfb.kill()
        temp.cleanup()
        raise


def _teardown(
    temp: tempfile.TemporaryDirectory[str],
    xvfb: subprocess.Popen[Any],
    process: subprocess.Popen[Any],
    inp: re4.XInput,
) -> None:
    try:
        inp.close()
    except Exception:
        pass
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    if xvfb.poll() is None:
        xvfb.terminate()
        try:
            xvfb.wait(timeout=2)
        except subprocess.TimeoutExpired:
            xvfb.kill()
            xvfb.wait(timeout=2)
    temp.cleanup()


def verify_candidate_save(root: Path, dosbox: Path, save_bytes: bytes) -> dict[str, Any]:
    temp, mount, xvfb, process, inp = _launch(root, dosbox, save_bytes)
    try:
        target = re4._casefold_file_map(mount)["antag.exe"]
        anchor = re4.find_unique_runtime_anchor(process.pid)
        bias, mapping = override_witness.validate_mapping(process.pid, anchor, target)
        re4.scenario_steps(inp, "resume")
        time.sleep(0.8)

        current_player_host = override_witness.data_host(
            anchor, bias, override_witness.CURRENT_PLAYER_ID_VA, 1
        )
        stardate_host = override_witness.resolve_stardate_host(anchor, bias)
        with re5.stopped_process(process.pid):
            snapshot = re4.snapshot_anchor_map(process.pid, anchor)
            current_player_id = re4.read_process(process.pid, current_player_host, 1)[0]
            stardate = int.from_bytes(re4.read_process(process.pid, stardate_host, 4), "little")

        sequence = discover_planet_record_sequence(snapshot)
        records = [describe_record(snapshot, base, name) for base, name in sequence]
        observation = evaluate_fixture_records(records, current_player_id)
        if observation["status"] != "passed":
            raise T3Error(f"runtime M1 fixture oracle failed: {observation['checks']}")
        resume = mount / "resume.gam"
        if resume.read_bytes() != save_bytes:
            raise T3Error("candidate fixture bytes changed merely by loading them")
        return {
            "status": "passed",
            "runtime_mapping": mapping,
            "current_player_id_source": {
                "static_va": f"0x{override_witness.CURRENT_PLAYER_ID_VA:x}",
                "read_through_validated_data_object_bias": True,
            },
            "stardate_at_observation": stardate,
            "process_stopped_for_coherent_snapshot": True,
            "save_unchanged_by_verification_load": True,
            "record_layout": {
                "record_size": re4.RECORD_SIZE,
                "name_offset": re4.NAME_OFFSET,
                "slot_offset": re5.SLOT_OFFSET,
                "action_offset": re5.ACTION_OFFSET,
                "owner_offset": re5.OWNER_OFFSET,
                "managed_offset": re4.STATE_OFFSET,
            },
            "observation": observation,
        }
    finally:
        _teardown(temp, xvfb, process, inp)


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = args.game_dir.expanduser().resolve()
    if not root.is_dir():
        raise T3Error("game-dir must exist")
    candidate_path = args.candidate_save.expanduser().resolve()
    if not candidate_path.is_file():
        raise T3Error("candidate-save must exist")
    fixture_manifest = args.fixture_manifest.expanduser().resolve()
    if not fixture_manifest.is_file():
        raise T3Error("fixture-manifest must exist")

    expected_candidate_hash = args.candidate_sha256.lower()
    candidate = candidate_path.read_bytes()
    actual_candidate_hash = sha256_bytes(candidate)
    if actual_candidate_hash != expected_candidate_hash:
        raise T3Error(
            f"candidate-save identity mismatch: got {actual_candidate_hash}, expected {expected_candidate_hash}"
        )

    fixture = re4.verify_fixture(root, fixture_manifest)
    files = re4._casefold_file_map(root)
    target = files.get("antag.exe")
    if target is None or target.stat().st_size != re4.TARGET_SIZE or sha256_file(target) != re4.TARGET_SHA256:
        raise T3Error("canonical ANTAG.EXE identity mismatch")

    dosbox = resolve_executable(args.dosbox)
    runtime_environment = {
        "dosbox": executable_identity(dosbox),
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "dosbox_config": {
            "cpu_core": "normal",
            "cycles": "max",
            "sdl_fullscreen": False,
            "sdl_audio_driver": "dummy",
            "xvfb_screen": "1024x768x24",
        },
    }
    verification = verify_candidate_save(root, dosbox, candidate)
    if candidate_path.read_bytes() != candidate:
        raise T3Error("source candidate changed during runtime experiment")
    observation = verification["observation"]
    return {
        "artifact_schema": ARTIFACT_SCHEMA,
        "scenario_contract": SCENARIO_CONTRACT,
        "roadmap_item": "T3",
        "runner_revision": args.runner_revision,
        "runner_source_sha256": sha256_file(Path(__file__)),
        "status": "passed",
        "blind_re_provenance": "clean",
        "evidence_class": "runtime",
        "target": {
            "filename": "ANTAG.EXE",
            "size": re4.TARGET_SIZE,
            "sha256": re4.TARGET_SHA256,
        },
        "retail_fixture": fixture,
        "runtime_environment": runtime_environment,
        "harness_dependencies": {
            "run_re4_runtime_state.py": sha256_file(Path(re4.__file__)),
            "run_re5_runtime_turn_path.py": sha256_file(Path(re5.__file__)),
            "run_re5_override_witness.py": sha256_file(Path(override_witness.__file__)),
        },
        "candidate_fixture": {
            "id": args.fixture_id,
            "size": len(candidate),
            "sha256": actual_candidate_hash,
            "storage": "operator-supplied",
            "source_unchanged": candidate_path.read_bytes() == candidate,
        },
        "verification": verification,
        "role_claim": {
            "role": "m1-multi-planet",
            "player_race_id": observation["current_player_id"],
            "player_owned_planet_count": observation["player_owned_planet_count"],
            "player_planet_names": observation["player_planet_names"],
            "planets_with_empty_current_action_at_load": observation[
                "planets_with_empty_current_action_at_load"
            ],
        },
        "diagnostic_guest_code_writes": False,
        "diagnostic_guest_data_writes": False,
        "source_inputs_modified": False,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    result.add_argument("--game-dir", type=Path, required=True)
    result.add_argument("--dosbox", required=True)
    result.add_argument("--fixture-manifest", type=Path, required=True)
    result.add_argument("--candidate-save", type=Path, required=True)
    result.add_argument("--candidate-sha256", required=True)
    result.add_argument("--fixture-id", required=True)
    result.add_argument("--runner-revision", required=True)
    result.add_argument("--artifact", type=Path, required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        artifact = validate_output_paths(
            artifact=args.artifact,
            candidate=args.candidate_save,
            fixture_manifest=args.fixture_manifest,
            game_dir=args.game_dir,
        )
        resolve_executable(args.dosbox)
        resolve_executable("Xvfb")
        resolve_executable("xwininfo")
    except (T3Error, OSError) as exc:
        print(f"T3 multi-planet fixture: FAIL: {exc}", file=sys.stderr)
        return 1

    try:
        result = run(args)
    except Exception as exc:
        failure = {
            "artifact_schema": ARTIFACT_SCHEMA,
            "scenario_contract": SCENARIO_CONTRACT,
            "roadmap_item": "T3",
            "runner_revision": args.runner_revision,
            "runner_source_sha256": sha256_file(Path(__file__)),
            "status": "failed",
            "blind_re_provenance": "clean",
            "evidence_class": "runtime",
            "failure": f"{type(exc).__name__}: {exc}",
        }
        write_json_atomic(artifact, failure)
        print(f"T3 multi-planet fixture: FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    write_json_atomic(artifact, result)
    claim = result["role_claim"]
    print(
        "T3 multi-planet fixture: PASS "
        f"save={result['candidate_fixture']['sha256']} "
        f"player={claim['player_race_id']} planets={claim['player_owned_planet_count']} "
        f"names={','.join(claim['player_planet_names'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
