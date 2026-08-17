from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "run_re4_runtime_state.py"
spec = importlib.util.spec_from_file_location("run_re4_runtime_state", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class RE4RuntimeStateTests(unittest.TestCase):
    def test_masked_find_accepts_relocation_bytes(self):
        data = b"\0" + bytes.fromhex("8b525aa112345678f7d289505ae932010000833d") + b"\0"
        self.assertEqual(module.find_masked(data, module.TOGGLE_PATTERN), [1])

    def test_masked_find_reports_multiple_matches(self):
        one = bytes.fromhex("8b525aa100000000f7d289505ae932010000833d")
        self.assertEqual(module.find_masked(one + b"x" + one, module.TOGGLE_PATTERN), [0, len(one) + 1])

    def test_transition_record_filters_unrelated_toggle_by_name_and_offsets(self):
        size = 0x400
        before = bytearray(size)
        managed = bytearray(size)
        restored = bytearray(size)
        real_base = 0x100
        false_field = 0x50
        before[real_base + module.NAME_OFFSET:real_base + module.NAME_OFFSET + 9] = b"Xerxes I\0"
        managed[:] = before
        restored[:] = before
        managed[false_field:false_field + 4] = module.MANAGED
        managed[real_base + module.STATE_OFFSET:real_base + module.STATE_OFFSET + 4] = module.MANAGED
        result = module.find_transition_record(bytes(before), bytes(managed), bytes(restored), "Xerxes I")
        self.assertEqual(result["record_offset_in_snapshot"], real_base)
        self.assertEqual(result["field_offset_in_snapshot"], real_base + module.STATE_OFFSET)

    def test_transition_record_fails_closed_on_missing_or_ambiguous_structured_candidate(self):
        before = bytearray(0x500)
        managed = bytearray(before)
        restored = bytearray(before)
        with self.assertRaises(module.RE4Error):
            module.find_transition_record(bytes(before), bytes(managed), bytes(restored), "Xerxes I")
        for base in (0x100, 0x200):
            before[base + module.NAME_OFFSET:base + module.NAME_OFFSET + 9] = b"Xerxes I\0"
            managed[base + module.NAME_OFFSET:base + module.NAME_OFFSET + 9] = b"Xerxes I\0"
            restored[base + module.NAME_OFFSET:base + module.NAME_OFFSET + 9] = b"Xerxes I\0"
            managed[base + module.STATE_OFFSET:base + module.STATE_OFFSET + 4] = module.MANAGED
        with self.assertRaises(module.RE4Error):
            module.find_transition_record(bytes(before), bytes(managed), bytes(restored), "Xerxes I")

    def test_transition_record_rejects_wrong_restore_value(self):
        before = bytearray(0x300)
        managed = bytearray(before)
        restored = bytearray(before)
        base = 0x100
        for buf in (before, managed, restored):
            buf[base + module.NAME_OFFSET:base + module.NAME_OFFSET + 10] = b"Shlupp IV\0"
        field = base + module.STATE_OFFSET
        managed[field:field + 4] = module.MANAGED
        restored[field:field + 4] = module.MANAGED
        with self.assertRaises(module.RE4Error):
            module.find_transition_record(bytes(before), bytes(managed), bytes(restored), "Shlupp IV")

    def test_fixture_manifest_is_pinned_to_committed_contract(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            custom = root / "custom.json"
            custom.write_text(json.dumps({"schema": 1, "files": []}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(module.RE4Error, "must exactly match"):
                module.verify_fixture(root, custom)

    def test_fixture_rejects_case_insensitive_filename_collisions(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "ANTAG.EXE").write_bytes(b"a")
            (root / "antag.exe").write_bytes(b"b")
            with self.assertRaisesRegex(module.RE4Error, "ambiguous case-insensitive"):
                module.verify_fixture(root, module.RETAIL_MANIFEST)

    def test_committed_manifest_hash_is_pinned(self):
        self.assertEqual(module.sha256_file(module.RETAIL_MANIFEST), module.RETAIL_MANIFEST_SHA256)

    def test_renderer_transition_requires_manual_managed_manual_differential(self):
        manual = "1" * 64
        result = module.validate_renderer_transition(manual, module.SELF_MANAGED_RGB_SHA256, manual)
        self.assertTrue(result["managed_matches_pinned_oracle"])
        self.assertTrue(result["manual_differs_from_managed"])
        self.assertTrue(result["restored_matches_manual"])

    def test_renderer_transition_rejects_same_manual_and_managed_region(self):
        managed = module.SELF_MANAGED_RGB_SHA256
        with self.assertRaisesRegex(module.RE4Error, "not differential"):
            module.validate_renderer_transition(managed, managed, managed)

    def test_renderer_transition_rejects_nonrestoring_manual_region(self):
        with self.assertRaisesRegex(module.RE4Error, "did not return"):
            module.validate_renderer_transition("1" * 64, module.SELF_MANAGED_RGB_SHA256, "2" * 64)

    def test_renderer_transition_rejects_wrong_managed_oracle(self):
        with self.assertRaisesRegex(module.RE4Error, "oracle mismatch"):
            module.validate_renderer_transition("1" * 64, "2" * 64, "1" * 64)

    def test_planet_list_row_coordinates_are_bounded(self):
        self.assertEqual(module.planet_list_row_y(0), 125)
        self.assertEqual(module.planet_list_row_y(1), 270)
        self.assertEqual(module.planet_list_row_y(2), 415)

    def test_self_managed_region_tracks_selected_row(self):
        self.assertEqual(module.self_managed_region(0), module.SELF_MANAGED_REGION)
        self.assertEqual(module.self_managed_region(1), (280, 214, 100, 8))
        self.assertEqual(module.self_managed_region(2), (280, 355, 100, 8))
        with self.assertRaises(module.RE4Error):
            module.self_managed_region(3)

    def test_select_planet_list_row_uses_requested_row(self):
        class FakeInput:
            def __init__(self):
                self.moves = []
                self.clicks = 0

            def move_to(self, x, y):
                self.moves.append((x, y))

            def click(self):
                self.clicks += 1

        inp = FakeInput()
        module.select_planet_list_row(inp, 2)
        self.assertEqual(inp.moves, [(205, 415)])
        self.assertEqual(inp.clicks, 1)
        with self.assertRaises(module.RE4Error):
            module.planet_list_row_y(3)


if __name__ == "__main__":
    unittest.main()
