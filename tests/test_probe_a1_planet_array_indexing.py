#!/usr/bin/env python3
"""Synthetic coverage for scripts/probe_a1_planet_array_indexing.py."""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

import probe_a1_planet_array_indexing as probe  # noqa: E402

SAMPLE = """
 20c94: 69 d2 7b 00 00 00     imul   edx,edx,0x7b
 20c9a: 03 15 10 20 09 00     add    edx,DWORD PTR ds:0x92010
 20ca0: a1 20 20 09 00        mov    eax,ds:0x92020
 3bf80: 69 c9 7b 00 00 00     imul   ecx,ecx,0x7b
 3bf86: 03 0d 10 20 09 00     add    ecx,DWORD PTR ds:0x92010
 3bf8c: 8b 15 30 20 09 00     mov    edx,DWORD PTR ds:0x92030
"""


class ProbeTests(unittest.TestCase):
    def test_parser_and_shared_operand_remain_leads_only(self) -> None:
        instructions = probe.parse_disassembly(SAMPLE)
        first = probe.analyze_window(
            instructions,
            start=0x20C94,
            stop=0x20CB0,
            data_start=0x90000,
            data_end=0x140000,
        )
        second = probe.analyze_window(
            instructions,
            start=0x3BF80,
            stop=0x3BFA0,
            data_start=0x90000,
            data_end=0x140000,
        )
        self.assertEqual(
            [0x92010, 0x92020],
            [item["value"] for item in first["data_object_absolute_operands"]],
        )
        self.assertEqual(1, len(first["stride_0x7b_hits"]))
        summary = probe.summarize_relationship({"first": first, "second": second})
        self.assertEqual([0x92010], summary["shared_data_object_operands"])
        self.assertEqual("unestablished", summary["status"])
        self.assertIsNone(summary["array_base"])
        self.assertIsNone(summary["array_count"])
        self.assertIsNone(summary["slot_indexing"])

    def test_unparseable_disassembly_fails_closed(self) -> None:
        with self.assertRaises(probe.ProbeError):
            probe.parse_disassembly("noise only")

    def test_empty_window_fails_closed(self) -> None:
        instructions = probe.parse_disassembly(SAMPLE)
        with self.assertRaises(probe.ProbeError):
            probe.analyze_window(
                instructions,
                start=0x100,
                stop=0x200,
                data_start=0x90000,
                data_end=0x140000,
            )


if __name__ == "__main__":
    unittest.main()
