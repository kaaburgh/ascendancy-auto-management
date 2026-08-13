#!/usr/bin/env python3
"""Run the bounded RE5 per-turn automation causality experiment.

RE5 intentionally builds on RE4's exact-fixture/runtime-anchor/UI harness. Each
sub-scenario runs from a temporary retail-tree copy. Diagnostic guest-code
changes are live-process-only, expected-byte checked, instruction-boundary
sized, restored, and re-verified before teardown.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
from typing import Any

# Running a file from scripts/ puts this directory on sys.path, so the stacked
# RE4 runner is a normal sibling-module dependency after RE4 merges.
import run_re4_runtime_state as re4

RESUME_SHA256 = "fe7b29f63b685df3b098c0bd109a44e95c9a36a2116617b6c0363eb289a813d3"
PLANET_NAME = "Xerxes I"
OWNER_OFFSET = 0x57
SLOT_OFFSET = 0x52
ACTION_OFFSET = 0x54
NO_SLOT = b"\xff\xff"
NO_ACTION = 0xFF

# RE2's canonical runtime anchor begins at static 0x37915. Relative static code
# relationships within that uniquely matched runtime mapping are sufficient for
# these exact-byte diagnostic sites; no DOS/4G selector/base mapping is assumed.
ANCHOR_VA = 0x37915
POLICY_CALL_VA = 0x3C118
POLICY_CALL_BYTES = bytes.fromhex("e8d3170000")  # call 0x3d8f0
ACTION_WRITE_VA = 0x34DF2
ACTION_WRITE_BYTES = bytes.fromhex("884654")  # mov [esi+0x54], al
DEFAULT_WINDOW_SECONDS = 7.0


class RE5Error(RuntimeError):
    pass


@dataclass(frozen=True)
class PatchPlan:
    name: str
    static_va: int
    expected: bytes
    replacement: bytes


POLICY_SUPPRESSION = PatchPlan(
    "suppress-gate-policy-call",
    POLICY_CALL_VA,
    POLICY_CALL_BYTES,
    b"\x90" * len(POLICY_CALL_BYTES),
)
ACTION_WRITE_SUPPRESSION = PatchPlan(
    "suppress-action-commit-write",
    ACTION_WRITE_VA,
    ACTION_WRITE_BYTES,
    b"\x90" * len(ACTION_WRITE_BYTES),
)


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    managed: bool
    patch: PatchPlan | None


SCENARIOS = (
    ScenarioSpec("manual-control", False, None),
    ScenarioSpec("managed-control", True, None),
    ScenarioSpec("managed-policy-suppressed", True, POLICY_SUPPRESSION),
    ScenarioSpec("managed-action-write-suppressed", True, ACTION_WRITE_SUPPRESSION),
)


def verify_runtime_input(root: Path, manifest_path: Path) -> dict[str, Any]:
    fixture = re4.verify_fixture(root, manifest_path)
    files = re4._casefold_file_map(root)
    resume = files.get("resume.gam")
    if resume is None or re4.sha256_file(resume) != RESUME_SHA256:
        raise RE5Error("resume.gam identity mismatch")
    return {
        **fixture,
        "resume": {
            "filename": "resume.gam",
            "size": resume.stat().st_size,
            "sha256": RESUME_SHA256,
        },
    }


def find_named_planet_record(snapshot: bytes, name: str = PLANET_NAME) -> int:
    needle = name.encode("ascii") + b"\0"
    candidates: list[int] = []
    start = 0
    while True:
        at = snapshot.find(needle, start)
        if at < 0:
            break
        base = at - re4.NAME_OFFSET
        if base >= 0 and base + re4.RECORD_SIZE <= len(snapshot):
            record = snapshot[base:base + re4.RECORD_SIZE]
            if record[re4.NAME_OFFSET:re4.NAME_OFFSET + len(needle)] == needle and record[OWNER_OFFSET] == 0:
                candidates.append(base)
        start = at + 1
    if len(candidates) != 1:
        raise RE5Error(
            f"expected exactly one player-owned {name!r} 0x{re4.RECORD_SIZE:x} record, got {len(candidates)}"
        )
    return candidates[0]


def static_va_host(anchor: dict[str, Any], static_va: int) -> int:
    host_anchor = anchor["map_start"] + anchor["anchor_offset"]
    host = host_anchor + (static_va - ANCHOR_VA)
    if host < anchor["map_start"] or host >= anchor["map_end"]:
        raise RE5Error(f"static VA 0x{static_va:x} resolves outside the runtime anchor mapping")
    return host


def write_process(pid: int, address: int, data: bytes) -> None:
    fd = os.open(f"/proc/{pid}/mem", os.O_RDWR)
    try:
        written = os.pwrite(fd, data, address)
    finally:
        os.close(fd)
    if written != len(data):
        raise RE5Error(f"short process write at 0x{address:x}: expected {len(data)}, got {written}")


def checked_apply_patch(pid: int, anchor: dict[str, Any], plan: PatchPlan) -> dict[str, Any]:
    address = static_va_host(anchor, plan.static_va)
    actual = re4.read_process(pid, address, len(plan.expected))
    if actual != plan.expected:
        raise RE5Error(
            f"{plan.name} expected bytes mismatch at static 0x{plan.static_va:x}: "
            f"expected {plan.expected.hex()}, got {actual.hex()}"
        )
    write_process(pid, address, plan.replacement)
    if re4.read_process(pid, address, len(plan.replacement)) != plan.replacement:
        raise RE5Error(f"{plan.name} live-process patch verification failed")
    return {
        "name": plan.name,
        "static_va": f"0x{plan.static_va:x}",
        "expected_bytes": plan.expected.hex(),
        "diagnostic_bytes": plan.replacement.hex(),
        "instruction_boundary_whole": True,
    }


def checked_restore_patch(pid: int, anchor: dict[str, Any], plan: PatchPlan) -> None:
    address = static_va_host(anchor, plan.static_va)
    actual = re4.read_process(pid, address, len(plan.replacement))
    if actual != plan.replacement:
        raise RE5Error(
            f"{plan.name} diagnostic bytes changed before restore: "
            f"expected {plan.replacement.hex()}, got {actual.hex()}"
        )
    write_process(pid, address, plan.expected)
    restored = re4.read_process(pid, address, len(plan.expected))
    if restored != plan.expected:
        raise RE5Error(f"{plan.name} restore verification failed: got {restored.hex()}")


def paused_read_process(pid: int, address: int, size: int) -> bytes:
    """Take one coherent bounded sample while the DOSBox process is stopped."""
    os.kill(pid, signal.SIGSTOP)
    try:
        deadline = time.monotonic() + 0.25
        while time.monotonic() < deadline:
            try:
                status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
            except FileNotFoundError as exc:
                raise RE5Error("DOSBox exited before paused memory sample") from exc
            state_line = next((line for line in status.splitlines() if line.startswith("State:")), "")
            if "T" in state_line or "t" in state_line:
                return re4.read_process(pid, address, size)
            time.sleep(0.001)
        raise RE5Error("DOSBox did not enter stopped state for bounded memory sample")
    finally:
        try:
            os.kill(pid, signal.SIGCONT)
        except ProcessLookupError:
            pass


def sample_record(pid: int, record_host: int) -> dict[str, str]:
    return {
        "owner_0x57": re4.read_process(pid, record_host + OWNER_OFFSET, 1).hex(),
        "slot_0x52": re4.read_process(pid, record_host + SLOT_OFFSET, 2).hex(),
        "action_0x54": re4.read_process(pid, record_host + ACTION_OFFSET, 1).hex(),
        "managed_0x5a": re4.read_process(pid, record_host + re4.STATE_OFFSET, 4).hex(),
    }


def arm_planet_mode(pid: int, record_host: int, inp: re4.XInput, managed: bool) -> float | None:
    current = re4.read_process(pid, record_host + re4.STATE_OFFSET, 4)
    if current not in (re4.MANUAL, re4.MANAGED):
        raise RE5Error(f"unexpected Xerxes +0x{re4.STATE_OFFSET:x}: {current.hex()}")
    expected = re4.MANAGED if managed else re4.MANUAL
    if current == expected:
        return None
    inp.key("m")
    return re4.wait_field(pid, record_host + re4.STATE_OFFSET, expected, timeout=1.0)


def monitor_turn(pid: int, record_host: int, timeout: float) -> dict[str, Any]:
    start = time.perf_counter()
    deadline = start + timeout
    window_offset = 0x50
    window_size = 0x12
    initial = paused_read_process(pid, record_host + window_offset, window_size)
    slot_index = SLOT_OFFSET - window_offset
    action_index = ACTION_OFFSET - window_offset
    state_index = re4.STATE_OFFSET - window_offset
    initial_slot = initial[slot_index:slot_index + 2]
    initial_action = initial[action_index]
    if initial_slot != NO_SLOT or initial_action != NO_ACTION:
        raise RE5Error(
            f"scenario must start empty: +0x52={initial_slot.hex()} +0x54={initial_action:02x}"
        )

    first_slot_change_ms: float | None = None
    first_action_change_ms: float | None = None
    slot_values: list[str] = []
    previous_slot = initial_slot
    final_window = initial
    while time.perf_counter() < deadline:
        final_window = paused_read_process(pid, record_host + window_offset, window_size)
        slot = final_window[slot_index:slot_index + 2]
        action = final_window[action_index]
        now_ms = (time.perf_counter() - start) * 1000.0
        if slot != previous_slot:
            if first_slot_change_ms is None:
                first_slot_change_ms = now_ms
            encoded = slot.hex()
            if not slot_values or slot_values[-1] != encoded:
                slot_values.append(encoded)
            previous_slot = slot
        if action != NO_ACTION:
            first_action_change_ms = now_ms
            break
        time.sleep(0.025)

    return {
        "window_ms": round((time.perf_counter() - start) * 1000.0, 3),
        "first_slot_change_ms": None if first_slot_change_ms is None else round(first_slot_change_ms, 3),
        "first_action_change_ms": None if first_action_change_ms is None else round(first_action_change_ms, 3),
        "observed_slot_values": slot_values[:16],
        "sampling": {"process_paused_per_sample": True, "interval_ms": 25},
        "final": {
            "owner_0x57": re4.read_process(pid, record_host + OWNER_OFFSET, 1).hex(),
            "slot_0x52": final_window[slot_index:slot_index + 2].hex(),
            "action_0x54": f"{final_window[action_index]:02x}",
            "managed_0x5a": final_window[state_index:state_index + 4].hex(),
        },
    }


def validate_scenario(spec: ScenarioSpec, trace: dict[str, Any]) -> None:
    first_slot = trace["first_slot_change_ms"]
    first_action = trace["first_action_change_ms"]
    final = trace["final"]
    expected_state = re4.MANAGED.hex() if spec.managed else re4.MANUAL.hex()
    if final["managed_0x5a"] != expected_state:
        raise RE5Error(f"{spec.name}: +0x5a drifted from armed state")
    if spec.name == "manual-control":
        if first_slot is not None or first_action is not None:
            raise RE5Error("manual-control unexpectedly selected or committed an automatic action")
    elif spec.name == "managed-control":
        if first_slot is None or first_action is None or final["action_0x54"] == "ff":
            raise RE5Error("managed-control did not select and commit an automatic action")
    elif spec.name == "managed-policy-suppressed":
        if first_slot is not None or first_action is not None:
            raise RE5Error("policy suppression still allowed selection/action mutation")
    elif spec.name == "managed-action-write-suppressed":
        if first_slot is None:
            raise RE5Error("action-write suppression saw no policy/selection output at +0x52")
        if first_action is not None or final["action_0x54"] != "ff":
            raise RE5Error("action-write suppression failed to keep +0x54 empty")
    else:  # pragma: no cover - SCENARIOS is closed above
        raise RE5Error(f"unhandled scenario {spec.name}")


def run_scenario(root: Path, dosbox: str, timeout: float, spec: ScenarioSpec) -> dict[str, Any]:
    print(f"RE5 {spec.name}: launching", flush=True)
    display = re4.choose_display()
    temp = tempfile.TemporaryDirectory(prefix=f"re5-{spec.name}-")
    mount = Path(temp.name) / "game"
    shutil.copytree(root, mount)
    config = Path(temp.name) / "dosbox-re5.conf"
    config.write_text("[cpu]\ncore=normal\ncycles=max\n[sdl]\nfullscreen=false\n", encoding="utf-8")
    env = os.environ.copy()
    env.update({"DISPLAY": display, "SDL_AUDIODRIVER": "dummy"})
    xvfb = subprocess.Popen(
        ["Xvfb", display, "-screen", "0", "1024x768x24", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    proc: subprocess.Popen[Any] | None = None
    inp: re4.XInput | None = None
    anchor: dict[str, Any] | None = None
    patch_applied = False
    patch_record: dict[str, Any] | None = None
    restore_verified = spec.patch is None
    try:
        time.sleep(0.35)
        proc = subprocess.Popen(
            [dosbox, "-conf", str(config), "-noconsole", "-c", f"mount c {mount}", "-c", "c:", "-c", "ANTAG.EXE"],
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
        inp.move_to(205, 125)
        inp.click()
        time.sleep(1.2)

        anchor = re4.find_unique_runtime_anchor(proc.pid)
        snapshot = re4.snapshot_anchor_map(proc.pid, anchor)
        record_offset = find_named_planet_record(snapshot)
        record_host = anchor["map_start"] + record_offset
        initial = sample_record(proc.pid, record_host)
        if initial["owner_0x57"] != "00" or initial["action_0x54"] != "ff" or initial["slot_0x52"] != "ffff":
            raise RE5Error(f"unexpected initial Xerxes state: {initial}")

        mode_toggle_ms = arm_planet_mode(proc.pid, record_host, inp, spec.managed)
        armed = sample_record(proc.pid, record_host)
        expected_state = re4.MANAGED.hex() if spec.managed else re4.MANUAL.hex()
        if armed["managed_0x5a"] != expected_state:
            raise RE5Error(f"failed to arm {spec.name}: {armed}")

        if spec.patch is not None:
            patch_record = checked_apply_patch(proc.pid, anchor, spec.patch)
            patch_applied = True

        inp.key("Escape")
        time.sleep(0.5)
        inp.key("Escape")
        time.sleep(0.8)
        inp.move_to(593, 68)
        inp.click()  # fast-forward
        trace = monitor_turn(proc.pid, record_host, timeout)
        inp.click()  # stop fast-forward before restore
        time.sleep(0.15)
        validate_scenario(spec, trace)

        if spec.patch is not None:
            checked_restore_patch(proc.pid, anchor, spec.patch)
            patch_applied = False
            restore_verified = True
            assert patch_record is not None
            patch_record["restored_original_bytes"] = True

        return {
            "name": spec.name,
            "status": "passed",
            "mode": "Managed" if spec.managed else "Manual",
            "dosbox_cpu_core": "normal",
            "planet": PLANET_NAME,
            "runtime_anchor": {
                "mapping_size": anchor["map_size"],
                "anchor_offset_in_mapping": anchor["anchor_offset"],
                "host_addresses_omitted": True,
            },
            "record": {
                "record_size": re4.RECORD_SIZE,
                "name_offset": re4.NAME_OFFSET,
                "owner_offset": OWNER_OFFSET,
                "slot_offset": SLOT_OFFSET,
                "action_offset": ACTION_OFFSET,
                "managed_offset": re4.STATE_OFFSET,
            },
            "initial": initial,
            "armed": armed,
            "mode_toggle_observation_ms": None if mode_toggle_ms is None else round(mode_toggle_ms, 3),
            "diagnostic_patch": patch_record,
            "turn_trace": trace,
            "process_alive_after_trace": proc.poll() is None,
            "diagnostic_patch_restore_verified": restore_verified,
        }
    finally:
        rollback_error: Exception | None = None
        if proc is not None and proc.poll() is None and patch_applied and spec.patch is not None and anchor is not None:
            try:
                checked_restore_patch(proc.pid, anchor, spec.patch)
            except Exception as exc:  # pragma: no cover - catastrophic cleanup
                rollback_error = exc
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
        if rollback_error is not None:
            raise RE5Error(f"diagnostic patch rollback failed during cleanup: {rollback_error}")


def summarize_causality(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_name = {item["name"]: item for item in results}
    if set(by_name) != {spec.name for spec in SCENARIOS} or any(item.get("status") != "passed" for item in results):
        raise RE5Error("cannot summarize incomplete RE5 scenario set")
    return {
        "manual_stays_idle": by_name["manual-control"]["turn_trace"]["first_action_change_ms"] is None,
        "managed_commits_action": by_name["managed-control"]["turn_trace"]["first_action_change_ms"] is not None,
        "gate_policy_call_is_necessary": by_name["managed-policy-suppressed"]["turn_trace"]["first_action_change_ms"] is None,
        "selection_survives_action_write_suppression": by_name["managed-action-write-suppressed"]["turn_trace"]["first_slot_change_ms"] is not None,
        "action_write_is_commit_seam": by_name["managed-action-write-suppressed"]["turn_trace"]["first_action_change_ms"] is None,
        "m1_preservation_seam": (
            "preserve legacy nonzero planet+0x5a gate semantics before static 0x3c118; "
            "leave downstream 0x3d8f0 policy and 0x34b0c mutation unchanged"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--dosbox", required=True)
    parser.add_argument("--fixture-manifest", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--window-seconds", type=float, default=DEFAULT_WINDOW_SECONDS)
    parser.add_argument(
        "--scenario",
        choices=("all",) + tuple(spec.name for spec in SCENARIOS),
        default="all",
        help="Complete four-scenario set by default; focused modes are for diagnosis/retry.",
    )
    args = parser.parse_args()
    root = args.game_dir.resolve()
    if not root.is_dir():
        parser.error("game-dir must exist")
    if args.window_seconds <= 0 or args.window_seconds > 30:
        parser.error("window-seconds must be > 0 and <= 30")
    for tool in (args.dosbox, "Xvfb", "xwininfo"):
        if shutil.which(tool) is None and not Path(tool).is_file():
            parser.error(f"required tool not found: {tool}")
    fixture = verify_runtime_input(root, args.fixture_manifest.resolve())
    args.artifacts.mkdir(parents=True, exist_ok=True)

    selected = list(SCENARIOS) if args.scenario == "all" else [next(spec for spec in SCENARIOS if spec.name == args.scenario)]
    result: dict[str, Any] = {
        "schema": 1,
        "roadmap_item": "RE5",
        "blind_re_provenance": "clean",
        "evidence_class": "runtime",
        "target": {"filename": "ANTAG.EXE", "size": re4.TARGET_SIZE, "sha256": re4.TARGET_SHA256},
        "fixture": fixture,
        "window_seconds": args.window_seconds,
        "diagnostic_runtime_patches_are_process_memory_only": True,
        "scenarios": [],
    }
    try:
        for spec in selected:
            scenario_result = run_scenario(root, args.dosbox, args.window_seconds, spec)
            result["scenarios"].append(scenario_result)
            print(f"RE5 {spec.name}: PASS")
        if args.scenario == "all":
            result["causality"] = summarize_causality(result["scenarios"])
        result["status"] = "passed"
    except Exception as exc:
        result["status"] = "failed"
        result["failure"] = f"{type(exc).__name__}: {exc}"
    (args.artifacts / "run.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if result["status"] != "passed":
        print(f"RE5: FAIL: {result['failure']}")
        return 1
    if args.scenario == "all":
        print("RE5 causal turn path: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
