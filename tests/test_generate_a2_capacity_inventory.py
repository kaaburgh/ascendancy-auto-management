#!/usr/bin/env python3
"""Synthetic coverage for scripts/generate_a2_capacity_inventory.py."""

from __future__ import annotations

import hashlib
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import generate_a2_capacity_inventory as capacity  # noqa: E402
import le_fixture  # noqa: E402
import le_image  # noqa: E402


class TestZeroRuns(unittest.TestCase):
    def test_finds_only_runs_at_or_above_threshold(self) -> None:
        data = b"A\x00\x00B\x00\x00\x00\x00C\x00\x00\x00"
        self.assertEqual([(4, 4), (9, 3)], capacity.find_zero_runs(data, 3))

    def test_trailing_run_is_kept(self) -> None:
        self.assertEqual([(1, 5)], capacity.find_zero_runs(b"X" + b"\x00" * 5, 5))

    def test_non_positive_threshold_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            capacity.find_zero_runs(b"\x00", 0)


class TestControlFlowReferences(unittest.TestCase):
    def test_direct_calls_and_branches_are_recorded(self) -> None:
        instructions = [
            (0x1000, 5, "call 0x1100"),
            (0x1005, 2, "jne 0x1200"),
            (0x1007, 5, "mov eax,0x1300"),
        ]
        self.assertEqual(
            [
                {"site": 0x1000, "target": 0x1100, "kind": "call"},
                {"site": 0x1005, "target": 0x1200, "kind": "branch"},
            ],
            capacity.direct_control_flow_references(instructions),
        )


class TestCliSafety(unittest.TestCase):
    def test_cli_cannot_override_canonical_target_hash(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            capacity.parse_args(
                ["target.le", "--expected-sha256", "0" * 64]
            )
        self.assertEqual(2, caught.exception.code)

    def test_output_cannot_alias_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = pathlib.Path(temp_dir) / "ANTAG_EN.EXE"
            target.write_bytes(b"immutable target bytes")
            with self.assertRaises(capacity.CapacityInventoryError) as caught:
                capacity.validate_output_path(target, target)
        self.assertIn("aliases immutable target input", str(caught.exception))

    def test_separate_output_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            target = root / "ANTAG_EN.EXE"
            target.write_bytes(b"immutable target bytes")
            capacity.validate_output_path(target, root / "artifacts" / "inventory.json")


class TestInventoryBoundary(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = le_fixture.build()
        self.image = le_image.LEImage(self.raw, "fixture.le")
        self.sha256 = hashlib.sha256(self.raw).hexdigest()

    def test_wrong_target_hash_fails_closed_before_disassembly(self) -> None:
        with self.assertRaises(capacity.CapacityInventoryError) as caught:
            capacity.build_inventory(
                self.image,
                expected_sha256="0" * 64,
                minimum_zero_run=16,
            )
        self.assertIn("target SHA-256 mismatch", str(caught.exception))

    def test_known_seam_outside_synthetic_image_fails_closed(self) -> None:
        with self.assertRaises(capacity.CapacityInventoryError) as caught:
            capacity.build_inventory(
                self.image,
                expected_sha256=self.sha256,
                minimum_zero_run=16,
            )
        self.assertIn("known seam", str(caught.exception))

    def test_file_spans_do_not_claim_virtual_zero_tail_is_file_backed(self) -> None:
        image = le_image.LEImage(
            le_fixture.build(
                objects=[
                    {
                        "flags": le_fixture.CODE_FLAGS,
                        "base": 0x10000,
                        "pages": 1,
                        "vsize": 0x200,
                    },
                    {
                        "flags": le_fixture.DATA_FLAGS,
                        "base": 0x20000,
                        "pages": 1,
                        "vsize": 0x3000,
                    },
                ]
            ),
            "bss.le",
        )
        data = image.objects[1]
        spans = capacity._file_spans(image, data.base_address + 0x1000, 0x100)
        self.assertEqual([], spans)


if __name__ == "__main__":
    unittest.main()
