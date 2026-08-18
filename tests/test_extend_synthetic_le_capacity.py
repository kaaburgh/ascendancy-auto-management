from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(SCRIPTS))

import le_fixture  # noqa: E402
import le_image  # noqa: E402
import extend_synthetic_le_capacity as growth  # noqa: E402


class SyntheticLEGrowthTests(unittest.TestCase):
    def setUp(self):
        self.fixture = le_fixture.build()
        self.before = le_image.LEImage(self.fixture)

    def test_growing_code_object_maps_appended_payload_and_preserves_other_object(self):
        payload = b"\x31\xc0\xc3"
        transformed = growth.grow_mapped_object(self.fixture, 1, payload)
        after = le_image.LEImage(transformed)

        self.assertEqual(after.page_count, self.before.page_count + 1)
        self.assertEqual(after.objects[0].page_count, self.before.objects[0].page_count + 1)
        self.assertEqual(after.objects[1].first_page, self.before.objects[1].first_page + 1)
        self.assertEqual(after.page_numbers, [1, 3, 2])
        self.assertEqual(after.data_page_offset, self.before.data_page_offset)
        self.assertEqual(len(transformed), len(self.fixture) + self.before.page_size)
        self.assertEqual(after.object_bytes(1)[self.before.page_size : self.before.page_size + len(payload)], payload)
        self.assertEqual(after.object_bytes(2), self.before.object_bytes(2))
        self.assertEqual(
            after.object_bytes(1)[: self.before.objects[0].virtual_size],
            self.before.object_bytes(1),
        )

    def test_growing_final_data_object_appends_logical_and_physical_page(self):
        payload = b"stage-two-control"
        transformed = growth.grow_mapped_object(self.fixture, 2, payload)
        after = le_image.LEImage(transformed)

        self.assertEqual(after.page_numbers, [1, 2, 3])
        self.assertEqual(after.objects[1].page_count, 2)
        self.assertEqual(
            after.object_bytes(2)[self.before.page_size : self.before.page_size + len(payload)],
            payload,
        )
        self.assertEqual(after.object_bytes(1), self.before.object_bytes(1))

    def test_transformation_is_deterministic(self):
        payload = bytes.fromhex("9090c3")
        first = growth.grow_mapped_object(self.fixture, 1, payload)
        second = growth.grow_mapped_object(self.fixture, 1, payload)
        self.assertEqual(first, second)
        self.assertEqual(hashlib.sha256(first).digest(), hashlib.sha256(second).digest())

    def test_empty_and_oversized_payloads_fail_closed(self):
        with self.assertRaisesRegex(growth.GrowthError, "non-empty"):
            growth.grow_mapped_object(self.fixture, 1, b"")
        with self.assertRaisesRegex(growth.GrowthError, "at most"):
            growth.grow_mapped_object(self.fixture, 1, b"x" * (self.before.page_size + 1))

    def test_short_final_physical_page_fails_closed(self):
        fixture = le_fixture.build(last_page_size=0x800)
        with self.assertRaisesRegex(growth.GrowthError, "full final physical page"):
            growth.grow_mapped_object(fixture, 1, b"x")

    def test_trailing_structure_bytes_fail_closed(self):
        fixture = self.fixture + b"suffix"
        with self.assertRaisesRegex(growth.GrowthError, "end exactly at EOF"):
            growth.grow_mapped_object(fixture, 1, b"x")

    def test_nonzero_page_map_slack_fails_closed(self):
        fixture = bytearray(self.fixture)
        fixture[self.before.page_map_file_end] = 0x7F
        with self.assertRaisesRegex(growth.GrowthError, "not all zero"):
            growth.grow_mapped_object(bytes(fixture), 1, b"x")

    def test_canonical_target_identity_is_explicitly_refused(self):
        digest = hashlib.sha256(self.fixture).hexdigest()
        with mock.patch.object(growth, "CANONICAL_TARGET_SHA256", digest):
            with self.assertRaisesRegex(growth.GrowthError, "canonical Ascendancy target"):
                growth.grow_mapped_object(self.fixture, 1, b"x")

    def test_cli_refuses_input_output_alias_and_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "control.exe"
            source.write_bytes(self.fixture)
            self.assertEqual(
                growth.main([str(source), str(source), "--object", "1", "--payload-hex", "90c3"]),
                1,
            )
            output = directory / "grown.exe"
            output.write_bytes(b"do-not-overwrite")
            self.assertEqual(
                growth.main([str(source), str(output), "--object", "1", "--payload-hex", "90c3"]),
                1,
            )
            self.assertEqual(output.read_bytes(), b"do-not-overwrite")


if __name__ == "__main__":
    unittest.main()
