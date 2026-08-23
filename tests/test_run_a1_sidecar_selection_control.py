from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_a1_sidecar_selection_control as control  # noqa: E402


class A1SelectionControlTests(unittest.TestCase):
    @staticmethod
    def point(label: str, pointer: int, digest: str) -> dict[str, object]:
        return {
            "logical_record": label,
            "record_pointer": pointer,
            "qualified_witness": {"metadata_sha256": digest},
        }

    def test_accepts_a_b_a_with_stable_first_pointer_and_witness(self) -> None:
        result = control.evaluate_selection_control([
            self.point("A", 0x1000, "a" * 64),
            self.point("B", 0x2000, "b" * 64),
            self.point("A", 0x1000, "a" * 64),
        ])
        self.assertTrue(result["passed"])
        self.assertFalse(result["population_replacement_observed"])

    def test_rejects_pointer_alias_between_distinct_records(self) -> None:
        with self.assertRaisesRegex(control.A1SelectionControlError, "same record pointer"):
            control.evaluate_selection_control([
                self.point("A", 0x1000, "a" * 64),
                self.point("B", 0x1000, "b" * 64),
                self.point("A", 0x1000, "a" * 64),
            ])

    def test_rejects_first_record_pointer_change(self) -> None:
        with self.assertRaisesRegex(control.A1SelectionControlError, "pointer changed"):
            control.evaluate_selection_control([
                self.point("A", 0x1000, "a" * 64),
                self.point("B", 0x2000, "b" * 64),
                self.point("A", 0x3000, "a" * 64),
            ])

    def test_rejects_non_distinguishing_witness(self) -> None:
        with self.assertRaisesRegex(control.A1SelectionControlError, "does not distinguish"):
            control.evaluate_selection_control([
                self.point("A", 0x1000, "a" * 64),
                self.point("B", 0x2000, "a" * 64),
                self.point("A", 0x1000, "a" * 64),
            ])

    def test_qualified_witness_binds_exact_prefix_digest(self) -> None:
        record = bytes(range(control.WITNESS_SIZE)) + b"suffix"
        digest = control.sha256_bytes(record[: control.WITNESS_SIZE])
        witness = control._qualified_witness(record, 0, "A", {"A": digest})
        self.assertEqual(witness["metadata_offset"], 0)
        self.assertEqual(witness["metadata_size"], control.WITNESS_SIZE)
        self.assertEqual(witness["metadata_sha256"], digest)

    def test_qualified_witness_rejects_wrong_independent_digest(self) -> None:
        record = bytes(range(control.WITNESS_SIZE)) + b"suffix"
        with self.assertRaisesRegex(control.A1SelectionControlError, "does not match independent qualification"):
            control._qualified_witness(record, 0, "A", {"A": "0" * 64})


if __name__ == "__main__":
    unittest.main()
