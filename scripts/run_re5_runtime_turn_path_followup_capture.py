#!/usr/bin/env python3
"""Preserve complete RE5 follow-up traces for planned inconclusive outcomes.

The runtime experiment itself is implemented by run_re5_runtime_turn_path_followup.
This entry point only changes result classification/reporting so a Manual probe
that reaches its hard timeout with positive progress but below the target keeps
its complete trace as `inconclusive` instead of losing it behind an exception.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any

import re5_followup_model as model
import run_re5_runtime_turn_path_followup as base


_ORIGINAL_VALIDATE = model.validate_scenario


def classify_observation(spec: model.ScenarioSpec, trace: dict[str, Any]) -> tuple[str, str | None]:
    try:
        _ORIGINAL_VALIDATE(spec, trace)
    except model.RE5FollowupError as exc:
        if (
            spec.name == "manual-gate-probe"
            and trace.get("stop_reason") == "timeout"
            and not trace.get("marker_seen", False)
            and trace.get("turn_progress", {}).get("delta", 0) > 0
            and not trace.get("turn_progress", {}).get("progress_target_met", False)
        ):
            return "inconclusive", str(exc)
        return "failed", str(exc)
    return "passed", None


def run_scenario(root: Path, dosbox: str, spec: model.ScenarioSpec) -> dict[str, Any]:
    captured: dict[str, str | None] = {}
    original_validate = _ORIGINAL_VALIDATE

    def validate_and_capture(inner_spec: model.ScenarioSpec, trace: dict[str, Any]) -> None:
        status, failure = classify_observation(inner_spec, trace)
        if status == "failed":
            original_validate(inner_spec, trace)
        if status == "inconclusive":
            captured["status"] = status
            captured["failure"] = failure

    model.validate_scenario = validate_and_capture
    try:
        result = base.run_scenario(root, dosbox, spec)
    finally:
        model.validate_scenario = original_validate
    if captured:
        result["status"] = captured["status"]
        result["oracle_failure"] = captured["failure"]
    return result


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

    fixture = base.legacy.verify_runtime_input(root, args.fixture_manifest.resolve())
    revision = model.resolve_runner_revision(args.runner_revision, Path(__file__).resolve().parents[1])
    args.artifacts.mkdir(parents=True, exist_ok=True)
    selected = list(model.SCENARIOS) if args.scenario == "all" else [model.spec_by_name(args.scenario)]
    result: dict[str, Any] = {
        "artifact_schema": model.RESULT_SCHEMA,
        "runner_revision": revision,
        "roadmap_item": "RE5",
        "blind_re_provenance": "clean",
        "evidence_class": "runtime",
        "target": {
            "filename": "ANTAG.EXE",
            "size": base.re4.TARGET_SIZE,
            "sha256": base.re4.TARGET_SHA256,
        },
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
            scenario = run_scenario(root, args.dosbox, spec)
            result["scenarios"].append(scenario)
            if scenario["status"] != "passed":
                result["status"] = scenario["status"]
                result["failure"] = scenario.get("oracle_failure")
                break
        else:
            if args.scenario == "all":
                result["causality"] = model.summarize_causality(result["scenarios"])
            result["status"] = "passed"
    except Exception as exc:
        result["status"] = "failed"
        result["failure"] = f"{type(exc).__name__}: {exc}"

    output = args.artifacts / "run.json" if args.scenario == "all" else model.focused_result_path(args.artifacts, args.scenario)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if result["status"] != "passed":
        print(f"RE5 follow-up: {result['status'].upper()}: {result['failure']}")
        return 1
    if args.scenario != "all":
        aggregate = model.aggregate_focused_results(args.artifacts, {"target": result["target"], "fixture": result["fixture"]})
        if aggregate is not None:
            print("RE5 follow-up focused artifacts aggregated: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
