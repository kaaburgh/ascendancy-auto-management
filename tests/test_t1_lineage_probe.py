#!/usr/bin/env python3
"""Synthetic tests for tools/t1_lineage_probe.py."""

from __future__ import annotations

import pathlib
import struct
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import t1_lineage_probe as lp  # noqa: E402


def synthetic_le(
    *,
    exec_size: int,
    writable_size: int,
    entry_offset: int,
    stack_offset: int,
    exec_pages: int,
    module_pages: int,
    strings: dict[int, bytes] | None = None,
    stub_tag: bytes = b"",
) -> bytes:
    le_offset = 0x80
    object_table_rel = 0xC4
    data = bytearray(0x1000)
    data[0:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, le_offset)
    data[0x50 : 0x50 + len(stub_tag)] = stub_tag

    off = le_offset
    data[off : off + 2] = b"LE"
    data[off + 2] = 0
    data[off + 3] = 0
    struct.pack_into("<I", data, off + 0x14, module_pages)
    struct.pack_into("<I", data, off + 0x18, 1)
    struct.pack_into("<I", data, off + 0x1C, entry_offset)
    struct.pack_into("<I", data, off + 0x20, 2)
    struct.pack_into("<I", data, off + 0x24, stack_offset)
    struct.pack_into("<I", data, off + 0x40, object_table_rel)
    struct.pack_into("<I", data, off + 0x44, 2)

    table = off + object_table_rel
    struct.pack_into("<6I", data, table, exec_size, 0x10000, 0x2045, 1, exec_pages, 0)
    struct.pack_into(
        "<6I", data, table + 24, writable_size, 0x90000, 0x2043, exec_pages + 1, 1, 0
    )
    for string_offset, value in (strings or {}).items():
        data[string_offset : string_offset + len(value)] = value
    return bytes(data)


class T1LineageProbeCase(unittest.TestCase):
    def test_unique_ascii_offsets_uses_exact_runs_and_drops_duplicates(self) -> None:
        data = b"\0ABCDEFGH\0UNIQUE_123\0ABCDEFGH\0short\0"
        result = lp.unique_ascii_offsets(data)
        self.assertEqual(result, {b"UNIQUE_123": 10})

    def test_parse_layout_reads_only_expected_two_object_geometry(self) -> None:
        data = synthetic_le(
            exec_size=0x1234,
            writable_size=0x5678,
            entry_offset=0x1111,
            stack_offset=0x2222,
            exec_pages=7,
            module_pages=8,
        )
        layout = lp.parse_layout(data)
        self.assertEqual(layout["le_offset"], 0x80)
        self.assertEqual(layout["entry_offset"], 0x1111)
        self.assertEqual(layout["stack_offset"], 0x2222)
        self.assertEqual(layout["objects"][0]["virtual_size"], 0x1234)
        self.assertEqual(layout["objects"][0]["page_count"], 7)
        self.assertEqual(layout["objects"][1]["virtual_size"], 0x5678)

    def test_report_reproduces_equal_layout_and_string_transforms(self) -> None:
        common_patch = {0x400: b"COMMON_ALPHA", 0x500: b"COMMON_BETA"}
        common_antag = {0x420: b"COMMON_ALPHA", 0x540: b"COMMON_BETA"}
        files = {
            "bugpatch-en": synthetic_le(
                exec_size=1000,
                writable_size=2000,
                entry_offset=900,
                stack_offset=2000,
                exec_pages=10,
                module_pages=11,
                strings=common_patch,
            ),
            "bugpatch-intl": synthetic_le(
                exec_size=1176,
                writable_size=2080,
                entry_offset=1076,
                stack_offset=2080,
                exec_pages=10,
                module_pages=11,
                strings=common_patch,
            ),
            "antagonizer-en": synthetic_le(
                exec_size=1000 + 19440,
                writable_size=2000 + 2864,
                entry_offset=900 + 19440,
                stack_offset=2000 + 2864,
                exec_pages=15,
                module_pages=16,
                strings=common_antag,
            ),
            "antagonizer-intl": synthetic_le(
                exec_size=1176 + 19440,
                writable_size=2080 + 2864,
                entry_offset=1076 + 19440,
                stack_offset=2080 + 2864,
                exec_pages=15,
                module_pages=16,
                strings=common_antag,
            ),
        }
        report = lp.build_report(files)
        self.assertTrue(report["layout_deltas"]["locale_delta_equal"])
        self.assertTrue(
            report["layout_deltas"]["antagonizer_delta_equal_across_locales"]
        )
        strings = report["string_displacements"]
        self.assertTrue(strings["common_string_sets_equal"])
        self.assertTrue(strings["histograms_equal"])
        self.assertEqual(strings["english"]["common_unique_ascii_strings"], 2)
        self.assertEqual(
            strings["english"]["histogram"],
            [{"delta": 32, "count": 1}, {"delta": 64, "count": 1}],
        )

    def test_report_rejects_nonidentical_bound_mz_regions(self) -> None:
        base = dict(
            exec_size=1000,
            writable_size=2000,
            entry_offset=900,
            stack_offset=2000,
            exec_pages=10,
            module_pages=11,
        )
        files = {
            "antagonizer-en": synthetic_le(**base),
            "antagonizer-intl": synthetic_le(**base),
            "bugpatch-en": synthetic_le(**base),
            "bugpatch-intl": synthetic_le(**base, stub_tag=b"DIFFERENT"),
        }
        with self.assertRaisesRegex(lp.ProbeError, "not byte-identical"):
            lp.build_report(files)

    def test_verify_identity_fails_closed_for_unknown_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "ANTAG_EN.EXE"
            path.write_bytes(b"not the target")
            with self.assertRaisesRegex(lp.ProbeError, "identity mismatch"):
                lp.verify_identity(path, "antagonizer-en")


if __name__ == "__main__":
    unittest.main()
