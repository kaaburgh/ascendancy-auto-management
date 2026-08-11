#!/usr/bin/env python3
"""Tests for tools/le_disasm.py against synthetic LE fixtures.

The fixture's code object contains real i386 instructions, so objdump runs for
real here. Tests assert on structure the tool derives, not on exact objdump
wording, so a binutils upgrade does not break them.
"""

from __future__ import annotations

import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import le_disasm  # noqa: E402
import le_fixture  # noqa: E402
from le_disasm import DisasmError  # noqa: E402
from le_image import LEError  # noqa: E402
from _quiet import quiet  # noqa: E402

OBJDUMP = shutil.which("objdump")
BASE = 0x10000


@unittest.skipUnless(OBJDUMP, "objdump is not installed")
class TestAnalyse(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)
        self.path = self.tmp / "fixture.le"
        self.path.write_bytes(le_fixture.build())
        self.report = le_disasm.analyse(self.path, None, OBJDUMP)

    def test_source_metadata_is_recorded(self) -> None:
        source = self.report["source"]
        self.assertEqual("fixture.le", source["name"])
        self.assertEqual(1, source["object"])
        self.assertEqual(BASE, source["base_address"])
        self.assertEqual(BASE, source["entry_address"])
        self.assertEqual(64, len(source["sha256"]))

    def test_tool_provenance_is_recorded(self) -> None:
        self.assertIn("objdump", self.report["tool"]["objdump"].lower())
        self.assertEqual("i386", self.report["tool"]["arch"])

    def test_instructions_were_decoded(self) -> None:
        self.assertGreater(self.report["instruction_count"], 0)

    def test_entry_point_is_a_candidate_function(self) -> None:
        entries = [f for f in self.report["functions"] if f["is_entry"]]
        self.assertEqual(1, len(entries))
        self.assertEqual(BASE, entries[0]["address"])

    def test_call_targets_become_candidate_functions(self) -> None:
        addresses = {f["address"] for f in self.report["functions"]}
        # sample_code calls +0x80 and +0xC0.
        self.assertIn(BASE + 0x80, addresses)
        self.assertIn(BASE + 0xC0, addresses)

    def test_callee_records_its_caller(self) -> None:
        by_address = {f["address"]: f for f in self.report["functions"]}
        self.assertGreaterEqual(by_address[BASE + 0x80]["callers"], 1)
        self.assertGreaterEqual(by_address[BASE + 0xC0]["callers"], 1)

    def test_call_graph_edges_start_at_the_entry(self) -> None:
        edges = {(e["from"], e["to"]) for e in self.report["call_edges"]}
        self.assertIn((BASE, BASE + 0x80), edges)
        self.assertIn((BASE, BASE + 0xC0), edges)

    def test_functions_are_sorted_and_bounded(self) -> None:
        functions = self.report["functions"]
        addresses = [f["address"] for f in functions]
        self.assertEqual(sorted(addresses), addresses)
        for function in functions:
            with self.subTest(address=function["address"]):
                self.assertGreater(function["end"], function["address"])

    def test_every_function_has_a_signature(self) -> None:
        for function in self.report["functions"]:
            self.assertEqual(64, len(function["signature"]))

    def test_mnemonic_histogram_is_present(self) -> None:
        mnemonics = dict(self.report["top_mnemonics"])
        self.assertIn("nop", mnemonics)


@unittest.skipUnless(OBJDUMP, "objdump is not installed")
class TestRefusals(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)
        self.path = self.tmp / "fixture.le"
        self.path.write_bytes(le_fixture.build())

    def test_data_object_is_refused(self) -> None:
        # Presenting a data object as code would produce confident nonsense.
        with self.assertRaises(DisasmError) as caught:
            le_disasm.analyse(self.path, 2, OBJDUMP)
        self.assertIn("not executable", str(caught.exception))

    def test_out_of_range_object_is_refused(self) -> None:
        with self.assertRaises(DisasmError):
            le_disasm.analyse(self.path, 9, OBJDUMP)

    def test_defective_container_propagates_as_le_error(self) -> None:
        bad = self.tmp / "bad.le"
        bad.write_bytes(le_fixture.build(signature=b"LX"))
        with self.assertRaises(LEError):
            le_disasm.analyse(bad, None, OBJDUMP)

    def test_missing_objdump_is_reported_clearly(self) -> None:
        original = le_disasm.shutil.which
        le_disasm.shutil.which = lambda _name: None
        self.addCleanup(setattr, le_disasm.shutil, "which", original)
        with self.assertRaises(DisasmError) as caught:
            le_disasm.find_objdump()
        self.assertIn("binutils", str(caught.exception))

    def test_explicit_objdump_is_honoured(self) -> None:
        self.assertEqual(OBJDUMP, le_disasm.find_objdump(OBJDUMP))

    def test_bad_objdump_invocation_fails_closed(self) -> None:
        with self.assertRaises(DisasmError):
            le_disasm.disassemble(b"\x90\x90", BASE, OBJDUMP, arch="not-an-arch")


