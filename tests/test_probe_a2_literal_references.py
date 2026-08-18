#!/usr/bin/env python3
"""Synthetic coverage for scripts/probe_a2_literal_references.py."""

from __future__ import annotations

import hashlib
import pathlib
import struct
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

import le_fixture  # noqa: E402
import le_image  # noqa: E402
import probe_a2_literal_references as probe  # noqa: E402


class TestLiteralScan(unittest.TestCase):
    def test_finds_linear_and_object_relative_values_at_unaligned_offsets(self) -> None:
        candidate = {"id": "data-gap", "object": 2, "address": 0x22040, "size": 0x20}
        data = bytearray(b"x" * 32)
        struct.pack_into("<I", data, 1, 0x22048)
        struct.pack_into("<I", data, 9, 0x204C)
        hits = probe.scan_u32_literals(
            [(1, 0x10000, bytes(data))],
            [candidate],
            {2: 0x20000},
        )
        self.assertEqual(2, len(hits))
        self.assertEqual(
            {"linear-va", "target-object-relative"},
            {hit["interpretation"] for hit in hits},
        )
        self.assertEqual({0x22048, 0x2204C}, {hit["target_address"] for hit in hits})

    def test_nearby_values_outside_candidate_are_not_hits(self) -> None:
        candidate = {"id": "data-gap", "object": 2, "address": 0x22040, "size": 0x20}
        data = struct.pack("<III", 0x2203F, 0x22060, 0x203F)
        hits = probe.scan_u32_literals(
            [(1, 0x10000, data)],
            [candidate],
            {2: 0x20000},
        )
        self.assertEqual([], hits)

    def test_missing_target_object_fails_closed(self) -> None:
        candidate = {"id": "missing", "object": 3, "address": 0x30010, "size": 4}
        with self.assertRaises(probe.LiteralReferenceProbeError):
            probe.scan_u32_literals([(1, 0x10000, b"abcd")], [candidate], {1: 0x10000})


class TestProbeBoundary(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = le_fixture.build()
        self.image = le_image.LEImage(self.raw, "fixture.le")
        self.sha256 = hashlib.sha256(self.raw).hexdigest()

    def test_wrong_target_hash_fails_closed(self) -> None:
        with self.assertRaises(probe.LiteralReferenceProbeError) as caught:
            probe.build_probe(
                self.image,
                expected_sha256="0" * 64,
                candidates=[{"id": "x", "object": 2, "address": 0x20010, "size": 4}],
            )
        self.assertIn("target SHA-256 mismatch", str(caught.exception))

    def test_candidate_outside_declared_object_fails_closed(self) -> None:
        with self.assertRaises(probe.LiteralReferenceProbeError) as caught:
            probe.build_probe(
                self.image,
                expected_sha256=self.sha256,
                candidates=[{"id": "x", "object": 2, "address": 0x21000, "size": 4}],
            )
        self.assertIn("outside object", str(caught.exception))

    def test_result_never_promotes_reuse_from_literal_scan(self) -> None:
        result = probe.build_probe(
            self.image,
            expected_sha256=self.sha256,
            candidates=[{"id": "x", "object": 2, "address": 0x20010, "size": 4}],
        )
        candidate = result["candidates"][0]
        self.assertFalse(candidate["reusable"])
        self.assertEqual("not established", candidate["reuse_evidence"])
        self.assertIn("absence of matches does not exclude", result["method"]["evidence_boundary"])


class TestCliSafety(unittest.TestCase):
    def test_cli_cannot_override_canonical_target_hash(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            probe.parse_args(["target.le", "--expected-sha256", "0" * 64])
        self.assertEqual(2, caught.exception.code)

    def test_output_cannot_alias_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = pathlib.Path(temp_dir) / "ANTAG_EN.EXE"
            target.write_bytes(b"immutable target bytes")
            with self.assertRaises(probe.LiteralReferenceProbeError):
                probe.validate_output_path(target, target)


if __name__ == "__main__":
    unittest.main()
