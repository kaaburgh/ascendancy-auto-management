#!/usr/bin/env python3
"""Tests for tools/le_diff.py.

The matching logic is pure data manipulation, so these tests build inventories
directly instead of disassembling anything. That keeps the assertions exact:
each test controls precisely which functions should match.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import le_diff  # noqa: E402
import le_fixture  # noqa: E402
from le_disasm import DisasmError  # noqa: E402
from _quiet import quiet  # noqa: E402

OBJDUMP = shutil.which("objdump")


def function(address: int, signature: str, *, size: int = 10, insns: int = 5,
             callers: int = 1, shape: str | None = None) -> dict:
    """A synthetic inventory entry.

    ``shape`` defaults to ``signature``: code that differs strictly usually
    differs in shape too. Pass a shared ``shape`` with differing ``signature``
    to model the constant-only case.
    """
    return {
        "address": address,
        "end": address + size,
        "instruction_count": insns,
        "byte_length": size,
        "callers": callers,
        "is_entry": False,
        "signature": signature,
        "shape_signature": shape if shape is not None else signature,
    }


def inventory(name: str, functions: list[dict]) -> dict:
    return {
        "source": {"name": name, "sha256": "0" * 64, "object": 1},
        "functions": functions,
    }


class TestCompare(unittest.TestCase):
    def test_identical_inventories_match_completely(self) -> None:
        functions = [function(0x1000, "aa"), function(0x2000, "bb")]
        report = le_diff.compare(
            inventory("left", functions), inventory("right", list(functions))
        )
        self.assertEqual(2, report["matched_function_count"])
        self.assertEqual([], report["only_in_left"])
        self.assertEqual([], report["only_in_right"])
        self.assertEqual(0, report["moved_but_identical_count"])
        self.assertEqual(1.0, report["left"]["matched_byte_fraction"])

    def test_relocated_but_identical_code_still_matches(self) -> None:
        # This is the property a byte diff cannot give us.
        left = inventory("left", [function(0x1000, "aa"), function(0x2000, "bb")])
        right = inventory("right", [function(0x9000, "aa"), function(0xA000, "bb")])
        report = le_diff.compare(left, right)
        self.assertEqual(2, report["matched_function_count"])
        self.assertEqual(2, report["moved_but_identical_count"])
        self.assertEqual([], report["only_in_left"])

    def test_matched_entries_record_both_addresses(self) -> None:
        left = inventory("left", [function(0x1000, "aa")])
        right = inventory("right", [function(0x9000, "aa")])
        report = le_diff.compare(left, right)
        self.assertEqual(1, report["matched_function_count"])

    def test_added_function_appears_only_in_left(self) -> None:
        left = inventory("left", [function(0x1000, "aa"), function(0x2000, "new")])
        right = inventory("right", [function(0x1000, "aa")])
        report = le_diff.compare(left, right)
        self.assertEqual(1, report["matched_function_count"])
        self.assertEqual([0x2000], [f["address"] for f in report["only_in_left"]])
        self.assertEqual([], report["only_in_right"])

    def test_removed_function_appears_only_in_right(self) -> None:
        left = inventory("left", [function(0x1000, "aa")])
        right = inventory("right", [function(0x1000, "aa"), function(0x2000, "gone")])
        report = le_diff.compare(left, right)
        self.assertEqual([0x2000], [f["address"] for f in report["only_in_right"]])
        self.assertEqual([], report["only_in_left"])

    def test_unmatched_are_sorted_by_size_descending(self) -> None:
        left = inventory("left", [
            function(0x1000, "s", size=10),
            function(0x2000, "m", size=500),
            function(0x3000, "l", size=100),
        ])
        report = le_diff.compare(left, inventory("right", []))
        self.assertEqual(
            [500, 100, 10], [f["byte_length"] for f in report["only_in_left"]]
        )

    def test_duplicate_signatures_match_as_a_multiset(self) -> None:
        # Thunks and stubs legitimately share a signature; three vs two must
        # leave exactly one unmatched rather than matching all or none.
        left = inventory("left", [function(a, "dup") for a in (0x1000, 0x2000, 0x3000)])
        right = inventory("right", [function(a, "dup") for a in (0x8000, 0x9000)])
        report = le_diff.compare(left, right)
        self.assertEqual(2, report["matched_function_count"])
        self.assertEqual(1, len(report["only_in_left"]))
        self.assertEqual(0, len(report["only_in_right"]))

    def test_byte_fraction_reflects_unmatched_volume(self) -> None:
        left = inventory("left", [
            function(0x1000, "aa", size=750),
            function(0x2000, "new", size=250),
        ])
        right = inventory("right", [function(0x1000, "aa", size=750)])
        report = le_diff.compare(left, right)
        self.assertEqual(1000, report["left"]["attributed_bytes"])
        self.assertEqual(250, report["left"]["unmatched_bytes"])
        self.assertEqual(0.75, report["left"]["matched_byte_fraction"])

    def test_empty_inventories_do_not_divide_by_zero(self) -> None:
        report = le_diff.compare(inventory("left", []), inventory("right", []))
        self.assertIsNone(report["left"]["matched_byte_fraction"])
        self.assertEqual(0, report["matched_function_count"])

    def test_report_carries_source_identity(self) -> None:
        report = le_diff.compare(
            inventory("antag", [function(0x1000, "aa")]),
            inventory("patch", [function(0x1000, "aa")]),
        )
        self.assertEqual("antag", report["left"]["name"])
        self.assertEqual("patch", report["right"]["name"])

    def test_report_states_that_unmatched_are_candidates(self) -> None:
        # The wording matters: this output must not read as established findings.
        report = le_diff.compare(inventory("l", []), inventory("r", []))
        self.assertIn("candidates", report["note"])


class TestConstantOnlyBucket(unittest.TestCase):
    """Same shape, different constants gets its own bucket.

    Folding this into "matched" hides real threshold changes; folding it into
    "changed" buries them under hundreds of data relocations.
    """

    def test_constant_difference_is_bucketed_not_matched(self) -> None:
        left = inventory("left", [function(0x1000, "strict-a", shape="same-shape")])
        right = inventory("right", [function(0x9000, "strict-b", shape="same-shape")])
        report = le_diff.compare(left, right)
        self.assertEqual(0, report["matched_function_count"])
        self.assertEqual(1, report["constant_only_difference_count"])
        self.assertEqual([], report["only_in_left"])
        self.assertEqual([], report["only_in_right"])

    def test_bucket_records_both_addresses(self) -> None:
        left = inventory("left", [function(0x1000, "a", shape="s")])
        right = inventory("right", [function(0x9000, "b", shape="s")])
        entry = le_diff.compare(left, right)["constant_only_differences"][0]
        self.assertEqual(0x1000, entry["left_address"])
        self.assertEqual(0x9000, entry["right_address"])

    def test_strict_match_takes_precedence(self) -> None:
        # An exact match must not be demoted into the constant-only bucket.
        left = inventory("left", [function(0x1000, "same", shape="s")])
        right = inventory("right", [function(0x9000, "same", shape="s")])
        report = le_diff.compare(left, right)
        self.assertEqual(1, report["matched_function_count"])
        self.assertEqual(0, report["constant_only_difference_count"])

    def test_structural_difference_stays_unmatched(self) -> None:
        left = inventory("left", [function(0x1000, "a", shape="shape-a")])
        right = inventory("right", [function(0x9000, "b", shape="shape-b")])
        report = le_diff.compare(left, right)
        self.assertEqual(0, report["constant_only_difference_count"])
        self.assertEqual([0x1000], [f["address"] for f in report["only_in_left"]])
        self.assertEqual([0x9000], [f["address"] for f in report["only_in_right"]])

    def test_bucket_is_sorted_by_size_descending(self) -> None:
        left = inventory("left", [
            function(0x1000, "a1", size=10, shape="s1"),
            function(0x2000, "a2", size=900, shape="s2"),
        ])
        right = inventory("right", [
            function(0x8000, "b1", size=10, shape="s1"),
            function(0x9000, "b2", size=900, shape="s2"),
        ])
        report = le_diff.compare(left, right)
        self.assertEqual(
            [900, 10],
            [f["byte_length"] for f in report["constant_only_differences"]],
        )

    def test_constant_only_does_not_count_as_structurally_unmatched(self) -> None:
        # The byte fraction must not be depressed by relocation noise.
        left = inventory("left", [function(0x1000, "a", size=100, shape="s")])
        right = inventory("right", [function(0x9000, "b", size=100, shape="s")])
        report = le_diff.compare(left, right)
        self.assertEqual(0, report["left"]["unmatched_function_count"])
        self.assertEqual(1.0, report["left"]["matched_byte_fraction"])

    def test_note_explains_all_three_buckets(self) -> None:
        report = le_diff.compare(inventory("l", []), inventory("r", []))
        for phrase in ("Matched", "constant_only_differences", "only_in_left"):
            self.assertIn(phrase, report["note"])


class TestLoadInventory(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)

    def test_json_inventory_is_loaded(self) -> None:
        path = self.tmp / "inv.json"
        path.write_text(json.dumps(inventory("x", [function(0x1000, "aa")])))
        self.assertEqual("x", le_diff.load_inventory(path)["source"]["name"])

    def test_malformed_json_is_refused(self) -> None:
        path = self.tmp / "bad.json"
        path.write_text("{not json")
        with self.assertRaises(DisasmError):
            le_diff.load_inventory(path)

    def test_json_missing_required_keys_is_refused(self) -> None:
        path = self.tmp / "wrong.json"
        path.write_text(json.dumps({"hello": "world"}))
        with self.assertRaises(DisasmError) as caught:
            le_diff.load_inventory(path)
        self.assertIn("not a le_disasm inventory", str(caught.exception))

    def test_missing_file_is_refused(self) -> None:
        with self.assertRaises(DisasmError):
            le_diff.load_inventory(self.tmp / "absent.json")


@unittest.skipUnless(OBJDUMP, "objdump is not installed")
class TestEndToEnd(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)

    def test_executables_can_be_compared_directly(self) -> None:
        same = self.tmp / "a.le"
        same.write_bytes(le_fixture.build())
        report = le_diff.compare(
            le_diff.load_inventory(same), le_diff.load_inventory(same)
        )
        self.assertEqual([], report["only_in_left"])
        self.assertGreater(report["matched_function_count"], 0)

    def test_relocating_the_code_object_still_matches(self) -> None:
        # Same code at a different base: every function should still match.
        low = self.tmp / "low.le"
        high = self.tmp / "high.le"
        low.write_bytes(le_fixture.build())
        high.write_bytes(le_fixture.build(objects=[
            {"flags": le_fixture.CODE_FLAGS, "base": 0x40000, "pages": 1,
             "vsize": 0x200},
            {"flags": le_fixture.DATA_FLAGS, "base": 0x50000, "pages": 1,
             "vsize": 0x800},
        ]))
        report = le_diff.compare(
            le_diff.load_inventory(low), le_diff.load_inventory(high)
        )
        self.assertEqual([], report["only_in_left"], report["only_in_left"])
        self.assertEqual(report["matched_function_count"],
                         report["moved_but_identical_count"])

    def test_cli_summary(self) -> None:
        path = self.tmp / "a.le"
        path.write_bytes(le_fixture.build())
        with quiet():
            self.assertEqual(0, le_diff.main([str(path), str(path), "--summary"]))

    def test_cli_writes_json(self) -> None:
        path = self.tmp / "a.le"
        path.write_bytes(le_fixture.build())
        out = self.tmp / "diff.json"
        with quiet():
            self.assertEqual(0, le_diff.main([str(path), str(path), "-o", str(out)]))
        self.assertGreater(out.stat().st_size, 0)

    def test_cli_refusal_exits_nonzero(self) -> None:
        bad = self.tmp / "bad.le"
        bad.write_bytes(le_fixture.build(signature=b"LX"))
        with quiet():
            self.assertEqual(2, le_diff.main([str(bad), str(bad)]))


if __name__ == "__main__":
    unittest.main()
