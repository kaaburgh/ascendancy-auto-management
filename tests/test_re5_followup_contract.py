from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import re5_followup_model as model
import run_re5_runtime_turn_path_followup_capture as followup


class RE5FollowupContractTests(unittest.TestCase):
    TARGET = {"filename": "ANTAG.EXE", "size": 610863, "sha256": model.re4.TARGET_SHA256}
    FIXTURE = {"id": "fixture", "resume": {"sha256": model.legacy.RESUME_SHA256}}

    def spec(self, name: str) -> model.ScenarioSpec:
        return model.spec_by_name(name)

    def trace(self, spec: model.ScenarioSpec, *, progress=10, marker=False, slot=None, action=None, final="ff") -> dict:
        return {
            "observation_policy": model.observation_policy(spec),
            "actual_observation_ms": 7000.0,
            "stop_reason": "fixed_window" if spec.stop_policy == model.STOP_FIXED_WINDOW else "progress_target",
            "first_slot_change_ms": slot,
            "first_action_change_ms": action,
            "marker_seen": marker,
            "first_marker_ms": 26.0 if marker else None,
            "final_action": final,
            "turn_progress": {
                "delta": progress,
                "progress_target": spec.progress_target,
                "progress_target_met": spec.progress_target is not None and progress >= spec.progress_target,
            },
            "collateral": {"collateral_pair_closed": False, "bracket_closed": False},
            "final": {
                "owner_0x57": "00",
                "slot_0x52": "ffff" if slot is None else "3400",
                "action_0x54": final,
                "managed_0x5a": "ffffffff" if spec.managed else "00000000",
            },
        }

    def scenario_result(self, spec: model.ScenarioSpec) -> dict:
        if spec.name == "manual-control":
            trace = self.trace(spec)
        elif spec.name == "manual-gate-probe":
            trace = self.trace(spec, progress=4)
        elif spec.name == "managed-gate-probe":
            trace = self.trace(spec, progress=1, marker=True, action=26.0)
        elif spec.name == "managed-control":
            trace = self.trace(spec, slot=4000.0, action=4010.0, final="00")
        elif spec.name == "managed-policy-suppressed":
            trace = self.trace(spec)
        else:
            trace = self.trace(spec, slot=4800.0)
        return {
            "name": spec.name,
            "status": "passed",
            "scenario_contract": spec.scenario_contract,
            "observation_policy": model.observation_policy(spec),
            "turn_trace": trace,
        }

    def test_stop_policies_and_manual_priority(self):
        self.assertIsNone(model.stop_reason_for_sample(
            self.spec("managed-gate-probe"), action_changed=True, bracket_closed=True, progress_delta=200
        ))
        manual = self.spec("manual-gate-probe")
        self.assertEqual(model.stop_reason_for_sample(
            manual, action_changed=False, bracket_closed=True, progress_delta=4
        ), "bracket_closed")
        self.assertEqual(model.stop_reason_for_sample(
            manual, action_changed=False, bracket_closed=False, progress_delta=4
        ), "progress_target")

    def test_first_observation_keeps_first_value(self):
        first = model.first_observation_ms(None, True, 26.0)
        self.assertEqual(model.first_observation_ms(first, True, 7000.0), 26.0)

    def test_manual_fallback_requires_four_progress_units(self):
        spec = self.spec("manual-gate-probe")
        self.assertFalse(spec.require_collateral_bracket)
        model.validate_scenario(spec, self.trace(spec, progress=4))
        with self.assertRaises(model.RE5FollowupError):
            model.validate_scenario(spec, self.trace(spec, progress=3))

    def test_manual_timeout_is_inconclusive_and_keeps_trace_semantics(self):
        spec = self.spec("manual-gate-probe")
        trace = self.trace(spec, progress=2)
        trace["stop_reason"] = "timeout"
        status, failure = followup.classify_observation(spec, trace)
        self.assertEqual(status, "inconclusive")
        self.assertIn("progress target", failure)

    def test_managed_probe_uses_ever_seen_event_not_final_state(self):
        spec = self.spec("managed-gate-probe")
        model.validate_scenario(spec, self.trace(spec, progress=200, marker=True, action=26.0, final="ff"))
        with self.assertRaises(model.RE5FollowupError):
            model.validate_scenario(spec, self.trace(spec, progress=200, marker=False, final="ff"))

    def test_manual_event_overturns_negative_oracle(self):
        spec = self.spec("manual-gate-probe")
        with self.assertRaises(model.RE5FollowupError):
            model.validate_scenario(spec, self.trace(spec, progress=4, marker=True, action=65.0))

    def write_set(self, artifacts: Path, *, mutate=None) -> None:
        for index, spec in enumerate(model.SCENARIOS):
            scenario = self.scenario_result(spec)
            record = {
                "artifact_schema": model.RESULT_SCHEMA,
                "runner_revision": f"{index + 1:040x}",
                "scenario_contract": spec.scenario_contract,
                "observation_policy": model.observation_policy(spec),
                "status": "passed",
                "target": self.TARGET,
                "fixture": self.FIXTURE,
                "scenarios": [scenario],
            }
            if mutate:
                mutate(spec, record)
            model.focused_result_path(artifacts, spec.name).write_text(json.dumps(record), encoding="utf-8")

    def test_aggregate_accepts_per_scenario_windows_and_revisions(self):
        with tempfile.TemporaryDirectory() as td:
            artifacts = Path(td)
            self.write_set(artifacts)
            result = model.aggregate_focused_results(artifacts, {"target": self.TARGET, "fixture": self.FIXTURE})
            self.assertIsNotNone(result)
            manual = next(row for row in result["source_artifacts"] if row["scenario"] == "manual-gate-probe")
            self.assertEqual(manual["observation_policy"]["max_window_seconds"], 30.0)

    def test_aggregate_rejects_unknown_contract_and_policy(self):
        def bad_contract(spec, record):
            if spec.name == "manual-gate-probe":
                record["scenario_contract"] = "re5/manual-gate-probe/v999"
        with tempfile.TemporaryDirectory() as td:
            artifacts = Path(td)
            self.write_set(artifacts, mutate=bad_contract)
            with self.assertRaises(model.RE5FollowupError):
                model.aggregate_focused_results(artifacts, {"target": self.TARGET, "fixture": self.FIXTURE})

        def bad_policy(spec, record):
            if spec.name == "manual-gate-probe":
                record["observation_policy"] = {**record["observation_policy"], "max_window_seconds": 7.0}
        with tempfile.TemporaryDirectory() as td:
            artifacts = Path(td)
            self.write_set(artifacts, mutate=bad_policy)
            with self.assertRaises(model.RE5FollowupError):
                model.aggregate_focused_results(artifacts, {"target": self.TARGET, "fixture": self.FIXTURE})


if __name__ == "__main__":
    unittest.main()
