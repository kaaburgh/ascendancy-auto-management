import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_re5_override_witness.py"
SPEC = importlib.util.spec_from_file_location("run_re5_override_witness", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
witness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(witness)


class RE5OverrideWitnessTests(unittest.TestCase):
    def test_uniform_bias_is_derived_from_all_signatures(self):
        anchor_offset = 100
        observations = [
            (
                0x90895,
                [anchor_offset + (0x90895 - witness.ANCHOR_VA) - 0xD000],
            ),
            (
                0x998BA,
                [anchor_offset + (0x998BA - witness.ANCHOR_VA) - 0xD000],
            ),
        ]
        self.assertEqual(witness.infer_uniform_bias(anchor_offset, observations), -0xD000)

    def test_bias_rejects_missing_signature(self):
        with self.assertRaises(witness.OverrideWitnessError):
            witness.infer_uniform_bias(0, [(0x90895, [])])

    def test_bias_rejects_ambiguous_signature(self):
        with self.assertRaises(witness.OverrideWitnessError):
            witness.infer_uniform_bias(0, [(0x90895, [1, 2])])

    def test_bias_rejects_inconsistent_signatures(self):
        with self.assertRaises(witness.OverrideWitnessError):
            witness.infer_uniform_bias(0, [(0x90895, [10]), (0x90EB8, [20])])

    @staticmethod
    def trace(sample_count=220, override=0, stardate=10, gap_ms=25.0):
        base = {
            "owner_0x57": 0,
            "slot_0x52": "ffff",
            "action_0x54": "ff",
            "managed_0x5a": "00000000",
            "override_0xa0d00": override,
            "current_player_id_0x104bea": 0,
            "stardate": stardate,
        }
        samples = []
        for index in range(sample_count):
            current = base.copy()
            current["stardate"] = stardate + index // 10
            current["t_ms"] = index * gap_ms
            samples.append(current)
        after = base.copy()
        after["stardate"] = stardate + 25
        return base, samples, after

    def test_evaluate_accepts_progressing_manual_zero_override_trace(self):
        before, samples, after = self.trace()
        self.assertEqual(witness.evaluate(before, samples, after)["status"], "passed")

    def test_evaluate_rejects_nonzero_override_sample(self):
        before, samples, after = self.trace()
        samples[50]["override_0xa0d00"] = 0xFFFFFFFF
        self.assertEqual(witness.evaluate(before, samples, after)["status"], "failed")

    def test_evaluate_rejects_insufficient_progress(self):
        before, samples, after = self.trace()
        after["stardate"] = before["stardate"] + witness.MIN_STARDATE_DELTA - 1
        result = witness.evaluate(before, samples, after)
        self.assertFalse(result["checks"]["stardate_progress_target_met"])

    def test_evaluate_rejects_sampling_gap_over_bound(self):
        before, samples, after = self.trace(gap_ms=witness.MAX_SAMPLE_GAP_MS + 1.0)
        result = witness.evaluate(before, samples, after)
        self.assertFalse(result["checks"]["max_sample_gap_within_bound"])


if __name__ == "__main__":
    unittest.main()
