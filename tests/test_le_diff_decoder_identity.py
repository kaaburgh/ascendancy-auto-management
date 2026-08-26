#!/usr/bin/env python3
"""`validate_inventory` must bind the analysis-model identity it claims to fail closed on.

Its docstring says it fails closed on "serialized inventories from incompatible
analysis models", and it checks the schema, the source fingerprint, the parser
layout and the header offsets. None of those is the decoder. Every match pass in
this module compares strings that objdump produced, so two inventories decoded by
different objdump versions or for different architectures are not comparable even
when every field the validator checks agrees.

These cases pin both halves: that an inventory records its decoder at all, and
that a comparison refuses to run across two different ones.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import le_diff  # noqa: E402
from le_disasm import DisasmError  # noqa: E402

from test_le_diff import (  # noqa: E402
    TOOL_ARCH,
    TOOL_METHOD,
    TOOL_NORMALIZATION,
    TOOL_OBJDUMP,
    function,
    inventory,
)

OTHER_OBJDUMP = "GNU objdump (GNU Binutils) 2.38"

# The digest of the normalize* pipeline whose behaviour TOOL_NORMALIZATION and
# le_disasm's own recorded prose describe. Bump both together -- see
# test_recorded_normalization_prose_is_pinned_to_the_pipeline_source.
NORMALIZATION_SOURCE_SHA256 = (
    "e091646ed4cbc27f0214dec4e0a706b278abfafe619a7401de9aacc6fe7c7ee2"
)


def functions():
    return [function(0x1000, "aa"), function(0x2000, "bb")]


class ValidateInventoryBindsDecoder(unittest.TestCase):
    def test_rejects_an_inventory_with_no_tool_block(self):
        report = inventory("left", functions())
        del report["tool"]
        with self.assertRaisesRegex(DisasmError, "carries no tool block"):
            le_diff.validate_inventory(report)

    def test_rejects_a_tool_block_that_is_not_an_object(self):
        report = inventory("left", functions())
        report["tool"] = "objdump 2.42"
        with self.assertRaisesRegex(DisasmError, "carries no tool block"):
            le_diff.validate_inventory(report)

    def test_rejects_a_tool_block_missing_any_required_field(self):
        for field in le_diff.REQUIRED_TOOL_FIELDS:
            with self.subTest(field=field):
                report = inventory("left", functions())
                del report["tool"][field]
                with self.assertRaisesRegex(DisasmError, "missing tool provenance fields"):
                    le_diff.validate_inventory(report)

    def test_rejects_blank_or_non_string_tool_fields(self):
        for value in ("", "   ", None, 42, ["objdump"]):
            with self.subTest(value=value):
                report = inventory("left", functions())
                report["tool"]["objdump"] = value
                with self.assertRaisesRegex(DisasmError, "invalid tool.objdump provenance"):
                    le_diff.validate_inventory(report)

    def test_accepts_an_inventory_that_records_its_decoder(self):
        le_diff.validate_inventory(inventory("left", functions()))

    def test_decoder_identity_reports_the_whole_recorded_model(self):
        report = inventory("left", functions())
        self.assertEqual(
            le_diff.decoder_identity(report),
            (TOOL_OBJDUMP, TOOL_ARCH, TOOL_METHOD, TOOL_NORMALIZATION),
        )


class CompareRefusesMismatchedDecoders(unittest.TestCase):
    def test_compare_refuses_two_different_objdump_versions(self):
        left = inventory("left", functions())
        right = inventory("right", functions(), objdump=OTHER_OBJDUMP)
        with self.assertRaisesRegex(DisasmError, "different analysis models"):
            le_diff.compare(left, right)

    def test_compare_refuses_two_different_architectures(self):
        left = inventory("left", functions())
        right = inventory("right", functions(), arch="x86-64")
        with self.assertRaisesRegex(DisasmError, "different analysis models"):
            le_diff.compare(left, right)

    def test_the_error_names_both_sides_of_the_disagreement(self):
        left = inventory("left", functions())
        right = inventory("right", functions(), objdump=OTHER_OBJDUMP)
        with self.assertRaises(DisasmError) as caught:
            le_diff.compare(left, right)
        message = str(caught.exception)
        self.assertIn(TOOL_OBJDUMP, message)
        self.assertIn(OTHER_OBJDUMP, message)

    def test_the_error_names_only_the_fields_that_actually_differ(self):
        left = inventory("left", functions())
        right = inventory("right", functions(), objdump=OTHER_OBJDUMP)
        with self.assertRaises(DisasmError) as caught:
            le_diff.compare(left, right)
        self.assertIn("objdump:", str(caught.exception))
        self.assertNotIn("arch:", str(caught.exception))

    def test_compare_still_runs_when_the_decoder_agrees(self):
        report = le_diff.compare(
            inventory("left", functions()), inventory("right", functions())
        )
        self.assertEqual(2, report["matched_function_count"])

    def test_compare_refuses_two_different_normalization_models(self):
        # The three signatures are hashes of strings the normalize* pipeline
        # produced. A normalization change makes every signature incomparable
        # even when objdump and arch are identical, so this must refuse.
        left = inventory("left", functions())
        right = inventory("right", functions(), normalization="shape_signature keeps hex")
        with self.assertRaisesRegex(DisasmError, "different analysis models"):
            le_diff.compare(left, right)

    def test_compare_refuses_two_different_sweep_methods(self):
        # method decides which functions enter the inventory at all, so a
        # difference there changes only_in_left/right without any real delta.
        left = inventory("left", functions())
        right = inventory("right", functions(), method="entry-point recursive descent")
        with self.assertRaisesRegex(DisasmError, "different analysis models"):
            le_diff.compare(left, right)

    def test_every_recorded_model_field_is_load_bearing(self):
        # No field in the tool block is decorative. If one is ever demoted to
        # prose, this fails and the demotion has to be argued for.
        for field in ("objdump", "arch", "method", "normalization"):
            with self.subTest(field=field):
                left = inventory("left", functions())
                right = inventory("right", functions())
                right["tool"][field] = "something else entirely"
                with self.assertRaisesRegex(DisasmError, "different analysis models"):
                    le_diff.compare(left, right)

    def test_recorded_normalization_prose_is_pinned_to_the_pipeline_source(self):
        """The recorded model text must not be able to go stale silently.

        Comparing the recorded prose only detects a normalization change if the
        prose is updated when the pipeline is. That is a self-declared label,
        and a label nobody checks is exactly the defect this module's guard
        exists to close. So the prose is pinned to the source it describes: edit
        normalize/normalize_references/normalize_shape and this fails until the
        recorded text and this digest are updated together.
        """
        import hashlib
        import inspect

        import le_disasm

        source = "".join(
            inspect.getsource(fn)
            for fn in (
                le_disasm.normalize,
                le_disasm.normalize_references,
                le_disasm.normalize_shape,
            )
        )
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        self.assertEqual(
            NORMALIZATION_SOURCE_SHA256,
            digest,
            "the normalize* pipeline changed. Update the tool.normalization text "
            "le_disasm records, then update NORMALIZATION_SOURCE_SHA256 here. "
            "Inventories produced before and after this change are not comparable.",
        )


class DiffMapPathBindsDecoderToo(unittest.TestCase):
    """`compare_with_pairs` reimplements the match passes instead of calling
    `compare`, so the binding added to `compare` alone would not reach it."""

    def module(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "generate_re1_diff_map", ROOT / "scripts" / "generate_re1_diff_map.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_compare_with_pairs_refuses_mismatched_decoders(self):
        module = self.module()
        left = inventory("left", functions())
        right = inventory("right", functions(), objdump=OTHER_OBJDUMP)
        with self.assertRaisesRegex(DisasmError, "different analysis models"):
            module.compare_with_pairs(left, right)

    def test_compare_with_pairs_still_runs_when_the_decoder_agrees(self):
        module = self.module()
        pairs = module.compare_with_pairs(
            inventory("left", functions()), inventory("right", functions())
        )
        self.assertEqual(2, len(pairs["exact"]))


class LoadInventoryBindsDecoder(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)

    def test_a_serialized_inventory_without_a_decoder_is_refused_on_load(self):
        report = inventory("stale", functions())
        del report["tool"]
        path = self.tmp / "stale.json"
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(DisasmError, "carries no tool block"):
            le_diff.load_inventory(path)


if __name__ == "__main__":
    unittest.main()
