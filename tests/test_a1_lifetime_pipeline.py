import json
import unittest
from pathlib import Path

from scripts.run_a1_lifetime_pipeline import run_synthetic_pipeline


ARTIFACT = Path("docs/experiments/A1-synthetic-lifetime-record.json")


class A1LifetimePipelineTests(unittest.TestCase):
    def test_synthetic_entry_point_runs_plan_execute_adapt_validate(self):
        record = run_synthetic_pipeline()
        self.assertEqual(record["schema"], "ascendancy.a1-sidecar-runtime-lifetime/v1")
        self.assertEqual(record["outcome"], "incomplete-harness")
        self.assertTrue(record["control"]["passed"])
        self.assertEqual(
            [step["label"] for step in record["transitions"]],
            ["selection-control", "new-game-reset", "save-load-replacement"],
        )
        self.assertEqual(record["observer_transcript"]["status"], "complete")
        self.assertFalse(record["claims"]["manual_transition_invalidation_established"])

    def test_committed_synthetic_record_matches_entry_point(self):
        committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        self.assertEqual(committed, run_synthetic_pipeline())


if __name__ == "__main__":
    unittest.main()
