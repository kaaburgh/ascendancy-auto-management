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
import le_disasm  # noqa: E402
import le_fixture  # noqa: E402
from le_disasm import DisasmError  # noqa: E402
from _quiet import quiet  # noqa: E402

OBJDUMP = shutil.which("objdump")


def function(
    address: int,
    signature: str,
    *,
    size: int = 10,
    insns: int = 5,
    callers: int = 1,
    reference: str | None = None,
    shape: str | None = None,
) -> dict:
    """A synthetic inventory entry for the three signature levels.

    ``reference`` defaults to ``signature`` and ``shape`` defaults to
    ``reference``. Give two functions different exact signatures but the same
    reference signature to model an in-image reference change; give them
    different reference signatures but one shared shape to model the remaining
    constant-only case.
    """
    reference_signature = reference if reference is not None else signature
    return {
        "address": address,
        "end": address + size,
        "instruction_count": insns,
        "byte_length": size,
        "callers": callers,
        "is_entry": False,
        "signature": signature,
        "reference_signature": reference_signature,
        "shape_signature": shape if shape is not None else reference_signature,
    }


TOOL_OBJDUMP = "GNU objdump (GNU Binutils) 2.42"
TOOL_ARCH = "i386"
TOOL_METHOD = "linear sweep of the whole object"
TOOL_NORMALIZATION = "signature preserves every operand"


def tool_block(
    objdump: str = TOOL_OBJDUMP,
    arch: str = TOOL_ARCH,
    method: str = TOOL_METHOD,
    normalization: str = TOOL_NORMALIZATION,
) -> dict:
    """The analysis-model identity le_disasm records.

    Every match pass compares strings this model produced -- objdump/arch decide
    the rendering, method decides which functions are in the inventory at all,
    and normalization decides what the signatures contain. Two inventories are
    only comparable when all four agree.
    """
    return {
        "objdump": objdump,
        "arch": arch,
        "method": method,
        "normalization": normalization,
    }


