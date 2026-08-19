from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

import run_a2_capacity_runtime_observation as a2


@dataclass(frozen=True)
class FakeObject:
    index: int
    base_address: int
    virtual_size: int

    @property
    def end_address(self) -> int:
        return self.base_address + self.virtual_size


class FakeImage:
    def __init__(self, base: int, body: bytes, index: int = 2) -> None:
        self.obj = FakeObject(index, base, len(body))
        self.body = body

    def object_containing(self, address: int):
        if self.obj.base_address <= address < self.obj.end_address:
            return self.obj
        return None

    def object_bytes(self, index: int) -> bytes:
        if index != self.obj.index:
            raise AssertionError(index)
        return self.body


class A2RuntimeObservationTests(unittest.TestCase):
    def test_static_candidate_requires_zero_payload_and_nonzero_guards(self):
        base = 0x20000
        body = b"ABCDEFGH" + b"\0" * 16 + b"QRSTUVWX"
        candidate = {"id": "candidate", "object": 2, "va": base + 8, "size": 16}
        result = a2.static_candidate_contract(FakeImage(base, body), candidate)
        self.assertEqual(result["object"], 2)
        self.assertEqual(result["size"], 16)
        self.assertEqual(result["static_zero_sha256"], a2.sha256_bytes(b"\0" * 16))

    def test_static_candidate_rejects_nonzero_payload(self):
        base = 0x20000
        body = b"ABCDEFGH" + b"\0" * 7 + b"!" + b"\0" * 8 + b"QRSTUVWX"
        candidate = {"id": "candidate", "object": 2, "va": base + 8, "size": 16}
        with self.assertRaisesRegex(a2.A2RuntimeObservationError, "no longer an all-zero"):
            a2.static_candidate_contract(FakeImage(base, body), candidate)

    def test_static_candidate_rejects_wrong_object(self):
        base = 0x20000
        body = b"ABCDEFGH" + b"\0" * 16 + b"QRSTUVWX"
        candidate = {"id": "candidate", "object": 1, "va": base + 8, "size": 16}
        with self.assertRaisesRegex(a2.A2RuntimeObservationError, "expected object 1"):
            a2.static_candidate_contract(FakeImage(base, body), candidate)

    def test_summary_preserves_negative_evidence_boundary_when_unchanged(self):
        candidate = {"id": "candidate", "size": 4}
        result = a2.summarize_snapshots(candidate, [b"\0" * 4, b"\0" * 4])
        self.assertFalse(result["differs_from_initial"])
        self.assertEqual(result["changed_offset_count"], 0)
        self.assertEqual(result["max_nonzero_byte_count"], 0)
        self.assertFalse(result["reusable"])
        self.assertEqual(result["reuse_evidence"], "not established")

    def test_summary_records_runtime_materialization_and_mutation_offsets(self):
        candidate = {"id": "candidate", "size": 5}
        result = a2.summarize_snapshots(
            candidate,
            [b"\0\0\0\0\0", b"\0\x01\0\x02\0", b"\0\x01\0\x03\0"],
        )
        self.assertTrue(result["differs_from_initial"])
        self.assertEqual(result["changed_offset_count"], 2)
        self.assertEqual(result["first_changed_offsets"], [1, 3])
        self.assertEqual(result["max_nonzero_byte_count"], 2)
        self.assertFalse(result["reusable"])

    def test_summary_rejects_short_snapshot(self):
        candidate = {"id": "candidate", "size": 4}
        with self.assertRaisesRegex(a2.A2RuntimeObservationError, "snapshot size mismatch"):
            a2.summarize_snapshots(candidate, [b"\0" * 4, b"\0" * 3])

    def test_candidate_host_range_is_anchor_relative_and_bounded(self):
        anchor = {
            "map_start": 0x10000000,
            "map_end": 0x10200000,
            "anchor_offset": 0x40000,
        }
        candidate = {"id": "candidate", "va": a2.ANCHOR_VA + 0x1234, "size": 32}
        start, end = a2.candidate_host_range(anchor, candidate)
        self.assertEqual(start, anchor["map_start"] + anchor["anchor_offset"] + 0x1234)
        self.assertEqual(end - start, 32)

    def test_candidate_host_range_rejects_mapping_escape(self):
        anchor = {
            "map_start": 0x10000000,
            "map_end": 0x10001000,
            "anchor_offset": 0x800,
        }
        candidate = {"id": "candidate", "va": a2.ANCHOR_VA + 0x900, "size": 0x100}
        with self.assertRaises((a2.A2RuntimeObservationError, a2.re5.RE5Error)):
            a2.candidate_host_range(anchor, candidate)


if __name__ == "__main__":
    unittest.main()
