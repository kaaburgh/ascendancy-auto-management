#!/usr/bin/env python3
"""Synthetic coverage for A2 raw literal reference probe."""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_a2_raw_literal_reference_probe as probe  # noqa: E402


class TestLiteralScan(unittest.TestCase):
    def test_detects_unaligned_overlapping_dword(self) -> None:
        candidates = ({"id": "c", "start": 0x12345678, "size": 4},)
        data = b"X" + (0x12345679).to_bytes(4, "little") + b"Y"
        self.assertEqual(
            [
                {
                    "site_address": 0x1001,
                    "literal_value": 0x12345679,
                    "candidate_id": "c",
                    "candidate_offset": 1,
                }
            ],
            probe.scan_literal_dwords(data, 0x1000, candidates),
        )

    def test_candidate_end_is_exclusive(self) -> None:
        candidates = ({"id": "c", "start": 0x2000, "size": 4},)
        self.assertIsNotNone(probe.candidate_for(0x2003, candidates))
        self.assertIsNone(probe.candidate_for(0x2004, candidates))

    def test_non_matching_words_are_ignored(self) -> None:
        candidates = ({"id": "c", "start": 0x3000, "size": 8},)
        data = (0x11111111).to_bytes(4, "little") + (0x22222222).to_bytes(4, "little")
        self.assertEqual([], probe.scan_literal_dwords(data, 0x4000, candidates))

    def test_cli_has_no_target_hash_override(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            probe.parse_args(["ANTAG_EN.EXE", "--expected-sha256", "0" * 64])
        self.assertEqual(2, caught.exception.code)


if __name__ == "__main__":
    unittest.main()
