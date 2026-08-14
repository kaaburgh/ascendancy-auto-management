#!/usr/bin/env python3
"""Read-only RE5 witness for the player-loop override gate.

This experiment does not patch guest code or data. It derives the runtime
placement of the LE data object from five independent initialized-data
signatures, then samples the RE3 override global together with Xerxes I state
and the independent stardate progress witness while DOSBox is confirmed
stopped for every coherent sample.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

import le_image  # noqa: E402
import run_re4_runtime_state as re4  # noqa: E402
import run_re5_runtime_turn_path as re5  # noqa: E402

ARTIFACT_SCHEMA = "ascendancy.re5-override-witness/v2"
SCENARIO_CONTRACT = "re5/manual-override-witness/v2"
ANCHOR_VA = 0x37915
GATE_OVERRIDE_COMPARE_VA = 0x3C102
EXPECTED_OVERRIDE_VA = 0xA0D00
CURRENT_PLAYER_ID_VA = 0x104BEA
STARDATE_DATA_VA = 0xA2F6C
LE_H_FIXUP_PAGE_TABLE = 0x68
LE_H_FIXUP_RECORD_TABLE = 0x6C
SIGNATURE_SPECS = (
    (0x90895, 40),
    (0x90EB8, 40),
    (0x95078, 40),
    (0x987D0, 32),
    (0x998BA, 15),
)
WINDOW_SECONDS = 7.0
SAMPLE_INTERVAL_SECONDS = 0.025
MIN_STARDATE_DELTA = 4
MIN_SAMPLES = 200
MAX_SAMPLE_GAP_MS = 50.0


class OverrideWitnessError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded_u32(data: bytes, offset: int, label: str) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise OverrideWitnessError(f"{label} is outside target bytes")
    return struct.unpack_from("<I", data, offset)[0]


def _parse_simple_le_fixup_records(blob: bytes) -> list[dict[str, int]]:
    """Parse the simple internal-offset fixups used on the canonical gate page.

    The exact target page contains only source type 0x07 records with flags
    0x00 (16-bit target offset) or 0x10 (32-bit target offset). Anything else
    fails closed rather than being guessed.
    """
    records: list[dict[str, int]] = []
    cursor = 0
    while cursor < len(blob):
        if cursor + 5 > len(blob):
            raise OverrideWitnessError("truncated LE fixup record")
        source_type = blob[cursor]
        flags = blob[cursor + 1]
        if source_type != 0x07 or flags not in (0x00, 0x10):
            raise OverrideWitnessError(
                f"unsupported LE fixup form source=0x{source_type:02x} flags=0x{flags:02x}"
            )
        source_offset = struct.unpack_from("<H", blob, cursor + 2)[0]
        target_object = blob[cursor + 4]
        target_size = 4 if flags == 0x10 else 2
        end = cursor + 5 + target_size
        if end > len(blob):
            raise OverrideWitnessError("truncated LE fixup target")
        target_offset = int.from_bytes(blob[cursor + 5:end], "little")
        records.append(
            {
                "source_type": source_type,
                "flags": flags,
                "source_offset": source_offset,
                "target_object": target_object,
                "target_offset": target_offset,
            }
        )
        cursor = end
    return records


def validate_gate_override_relationship(image: Any, target_bytes: bytes) -> tuple[int, dict[str, Any]]:
    """Derive the override VA from the gate instruction and its LE relocation."""
    instruction = static_bytes(image, target_bytes, GATE_OVERRIDE_COMPARE_VA, 7)
    if instruction[:2] != b"\x83\x3d" or instruction[6] != 0:
        raise OverrideWitnessError(
            f"unexpected gate compare encoding at 0x{GATE_OVERRIDE_COMPARE_VA:x}: {instruction.hex()}"
        )
    raw_target_offset = int.from_bytes(instruction[2:6], "little")
    source_va = GATE_OVERRIDE_COMPARE_VA + 2
    source_object = image.object_containing(source_va)
    if source_object is None:
        raise OverrideWitnessError("gate compare immediate is not inside an LE object")
    source_relative = source_va - source_object.base_address
    page_index = (source_object.first_page - 1) + source_relative // image.page_size
    source_offset = source_relative % image.page_size

    page_table_rel = _bounded_u32(
        target_bytes, image.lfanew + LE_H_FIXUP_PAGE_TABLE, "LE fixup page-table offset"
    )
    record_table_rel = _bounded_u32(
        target_bytes, image.lfanew + LE_H_FIXUP_RECORD_TABLE, "LE fixup record-table offset"
    )
    page_table = image.lfanew + page_table_rel
    record_table = image.lfanew + record_table_rel
    start = _bounded_u32(
        target_bytes, page_table + page_index * 4, "gate fixup-page start"
    )
    end = _bounded_u32(
        target_bytes, page_table + (page_index + 1) * 4, "gate fixup-page end"
    )
    if start > end or record_table + end > len(target_bytes):
        raise OverrideWitnessError("gate fixup-page span is invalid")
    records = _parse_simple_le_fixup_records(target_bytes[record_table + start:record_table + end])
    matches = [record for record in records if record["source_offset"] == source_offset]
    if len(matches) != 1:
        raise OverrideWitnessError(
            f"gate immediate relocation match count {len(matches)} != 1 at page offset 0x{source_offset:x}"
        )
    relocation = matches[0]
    if relocation["flags"] != 0x10:
        raise OverrideWitnessError("gate immediate relocation is not a 32-bit target offset")
    if relocation["target_offset"] != raw_target_offset:
        raise OverrideWitnessError(
            "gate immediate bytes disagree with LE relocation target offset"
        )
    target_objects = [obj for obj in image.objects if obj.index == relocation["target_object"]]
    if len(target_objects) != 1:
        raise OverrideWitnessError(
            f"gate relocation target object {relocation['target_object']} is not unique"
        )
    target_object = target_objects[0]
    derived_va = target_object.base_address + relocation["target_offset"]
    if derived_va != EXPECTED_OVERRIDE_VA:
        raise OverrideWitnessError(
            f"gate relocation derives 0x{derived_va:x}, expected 0x{EXPECTED_OVERRIDE_VA:x}"
        )
    return derived_va, {
        "status": "passed",
        "gate_compare_static_va": f"0x{GATE_OVERRIDE_COMPARE_VA:x}",
        "instruction_sha256": hashlib.sha256(instruction).hexdigest(),
        "relocation_source_page_offset": f"0x{source_offset:x}",
        "relocation_target_object": target_object.index,
        "relocation_target_offset": f"0x{relocation['target_offset']:x}",
        "target_object_base": f"0x{target_object.base_address:x}",
        "derived_override_static_va": f"0x{derived_va:x}",
    }


def resolve_stardate_host(anchor: dict[str, Any], bias: int) -> int:
    """Resolve stardate through the data-object bias and cross-check the old anchor delta."""
    via_data = data_host(anchor, bias, STARDATE_DATA_VA, 4)
    via_anchor = re5.anchor_delta_host(anchor, re5.STARDATE_ANCHOR_DELTA, 4)
    if via_data != via_anchor:
        raise OverrideWitnessError(
            "data-object bias does not resolve stardate to the established anchor-relative witness"
        )
    return via_data


def fixture_contains_name(root: Path, name: str) -> bool:
    wanted = name.casefold()
    return any(path.is_file() and path.name.casefold() == wanted for path in root.rglob("*"))


def infer_uniform_bias(anchor_offset: int, observations: list[tuple[int, list[int]]]) -> int:
    biases: list[int] = []
    for static_va, hits in observations:
        if len(hits) != 1:
            raise OverrideWitnessError(
                f"signature 0x{static_va:x} match count {len(hits)} != 1"
            )
        biases.append(hits[0] - anchor_offset - (static_va - ANCHOR_VA))
    if not biases or len(set(biases)) != 1:
        raise OverrideWitnessError(f"inconsistent data-object runtime biases: {biases}")
    return biases[0]


def static_bytes(image: Any, target_bytes: bytes, static_va: int, size: int) -> bytes:
    file_offset = image.va_to_file_offset(static_va)
    if file_offset is None:
        raise OverrideWitnessError(f"VA 0x{static_va:x} is not file-backed")
    data = target_bytes[file_offset:file_offset + size]
    if len(data) != size:
        raise OverrideWitnessError(f"short static signature at 0x{static_va:x}")
    return data


def validate_mapping(pid: int, anchor: dict[str, Any], target: Path) -> tuple[int, dict[str, Any]]:
    image = le_image.load(target)
    target_bytes = target.read_bytes()
    if image.sha256 != re4.TARGET_SHA256:
        raise OverrideWitnessError("target hash mismatch")

    with re5.stopped_process(pid):
        mapping = re4.read_process(pid, anchor["map_start"], anchor["map_size"])

    observations: list[tuple[int, list[int]]] = []
    evidence: list[dict[str, Any]] = []
    for static_va, size in SIGNATURE_SPECS:
        signature = static_bytes(image, target_bytes, static_va, size)
        hits: list[int] = []
        position = 0
        while True:
            found = mapping.find(signature, position)
            if found < 0:
                break
            hits.append(found)
            position = found + 1
        observations.append((static_va, hits))
        evidence.append(
            {
                "static_va": f"0x{static_va:x}",
                "size": size,
                "runtime_match_count": len(hits),
                "runtime_mapping_offset": hits[0] if len(hits) == 1 else None,
                "static_bytes_sha256": hashlib.sha256(signature).hexdigest(),
            }
        )

    bias = infer_uniform_bias(anchor["anchor_offset"], observations)
    return bias, {
        "status": "passed",
        "anchor_static_va": f"0x{ANCHOR_VA:x}",
        "data_object_runtime_bias": f"{bias:+#x}",
        "signatures": evidence,
        "host_addresses_omitted": True,
    }


def data_host(anchor: dict[str, Any], bias: int, static_va: int, size: int = 1) -> int:
    anchor_host = anchor["map_start"] + anchor["anchor_offset"]
    host = anchor_host + (static_va - ANCHOR_VA) + bias
    if host < anchor["map_start"] or host + size > anchor["map_end"]:
        raise OverrideWitnessError(f"data VA 0x{static_va:x} resolves outside runtime mapping")
    return host


def sample(
    pid: int, anchor: dict[str, Any], bias: int, override_va: int, record_host: int
) -> dict[str, Any]:
    override_host = data_host(anchor, bias, override_va, 4)
    current_player_host = data_host(anchor, bias, CURRENT_PLAYER_ID_VA, 1)
    stardate_host = resolve_stardate_host(anchor, bias)
    window_offset = 0x50
    window_size = 0x0E

    with re5.stopped_process(pid):
        window = re4.read_process(pid, record_host + window_offset, window_size)
        override = int.from_bytes(re4.read_process(pid, override_host, 4), "little")
        current_player = re4.read_process(pid, current_player_host, 1)[0]
        stardate = int.from_bytes(re4.read_process(pid, stardate_host, 4), "little")

    return {
        "owner_0x57": window[re5.OWNER_OFFSET - window_offset],
        "slot_0x52": window[
            re5.SLOT_OFFSET - window_offset:re5.SLOT_OFFSET - window_offset + 2
        ].hex(),
        "action_0x54": f"{window[re5.ACTION_OFFSET - window_offset]:02x}",
        "managed_0x5a": window[
            re4.STATE_OFFSET - window_offset:re4.STATE_OFFSET - window_offset + 4
        ].hex(),
        "override_0xa0d00": override,
        "current_player_id_0x104bea": current_player,
        "stardate": stardate,
    }


def evaluate(before: dict[str, Any], samples: list[dict[str, Any]], after: dict[str, Any]) -> dict[str, Any]:
    if not samples:
        raise OverrideWitnessError("no runtime samples")

    all_samples = [before, *samples, after]

    def values(key: str) -> list[Any]:
        return sorted({item[key] for item in all_samples})

    times = [float(item["t_ms"]) for item in samples]
    gaps = [later - earlier for earlier, later in zip(times, times[1:])]
    max_gap_ms = max(gaps, default=0.0)
    stardate_delta = int(after["stardate"]) - int(before["stardate"])
    checks = {
        "sample_count_at_least_minimum": len(samples) >= MIN_SAMPLES,
        "max_sample_gap_within_bound": max_gap_ms <= MAX_SAMPLE_GAP_MS,
        "stardate_progress_target_met": stardate_delta >= MIN_STARDATE_DELTA,
        "override_zero_in_every_sample": values("override_0xa0d00") == [0],
        "current_player_id_zero_in_every_sample": values("current_player_id_0x104bea") == [0],
        "xerxes_owner_zero_in_every_sample": values("owner_0x57") == [0],
        "manual_state_stable": values("managed_0x5a") == ["00000000"],
        "action_remains_empty": values("action_0x54") == ["ff"],
        "slot_remains_empty": values("slot_0x52") == ["ffff"],
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "sample_count": len(samples),
        "max_sample_gap_ms": round(max_gap_ms, 3),
        "stardate_initial": before["stardate"],
        "stardate_final": after["stardate"],
        "stardate_delta": stardate_delta,
        "override_values_observed": values("override_0xa0d00"),
        "current_player_ids_observed": values("current_player_id_0x104bea"),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = args.game_dir.resolve()
    fixture = re5.verify_runtime_input(root, args.fixture_manifest.resolve())
    files = re4._casefold_file_map(root)
    target = files["antag.exe"]
    if fixture_contains_name(root, "flash.pop"):
        raise OverrideWitnessError("canonical fixture unexpectedly contains flash.pop")

    display = re4.choose_display()
    temp = tempfile.TemporaryDirectory(prefix="re5-override-v1-")
    mount = Path(temp.name) / "game"
    shutil.copytree(root, mount)
    config = Path(temp.name) / "dosbox.conf"
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
    process: subprocess.Popen[Any] | None = None
    inp: re4.XInput | None = None
    try:
        time.sleep(0.35)
        process = subprocess.Popen(
            [
                str(args.dosbox),
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
        window = re4.wait_window(display, env, process)
        inp = re4.XInput(display, window)
        time.sleep(5.0)
        inp.key("space")
        re4.wait_game_geometry(window, env, process)
        time.sleep(4.2)

        anchor = re4.find_unique_runtime_anchor(process.pid)
        image = le_image.load(target)
        target_bytes = target.read_bytes()
        override_va, gate_relationship = validate_gate_override_relationship(image, target_bytes)
        bias, mapping = validate_mapping(process.pid, anchor, target)
        re4.scenario_steps(inp, "resume")
        inp.move_to(205, 125)
        inp.click()
        time.sleep(1.2)

        with re5.stopped_process(process.pid):
            snapshot = re4.snapshot_anchor_map(process.pid, anchor)
        record_offset = re5.find_named_planet_record(snapshot)
        record_host = anchor["map_start"] + record_offset
        initial = sample(process.pid, anchor, bias, override_va, record_host)
        if (
            initial["owner_0x57"] != 0
            or initial["slot_0x52"] != "ffff"
            or initial["action_0x54"] != "ff"
            or initial["managed_0x5a"] != "00000000"
            or initial["current_player_id_0x104bea"] != 0
        ):
            raise OverrideWitnessError(f"unexpected initial Manual Xerxes state: {initial}")

        inp.key("Escape")
        time.sleep(0.5)
        inp.key("Escape")
        time.sleep(0.8)
        before = sample(process.pid, anchor, bias, override_va, record_host)

        inp.move_to(593, 68)
        inp.click()
        start = time.perf_counter()
        samples: list[dict[str, Any]] = []
        while time.perf_counter() - start < WINDOW_SECONDS:
            current = sample(process.pid, anchor, bias, override_va, record_host)
            current["t_ms"] = round((time.perf_counter() - start) * 1000.0, 3)
            samples.append(current)
            time.sleep(SAMPLE_INTERVAL_SECONDS)
        inp.click()
        time.sleep(0.15)
        after = sample(process.pid, anchor, bias, override_va, record_host)
        observation = evaluate(before, samples, after)

        return {
            "artifact_schema": ARTIFACT_SCHEMA,
            "scenario_contract": SCENARIO_CONTRACT,
            "runner_revision": args.runner_revision,
            "source_sha256": sha256_file(Path(__file__)),
            "status": observation["status"],
            "blind_re_provenance": "clean",
            "evidence_class": "runtime",
            "target": {
                "filename": "ANTAG.EXE",
                "size": re4.TARGET_SIZE,
                "sha256": re4.TARGET_SHA256,
            },
            "fixture": fixture,
            "diagnostic_guest_code_writes": False,
            "diagnostic_guest_data_writes": False,
            "mapping_validation": mapping,
            "static_relationships": {
                "override_static_va": f"0x{override_va:x}",
                "current_player_id_static_va": f"0x{CURRENT_PLAYER_ID_VA:x}",
                "stardate_data_static_va": f"0x{STARDATE_DATA_VA:x}",
                "stardate_anchor_delta": f"0x{re5.STARDATE_ANCHOR_DELTA:x}",
                "gate_override_relationship": gate_relationship,
                "stardate_data_path_cross_checked": True,
            },
            "observation_policy": {
                "stop_policy": "fixed_window",
                "window_seconds": WINDOW_SECONDS,
                "requested_interval_ms": SAMPLE_INTERVAL_SECONDS * 1000.0,
                "minimum_stardate_delta": MIN_STARDATE_DELTA,
                "minimum_samples": MIN_SAMPLES,
                "maximum_sample_gap_ms": MAX_SAMPLE_GAP_MS,
                "process_paused_per_coherent_sample": True,
            },
            "before": before,
            "after": after,
            "observation": observation,
        }
    finally:
        if inp is not None:
            try:
                inp.close()
            except Exception:
                pass
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


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    result.add_argument("--game-dir", type=Path, required=True)
    result.add_argument("--dosbox", type=Path, required=True)
    result.add_argument("--fixture-manifest", type=Path, required=True)
    result.add_argument("--runner-revision", required=True)
    result.add_argument("--output", type=Path, required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = run(args)
    except Exception as exc:
        print(f"RE5 override witness: FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    observation = result["observation"]
    print(
        f"RE5 override witness: {result['status'].upper()} "
        f"revision={result['runner_revision']} source={result['source_sha256']} "
        f"samples={observation['sample_count']} maxgap={observation['max_sample_gap_ms']}ms "
        f"stardate_delta={observation['stardate_delta']} "
        f"override={observation['override_values_observed']} "
        f"bias={result['mapping_validation']['data_object_runtime_bias']}"
    )
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
