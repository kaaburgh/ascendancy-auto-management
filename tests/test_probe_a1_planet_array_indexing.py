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

CENSUS_SAMPLE = """
 223f8: 90                    nop
 22400: 55                    push   ebp
 22401: 89 e5                 mov    ebp,esp
 2241e: 90                    nop
 22421: c7 40 5a 00 00 00 00 movl   $0x0,0x5a(%eax)
 22428: c3                    ret
 23000: e8 fb f3 ff ff        call   22400
 23005: a1 60 36 04 00        mov    eax,ds:0x43660
 2300a: 8b 15 64 36 04 00     mov    edx,DWORD PTR ds:0x43664
 23010: 69 c9 7b 00 00 00     imul   ecx,ecx,0x7b
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

    def test_reestablishes_initializer_and_collects_bounded_census(self) -> None:
        instructions = probe.parse_disassembly(CENSUS_SAMPLE)
        initializer = probe.reestablish_initializer(instructions)
        self.assertEqual(0x22400, initializer["entry"])
        self.assertEqual(0x22421, initializer["zero_write"])
        census = probe.collect_census(instructions, initializer["entry"])
        self.assertEqual([0x23000], [item["call_site"] for item in census["initializer_direct_callers"]])
        self.assertEqual(1, census["selected_globals"]["0x43660"]["reference_count"])
        self.assertEqual(1, census["selected_globals"]["0x43664"]["reference_count"])
        self.assertEqual([0x23010], [item["address"] for item in census["stride_0x7b_contexts"]])
        self.assertFalse(census["identity_contract_established"])

    def test_direct_call_target_accepts_objdump_with_or_without_0x_prefix(self) -> None:
        for operands in ("22400", "0x22400"):
            with self.subTest(operands=operands):
                self.assertEqual(
                    0x22400,
                    probe.parse_direct_call_target(
                        {"address": 0x23000, "mnemonic": "call", "operands": operands}
                    ),
                )

    def test_unrelated_zero_write_does_not_make_supported_initializer_ambiguous(self) -> None:
        instructions = probe.parse_disassembly(
            CENSUS_SAMPLE + "\n 24000: c7 40 5a 00 00 00 00 movl $0x0,0x5a(%eax)\n"
        )
        initializer = probe.reestablish_initializer(instructions)
        self.assertEqual(0x22421, initializer["zero_write"])

    def test_initializer_ambiguity_inside_supported_span_fails_closed(self) -> None:
        instructions = probe.parse_disassembly(
            CENSUS_SAMPLE.replace(
                " 2241e: 90                    nop\n",
                " 22410: c7 40 5a 00 00 00 00 movl   $0x0,0x5a(%eax)\n 2241e: 90                    nop\n",
            )
        )
        with self.assertRaises(probe.ProbeError):
            probe.reestablish_initializer(instructions)

    def test_initializer_entry_shape_change_fails_closed(self) -> None:
        instructions = probe.parse_disassembly(CENSUS_SAMPLE.replace("push   ebp", "push   eax"))
        with self.assertRaises(probe.ProbeError):
            probe.reestablish_initializer(instructions)

    def test_census_missing_supported_global_fails_closed(self) -> None:
        instructions = probe.parse_disassembly(
            CENSUS_SAMPLE.replace(" 2300a: 8b 15 64 36 04 00     mov    edx,DWORD PTR ds:0x43664\n", "")
        )
        initializer = probe.reestablish_initializer(instructions)
        with self.assertRaises(probe.ProbeError):
            probe.collect_census(instructions, initializer["entry"])

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
