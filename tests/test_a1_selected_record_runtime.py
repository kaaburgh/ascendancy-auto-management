from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from a1_selected_record_runtime import (  # noqa: E402
    A1SelectedRecordResolutionError,
    SELECTED_PLANET_STATIC_VA,
    resolve_selected_record,
)


class SelectedRecordResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.map_start = 0x10000000
        self.guest_pointer = 0x2340
        self.anchor = {
            "map_start": self.map_start,
            "map_end": self.map_start + 0x10000,
        }
        self.record = bytearray(0x7B)
        self.record[8:14] = b"stable"
        digest = hashlib.sha256(self.record[8:14]).hexdigest()
        self.manifest = {
            "schema": "ascendancy.a1-sidecar-scenario-qualification/v2",
            "planets": {"A": digest},
            "witness_ranges": {
                "A": {
                    "metadata_basis": "bounded-record-metadata",
                    "record_offset": 8,
                    "length": 6,
                    "sha256": digest,
                    "rationale": "synthetic stable bytes",
                }
            },
        }

    def _data_host(
        self, anchor: dict[str, int], bias: int, static_va: int, size: int
    ) -> int:
        self.assertEqual(static_va, SELECTED_PLANET_STATIC_VA)
        self.assertEqual(size, 4)
        return self.map_start + 0x100

    def _reader(self, pid: int, address: int, size: int) -> bytes:
        if address == self.map_start + 0x100:
            return self.guest_pointer.to_bytes(4, "little")
        if address == self.map_start + self.guest_pointer:
            return bytes(self.record)
        raise AssertionError((address, size))

    def test_qualifies_selected_pointer_candidate(self) -> None:
        got = resolve_selected_record(
            7,
            self.anchor,
            0,
            self.manifest,
            "A",
            read_process=self._reader,
            data_host=self._data_host,
        )
        self.assertEqual(got["record_pointer"], self.guest_pointer)
        self.assertEqual(got["record"], bytes(self.record))
        self.assertTrue(got["qualified_witness"]["matched"])

    def test_rejects_pointer_outside_mapping(self) -> None:
        self.guest_pointer = 0x20000
        with self.assertRaisesRegex(A1SelectedRecordResolutionError, "outside bounded"):
            resolve_selected_record(
                7,
                self.anchor,
                0,
                self.manifest,
                "A",
                read_process=self._reader,
                data_host=self._data_host,
            )

    def test_rejects_short_pointer_read(self) -> None:
        def reader(pid: int, address: int, size: int) -> bytes:
            return b"\x01\x02"

        with self.assertRaisesRegex(
            A1SelectedRecordResolutionError, "short selected-planet pointer"
        ):
            resolve_selected_record(
                7,
                self.anchor,
                0,
                self.manifest,
                "A",
                read_process=reader,
                data_host=self._data_host,
            )

    def test_rejects_short_record_read(self) -> None:
        def reader(pid: int, address: int, size: int) -> bytes:
            if size == 4:
                return self.guest_pointer.to_bytes(4, "little")
            return bytes(self.record[:-1])

        with self.assertRaisesRegex(
            A1SelectedRecordResolutionError, "short selected-planet record"
        ):
            resolve_selected_record(
                7,
                self.anchor,
                0,
                self.manifest,
                "A",
                read_process=reader,
                data_host=self._data_host,
            )

    def test_rejects_witness_mismatch(self) -> None:
        self.record[8] = ord("X")
        with self.assertRaisesRegex(
            A1SelectedRecordResolutionError, "failed the predeclared"
        ):
            resolve_selected_record(
                7,
                self.anchor,
                0,
                self.manifest,
                "A",
                read_process=self._reader,
                data_host=self._data_host,
            )

    def test_rejects_null_pointer(self) -> None:
        self.guest_pointer = 0
        with self.assertRaisesRegex(A1SelectedRecordResolutionError, "null"):
            resolve_selected_record(
                7,
                self.anchor,
                0,
                self.manifest,
                "A",
                read_process=self._reader,
                data_host=self._data_host,
            )


if __name__ == "__main__":
    unittest.main()
