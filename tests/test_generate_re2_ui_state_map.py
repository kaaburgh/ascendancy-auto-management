from __future__ import annotations

import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "generate_re2_ui_state_map.py"
spec = importlib.util.spec_from_file_location("generate_re2_ui_state_map", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class RE2UIStateMapTests(unittest.TestCase):
    def test_pattern_parser_masks_wildcards(self):
        values, masks = module.parse_pattern("83 7e ?? 00")
        self.assertEqual(values, bytes.fromhex("83 7e 00 00"))
        self.assertEqual(masks, bytes.fromhex("ff ff 00 ff"))

    def test_pattern_parser_rejects_invalid_token(self):
        with self.assertRaises(module.RE2Error):
            module.parse_pattern("83 xyz")

    def test_find_unique_accepts_one_match(self):
        data = bytes.fromhex("00 aa 11 cc 00 aa 22 dd 00")
        self.assertEqual(module.find_unique(data, "aa ?? cc", "fixture"), 1)

    def test_find_unique_fails_closed_on_zero_or_multiple_matches(self):
        with self.assertRaises(module.RE2Error):
            module.find_unique(b"\x00\x01", "aa", "zero")
        with self.assertRaises(module.RE2Error):
            module.find_unique(bytes.fromhex("aa 00 aa"), "aa", "ambiguous")

    def test_rel32_target_is_signed_and_base_aware(self):
        code = b"\x90\xe8\xfb\xff\xff\xff\x90"
        self.assertEqual(module.rel32_target(code, 1, 0x10000), 0x10001)

    def test_jcc_rel32_target_decodes_je(self):
        code = b"\x0f\x84\x05\x00\x00\x00" + b"\x90" * 5
        self.assertEqual(module.jcc_rel32_target(code, 0, 0x2000), 0x200B)

    def test_c_string_is_bounded(self):
        self.assertEqual(module.c_string(b"abc\0tail", 0), b"abc")
        with self.assertRaises(module.RE2Error):
            module.c_string(b"abc", 0, limit=3)

    def test_user_facing_markers_require_both_semantic_anchors(self):
        payload = (
            b'// 98\r\n"Self Managed"\r\n'
            b'Pressing "M"\r\nwill toggle the Managed feature\r\n'
        )
        self.assertEqual(
            module.verify_user_facing_text(payload),
            {"resource_98_self_managed": True, "tutorial_m_toggle": True},
        )
        with self.assertRaises(module.RE2Error):
            module.verify_user_facing_text(b'// 98\r\n"Self Managed"\r\n')


if __name__ == "__main__":
    unittest.main()
