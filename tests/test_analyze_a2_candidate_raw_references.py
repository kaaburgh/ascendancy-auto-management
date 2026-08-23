#!/usr/bin/env python3
"""Synthetic coverage for scripts/analyze_a2_candidate_raw_references.py."""
from __future__ import annotations

import hashlib
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analyze_a2_candidate_raw_references as probe  # noqa: E402


class TestRawReferenceScan(unittest.TestCase):
    def test_finds_linear_and_object_relative_references(self) -> None:
        candidate = probe.Candidate("candidate", 0x92000, 0x20, 0x90000)
        data = (
            b"AA"
            + (0x92005).to_bytes(4, "little")
            + b"BBB"
            + (0x2007).to_bytes(4, "little")
            + b"CC"
        )
        matches = probe.scan_raw_references(data, (candidate,))
        self.assertEqual(
            [
                {
                    "file_offset": 2,
                    "value": 0x92005,
                    "candidate": "candidate",
                    "encoding": "linear-va",
                    "candidate_delta": 5,
                },
                {
                    "file_offset": 9,
                    "value": 0x2007,
                    "candidate": "candidate",
                    "encoding": "object-relative",
                    "candidate_delta": 7,
                },
            ],
            matches,
        )

    def test_values_outside_candidate_are_not_reported(self) -> None:
        candidate = probe.Candidate("candidate", 0x92000, 0x20, 0x90000)
        data = (0x91FFF).to_bytes(4, "little") + (0x2020).to_bytes(4, "little")
        self.assertEqual([], probe.scan_raw_references(data, (candidate,)))

    def test_short_input_is_valid_and_empty(self) -> None:
        self.assertEqual([], probe.scan_raw_references(b"abc", (probe.CANDIDATES[0],)))


class TestReportBoundary(unittest.TestCase):
    def test_wrong_target_hash_fails_closed(self) -> None:
        with self.assertRaises(probe.RawReferenceError) as caught:
            probe.build_report(b"fixture", name="fixture.le", expected_sha256="0" * 64)
        self.assertIn("target SHA-256 mismatch", str(caught.exception))

    def test_report_never_marks_candidates_reusable(self) -> None:
        data = b"fixture"
        digest = hashlib.sha256(data).hexdigest()
        report = probe.build_report(data, name="fixture.le", expected_sha256=digest)
        self.assertTrue(report["candidates"])
        self.assertTrue(all(candidate["reusable"] is False for candidate in report["candidates"]))
        self.assertIn("does not establish", report["method"]["semantics"])


class TestCliSafety(unittest.TestCase):
    def test_cli_cannot_override_canonical_target_hash(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            probe.parse_args(["target.le", "--expected-sha256", "0" * 64])
        self.assertEqual(2, caught.exception.code)

    def test_output_cannot_alias_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = pathlib.Path(temp_dir) / "ANTAG_EN.EXE"
            target.write_bytes(b"immutable")
            with self.assertRaises(probe.RawReferenceError):
                probe.validate_output_path(target, target)

    def test_separate_output_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            target = root / "ANTAG_EN.EXE"
            target.write_bytes(b"immutable")
            probe.validate_output_path(target, root / "artifacts" / "raw-refs.json")


if __name__ == "__main__":
    unittest.main()
