#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "probe_a1_managed_field_writers.py"
spec = importlib.util.spec_from_file_location("probe_a1_managed_field_writers", MODULE_PATH)
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


class ManagedFieldWriterProbeTests(unittest.TestCase):
    def test_parser_classifies_direct_write_and_read(self):
        text = """
  22421: c7 40 5a 00 00 00 00  movl   $0x0,0x5a(%eax)
  35473: 83 7e 5a 00           cmpl   $0x0,0x5a(%esi)
  3791f: 89 50 5a              mov    %edx,0x5a(%eax)
"""
        refs = probe.parse_objdump(text)
        self.assertEqual([item["address"] for item in refs], [0x22421, 0x35473, 0x3791F])
        self.assertTrue(refs[0]["potential_write"])
        self.assertFalse(refs[1]["potential_write"])
        self.assertTrue(refs[2]["potential_write"])

    def test_parser_ignores_other_displacements(self):
        text = """
  10000: 89 50 54              mov    %edx,0x54(%eax)
  10003: 8b 48 5a              mov    0x5a(%eax),%ecx
"""
        refs = probe.parse_objdump(text)
        self.assertEqual(len(refs), 1)
        self.assertFalse(refs[0]["field_is_destination"])
        self.assertFalse(refs[0]["potential_write"])

    def test_known_sites_fail_closed_when_missing(self):
        with self.assertRaises(probe.ProbeError):
            probe.validate_known_sites([])

    def test_known_writer_must_be_classified_as_write(self):
        refs = []
        for address in probe.KNOWN_SITES:
            refs.append(
                {
                    "address": address,
                    "mnemonic": "cmp",
                    "operands": "$0x0,0x5a(%eax)",
                    "field_is_destination": True,
                    "potential_write": False,
                }
            )
        with self.assertRaises(probe.ProbeError):
            probe.validate_known_sites(refs)


if __name__ == "__main__":
    unittest.main()