@unittest.skipUnless(OBJDUMP, "objdump is not installed")
class TestInstructionLengths(unittest.TestCase):
    """Lengths come from address deltas, not from objdump's byte column.

    objdump wraps the byte listing at 7 bytes per line and the continuation
    lines carry no disassembly text, so counting printed bytes undercounts
    every instruction longer than 7 bytes.
    """

    def test_long_instruction_length_is_not_truncated(self) -> None:
        # 9-byte mov, then two nops: objdump prints the mov's bytes over 2 lines.
        data = b"\x66\xc7\x80\x44\x33\x22\x11\x66\x55\x90\x90"
        instructions = le_disasm.disassemble(data, BASE, OBJDUMP)
        self.assertEqual(3, len(instructions))
        self.assertEqual(9, instructions[0][1])
        self.assertEqual(len(data), sum(length for _a, length, _t in instructions))

    def test_lengths_tile_the_whole_object(self) -> None:
        data = b"\x90" * 64
        instructions = le_disasm.disassemble(data, BASE, OBJDUMP)
        self.assertEqual(len(data), sum(length for _a, length, _t in instructions))

    def test_addresses_are_contiguous(self) -> None:
        data = b"\x55\x89\xe5\xc9\xc3" + b"\x90" * 16
        instructions = le_disasm.disassemble(data, BASE, OBJDUMP)
        for (address, length, _t), (following, _l, _x) in zip(
            instructions, instructions[1:]
        ):
            self.assertEqual(following, address + length)


class TestNormalize(unittest.TestCase):
    # Ranges standing in for a code object and a data object.
    RANGES = ((0x10000, 0x82736), (0x90000, 0x138220))

    def norm(self, text: str) -> str:
        return le_disasm.normalize(text, self.RANGES)

    def test_in_range_addresses_are_masked(self) -> None:
        self.assertEqual("call ADDR", self.norm("call   0x783b4"))

    def test_shifted_calls_normalize_identically(self) -> None:
        # Relocation tolerance: the same call to a different target matches.
        self.assertEqual(self.norm("call 0x11111"), self.norm("call 0x22222"))

    def test_semantic_constants_are_preserved(self) -> None:
        # The critical property. Masking every hex operand would make a
        # threshold change invisible and drop it from the candidate list.
        self.assertNotEqual(self.norm("cmp eax,0x1"), self.norm("cmp eax,0x2"))
        self.assertEqual("cmp eax,0x1", self.norm("cmp    eax,0x1"))

    def test_frame_displacements_are_preserved(self) -> None:
        self.assertEqual(
            "mov ebx,DWORD PTR [ebp+0x8]",
            self.norm("mov    ebx,DWORD PTR [ebp+0x8]"),
        )
        self.assertNotEqual(
            self.norm("mov ebx,DWORD PTR [ebp+0x8]"),
            self.norm("mov ebx,DWORD PTR [ebp+0xc]"),
        )

    def test_data_addresses_are_masked(self) -> None:
        # An immediate pointing into the data object relocates between builds.
        self.assertEqual("mov eax,ADDR", self.norm("mov eax,0x98267"))

    def test_out_of_range_large_constants_are_preserved(self) -> None:
        self.assertEqual("mov eax,0xdeadbeef", self.norm("mov eax,0xdeadbeef"))

    def test_registers_are_preserved(self) -> None:
        self.assertNotEqual(self.norm("mov eax,0x1"), self.norm("mov ebx,0x1"))

    def test_whitespace_is_collapsed(self) -> None:
        self.assertEqual("push ebp", self.norm("push    ebp"))

    def test_without_ranges_nothing_is_masked(self) -> None:
        # Callers must pass ranges to get relocation tolerance; the default is
        # deliberately lossless rather than silently over-masking.
        self.assertEqual("call 0x783b4", le_disasm.normalize("call   0x783b4"))


