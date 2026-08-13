"""Pure evidence/oracle model for the RE5 gate-probe follow-up.

This module intentionally contains no process-memory writes. Runtime diagnostics
reuse the already reviewed RE5 primitives in run_re5_runtime_turn_path.py.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

import run_re5_runtime_turn_path as legacy

re4 = legacy.re4

DEFAULT_WINDOW_SECONDS = 7.0
MANUAL_GATE_MAX_WINDOW_SECONDS = 30.0
MANUAL_GATE_PROGRESS_TARGET = 4
RESULT_SCHEMA = 3
RUNNER_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
STOP_FIRST_ACTION = "first_action"
STOP_FIXED_WINDOW = "fixed_window"
STOP_PROGRESS_TARGET_OR_TIMEOUT = "progress_target_or_timeout"


class RE5FollowupError(legacy.RE5Error):
    pass


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    managed: bool
    patch: legacy.PatchPlan | None
    stop_policy: str
    max_window_seconds: float
    progress_target: int | None
    scenario_contract: str
    require_collateral_bracket: bool = False


SCENARIOS = (
    ScenarioSpec("manual-control", False, None, STOP_FIRST_ACTION, DEFAULT_WINDOW_SECONDS, None, "re5/manual-control/v1"),
    ScenarioSpec(
        "manual-gate-probe", False, legacy.GATE_REACHABILITY_PROBE, STOP_PROGRESS_TARGET_OR_TIMEOUT,
        MANUAL_GATE_MAX_WINDOW_SECONDS, MANUAL_GATE_PROGRESS_TARGET, "re5/manual-gate-probe/v3", False,
    ),
    ScenarioSpec(
        "managed-gate-probe", True, legacy.GATE_REACHABILITY_PROBE, STOP_FIXED_WINDOW,
        DEFAULT_WINDOW_SECONDS, None, "re5/managed-gate-probe/v3",
    ),
    ScenarioSpec("managed-control", True, None, STOP_FIRST_ACTION, DEFAULT_WINDOW_SECONDS, None, "re5/managed-control/v1"),
    ScenarioSpec(
        "managed-policy-suppressed", True, legacy.POLICY_SUPPRESSION, STOP_FIRST_ACTION,
        DEFAULT_WINDOW_SECONDS, None, "re5/managed-policy-suppressed/v1",
    ),
    ScenarioSpec(
        "managed-action-write-suppressed", True, legacy.ACTION_WRITE_SUPPRESSION, STOP_FIRST_ACTION,
        DEFAULT_WINDOW_SECONDS, None, "re5/managed-action-write-suppressed/v1",
    ),
)


ACCEPTED_SCENARIO_CONTRACTS = {
    spec.name: {spec.scenario_contract} for spec in SCENARIOS
}
# The already captured managed-gate-probe/v2 artifact used a stricter collateral
# precondition (+0x54 == ff at monitor start) and therefore remains valid under
# the relaxed v3 supplemental-telemetry contract. Runner revision is provenance,
# not an automatic compatibility discriminator.
ACCEPTED_SCENARIO_CONTRACTS["managed-gate-probe"].add("re5/managed-gate-probe/v2")


def spec_by_name(name: str) -> ScenarioSpec:
    return next(spec for spec in SCENARIOS if spec.name == name)


def observation_policy(spec: ScenarioSpec) -> dict[str, Any]:
    return {
        "stop_policy": spec.stop_policy,
        "max_window_seconds": spec.max_window_seconds,
        "progress_target": spec.progress_target,
    }


def resolve_runner_revision(explicit: str | None, repo_root: Path) -> str:
    candidate = explicit or os.environ.get("RE5_RUNNER_REVISION")
    if candidate is None:
        try:
            candidate = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True, stderr=subprocess.DEVNULL
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            candidate = None
    if candidate is None or RUNNER_REVISION_RE.fullmatch(candidate) is None:
        raise RE5FollowupError(
            "runner revision must be an exact 40-hex git SHA via --runner-revision, RE5_RUNNER_REVISION, or git"
        )
    return candidate


BRACKET_NAME_FIELD_SIZE = 0x20
# Phase -1 on the exact pinned resume established that immediate +/-1 records
# are structurally valid but unowned (owner ff). They cannot witness the
# owner-gated 0x3c118 path. These nearest *owned* records on either side are
# therefore supplemental cross-race telemetry only, never a hard player-loop
# bracket. No array base/count is inferred.
EXPECTED_LOCAL_COLLATERAL = {
    "left": {"record_delta": -4, "name": "Stavern I", "owner": 0x01},
    "right": {"record_delta": 8, "name": "Hurble I", "owner": 0x05},
}


def decode_ascii_z_name(record: bytes) -> str:
    field = record[re4.NAME_OFFSET:re4.NAME_OFFSET + BRACKET_NAME_FIELD_SIZE]
    nul = field.find(b"\0")
    if nul <= 0:
        raise RE5FollowupError("planet record name is not non-empty NUL-terminated ASCII")
    raw = field[:nul]
    if any(byte < 0x20 or byte > 0x7E for byte in raw):
        raise RE5FollowupError("planet record name contains non-printable/non-ASCII bytes")
    return raw.decode("ascii")


def validate_local_collateral(snapshot: bytes, xerxes_offset: int) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for side, expected in EXPECTED_LOCAL_COLLATERAL.items():
        offset = xerxes_offset + expected["record_delta"] * re4.RECORD_SIZE
        if offset < 0 or offset + re4.RECORD_SIZE > len(snapshot):
            raise RE5FollowupError(f"{side} collateral record resolves outside runtime snapshot")
        record = snapshot[offset:offset + re4.RECORD_SIZE]
        name = decode_ascii_z_name(record)
        owner = record[legacy.OWNER_OFFSET]
        action = record[legacy.ACTION_OFFSET]
        if name != expected["name"] or owner != expected["owner"]:
            raise RE5FollowupError(
                f"{side} collateral record identity mismatch: expected {expected['name']!r}/owner "
                f"{expected['owner']:02x}, got {name!r}/owner {owner:02x}"
            )
        result[side] = {
            "record_delta": expected["record_delta"],
            "name": name,
            "owner_0x57": f"{owner:02x}",
            "initial_action_0x54": f"{action:02x}",
            "same_player_loop_hard_witness": False,
        }
    return result


def first_observation_ms(current: float | None, observed: bool, now_ms: float) -> float | None:
    return now_ms if current is None and observed else current


def update_collateral_seen(seen: set[str], actions: dict[str, int]) -> set[str]:
    updated = set(seen)
    updated.update(side for side, value in actions.items() if value == legacy.GATE_MARKER_ACTION)
    return updated


def stop_reason_for_sample(
    spec: ScenarioSpec, *, action_changed: bool, bracket_closed: bool, progress_delta: int
) -> str | None:
    if spec.stop_policy == STOP_FIRST_ACTION:
        return "first_action" if action_changed else None
    if spec.stop_policy == STOP_FIXED_WINDOW:
        return None
    if spec.stop_policy == STOP_PROGRESS_TARGET_OR_TIMEOUT:
        if bracket_closed and progress_delta > 0:
            return "bracket_closed"
        if spec.progress_target is not None and progress_delta >= spec.progress_target:
            return "progress_target"
        return None
    raise RE5FollowupError(f"unknown stop policy for {spec.name}: {spec.stop_policy}")


def validate_scenario(spec: ScenarioSpec, trace: dict[str, Any]) -> None:
    if trace.get("observation_policy") != observation_policy(spec):
        raise RE5FollowupError(f"{spec.name}: observation policy does not match scenario contract")
    first_slot = trace["first_slot_change_ms"]
    first_action = trace["first_action_change_ms"]
    final = trace["final"]
    expected_state = re4.MANAGED.hex() if spec.managed else re4.MANUAL.hex()
    if final["managed_0x5a"] != expected_state:
        raise RE5FollowupError(f"{spec.name}: +0x5a drifted from armed state")
    if spec.name in {"manual-control", "manual-gate-probe", "managed-policy-suppressed"}:
        if trace.get("turn_progress", {}).get("delta", 0) <= 0:
            raise RE5FollowupError(f"{spec.name}: stardate did not advance during negative observation")
    if spec.name == "manual-control":
        if first_slot is not None or first_action is not None:
            raise RE5FollowupError("manual-control unexpectedly selected or committed an automatic action")
    elif spec.name == "manual-gate-probe":
        if trace.get("marker_seen") or first_slot is not None or first_action is not None:
            raise RE5FollowupError("manual gate probe reached 0x3c118 despite +0x5a == 0")
        collateral = trace.get("collateral") or {}
        if spec.require_collateral_bracket:
            if not collateral.get("bracket_closed"):
                raise RE5FollowupError("manual gate probe did not close the two-sided collateral bracket")
        elif not trace.get("turn_progress", {}).get("progress_target_met", False):
            raise RE5FollowupError("manual gate probe lacks a hard bracket and did not reach progress target")
    elif spec.name == "managed-gate-probe":
        if not trace.get("marker_seen") or trace.get("first_marker_ms") is None:
            raise RE5FollowupError("managed gate probe did not observe the 0x3c118 marker write")
    elif spec.name == "managed-control":
        if first_slot is None or first_action is None or final["action_0x54"] == "ff":
            raise RE5FollowupError("managed-control did not select and commit an automatic action")
    elif spec.name == "managed-policy-suppressed":
        if first_slot is not None or first_action is not None:
            raise RE5FollowupError("policy suppression still allowed selection/action mutation")
    elif spec.name == "managed-action-write-suppressed":
        if first_slot is None:
            raise RE5FollowupError("action-write suppression saw no selection output at +0x52")
        if first_action is not None or final["action_0x54"] != "ff":
            raise RE5FollowupError("action-write suppression failed to keep +0x54 empty")
    else:
        raise RE5FollowupError(f"unhandled scenario {spec.name}")


def summarize_causality(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_name = {item["name"]: item for item in results}
    if set(by_name) != {spec.name for spec in SCENARIOS} or any(item.get("status") != "passed" for item in results):
        raise RE5FollowupError("cannot summarize incomplete RE5 scenario set")
    manual = by_name["manual-gate-probe"]["turn_trace"]
    managed = by_name["managed-gate-probe"]["turn_trace"]
    hard = spec_by_name("manual-gate-probe").require_collateral_bracket
    support = bool((manual.get("collateral") or {}).get("bracket_closed")) if hard else bool(
        manual["turn_progress"].get("progress_target_met", False)
    )
    return {
        "manual_turn_progress_witnessed": by_name["manual-control"]["turn_trace"]["turn_progress"]["delta"] > 0,
        "manual_gate_probe_turn_progress_witnessed": manual["turn_progress"]["delta"] > 0,
        "manual_gate_probe_progress_achieved": manual["turn_progress"]["delta"],
        "manual_gate_probe_progress_target": manual["turn_progress"].get("progress_target"),
        "manual_gate_probe_progress_target_met": manual["turn_progress"].get("progress_target_met", False),
        "manual_gate_probe_embedded_bracket_hard": hard,
        "manual_gate_probe_collateral_pair_closed": bool((manual.get("collateral") or {}).get("collateral_pair_closed")),
        "managed_gate_probe_stardate_delta": managed["turn_progress"]["delta"],
        "managed_gate_probe_first_marker_ms": managed.get("first_marker_ms"),
        "policy_suppressed_turn_progress_witnessed": by_name["managed-policy-suppressed"]["turn_trace"]["turn_progress"]["delta"] > 0,
        "manual_stays_idle": by_name["manual-control"]["turn_trace"]["first_action_change_ms"] is None,
        "manual_does_not_reach_gate_policy_call": not manual.get("marker_seen", False),
        "managed_reaches_gate_policy_call": bool(managed.get("marker_seen", False)),
        "override_path_inactive_for_manual_probe": (
            not manual.get("marker_seen", False) and bool(managed.get("marker_seen", False)) and support
        ),
        "managed_commits_action": by_name["managed-control"]["turn_trace"]["first_action_change_ms"] is not None,
        "gate_policy_call_is_necessary": by_name["managed-policy-suppressed"]["turn_trace"]["first_action_change_ms"] is None,
        "selection_survives_action_write_suppression": by_name["managed-action-write-suppressed"]["turn_trace"]["first_slot_change_ms"] is not None,
        "action_write_is_commit_seam": by_name["managed-action-write-suppressed"]["turn_trace"]["first_action_change_ms"] is None,
        "m1_preservation_seam": (
            "preserve legacy nonzero planet+0x5a gate semantics before static 0x3c118; "
            "leave downstream 0x3d8f0 policy and 0x34b0c mutation unchanged"
        ),
    }


def focused_result_path(artifacts: Path, scenario_name: str) -> Path:
    return artifacts / f"run-{scenario_name}.json"


def aggregate_focused_results(artifacts: Path, expected: dict[str, Any]) -> dict[str, Any] | None:
    paths = [focused_result_path(artifacts, spec.name) for spec in SCENARIOS]
    if not all(path.is_file() for path in paths):
        return None
    scenarios: list[dict[str, Any]] = []
    source_artifacts: list[dict[str, Any]] = []
    for spec, path in zip(SCENARIOS, paths):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("artifact_schema") != RESULT_SCHEMA:
            raise RE5FollowupError(f"focused artifact schema mismatch: {path.name}")
        record_contract = record.get("scenario_contract")
        if record_contract not in ACCEPTED_SCENARIO_CONTRACTS[spec.name]:
            raise RE5FollowupError(f"focused artifact scenario contract mismatch: {path.name}")
        revision = record.get("runner_revision")
        if not isinstance(revision, str) or RUNNER_REVISION_RE.fullmatch(revision) is None:
            raise RE5FollowupError(f"focused artifact runner revision missing/invalid: {path.name}")
        if record.get("observation_policy") != observation_policy(spec):
            raise RE5FollowupError(f"focused artifact observation policy mismatch: {path.name}")
        if record.get("status") != "passed" or record.get("target") != expected["target"] or record.get("fixture") != expected["fixture"]:
            raise RE5FollowupError(f"focused artifact identity/status mismatch: {path.name}")
        if len(record.get("scenarios", [])) != 1 or record["scenarios"][0].get("name") != spec.name:
            raise RE5FollowupError(f"focused artifact scenario mismatch: {path.name}")
        scenario = record["scenarios"][0]
        if scenario.get("status") != "passed" or scenario.get("scenario_contract") != record_contract:
            raise RE5FollowupError(f"focused artifact embedded contract/status mismatch: {path.name}")
        if scenario.get("observation_policy") != observation_policy(spec):
            raise RE5FollowupError(f"focused artifact embedded observation policy mismatch: {path.name}")
        try:
            validate_scenario(spec, scenario["turn_trace"])
        except (KeyError, TypeError, legacy.RE5Error) as exc:
            raise RE5FollowupError(f"focused artifact current-oracle validation failed: {path.name}: {exc}") from exc
        scenarios.append(scenario)
        source_artifacts.append({
            "filename": path.name,
            "scenario": spec.name,
            "scenario_contract": record_contract,
            "runner_revision": revision,
            "observation_policy": observation_policy(spec),
        })
    aggregate = {
        "artifact_schema": RESULT_SCHEMA,
        "roadmap_item": "RE5",
        "blind_re_provenance": "clean",
        "evidence_class": "runtime",
        "target": expected["target"],
        "fixture": expected["fixture"],
        "diagnostic_runtime_patches_are_process_memory_only": True,
        "source_artifacts": source_artifacts,
        "scenarios": scenarios,
        "causality": summarize_causality(scenarios),
        "status": "passed",
    }
    (artifacts / "run-aggregate.json").write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return aggregate
