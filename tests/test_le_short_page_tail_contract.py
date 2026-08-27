#!/usr/bin/env python3
"""Regression contract for short physical LE pages mapped out of order."""

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import le_fixture  # noqa: E402
import le_image  # noqa: E402


class TestShortPageTailContract(unittest.TestCase):
    def test_virtual_zero_padding_has_no_file_offset(self) -> None:
        """Keep synthesized virtual zeros distinct from physical file bytes."""
        raw = le_fixture.build(
            objects=[
                {
                    "flags": le_fixture.CODE_FLAGS,
                    "base": 0x10000,
                    "pages": 1,
                    "vsize": 0x1000,
                },
                {
                    "flags": le_fixture.DATA_FLAGS,
                    "base": 0x20000,
                    "pages": 1,
                    "vsize": 0x1000,
                },
            ],
            last_page_size=0x200,
            page_numbers=[2, 1],
        )
        image = le_image.LEImage(raw, "short-page-remap.le")
        code = image.objects[0]

        # Physical page 2 is the short final enumerated page. object_bytes()
        # reconstructs its full virtual page with zero padding, but those
        # synthesized bytes intentionally have no backing file offset.
        self.assertEqual(b"\x00" * 0xE00, image.object_bytes(1)[0x200:])
        self.assertIsNone(image.va_to_file_offset(code.base_address + 0x200))
        self.assertIsNone(image.va_to_file_offset(code.end_address - 1))

        # The physically present prefix remains file-backed.
        self.assertIsNotNone(image.va_to_file_offset(code.base_address + 0x1FF))


if __name__ == "__main__":
    unittest.main()
