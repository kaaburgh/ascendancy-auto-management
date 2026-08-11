#!/usr/bin/env python3
"""Tests for tools/le_image.py, driven entirely by synthetic LE fixtures.

No proprietary bytes are involved, so this runs in CI. Each fail-closed test
injects one specific structural defect via tools/le_fixture.py.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import le_fixture  # noqa: E402
import le_image  # noqa: E402
from le_image import LEError  # noqa: E402
from _quiet import quiet  # noqa: E402


class TestValidImage(unittest.TestCase):
    def setUp(self) -> None:
        self.image = le_image.LEImage(le_fixture.build(), "fixture.le")

    def test_container_fields(self) -> None:
        self.assertEqual(0x80, self.image.lfanew)
        self.assertEqual("80386", self.image.cpu_name)
        self.assertEqual(0x1000, self.image.page_size)
        self.assertEqual(2, self.image.object_count)

    def test_object_classification(self) -> None:
        code, data = self.image.objects
        self.assertEqual("code", code.kind)
        self.assertEqual("data", data.kind)
        self.assertIn("executable", code.names)
        self.assertIn("writable", data.names)
        self.assertNotIn("executable", data.names)

    def test_entry_address_is_base_plus_eip(self) -> None:
        self.assertEqual(0x10000, self.image.entry_address)

    def test_object_bytes_length_matches_virtual_size(self) -> None:
        for obj in self.image.objects:
            with self.subTest(object=obj.index):
                self.assertEqual(
                    obj.virtual_size, len(self.image.object_bytes(obj.index))
                )

    def test_object_bytes_truncates_page_padding(self) -> None:
        # One 4096-byte page backs a 512-byte object; the tail is padding.
        code = self.image.object_bytes(1)
        self.assertEqual(512, len(code))
        self.assertEqual(b"\x55\x89\xe5", code[:3])

    def test_object_bytes_zero_fills_uninitialised_space(self) -> None:
        # The data object declares more virtual size than its pages provide.
        data = self.image.object_bytes(2)
        self.assertEqual(2048, len(data))
        self.assertTrue(any(data), "expected some initialised content")

    def test_object_containing_maps_addresses(self) -> None:
        self.assertEqual(1, self.image.object_containing(0x10010).index)
        self.assertEqual(2, self.image.object_containing(0x20010).index)
        self.assertIsNone(self.image.object_containing(0xFFFFFF))

    def test_page_helpers(self) -> None:
        self.assertEqual(self.image.page_size, self.image.page_length(1))
        self.assertEqual(
            self.image.last_page_size, self.image.page_length(self.image.page_count)
        )

    def test_trailing_region_is_reported(self) -> None:
        self.assertEqual(self.image.size, self.image.page_data_end)
        self.assertEqual(0, self.image.trailing_size)

    def test_unknown_object_index_is_rejected(self) -> None:
        for index in (0, 3, -1):
            with self.subTest(index=index):
                with self.assertRaises(LEError):
                    self.image.object_bytes(index)

    def test_to_dict_is_json_serialisable(self) -> None:
        text = json.dumps(self.image.to_dict())
        self.assertIn("80386", text)


class TestStrings(unittest.TestCase):
    def test_strings_report_virtual_addresses(self) -> None:
        marker = b"ASCENDANCY-FIXTURE-MARKER"
        data = bytearray(le_fixture.build())
        image = le_image.LEImage(bytes(data), "fixture.le")
        # Place the marker at a known offset inside the data object's first page.
        offset = image.page_file_offset(image.objects[1].first_page) + 0x40
        # NUL-delimit so the printable run is exactly the marker: the filler
        # bytes around it are themselves partly printable.
        data[offset - 1] = 0
        data[offset : offset + len(marker)] = marker
        data[offset + len(marker)] = 0
        image = le_image.LEImage(bytes(data), "fixture.le")

        found = [s for s in image.strings(8) if marker.decode() in s["text"]]
        self.assertEqual(1, len(found), found)
        self.assertEqual(image.objects[1].base_address + 0x40, found[0]["address"])
        self.assertEqual(2, found[0]["object"])

    def test_min_length_is_respected(self) -> None:
        image = le_image.LEImage(le_fixture.build(), "fixture.le")
        for item in image.strings(6):
            self.assertGreaterEqual(item["length"], 6)

    def test_longer_min_length_yields_no_more_results(self) -> None:
        image = le_image.LEImage(le_fixture.build(), "fixture.le")
        self.assertLessEqual(len(image.strings(12)), len(image.strings(4)))


class TestAddressMapping(unittest.TestCase):
    """VA-to-file mapping, and the anchor check that validates the page offset."""

    def setUp(self) -> None:
        self.data = le_fixture.build()
        self.image = le_image.LEImage(self.data, "fixture.le")

    def test_entry_maps_to_the_first_page_of_page_data(self) -> None:
        self.assertEqual(
            self.image.data_page_offset,
            self.image.va_to_file_offset(self.image.entry_address),
        )

    def test_mapping_round_trips_against_real_bytes(self) -> None:
        offset = self.image.va_to_file_offset(self.image.entry_address)
        self.assertEqual(b"\x55\x89\xe5", self.data[offset : offset + 3])

    def test_addresses_outside_any_object_are_unmapped(self) -> None:
        self.assertIsNone(self.image.va_to_file_offset(0xFFFFFFF))

    def test_zero_filled_tail_is_unmapped(self) -> None:
        # An object whose virtual size exceeds the bytes its pages provide: the
        # tail is bss/stack/heap and has no file offset at all.
        image = le_image.LEImage(le_fixture.build(objects=[
            {"flags": le_fixture.CODE_FLAGS, "base": 0x10000, "pages": 1,
             "vsize": 0x200},
            {"flags": le_fixture.DATA_FLAGS, "base": 0x20000, "pages": 1,
             "vsize": 0x3000},
        ]), "bss.le")
        data = image.objects[1]
        self.assertIsNotNone(image.va_to_file_offset(data.base_address))
        self.assertIsNone(image.va_to_file_offset(data.end_address - 1))

    def test_anchor_confirms_known_bytes(self) -> None:
        marker = b"ANCHOR-MARKER"
        raw = bytearray(self.data)
        offset = self.image.page_file_offset(self.image.objects[1].first_page) + 0x20
        raw[offset : offset + len(marker)] = marker
        image = le_image.LEImage(bytes(raw), "fixture.le")
        image.check_anchor(image.objects[1].base_address + 0x20, marker)

    def test_anchor_mismatch_is_refused(self) -> None:
        with self.assertRaises(LEError) as caught:
            self.image.check_anchor(self.image.entry_address, b"NOT-THERE")
        self.assertIn("anchor mismatch", str(caught.exception))

    def test_anchor_on_unmapped_address_is_refused(self) -> None:
        with self.assertRaises(LEError):
            self.image.check_anchor(0xFFFFFFF, b"x")

    def test_anchor_catches_a_page_offset_read_from_the_wrong_field(self) -> None:
        # The point of the anchor check: if the page-data offset came from the
        # wrong header field, content no longer sits at its expected address.
        # Written to 0x80 instead of 0x70, so the parser reads 0 and mis-maps.
        marker = b"ANCHOR-MARKER"
        good = le_fixture.build()
        reference = le_image.LEImage(good, "good.le")
        address = reference.objects[1].base_address + 0x20
        offset = reference.page_file_offset(reference.objects[1].first_page) + 0x20

        raw = bytearray(le_fixture.build(page_off_field=0x80))
        raw[offset : offset + len(marker)] = marker
        image = le_image.LEImage(bytes(raw), "mismapped.le")
        self.assertNotEqual(reference.data_page_offset, image.data_page_offset)
        with self.assertRaises(LEError):
            image.check_anchor(address, marker)

    def test_parser_reads_the_documented_page_offset_field(self) -> None:
        # Guards against silently changing H_DATAPAGE: the value written to
        # 0x70 must be the one the parser uses.
        image = le_image.LEImage(le_fixture.build(), "fixture.le")
        import struct

        expected = struct.unpack_from("<I", le_fixture.build(),
                                      image.lfanew + le_image.H_DATAPAGE)[0]
        self.assertEqual(expected, image.data_page_offset)


class TestFailsClosed(unittest.TestCase):
    def assertRefused(self, needle: str, **overrides) -> None:
        with self.assertRaises(LEError) as caught:
            le_image.LEImage(le_fixture.build(**overrides), "defective.le")
        self.assertIn(needle, str(caught.exception).lower())

    def test_not_an_mz_file(self) -> None:
        self.assertRefused("not an mz", mz_magic=b"ZZ")

    def test_lx_image_is_named_as_such(self) -> None:
        # LX has a different page table; guessing at it would be worse than failing.
        self.assertRefused("lx", signature=b"LX")

    def test_missing_le_signature(self) -> None:
        self.assertRefused("no le signature", signature=b"XX")

    def test_big_endian_is_refused(self) -> None:
        self.assertRefused("big-endian", byte_order=1)
        self.assertRefused("big-endian", word_order=1)

    def test_unsupported_format_level(self) -> None:
        self.assertRefused("format level", format_level=1)

    def test_unknown_cpu(self) -> None:
        self.assertRefused("cpu", cpu=0x99)

    def test_non_power_of_two_page_size(self) -> None:
        self.assertRefused("power of two", page_size=3000)

    def test_last_page_size_out_of_range(self) -> None:
        self.assertRefused("last page size", last_page_size=0)
        self.assertRefused("last page size", page_size=0x1000, last_page_size=0x2000)

    def test_zero_objects_declared(self) -> None:
        self.assertRefused("zero objects", declared_object_count=0)

    def test_object_page_sum_mismatch(self) -> None:
        # A page map that is internally valid, but longer than the objects map.
        self.assertRefused(
            "objects map",
            declared_page_count=3,
            page_numbers=[1, 2, 3],
            page_flags=[0, 0, 0],
        )

    def test_page_number_out_of_range(self) -> None:
        self.assertRefused("outside", page_numbers=[1, 99])

    def test_iterated_pages_are_named_and_refused(self) -> None:
        self.assertRefused("iterated", page_flags=[0x01, 0x00])

    def test_zero_filled_pages_are_named_and_refused(self) -> None:
        self.assertRefused("zero-filled", page_flags=[0x00, 0x03])

    def test_invalid_object_flag(self) -> None:
        self.assertRefused(
            "invalid",
            objects=[
                {"flags": le_fixture.CODE_FLAGS | 0x0080, "base": 0x10000,
                 "pages": 1, "vsize": 0x200},
                {"flags": le_fixture.DATA_FLAGS, "base": 0x20000,
                 "pages": 1, "vsize": 0x800},
            ],
        )

    def test_entry_outside_its_object(self) -> None:
        self.assertRefused("outside object", eip=0x9999)

    def test_entry_object_out_of_range(self) -> None:
        self.assertRefused("entry object", start_object=7)

    def test_entry_object_must_be_executable(self) -> None:
        self.assertRefused("not executable", start_object=2, eip=0)

    def test_page_data_past_end_of_file(self) -> None:
        self.assertRefused("past end of file", truncate_to=6000)

    def test_lfanew_past_end_of_file(self) -> None:
        # Header start survives truncation, but the LE header no longer fits.
        self.assertRefused("e_lfanew", truncate_to=0x100)

    def test_file_too_small(self) -> None:
        with self.assertRaises(LEError) as caught:
            le_image.LEImage(b"MZ", "tiny.le")
        self.assertIn("too small", str(caught.exception))

    def test_object_table_past_end_of_file(self) -> None:
        # Truncating just after the header leaves no room for the object table.
        self.assertRefused("object table", truncate_to=0x80 + 0x90 + 4)


class TestLoadAndCli(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)
        self.path = self.tmp / "fixture.le"
        self.path.write_bytes(le_fixture.build())

    def test_load_reads_from_disk(self) -> None:
        image = le_image.load(self.path)
        self.assertEqual("fixture.le", image.name)

    def test_load_missing_file_is_refused(self) -> None:
        with self.assertRaises(LEError):
            le_image.load(self.tmp / "absent.le")

    def test_cli_info(self) -> None:
        with quiet():
            self.assertEqual(0, le_image.main(["info", str(self.path)]))

    def test_cli_info_json(self) -> None:
        with quiet():
            self.assertEqual(0, le_image.main(["info", str(self.path), "--json"]))

    def test_cli_strings(self) -> None:
        with quiet():
            self.assertEqual(0, le_image.main(["strings", str(self.path), "--json"]))

    def test_cli_extract_writes_object(self) -> None:
        out = self.tmp / "obj1.bin"
        with quiet():
            self.assertEqual(
                0,
                le_image.main(
                    ["extract", str(self.path), "--object", "1", "-o", str(out)]
                ),
            )
        self.assertEqual(512, out.stat().st_size)

    def test_cli_reports_defects_without_traceback(self) -> None:
        bad = self.tmp / "bad.le"
        bad.write_bytes(le_fixture.build(signature=b"LX"))
        with quiet():
            self.assertEqual(2, le_image.main(["info", str(bad)]))


if __name__ == "__main__":
    unittest.main()
