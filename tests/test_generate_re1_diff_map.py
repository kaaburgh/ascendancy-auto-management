from __future__ import annotations

import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "generate_re1_diff_map.py"
spec = importlib.util.spec_from_file_location("generate_re1_diff_map", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def function(
    address: int,
    signature: str,
    reference: str,
    shape: str,
    *,
    callers: int = 0,
    byte_length: int = 4,
):
    return {
        "address": address,
        "end": address + byte_length,
        "instruction_count": 1,
        "byte_length": byte_length,
        "callers": callers,
        "signature": signature,
        "reference_signature": reference,
        "shape_signature": shape,
    }


def inventory(functions):
    return {
        "schema": module.le_diff.le_disasm.INVENTORY_SCHEMA,
        "source": {
            "name": "fixture.exe",
            "sha256": "0" * 64,
            "object": 1,
            "object_sha256": "1" * 64,
            "parser_layout": module.le_diff.le_disasm.PARSER_LAYOUT_ID,
            "page_offset_header_offset": module.le_diff.le_image.H_DATAPAGE,
            "data_page_offset": 0,
        },
        "functions": functions,
    }


class RE1DiffMapTests(unittest.TestCase):
    def test_compare_preserves_all_four_classes(self):
        left = inventory(
            [
                function(0x1000, "same", "same", "same"),
                function(0x1100, "l-ref", "ref", "ref-shape"),
                function(0x1200, "l-const", "l-const-ref", "const-shape"),
                function(0x1300, "l-struct", "l-struct-ref", "l-struct-shape"),
            ]
        )
        right = inventory(
            [
                function(0x2000, "same", "same", "same"),
                function(0x2100, "r-ref", "ref", "ref-shape"),
                function(0x2200, "r-const", "r-const-ref", "const-shape"),
                function(0x2300, "r-struct", "r-struct-ref", "r-struct-shape"),
            ]
        )
        diff = module.compare_with_pairs(left, right)
        self.assertEqual(
            module.counts(diff),
            {
                "exact": 1,
                "reference_only": 1,
                "constant_only": 1,
                "structural_left": 1,
                "structural_right": 1,
            },
        )

    def test_cross_locale_requires_same_product_class(self):
        antag_locale = {0x1000: (0x1010, "reference_only")}
        patch_locale = {0x2000: (0x2010, "reference_only")}
        same = module.cross_locale_status(
            0x1000,
            0x2000,
            "constant_only",
            antag_locale,
            patch_locale,
            {0x1010: (0x2010, "constant_only")},
            set(),
        )
        changed = module.cross_locale_status(
            0x1000,
            0x2000,
            "constant_only",
            antag_locale,
            patch_locale,
            {0x1010: (0x2010, "reference_only")},
            set(),
        )
        mismatched_pair = module.cross_locale_status(
            0x1000,
            0x2000,
            "constant_only",
            antag_locale,
            patch_locale,
            {0x1010: (0x2020, "constant_only")},
            set(),
        )
        self.assertTrue(same["corroborated"])
        self.assertFalse(changed["corroborated"])
        self.assertFalse(mismatched_pair["corroborated"])

    def test_structural_corroboration_never_invents_patch_pair(self):
        status = module.cross_locale_status(
            0x1000,
            None,
            "structural",
            {0x1000: (0x1010, "reference_only")},
            {},
            {},
            {0x1010},
        )
        self.assertTrue(status["corroborated"])
        self.assertIsNone(status["patch_intl_address"])
        self.assertEqual(status["intl_product_class"], "structural")

    def test_unique_locale_pair_is_mapped(self):
        left = function(0x1000, "same", "same", "same")
        right = function(0x2000, "same", "same", "same")
        mapping, ambiguous = module.unambiguous_pair_map(
            {
                "exact": [(left, right)],
                "reference_only": [],
                "constant_only": [],
                "structural_left": [],
                "structural_right": [],
            }
        )
        self.assertEqual(mapping, {0x1000: (0x2000, "exact")})
        self.assertEqual(ambiguous["exact"], 0)

    def test_duplicate_locale_signatures_are_not_mapped_by_pair_order(self):
        left_a = function(0x1000, "dup", "left-a", "shape-a")
        left_b = function(0x1100, "dup", "left-b", "shape-b")
        right_a = function(0x2000, "dup", "right-a", "shape-c")
        right_b = function(0x2100, "dup", "right-b", "shape-d")
        mapping, ambiguous = module.unambiguous_pair_map(
            {
                "exact": [(left_a, right_a), (left_b, right_b)],
                "reference_only": [],
                "constant_only": [],
                "structural_left": [],
                "structural_right": [],
            }
        )
        self.assertEqual(mapping, {})
        self.assertEqual(ambiguous["exact"], 2)

    def test_stage_uniqueness_includes_later_leftovers(self):
        left_pair = function(0x1000, "left-a", "dup-ref", "shape-a")
        right_pair = function(0x2000, "right-a", "dup-ref", "shape-b")
        left_later = function(0x1100, "left-b", "dup-ref", "shape-c")
        mapping, ambiguous = module.unambiguous_pair_map(
            {
                "exact": [],
                "reference_only": [(left_pair, right_pair)],
                "constant_only": [],
                "structural_left": [left_later],
                "structural_right": [],
            }
        )
        self.assertEqual(mapping, {})
        self.assertEqual(ambiguous["reference_only"], 1)

    def test_candidate_sort_is_deterministic_and_evidence_first(self):
        def candidate(address, cls, corroborated, callers, byte_length):
            return {
                "antag_en_address": address,
                "class": cls,
                "callers": callers,
                "byte_length": byte_length,
                "cross_locale": {"corroborated": corroborated},
            }

        candidates = [
            candidate(0x1400, "reference_only", True, 99, 100),
            candidate(0x1300, "structural", False, 99, 100),
            candidate(0x1200, "structural", True, 1, 10),
            candidate(0x1100, "structural", True, 2, 5),
        ]
        ordered = sorted(candidates, key=module.candidate_sort_key)
        self.assertEqual(
            [item["antag_en_address"] for item in ordered],
            [0x1100, 0x1200, 0x1400, 0x1300],
        )

    def test_pinned_pair_count_gate_fails_on_analysis_drift(self):
        module.validate_pair_counts(module.EXPECTED_PAIR_COUNTS)
        changed = {
            pair: dict(values) for pair, values in module.EXPECTED_PAIR_COUNTS.items()
        }
        changed["product-en"]["exact"] += 1
        with self.assertRaises(module.RE1Error):
            module.validate_pair_counts(changed)


if __name__ == "__main__":
    unittest.main()
