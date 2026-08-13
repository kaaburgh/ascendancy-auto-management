from __future__ import annotations

import importlib.util
import pathlib
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


if __name__ == "__main__":
    unittest.main()
