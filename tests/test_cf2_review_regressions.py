#!/usr/bin/env python3
"""Regression tests for late CF2 review findings."""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from scripts import validate_cf2_real_targets  # noqa: E402
import le_fixture  # noqa: E402
import le_image  # noqa: E402


class TestShortPhysicalPageReconstruction(unittest.TestCase):
    def test_short_page_is_padded_before_next_virtual_page(self) -> None:
        page_size = 0x1000
        short_size = 0x100
        raw = le_fixture.build(
            objects=[
                {
                    "flags": le_fixture.CODE_FLAGS,
                    "base": 0x10000,
                    "pages": 2,
                    "vsize": 2 * page_size,
                },
                {
                    "flags": le_fixture.DATA_FLAGS,
                    "base": 0x20000,
                    "pages": 1,
                    "vsize": short_size,
                },
            ],
            page_size=page_size,
            last_page_size=short_size,
            # Object 1 maps the physically last, short page first, then a
            # normal full page. Object 2 maps the remaining physical page.
            page_numbers=[3, 1, 2],
        )
        image = le_image.LEImage(raw, "nonsequential-short.le")

        rebuilt = image.object_bytes(1)
        short_offset = image.page_file_offset(3)
        second_offset = image.page_file_offset(1)

        self.assertEqual(raw[short_offset : short_offset + short_size], rebuilt[:short_size])
        self.assertEqual(
            b"\x00" * (page_size - short_size),
            rebuilt[short_size:page_size],
        )
        self.assertEqual(
            raw[second_offset : second_offset + 32],
            rebuilt[page_size : page_size + 32],
        )
        self.assertEqual(
            second_offset,
            image.va_to_file_offset(image.objects[0].base_address + page_size),
        )


class TestSelectedBinaryDirectory(unittest.TestCase):
    def test_fetch_and_verify_use_selected_directory(self) -> None:
        selected = pathlib.Path("somewhere") / "custom-targets"
        resolved = selected.resolve()

        with mock.patch.object(validate_cf2_real_targets, "run") as run:
            actual = validate_cf2_real_targets.prepare_targets(selected, fetch=True)

        command = [
            sys.executable,
            "tools/fetch_free_targets.py",
            "--dest",
            str(resolved),
        ]
        self.assertEqual(resolved, actual)
        self.assertEqual(
            [mock.call(command), mock.call([*command, "--verify"])],
            run.call_args_list,
        )


if __name__ == "__main__":
    unittest.main()
