from __future__ import annotations

import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "generate_re1_diff_map.py"
spec = importlib.util.spec_from_file_location("generate_re1_diff_map", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def function(address: int, signature: str, reference: str, shape: str):
    return {
        "address": address,
        "end": address + 4,
        "instruction_count": 1,
        "byte_length": 4,
        "callers": 0,
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
        left = inventory([
            function(0x1000, "same", "same", "same"),
            function(0x1100, "l-ref", "ref", "ref-shape"),
            function(0x1200, "l-const", "l-const-ref", "const-shape"),
            function(0x1300, "l-struct", "l-struct-ref", "l-struct-shape"),
        ])
        right = inventory([
            function(0x2000, "same", "same", "same"),
            function(0x2100, "r-ref", "ref", "ref-shape"),
            function(0x2200, "r-const", "r-const-ref", "const-shape"),
            function(0x2300, "r-struct", "r-struct-ref", "r-struct-shape"),
        ])
        diff = module.compare_with_pairs(left, right)
        self.assertEqual(
            module.counts(diff),
            {"exact": 1, "reference_only": 1, "constant_only": 1,
             "structural_left": 1, "structural_right": 1},
        )

    def test_cross_locale_requires_same_product_class(self):
        antag_locale = {0x1000: (0x1010, "reference_only")}
        patch_locale = {0x2000: (0x2010, "reference_only")}
        same = module.cross_locale_status(
            0x1000, 0x2000, "constant_only", antag_locale, patch_locale,
            {(0x1010, 0x2010): "constant_only"}, set(),
        )
        changed = module.cross_locale_status(
            0x1000, 0x2000, "constant_only", antag_locale, patch_locale,
            {(0x1010, 0x2010): "reference_only"}, set(),
        )
        self.assertTrue(same["corroborated"])
        self.assertFalse(changed["corroborated"])

    def test_structural_corroboration_never_invents_patch_pair(self):
        status = module.cross_locale_status(
            0x1000, None, "structural", {0x1000: (0x1010, "reference_only")},
            {}, {}, {0x1010},
        )
        self.assertTrue(status["corroborated"])
        self.assertIsNone(status["patch_intl_address"])
        self.assertEqual(status["intl_product_class"], "structural")


if __name__ == "__main__":
    unittest.main()