@unittest.skipUnless(OBJDUMP, "objdump is not installed")
class TestConstantChangesAreVisible(unittest.TestCase):
    """A constant-only difference must survive into the diff as a candidate."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)

    def build_with_threshold(self, name: str, immediate: int) -> pathlib.Path:
        image = bytearray(le_fixture.build())
        header = le_disasm.le_image.LEImage(bytes(image), name)
        offset = header.page_file_offset(header.objects[0].first_page) + 0x40
        # cmp eax, imm32 ; ret  — differs only in the compared constant.
        body = b"\x3d" + immediate.to_bytes(4, "little") + b"\xc3"
        image[offset : offset + len(body)] = body
        path = self.tmp / name
        path.write_bytes(bytes(image))
        return path

    def test_threshold_difference_is_reported(self) -> None:
        one = self.build_with_threshold("one.le", 1)
        two = self.build_with_threshold("two.le", 2)
        left = le_disasm.analyse(one, None, OBJDUMP)
        right = le_disasm.analyse(two, None, OBJDUMP)

        signatures_left = {f["signature"] for f in left["functions"]}
        signatures_right = {f["signature"] for f in right["functions"]}
        self.assertNotEqual(
            signatures_left,
            signatures_right,
            "a constant-only change must not produce identical signatures",
        )


@unittest.skipUnless(OBJDUMP, "objdump is not installed")
class TestAlternateObjectSeeding(unittest.TestCase):
    """Selecting a non-entry executable object must stay inside that object."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)
        self.path = self.tmp / "two-code.le"
        self.path.write_bytes(le_fixture.build(objects=[
            {"flags": le_fixture.CODE_FLAGS, "base": 0x10000, "pages": 1,
             "vsize": 0x200},
            {"flags": le_fixture.CODE_FLAGS, "base": 0x50000, "pages": 1,
             "vsize": 0x200},
            {"flags": le_fixture.DATA_FLAGS, "base": 0x90000, "pages": 1,
             "vsize": 0x800},
        ], stack_object=3))

    def test_entry_object_still_seeds_with_the_entry(self) -> None:
        report = le_disasm.analyse(self.path, 1, OBJDUMP)
        self.assertEqual(0x10000, report["tool"]["seed_address"])
        self.assertEqual(1, len([f for f in report["functions"] if f["is_entry"]]))

    def test_alternate_object_seeds_at_its_own_base(self) -> None:
        report = le_disasm.analyse(self.path, 2, OBJDUMP)
        self.assertEqual(0x50000, report["tool"]["seed_address"])

    def test_alternate_object_has_no_out_of_range_candidates(self) -> None:
        report = le_disasm.analyse(self.path, 2, OBJDUMP)
        source = report["source"]
        for function in report["functions"]:
            with self.subTest(address=function["address"]):
                self.assertGreaterEqual(function["address"], source["base_address"])
                self.assertLess(function["address"], source["end_address"])
                self.assertLessEqual(function["end"], source["end_address"])

    def test_alternate_object_flags_no_entry(self) -> None:
        report = le_disasm.analyse(self.path, 2, OBJDUMP)
        self.assertEqual([], [f for f in report["functions"] if f["is_entry"]])

    def test_out_of_range_seed_is_refused(self) -> None:
        with self.assertRaises(DisasmError) as caught:
            le_disasm.build_inventory([], 0x1000, None, 0x10000, 0x20000)
        self.assertIn("outside the analysed range", str(caught.exception))


class TestCallEncoding(unittest.TestCase):
    def test_call_rel32_round_trips(self) -> None:
        encoded = le_fixture.call_rel32(0x10000, 0x10080)
        self.assertEqual(b"\xe8", encoded[:1])
        self.assertEqual(5, len(encoded))
        displacement = int.from_bytes(encoded[1:], "little", signed=True)
        self.assertEqual(0x10080, 0x10000 + 5 + displacement)


@unittest.skipUnless(OBJDUMP, "objdump is not installed")
class TestCli(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)
        self.path = self.tmp / "fixture.le"
        self.path.write_bytes(le_fixture.build())

    def test_summary_mode(self) -> None:
        with quiet():
            self.assertEqual(0, le_disasm.main([str(self.path), "--summary"]))

    def test_json_to_file(self) -> None:
        out = self.tmp / "inventory.json"
        with quiet():
            self.assertEqual(0, le_disasm.main([str(self.path), "-o", str(out)]))
        self.assertGreater(out.stat().st_size, 0)

    def test_refusal_exits_nonzero(self) -> None:
        with quiet():
            self.assertEqual(2, le_disasm.main([str(self.path), "--object", "2"]))


if __name__ == "__main__":
    unittest.main()
