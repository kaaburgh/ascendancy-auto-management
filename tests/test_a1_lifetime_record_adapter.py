from __future__ import annotations

import unittest

from scripts.a1_lifetime_record_adapter import (
    A1LifetimeRecordAdapterError,
    adapt_transcript,
)
from scripts.a1_lifetime_observer_core import TRANSCRIPT_SCHEMA
from scripts.a1_sidecar_lifetime_oracle import validate_record


def _witness(digest: str) -> dict:
    return {
        "scenario_planet": "A",
        "metadata_basis": "bounded-record-metadata",
        "record_offset": 8,
        "length": 8,
        "metadata_sha256": digest,
    }


def _point(step: str, phase: str, logical: str, pointer: int, digest: str) -> dict:
    witness = _witness(digest)
    witness["scenario_planet"] = logical
    return {
        "step": step,
        "logical_record": logical,
        "phase": phase,
        "record_pointer": pointer,
        "population_replacement": False,
        "managed_field_value": 0,
        "qualified_witness": witness,
        "attempt": 1,
    }


def _complete_transcript() -> dict:
    a = "a" * 64
    b = "b" * 64
    c = "c" * 64
    d = "d" * 64
    return {
        "schema": TRANSCRIPT_SCHEMA,
        "status": "complete",
        "steps": [
            _point("control-a1", "selection-control", "A", 100, a),
            _point("control-b", "selection-control", "B", 200, b),
            _point("control-a2", "selection-control", "A", 100, a),
            _point("ng-pre", "pre-replacement", "A", 100, a),
            {
                "step": "ng",
                "mechanism": "new-game-reset",
                "lifecycle_signal": {
                    "name": "epoch",
                    "before": 1,
                    "after": 2,
                    "changed_before_post_qualification": True,
                },
            },
            _point("ng-post", "post-replacement", "C", 300, c),
            _point("sl-pre", "pre-replacement", "C", 300, c),
            {
                "step": "sl",
                "mechanism": "save-load-replacement",
                "lifecycle_signal": {
                    "name": "epoch",
                    "before": 2,
                    "after": 3,
                    "changed_before_post_qualification": True,
                },
            },
            _point("sl-post", "post-replacement", "D", 400, d),
        ],
        "replacement_legs": [
            {
                "mechanism": "new-game-reset",
                "pre_step": "ng-pre",
                "replace_step": "ng",
                "post_step": "ng-post",
                "pre_record_pointer": 100,
                "post_record_pointer": 300,
                "pre_logical_record": "A",
                "post_logical_record": "C",
                "pointer_reused_after_replacement": False,
                "lifecycle_signal": {
                    "name": "epoch",
                    "before": 1,
                    "after": 2,
                    "changed_before_post_qualification": True,
                },
            },
            {
                "mechanism": "save-load-replacement",
                "pre_step": "sl-pre",
                "replace_step": "sl",
                "post_step": "sl-post",
                "pre_record_pointer": 300,
                "post_record_pointer": 400,
                "pre_logical_record": "C",
                "post_logical_record": "D",
                "pointer_reused_after_replacement": False,
                "lifecycle_signal": {
                    "name": "epoch",
                    "before": 2,
                    "after": 3,
                    "changed_before_post_qualification": True,
                },
            },
        ],
    }


class A1LifetimeRecordAdapterTests(unittest.TestCase):
    def test_complete_transcript_projects_coverage_but_never_positive_claim(self) -> None:
        record = adapt_transcript(_complete_transcript())

        self.assertEqual(record["outcome"], "incomplete-harness")
        self.assertTrue(record["control"]["passed"])
        self.assertEqual(
            {step["label"] for step in record["transitions"]},
            {"selection-control", "new-game-reset", "save-load-replacement"},
        )
        verdict = validate_record(record)
        self.assertTrue(verdict["coverage_complete"])
        self.assertFalse(verdict["positive_contract_accepted"])
        self.assertTrue(all(value is False for value in record["claims"].values()))

    def test_incomplete_transcript_stays_incomplete_and_preserves_error(self) -> None:
        transcript = {
            "schema": TRANSCRIPT_SCHEMA,
            "status": "incomplete-harness",
            "steps": [],
            "replacement_legs": [],
            "error": "qualification failed",
        }
        record = adapt_transcript(transcript)

        self.assertEqual(record["outcome"], "incomplete-harness")
        self.assertFalse(record["control"]["passed"])
        self.assertEqual(record["observer_transcript"]["error"], "qualification failed")
        verdict = validate_record(record)
        self.assertFalse(verdict["coverage_complete"])
        self.assertFalse(verdict["positive_contract_accepted"])

    def test_unsupported_schema_is_rejected(self) -> None:
        transcript = _complete_transcript()
        transcript["schema"] = "ascendancy.a1-lifetime-observer-transcript/v999"
        with self.assertRaisesRegex(A1LifetimeRecordAdapterError, "unsupported or missing"):
            adapt_transcript(transcript)

    def test_complete_transcript_requires_both_replacement_mechanisms(self) -> None:
        transcript = _complete_transcript()
        transcript["replacement_legs"][1]["mechanism"] = "new-game-reset"
        with self.assertRaisesRegex(A1LifetimeRecordAdapterError, "cover new-game-reset"):
            adapt_transcript(transcript)

    def test_complete_transcript_revalidates_selection_control(self) -> None:
        transcript = _complete_transcript()
        transcript["steps"][2]["record_pointer"] = 999
        with self.assertRaisesRegex(A1LifetimeRecordAdapterError, "first record pointer"):
            adapt_transcript(transcript)

    def test_replacement_leg_must_reference_existing_step_sequence(self) -> None:
        transcript = _complete_transcript()
        transcript["replacement_legs"][0]["pre_step"] = "missing-step"
        with self.assertRaisesRegex(A1LifetimeRecordAdapterError, "references missing transcript step"):
            adapt_transcript(transcript)

    def test_replacement_leg_must_match_step_stream_fields(self) -> None:
        transcript = _complete_transcript()
        transcript["replacement_legs"][0]["post_record_pointer"] = 999
        with self.assertRaisesRegex(A1LifetimeRecordAdapterError, "post_record_pointer"):
            adapt_transcript(transcript)

    def test_replacement_leg_must_match_action_lifecycle_signal(self) -> None:
        transcript = _complete_transcript()
        transcript["replacement_legs"][0]["lifecycle_signal"]["after"] = 99
        with self.assertRaisesRegex(A1LifetimeRecordAdapterError, "lifecycle_signal"):
            adapt_transcript(transcript)

    def test_replacement_leg_requires_consecutive_pre_action_post_steps(self) -> None:
        transcript = _complete_transcript()
        transcript["steps"].insert(5, _point("interloper", "pre-replacement", "Z", 500, "e" * 64))
        with self.assertRaisesRegex(A1LifetimeRecordAdapterError, "consecutive pre/action/post"):
            adapt_transcript(transcript)

    def test_transcript_cannot_smuggle_positive_outcome(self) -> None:
        transcript = _complete_transcript()
        transcript["outcome"] = "positive-epoch-pointer"
        transcript["claims"] = {"epoch_boundary_established": True}
        record = adapt_transcript(transcript)
        self.assertEqual(record["outcome"], "incomplete-harness")
        self.assertFalse(record["claims"]["epoch_boundary_established"])


if __name__ == "__main__":
    unittest.main()
