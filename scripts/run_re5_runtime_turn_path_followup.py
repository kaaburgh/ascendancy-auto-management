#!/usr/bin/env python3
"""Run the RE5 v3 follow-up evidence experiment.

Low-level diagnostic patching is delegated to the existing reviewed RE5 runner.
This follow-up changes observation policy and evidence contracts only. Each run
still uses a fresh temporary retail tree and restores/re-verifies live-process
instruction bytes before teardown.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any

import run_re5_runtime_turn_path as legacy
import re5_followup_model as model

re4 = legacy.re4


def monitor_turn(
    pid: int,
    record_host: int,
    anchor: dict[str, Any],
    spec: model.ScenarioSpec,
    collateral: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    start = time.perf_counter()
    deadline = start + spec.max_window_seconds
    window_offset = 0x50
    window_size = 0x12
    stardate_address = legacy.anchor_delta_host(anchor, legacy.STARDATE_ANCHOR_DELTA, 4)
    probe = spec.patch == legacy.GATE_REACHABILITY_PROBE
    if probe != (collateral is not None):
        raise model.RE5FollowupError(f"{spec.name}: local collateral validation missing/unexpected")

    def coherent_sample() -> tuple[bytes, int, dict[str, int]]:
        # All fields in one sample are read while DOSBox is confirmed stopped.
        with legacy.stopped_process(pid):
            window = re4.read_process(pid, record_host + window_offset, window_size)
            stardate = int.from_bytes(re4.read_process(pid, stardate_address, 4), "little")
            actions: dict[str, int] = {}
            if collateral is not None:
                for side, item in collateral.items():
                    address = record_host + item["record_delta"] * re4.RECORD_SIZE + legacy.ACTION_OFFSET
                    actions[side] = re4.read_process(pid, address, 1)[0]
        return window, stardate, actions

    initial, initial_stardate, initial_collateral = coherent_sample()
    slot_index = legacy.SLOT_OFFSET - window_offset
    action_index = legacy.ACTION_OFFSET - window_offset
    state_index = re4.STATE_OFFSET - window_offset
    initial_slot = initial[slot_index:slot_index + 2]
    initial_action = initial[action_index]
    if initial_slot != legacy.NO_SLOT or initial_action != legacy.NO_ACTION:
        raise model.RE5FollowupError(
            f"scenario must start empty: +0x52={initial_slot.hex()} +0x54={initial_action:02x}"
        )
    first_slot_change_ms: float | None = None
    first_action_change_ms: float | None = None
    first_marker_ms: float | None = None
    marker_seen = False
    collateral_seen: set[str] = set()
    slot_values: list[str] = []
    previous_slot = initial_slot
    final_window = initial
    final_stardate = initial_stardate
    stop_reason: str | None = None

    while time.perf_counter() < deadline:
        final_window, final_stardate, collateral_actions = coherent_sample()
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
        first_action_change_ms = model.first_observation_ms(first_action_change_ms, action != legacy.NO_ACTION, now_ms)
        if action == legacy.GATE_MARKER_ACTION:
            marker_seen = True
            first_marker_ms = model.first_observation_ms(first_marker_ms, True, now_ms)
        collateral_seen = model.update_collateral_seen(collateral_seen, collateral_actions)

        progress_delta = final_stardate - initial_stardate
        pair_closed = probe and {"left", "right"}.issubset(collateral_seen)
        hard_bracket_closed = spec.require_collateral_bracket and pair_closed
        stop_reason = model.stop_reason_for_sample(
            spec,
            action_changed=action != legacy.NO_ACTION,
            bracket_closed=hard_bracket_closed,
            progress_delta=progress_delta,
        )
        if stop_reason is not None:
            break
        time.sleep(0.025)

    if stop_reason is None:
        stop_reason = "fixed_window" if spec.stop_policy == model.STOP_FIXED_WINDOW else "timeout"

    actual_ms = round((time.perf_counter() - start) * 1000.0, 3)
    progress_delta = final_stardate - initial_stardate
    collateral_result: dict[str, Any] | None = None
    if collateral is not None:
        pair_closed = {"left", "right"}.issubset(collateral_seen)
        collateral_result = {
            "static_stride_assumption": "RE3 gate loop walks planet records by +0x7b",
            "local_collateral_validated": True,
            "records": collateral,
            "initial_action_at_monitor": {side: f"{value:02x}" for side, value in initial_collateral.items()},
            "marker_seen_ever": {side: side in collateral_seen for side in ("left", "right")},
            "collateral_pair_closed": pair_closed,
            "hard_gate_oracle_eligible": spec.require_collateral_bracket,
            "bracket_closed": spec.require_collateral_bracket and pair_closed,
            "limitation": "records belong to other race owners; cross-race telemetry only",
        }

    return {
        "observation_policy": model.observation_policy(spec),
        "actual_observation_ms": actual_ms,
        "stop_reason": stop_reason,
        "first_slot_change_ms": None if first_slot_change_ms is None else round(first_slot_change_ms, 3),
        "first_action_change_ms": None if first_action_change_ms is None else round(first_action_change_ms, 3),
        "marker_seen": marker_seen,
        "first_marker_ms": None if first_marker_ms is None else round(first_marker_ms, 3),
        "final_action": f"{final_window[action_index]:02x}",
        "observed_slot_values": slot_values[:16],
        "sampling": {"process_paused_per_sample": True, "interval_ms": 25},
        "turn_progress": {
            "witness": "upper-right stardate dword",
            "anchor_delta": f"+0x{legacy.STARDATE_ANCHOR_DELTA:x}",
            "width": 4,
            "initial": initial_stardate,
            "final": final_stardate,
            "delta": progress_delta,
            "progress_target": spec.progress_target,
            "progress_target_met": spec.progress_target is not None and progress_delta >= spec.progress_target,
        },
        "collateral": collateral_result,
        "final": {
            "owner_0x57": final_window[legacy.OWNER_OFFSET - window_offset:legacy.OWNER_OFFSET - window_offset + 1].hex(),
            "slot_0x52": final_window[slot_index:slot_index + 2].hex(),
            "action_0x54": f"{final_window[action_index]:02x}",
            "managed_0x5a": final_window[state_index:state_index + 4].hex(),
        },
    }


def run_scenario(root: Path, dosbox: str, spec: model.ScenarioSpec) -> dict[str, Any]:
    print(f"RE5 follow-up {spec.name}: launching", flush=True)
    display = re4.choose_display()
    temp = tempfile.TemporaryDirectory(prefix=f"re5-v3-{spec.name}-")
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
        record_offset = legacy.find_named_planet_record(snapshot)
        record_host = anchor["map_start"] + record_offset
        collateral = (
            model.validate_local_collateral(snapshot, record_offset)
            if spec.patch == legacy.GATE_REACHABILITY_PROBE else None
        )
        initial = legacy.sample_record(proc.pid, record_host)
        if initial["owner_0x57"] != "00" or initial["action_0x54"] != "ff" or initial["slot_0x52"] != "ffff":
            raise model.RE5FollowupError(f"unexpected initial Xerxes state: {initial}")

        mode_toggle_ms = legacy.arm_planet_mode(proc.pid, record_host, inp, spec.managed)
        armed = legacy.sample_record(proc.pid, record_host)
        expected_state = re4.MANAGED.hex() if spec.managed else re4.MANUAL.hex()
        if armed["managed_0x5a"] != expected_state:
            raise model.RE5FollowupError(f"failed to arm {spec.name}: {armed}")

        if spec.patch is not None:
            patch_record = legacy.checked_apply_patch(proc.pid, anchor, spec.patch)
            patch_applied = True

        inp.key("Escape")
        time.sleep(0.5)
        inp.key("Escape")
        time.sleep(0.8)
        inp.move_to(593, 68)
        inp.click()
        trace = monitor_turn(proc.pid, record_host, anchor, spec, collateral)
        inp.click()
        time.sleep(0.15)
        model.validate_scenario(spec, trace)

        if spec.patch is not None:
            legacy.checked_restore_patch(proc.pid, anchor, spec.patch)
            patch_applied = False
            restore_verified = True
            assert patch_record is not None
            patch_record["restored_original_bytes"] = True

        return {
            "name": spec.name,
            "status": "passed",
            "mode": "Managed" if spec.managed else "Manual",
            "dosbox_cpu_core": "normal",
            "planet": legacy.PLANET_NAME,
            "scenario_contract": spec.scenario_contract,
            "observation_policy": model.observation_policy(spec),
            "runtime_anchor": {
                "mapping_size": anchor["map_size"],
                "anchor_offset_in_mapping": anchor["anchor_offset"],
                "host_addresses_omitted": True,
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
                legacy.checked_restore_patch(proc.pid, anchor, spec.patch)
            except Exception as exc:
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
            raise model.RE5FollowupError(f"diagnostic patch rollback failed during cleanup: {rollback_error}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--dosbox", required=True)
    parser.add_argument("--fixture-manifest", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--runner-revision")
    parser.add_argument("--scenario", choices=("all",) + tuple(spec.name for spec in model.SCENARIOS), default="all")
    args = parser.parse_args()
    root = args.game_dir.resolve()
    if not root.is_dir():
        parser.error("game-dir must exist")
    for tool in (args.dosbox, "Xvfb", "xwininfo"):
        if shutil.which(tool) is None and not Path(tool).is_file():
            parser.error(f"required tool not found: {tool}")

    fixture = legacy.verify_runtime_input(root, args.fixture_manifest.resolve())
    revision = model.resolve_runner_revision(args.runner_revision, Path(__file__).resolve().parents[1])
    args.artifacts.mkdir(parents=True, exist_ok=True)
    selected = list(model.SCENARIOS) if args.scenario == "all" else [model.spec_by_name(args.scenario)]
    result: dict[str, Any] = {
        "artifact_schema": model.RESULT_SCHEMA,
        "runner_revision": revision,
        "roadmap_item": "RE5",
        "blind_re_provenance": "clean",
        "evidence_class": "runtime",
        "target": {"filename": "ANTAG.EXE", "size": re4.TARGET_SIZE, "sha256": re4.TARGET_SHA256},
        "fixture": fixture,
        "diagnostic_runtime_patches_are_process_memory_only": True,
        "scenarios": [],
    }
    if len(selected) == 1:
        result["scenario_contract"] = selected[0].scenario_contract
        result["observation_policy"] = model.observation_policy(selected[0])
    else:
        result["scenario_contracts"] = {spec.name: spec.scenario_contract for spec in selected}
        result["observation_policies"] = {spec.name: model.observation_policy(spec) for spec in selected}
    try:
        for spec in selected:
            scenario_result = run_scenario(root, args.dosbox, spec)
            result["scenarios"].append(scenario_result)
            print(f"RE5 follow-up {spec.name}: PASS")
        if args.scenario == "all":
            result["causality"] = model.summarize_causality(result["scenarios"])
        result["status"] = "passed"
    except Exception as exc:
        result["status"] = "failed"
        result["failure"] = f"{type(exc).__name__}: {exc}"

    output = args.artifacts / "run.json" if args.scenario == "all" else model.focused_result_path(args.artifacts, args.scenario)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if result["status"] != "passed":
        print(f"RE5 follow-up: FAIL: {result['failure']}")
        return 1
    if args.scenario == "all":
        print("RE5 follow-up causal turn path: PASS")
    else:
        aggregate = model.aggregate_focused_results(args.artifacts, {"target": result["target"], "fixture": result["fixture"]})
        if aggregate is not None:
            print("RE5 follow-up focused artifacts aggregated: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
