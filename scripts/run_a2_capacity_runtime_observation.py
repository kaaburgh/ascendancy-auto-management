#!/usr/bin/env python3
"""Observe A2 Stage-1 candidate ranges at runtime without writing guest memory.

This experiment is intentionally read-only. It uses the already established RE2
runtime code anchor to translate exact-target static VAs into the DOSBox guest
memory mapping, validates that translation with file-backed boundary guards,
then takes coherent stopped-process snapshots while the canonical game advances.
Observed mutation can disqualify a candidate from "unused zero cave" assumptions;
absence of mutation in this bounded scenario is not proof of reusability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import le_image  # noqa: E402
import run_re4_runtime_state as re4  # noqa: E402
import run_re5_runtime_turn_path as re5  # noqa: E402

SCHEMA = "ascendancy.a2-capacity-runtime-observation/v1"
TARGET_SHA256 = re4.TARGET_SHA256
ANCHOR_VA = re5.ANCHOR_VA
DEFAULT_WINDOW_SECONDS = 7.0
DEFAULT_SAMPLE_INTERVAL = 0.05
MAX_WINDOW_SECONDS = 20.0
MAX_SAMPLE_INTERVAL = 0.25
MIN_SAMPLE_INTERVAL = 0.025
GUARD_WIDTH = 8

CANDIDATES = (
    {"id": "object2-zero-0x96c10", "object": 2, "va": 0x96C10, "size": 6206},
    {"id": "object2-zero-0x988dc", "object": 2, "va": 0x988DC, "size": 3052},
)


class A2RuntimeObservationError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _candidate_object(image: le_image.LEImage, candidate: dict[str, Any]) -> le_image.LEObject:
    start = int(candidate["va"])
    size = int(candidate["size"])
    if size <= 0:
        raise A2RuntimeObservationError(f"{candidate['id']}: candidate size must be positive")
    obj = image.object_containing(start)
    end_obj = image.object_containing(start + size - 1)
    if obj is None or end_obj is None or obj.index != end_obj.index:
        raise A2RuntimeObservationError(f"{candidate['id']}: candidate crosses or escapes an LE object")
    if obj.index != int(candidate["object"]):
        raise A2RuntimeObservationError(
            f"{candidate['id']}: expected object {candidate['object']}, got {obj.index}"
        )
    return obj


def static_candidate_contract(
    image: le_image.LEImage, candidate: dict[str, Any], guard_width: int = GUARD_WIDTH
) -> dict[str, Any]:
    obj = _candidate_object(image, candidate)
    start = int(candidate["va"])
    size = int(candidate["size"])
    offset = start - obj.base_address
    body = image.object_bytes(obj.index)
    payload = body[offset:offset + size]
    if len(payload) != size:
        raise A2RuntimeObservationError(f"{candidate['id']}: short reconstructed candidate bytes")
    if any(payload):
        raise A2RuntimeObservationError(
            f"{candidate['id']}: exact-target candidate is no longer an all-zero range"
        )
    if offset < guard_width or offset + size + guard_width > len(body):
        raise A2RuntimeObservationError(f"{candidate['id']}: insufficient file-backed guard room")
    before = body[offset - guard_width:offset]
    after = body[offset + size:offset + size + guard_width]
    if not any(before) or not any(after):
        raise A2RuntimeObservationError(
            f"{candidate['id']}: boundary guards must each contain at least one non-zero byte"
        )
    return {
        "id": candidate["id"],
        "object": obj.index,
        "va": start,
        "size": size,
        "static_zero_sha256": sha256_bytes(payload),
        "guard_width": guard_width,
        "before_guard_sha256": sha256_bytes(before),
        "after_guard_sha256": sha256_bytes(after),
        "_before_guard": before,
        "_after_guard": after,
    }


def candidate_host_range(
    anchor: dict[str, Any], candidate: dict[str, Any]
) -> tuple[int, int]:
    start = re5.static_va_host(anchor, int(candidate["va"]))
    size = int(candidate["size"])
    end = start + size
    if start < anchor["map_start"] or end > anchor["map_end"]:
        raise A2RuntimeObservationError(
            f"{candidate['id']}: translated range escapes runtime anchor mapping"
        )
    return start, end


def validate_runtime_guards(
    pid: int,
    anchor: dict[str, Any],
    candidate: dict[str, Any],
    static_contract: dict[str, Any],
) -> dict[str, Any]:
    width = int(static_contract["guard_width"])
    start, end = candidate_host_range(anchor, candidate)
    with re5.stopped_process(pid):
        before = re4.read_process(pid, start - width, width)
        after = re4.read_process(pid, end, width)
    expected_before = static_contract["_before_guard"]
    expected_after = static_contract["_after_guard"]
    if before != expected_before or after != expected_after:
        raise A2RuntimeObservationError(
            f"{candidate['id']}: runtime boundary guards do not match exact-target bytes; "
            "anchor-relative mapping is not independently validated"
        )
    return {
        "guard_width": width,
        "before_matches_static": True,
        "after_matches_static": True,
        "before_guard_sha256": sha256_bytes(before),
        "after_guard_sha256": sha256_bytes(after),
    }


def summarize_snapshots(
    candidate: dict[str, Any], snapshots: list[bytes]
) -> dict[str, Any]:
    if not snapshots:
        raise A2RuntimeObservationError(f"{candidate['id']}: no runtime snapshots")
    size = int(candidate["size"])
    if any(len(sample) != size for sample in snapshots):
        raise A2RuntimeObservationError(f"{candidate['id']}: snapshot size mismatch")
    initial = snapshots[0]
    changed: set[int] = set()
    max_nonzero = 0
    unique_hashes: list[str] = []
    seen_hashes: set[str] = set()
    for sample in snapshots:
        max_nonzero = max(max_nonzero, sum(byte != 0 for byte in sample))
        digest = sha256_bytes(sample)
        if digest not in seen_hashes and len(unique_hashes) < 16:
            seen_hashes.add(digest)
            unique_hashes.append(digest)
        changed.update(i for i, (a, b) in enumerate(zip(initial, sample)) if a != b)
    final = snapshots[-1]
    return {
        "sample_count": len(snapshots),
        "initial_sha256": sha256_bytes(initial),
        "final_sha256": sha256_bytes(final),
        "initial_nonzero_byte_count": sum(byte != 0 for byte in initial),
        "max_nonzero_byte_count": max_nonzero,
        "differs_from_initial": bool(changed),
        "changed_offset_count": len(changed),
        "first_changed_offsets": sorted(changed)[:64],
        "unique_snapshot_sha256": unique_hashes,
        "reusable": False,
        "reuse_evidence": "not established",
    }


def coherent_snapshot(
    pid: int,
    anchor: dict[str, Any],
    candidates: tuple[dict[str, Any], ...],
    stardate_address: int,
) -> tuple[dict[str, bytes], int]:
    with re5.stopped_process(pid):
        data = {}
        for candidate in candidates:
            start, end = candidate_host_range(anchor, candidate)
            sample = re4.read_process(pid, start, end - start)
            if len(sample) != end - start:
                raise A2RuntimeObservationError(f"{candidate['id']}: short process-memory sample")
            data[candidate["id"]] = sample
        stardate = int.from_bytes(re4.read_process(pid, stardate_address, 4), "little")
    return data, stardate


def _material_hashes() -> dict[str, str]:
    paths = (
        "scripts/run_a2_capacity_runtime_observation.py",
        "scripts/run_re4_runtime_state.py",
        "scripts/run_re5_runtime_turn_path.py",
        "tools/le_image.py",
        "tools/retail-runtime-manifest.json",
    )
    return {path: re4.sha256_file(ROOT / path) for path in paths}


def run_observation(
    root: Path,
    manifest_path: Path,
    dosbox: str,
    window_seconds: float,
    sample_interval: float,
) -> dict[str, Any]:
    if not (0 < window_seconds <= MAX_WINDOW_SECONDS):
        raise A2RuntimeObservationError(
            f"window seconds must be in (0, {MAX_WINDOW_SECONDS}], got {window_seconds}"
        )
    if not (MIN_SAMPLE_INTERVAL <= sample_interval <= MAX_SAMPLE_INTERVAL):
        raise A2RuntimeObservationError(
            f"sample interval must be in [{MIN_SAMPLE_INTERVAL}, {MAX_SAMPLE_INTERVAL}], "
            f"got {sample_interval}"
        )

    fixture = re5.verify_runtime_input(root, manifest_path)
    files = re4._casefold_file_map(root)
    target = files["antag.exe"]
    target_bytes = target.read_bytes()
    image = le_image.LEImage(target_bytes, name="ANTAG.EXE")
    if image.sha256 != TARGET_SHA256:
        raise A2RuntimeObservationError("canonical target identity mismatch after LE parse")
    contracts = {
        candidate["id"]: static_candidate_contract(image, candidate) for candidate in CANDIDATES
    }

    display = re4.choose_display()
    temp = tempfile.TemporaryDirectory(prefix="a2-capacity-runtime-")
    mount = Path(temp.name) / "game"
    shutil.copytree(root, mount)
    config = Path(temp.name) / "dosbox-a2-capacity.conf"
    config.write_text(
        "[cpu]\ncore=normal\ncycles=max\n[sdl]\nfullscreen=false\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update({"DISPLAY": display, "SDL_AUDIODRIVER": "dummy"})
    xvfb = subprocess.Popen(
        ["Xvfb", display, "-screen", "0", "1024x768x24", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    proc: subprocess.Popen[Any] | None = None
    inp: re4.XInput | None = None
    try:
        time.sleep(0.35)
        proc = subprocess.Popen(
            [
                dosbox,
                "-conf",
                str(config),
                "-noconsole",
                "-c",
                f"mount c {mount}",
                "-c",
                "c:",
                "-c",
                "ANTAG.EXE",
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        window = re4.wait_window(display, env, proc)
        inp = re4.XInput(display, window)
        time.sleep(5.0)
        inp.key("space")
        re4.wait_game_geometry(window, env, proc)
        time.sleep(4.2)
        re4.scenario_steps(inp, "resume")
        re4.select_planet_list_row(inp, 0)
        time.sleep(1.2)

        anchor = re4.find_unique_runtime_anchor(proc.pid)
        snapshot = re4.snapshot_anchor_map(proc.pid, anchor)
        record_offset = re5.find_named_planet_record(snapshot, re5.PLANET_NAME)
        record_host = anchor["map_start"] + record_offset
        re5.arm_planet_mode(proc.pid, record_host, inp, managed=False)

        guard_results = {
            candidate["id"]: validate_runtime_guards(
                proc.pid, anchor, candidate, contracts[candidate["id"]]
            )
            for candidate in CANDIDATES
        }
        stardate_address = re5.anchor_delta_host(anchor, re5.STARDATE_ANCHOR_DELTA, 4)
        initial_samples, initial_stardate = coherent_snapshot(
            proc.pid, anchor, CANDIDATES, stardate_address
        )
        samples = {candidate["id"]: [initial_samples[candidate["id"]]] for candidate in CANDIDATES}

        inp.key("Escape")
        time.sleep(0.5)
        inp.key("Escape")
        time.sleep(0.8)
        inp.move_to(593, 68)
        inp.click()  # fast-forward
        start = time.monotonic()
        deadline = start + window_seconds
        final_stardate = initial_stardate
        while time.monotonic() < deadline:
            sample_set, final_stardate = coherent_snapshot(
                proc.pid, anchor, CANDIDATES, stardate_address
            )
            for candidate in CANDIDATES:
                samples[candidate["id"]].append(sample_set[candidate["id"]])
            time.sleep(sample_interval)
        inp.click()  # stop fast-forward
        elapsed = time.monotonic() - start

        if final_stardate <= initial_stardate:
            raise A2RuntimeObservationError(
                "stardate did not advance; negative mutation observations would be non-informative"
            )

        summaries = []
        for candidate in CANDIDATES:
            static_public = {
                key: value
                for key, value in contracts[candidate["id"]].items()
                if not key.startswith("_")
            }
            summaries.append(
                {
                    **static_public,
                    "runtime_mapping": guard_results[candidate["id"]],
                    "observation": summarize_snapshots(
                        candidate, samples[candidate["id"]]
                    ),
                }
            )

        re5.verify_runtime_input(root, manifest_path)

        return {
            "artifact_schema": SCHEMA,
            "evidence_class": "runtime",
            "blind_re_provenance": "clean",
            "status": "passed",
            "claim_boundary": (
                "Observed mutation or non-zero runtime materialization is evidence against "
                "treating a candidate as an unused zero cave. Absence of mutation in this "
                "bounded scenario is not evidence of reusability and does not observe reads."
            ),
            "target": {
                "filename": "ANTAG.EXE",
                "sha256": TARGET_SHA256,
                "size": re4.TARGET_SIZE,
            },
            "retail_fixture": fixture,
            "runtime_environment": {
                "dosbox": {
                    "command": Path(dosbox).name,
                    "cpu_core": "normal",
                    "cycles": "max",
                },
                "xvfb": True,
            },
            "runtime_anchor": {
                "static_va": f"0x{ANCHOR_VA:x}",
                "mapping_size": anchor["map_size"],
                "anchor_offset_in_mapping": anchor["anchor_offset"],
                "host_addresses_omitted": True,
            },
            "scenario": {
                "fixture": "canonical resume.gam",
                "planet": re5.PLANET_NAME,
                "mode": "Manual",
                "fast_forward": True,
                "window_seconds": round(elapsed, 3),
                "sample_interval_seconds": sample_interval,
                "process_paused_per_sample": True,
                "stardate_initial": initial_stardate,
                "stardate_final": final_stardate,
                "stardate_delta": final_stardate - initial_stardate,
            },
            "diagnostic_guest_code_writes": False,
            "diagnostic_guest_data_writes": False,
            "source_inputs_modified": False,
            "material_repository_inputs": _material_hashes(),
            "candidates": summaries,
        }
    finally:
        if inp is not None:
            try:
                inp.close()
            except Exception:
                pass
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        if xvfb.poll() is None:
            xvfb.terminate()
            try:
                xvfb.wait(timeout=2)
            except subprocess.TimeoutExpired:
                xvfb.kill()
        temp.cleanup()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument(
        "--fixture-manifest", type=Path, default=ROOT / "tools" / "retail-runtime-manifest.json"
    )
    parser.add_argument("--dosbox", default="dosbox")
    parser.add_argument("--window-seconds", type=float, default=DEFAULT_WINDOW_SECONDS)
    parser.add_argument("--sample-interval", type=float, default=DEFAULT_SAMPLE_INTERVAL)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        game_dir = args.game_dir.resolve()
        output = args.output.resolve()
        try:
            output.relative_to(game_dir)
        except ValueError:
            pass
        else:
            raise A2RuntimeObservationError(
                "output must be outside the immutable retail evidence tree"
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        result = run_observation(
            game_dir,
            args.fixture_manifest.resolve(),
            args.dosbox,
            args.window_seconds,
            args.sample_interval,
        )
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            "A2 runtime capacity observation: PASS "
            + ", ".join(
                f"{item['id']} changed={item['observation']['changed_offset_count']} "
                f"initial_nonzero={item['observation']['initial_nonzero_byte_count']}"
                for item in result["candidates"]
            )
        )
        return 0
    except (A2RuntimeObservationError, re4.RE4Error, re5.RE5Error, le_image.LEError, OSError) as exc:
        print(f"A2 runtime capacity observation: FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