def inventory(
    name: str,
    functions: list[dict],
    *,
    objdump: str = TOOL_OBJDUMP,
    arch: str = TOOL_ARCH,
    method: str = TOOL_METHOD,
    normalization: str = TOOL_NORMALIZATION,
) -> dict:
    return {
        "schema": le_disasm.INVENTORY_SCHEMA,
        "source": {
            "name": name,
            "sha256": "0" * 64,
            "object": 1,
            "object_sha256": "1" * 64,
            "parser_layout": le_disasm.PARSER_LAYOUT_ID,
            "page_offset_header_offset": 0x80,
            "data_page_offset": 0x1000,
        },
        "tool": tool_block(objdump, arch, method, normalization),
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
        self.assertEqual(0, report["reference_only_difference_count"])
        self.assertEqual(0, report["constant_only_difference_count"])
        self.assertEqual(0, report["moved_but_identical_count"])
        self.assertEqual(1.0, report["left"]["matched_byte_fraction"])

    def test_relocated_exact_code_can_still_match(self) -> None:
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
        left = inventory("left", [function(a, "dup") for a in (0x1000, 0x2000, 0x3000)])
        right = inventory("right", [function(a, "dup") for a in (0x8000, 0x9000)])
        report = le_diff.compare(left, right)
        self.assertEqual(2, report["matched_function_count"])
        self.assertEqual(1, len(report["only_in_left"]))
        self.assertEqual(0, len(report["only_in_right"]))

    def test_byte_fraction_reflects_structurally_unmatched_volume(self) -> None:
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
        self.assertEqual("1" * 64, report["left"]["object_sha256"])

    def test_report_states_that_differences_are_candidates(self) -> None:
        report = le_diff.compare(inventory("l", []), inventory("r", []))
        self.assertIn("candidates", report["note"])


class TestReferenceOnlyBucket(unittest.TestCase):
    """Changed in-image references must never be called identical."""

    def test_reference_retarget_is_bucketed_not_matched(self) -> None:
        left = inventory("left", [function(0x1000, "call-a", reference="call-ADDR")])
        right = inventory("right", [function(0x9000, "call-b", reference="call-ADDR")])
        report = le_diff.compare(left, right)
        self.assertEqual(0, report["matched_function_count"])
        self.assertEqual(1, report["reference_only_difference_count"])
        self.assertEqual(0, report["constant_only_difference_count"])
        self.assertEqual([], report["only_in_left"])
        self.assertEqual([], report["only_in_right"])

    def test_bucket_records_both_addresses_and_move(self) -> None:
        left = inventory("left", [function(0x1000, "a", reference="r")])
        right = inventory("right", [function(0x9000, "b", reference="r")])
        entry = le_diff.compare(left, right)["reference_only_differences"][0]
        self.assertEqual(0x1000, entry["left_address"])
        self.assertEqual(0x9000, entry["right_address"])
        self.assertTrue(entry["moved"])

    def test_exact_match_takes_precedence(self) -> None:
        left = inventory("left", [function(0x1000, "same", reference="r")])
        right = inventory("right", [function(0x9000, "same", reference="r")])
        report = le_diff.compare(left, right)
        self.assertEqual(1, report["matched_function_count"])
        self.assertEqual(0, report["reference_only_difference_count"])

    def test_reference_only_does_not_count_as_structural_unmatched(self) -> None:
        left = inventory("left", [function(0x1000, "a", size=100, reference="r")])
        right = inventory("right", [function(0x9000, "b", size=100, reference="r")])
        report = le_diff.compare(left, right)
        self.assertEqual(0, report["left"]["unmatched_function_count"])
        self.assertEqual(1.0, report["left"]["matched_byte_fraction"])


class TestConstantOnlyBucket(unittest.TestCase):
    """Same shape, different non-reference constants gets its own bucket."""

    def test_constant_difference_is_bucketed_not_matched(self) -> None:
        left = inventory(
            "left", [function(0x1000, "exact-a", reference="ref-a", shape="same-shape")]
        )
        right = inventory(
            "right", [function(0x9000, "exact-b", reference="ref-b", shape="same-shape")]
        )
        report = le_diff.compare(left, right)
        self.assertEqual(0, report["matched_function_count"])
        self.assertEqual(0, report["reference_only_difference_count"])
        self.assertEqual(1, report["constant_only_difference_count"])
        self.assertEqual([], report["only_in_left"])
        self.assertEqual([], report["only_in_right"])

    def test_bucket_records_both_addresses(self) -> None:
        left = inventory("left", [function(0x1000, "a", reference="ra", shape="s")])
        right = inventory("right", [function(0x9000, "b", reference="rb", shape="s")])
        entry = le_diff.compare(left, right)["constant_only_differences"][0]
        self.assertEqual(0x1000, entry["left_address"])
        self.assertEqual(0x9000, entry["right_address"])

    def test_reference_match_takes_precedence(self) -> None:
        left = inventory("left", [function(0x1000, "a", reference="same", shape="s")])
        right = inventory("right", [function(0x9000, "b", reference="same", shape="s")])
        report = le_diff.compare(left, right)
        self.assertEqual(1, report["reference_only_difference_count"])
        self.assertEqual(0, report["constant_only_difference_count"])

    def test_structural_difference_stays_unmatched(self) -> None:
        left = inventory("left", [function(0x1000, "a", reference="ra", shape="shape-a")])
        right = inventory("right", [function(0x9000, "b", reference="rb", shape="shape-b")])
        report = le_diff.compare(left, right)
        self.assertEqual(0, report["constant_only_difference_count"])
        self.assertEqual([0x1000], [f["address"] for f in report["only_in_left"]])
        self.assertEqual([0x9000], [f["address"] for f in report["only_in_right"]])

    def test_bucket_is_sorted_by_size_descending(self) -> None:
        left = inventory("left", [
            function(0x1000, "a1", size=10, reference="ra1", shape="s1"),
            function(0x2000, "a2", size=900, reference="ra2", shape="s2"),
        ])
        right = inventory("right", [
            function(0x8000, "b1", size=10, reference="rb1", shape="s1"),
            function(0x9000, "b2", size=900, reference="rb2", shape="s2"),
        ])
        report = le_diff.compare(left, right)
        self.assertEqual(
            [900, 10],
            [f["byte_length"] for f in report["constant_only_differences"]],
        )

    def test_constant_only_does_not_count_as_structural_unmatched(self) -> None:
        left = inventory("left", [
            function(0x1000, "a", size=100, reference="ra", shape="s")
        ])
        right = inventory("right", [
            function(0x9000, "b", size=100, reference="rb", shape="s")
        ])
        report = le_diff.compare(left, right)
        self.assertEqual(0, report["left"]["unmatched_function_count"])
        self.assertEqual(1.0, report["left"]["matched_byte_fraction"])

    def test_note_explains_all_four_classes(self) -> None:
        report = le_diff.compare(inventory("l", []), inventory("r", []))
        for phrase in (
            "Matched",
            "reference_only_differences",
            "constant_only_differences",
            "only_in_left",
        ):
            self.assertIn(phrase, report["note"])


class TestLoadInventory(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)

    def test_current_json_inventory_is_loaded(self) -> None:
        path = self.tmp / "inv.json"
        path.write_text(json.dumps(inventory("x", [function(0x1000, "aa")])))
        self.assertEqual("x", le_diff.load_inventory(path)["source"]["name"])

    def test_malformed_json_is_refused(self) -> None:
        path = self.tmp / "bad.json"
        path.write_text("{not json")
        with self.assertRaises(DisasmError):
            le_diff.load_inventory(path)

    def test_legacy_unversioned_inventory_is_refused(self) -> None:
        path = self.tmp / "legacy.json"
        legacy = inventory("legacy", [function(0x1000, "aa")])
        legacy.pop("schema")
        path.write_text(json.dumps(legacy))
        with self.assertRaises(DisasmError) as caught:
            le_diff.load_inventory(path)
        self.assertIn("unsupported inventory schema", str(caught.exception))

    def test_wrong_schema_version_is_refused(self) -> None:
        path = self.tmp / "old.json"
        old = inventory("old", [function(0x1000, "aa")])
        old["schema"] = "ascendancy.le-disasm.inventory/v1"
        path.write_text(json.dumps(old))
        with self.assertRaises(DisasmError):
            le_diff.load_inventory(path)

    def test_wrong_parser_layout_is_refused(self) -> None:
        path = self.tmp / "wrong-layout.json"
        wrong = inventory("wrong", [function(0x1000, "aa")])
        wrong["source"]["parser_layout"] = "page-off-0x70"
        path.write_text(json.dumps(wrong))
        with self.assertRaises(DisasmError) as caught:
            le_diff.load_inventory(path)
        self.assertIn("parser layout", str(caught.exception))

    def test_missing_object_fingerprint_is_refused(self) -> None:
        path = self.tmp / "no-object-hash.json"
        wrong = inventory("wrong", [function(0x1000, "aa")])
        del wrong["source"]["object_sha256"]
        path.write_text(json.dumps(wrong))
        with self.assertRaises(DisasmError) as caught:
            le_diff.load_inventory(path)
        self.assertIn("source fingerprint fields", str(caught.exception))

    def test_missing_reference_signature_is_refused(self) -> None:
        path = self.tmp / "old-functions.json"
        wrong = inventory("wrong", [function(0x1000, "aa")])
        del wrong["functions"][0]["reference_signature"]
        path.write_text(json.dumps(wrong))
        with self.assertRaises(DisasmError) as caught:
            le_diff.load_inventory(path)
        self.assertIn("reference_signature", str(caught.exception))

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

    def test_relocating_the_code_object_is_not_structurally_different(self) -> None:
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
        self.assertEqual([], report["only_in_right"], report["only_in_right"])
        self.assertGreater(report["reference_only_difference_count"], 0)

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
