#!/usr/bin/env python3
"""Deterministic synthetic-fixture tests for tools/inspect_target.py."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import struct
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import inspect_target as it  # noqa: E402


def synthetic_le(*, extender: bytes = b"DOS/4GW") -> bytes:
    secondary = 0x80
    data = bytearray(secondary + 0x84 + 32)
    data[0:2] = b"MZ"
    struct.pack_into("<H", data, 0x02, 0x1234)
    struct.pack_into("<H", data, 0x04, 7)
    struct.pack_into("<H", data, 0x06, 2)
    struct.pack_into("<H", data, 0x08, 4)
    struct.pack_into("<H", data, 0x0E, 0x1111)
    struct.pack_into("<H", data, 0x10, 0x2222)
    struct.pack_into("<H", data, 0x14, 0x3333)
    struct.pack_into("<H", data, 0x16, 0x4444)
    struct.pack_into("<H", data, 0x18, 0x40)
    struct.pack_into("<H", data, 0x1A, 0)
    struct.pack_into("<I", data, 0x3C, secondary)
    data[0x50 : 0x50 + len(extender)] = extender

    off = secondary
    data[off : off + 2] = b"LE"
    data[off + 0x02] = 0
    data[off + 0x03] = 0
    struct.pack_into("<I", data, off + 0x04, 0)
    struct.pack_into("<H", data, off + 0x08, 2)
    struct.pack_into("<H", data, off + 0x0A, 3)
    struct.pack_into("<I", data, off + 0x0C, 0x01020304)
    struct.pack_into("<I", data, off + 0x10, 0xAABBCCDD)
    struct.pack_into("<I", data, off + 0x14, 9)
    struct.pack_into("<I", data, off + 0x18, 3)
    struct.pack_into("<I", data, off + 0x1C, 0x12345678)
    struct.pack_into("<I", data, off + 0x20, 4)
    struct.pack_into("<I", data, off + 0x24, 0x87654321)
    struct.pack_into("<I", data, off + 0x28, 4096)
    struct.pack_into("<I", data, off + 0x2C, 1024)
    struct.pack_into("<I", data, off + 0x30, 0x50)
    struct.pack_into("<I", data, off + 0x38, 0x60)
    struct.pack_into("<I", data, off + 0x40, 0xB0)
    struct.pack_into("<I", data, off + 0x44, 5)
    struct.pack_into("<I", data, off + 0x48, 0xD0)
    struct.pack_into("<I", data, off + 0x68, 0x130)
    struct.pack_into("<I", data, off + 0x6C, 0x140)
    struct.pack_into("<I", data, off + 0x70, 0x150)
    struct.pack_into("<I", data, off + 0x74, 2)
    struct.pack_into("<I", data, off + 0x78, 0x160)
    struct.pack_into("<I", data, off + 0x80, 0x2000)
    return bytes(data)


class FixtureCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)

    def write(self, name: str, data: bytes) -> pathlib.Path:
        path = self.tmp / name
        path.write_bytes(data)
        return path

    def target(self, path: pathlib.Path, label: str | None = None) -> dict:
        return it.build_target_record(path, str(path), label)


class TestFingerprint(FixtureCase):
    def test_emits_manifest_hash_size_filename_and_label(self) -> None:
        payload = synthetic_le()
        path = self.write("CANDIDATE.EXE", payload)
        target = self.target(path, "candidate 1")
        manifest = it.build_manifest(target)
        self.assertEqual(1, manifest["schema"])
        self.assertEqual([target], manifest["targets"])
        self.assertIsNone(target["id"])
        self.assertEqual("CANDIDATE.EXE", target["filename"])
        self.assertEqual("candidate 1", target["label"])
        self.assertEqual(len(payload), target["size"])
        self.assertEqual(hashlib.sha256(payload).hexdigest(), target["sha256"])

    def test_repeated_capture_is_identical(self) -> None:
        path = self.write("CANDIDATE.EXE", synthetic_le())
        one = it.build_manifest(self.target(path, "same"))
        two = it.build_manifest(self.target(path, "same"))
        self.assertEqual(one, two)
        self.assertEqual(
            json.dumps(one, indent=2, sort_keys=True),
            json.dumps(two, indent=2, sort_keys=True),
        )

    def test_recorded_command_does_not_leak_parent_paths(self) -> None:
        path = self.write("CANDIDATE.EXE", synthetic_le())
        output = self.tmp / "records" / "capture.json"
        target = it.build_target_record(
            path, str(path), "release label", str(output), target_id="candidate-en"
        )
        command = target["capture"]["command"]
        self.assertIn("CANDIDATE.EXE", command)
        self.assertIn("candidate-en", command)
        self.assertIn("release label", command)
        self.assertIn("capture.json", command)
        self.assertNotIn(str(self.tmp), command)

    def test_target_id_is_explicit_and_validated(self) -> None:
        path = self.write("CANDIDATE.EXE", synthetic_le())
        target = it.build_target_record(
            path, str(path), None, target_id="antagonizer-en"
        )
        self.assertEqual("antagonizer-en", target["id"])
        for invalid in ("Antagonizer EN", "../escape", "", "has space"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(it.InspectError):
                    it.build_target_record(
                        path, str(path), None, target_id=invalid
                    )


class TestMZLEParsing(FixtureCase):
    def test_parses_container_and_load_metadata(self) -> None:
        path = self.write("LE.EXE", synthetic_le())
        target = self.target(path)
        self.assertEqual(
            "DOS MZ + Linear Executable (LE)",
            target["container"]["detected_format"],
        )
        self.assertEqual("x86 (Intel 80386)", target["container"]["architecture"])
        self.assertEqual(0x80, target["container"]["mz"]["secondary_header_offset"])
        le = target["container"]["le"]
        self.assertEqual("LE", le["magic"])
        self.assertEqual(2, le["cpu_type"])
        self.assertEqual("Intel 80386", le["cpu_name"])
        self.assertEqual(3, le["os_type"])
        self.assertIsNone(le["os_name"])
        self.assertEqual(4096, le["page_size"])
        self.assertEqual(5, le["object_count"])
        self.assertEqual("0x00002000", le["data_pages_offset"])
        self.assertEqual("DOS/4GW", target["container"]["extender"]["name"])
        self.assertEqual([], target["warnings"])

    def test_mz_without_le_is_reported_without_guessing_architecture(self) -> None:
        payload = bytearray(128)
        payload[:2] = b"MZ"
        struct.pack_into("<I", payload, 0x3C, 0x60)
        payload[0x60:0x62] = b"NE"
        path = self.write("MZ.EXE", bytes(payload))
        target = self.target(path)
        self.assertEqual("DOS MZ", target["container"]["detected_format"])
        self.assertIsNone(target["container"]["architecture"])
        self.assertNotIn("le", target["container"])

    def test_unknown_file_is_fingerprinted_without_format_guess(self) -> None:
        path = self.write("blob.bin", b"not an executable")
        target = self.target(path)
        self.assertEqual("unknown", target["container"]["detected_format"])
        self.assertIsNone(target["container"]["architecture"])
        self.assertEqual([], target["warnings"])

    def test_truncated_mz_is_bounded(self) -> None:
        path = self.write("short.exe", b"MZ" + b"\x00" * 8)
        target = self.target(path)
        self.assertEqual("DOS MZ", target["container"]["detected_format"])
        self.assertEqual(1, len(target["warnings"]))
        self.assertIn("truncated", target["warnings"][0])

    def test_secondary_header_outside_file_is_bounded(self) -> None:
        payload = bytearray(64)
        payload[:2] = b"MZ"
        struct.pack_into("<I", payload, 0x3C, 0x1000)
        path = self.write("bad.exe", bytes(payload))
        target = self.target(path)
        self.assertEqual("DOS MZ", target["container"]["detected_format"])
        self.assertIn("outside the file", target["warnings"][0])

    def test_truncated_le_header_is_reported(self) -> None:
        payload = bytearray(0x80 + 8)
        payload[:2] = b"MZ"
        struct.pack_into("<I", payload, 0x3C, 0x80)
        payload[0x80:0x82] = b"LE"
        path = self.write("bad-le.exe", bytes(payload))
        target = self.target(path)
        self.assertEqual(
            "DOS MZ + Linear Executable (LE)",
            target["container"]["detected_format"],
        )
        self.assertEqual({"magic": "LE"}, target["container"]["le"])
        self.assertIsNone(target["container"]["architecture"])
        self.assertIn("truncated", target["warnings"][0])

    def test_unsupported_le_ordering_does_not_decode_multibyte_metadata(self) -> None:
        for relative_offset in (0x02, 0x03):
            with self.subTest(relative_offset=relative_offset):
                payload = bytearray(synthetic_le())
                payload[0x80 + relative_offset] = 1
                path = self.write(f"order-{relative_offset}.exe", bytes(payload))
                target = self.target(path)
                le = target["container"]["le"]
                self.assertEqual("LE", le["magic"])
                self.assertEqual(
                    1 if relative_offset == 0x02 else 0, le["byte_order"]
                )
                self.assertEqual(
                    1 if relative_offset == 0x03 else 0, le["word_order"]
                )
                self.assertNotIn("cpu_type", le)
                self.assertNotIn("page_size", le)
                self.assertIsNone(target["container"]["architecture"])
                self.assertIn("unsupported byte/word order", target["warnings"][0])

    def test_unknown_le_cpu_type_is_preserved_without_architecture_guess(self) -> None:
        payload = bytearray(synthetic_le())
        struct.pack_into("<H", payload, 0x80 + 0x08, 99)
        path = self.write("odd.exe", bytes(payload))
        target = self.target(path)
        self.assertEqual(99, target["container"]["le"]["cpu_type"])
        self.assertIsNone(target["container"]["le"]["cpu_name"])
        self.assertIsNone(target["container"]["architecture"])

    def test_extender_marker_is_optional(self) -> None:
        path = self.write("noext.exe", synthetic_le(extender=b"NOEXT"))
        target = self.target(path)
        self.assertNotIn("extender", target["container"])


class TestCLI(FixtureCase):
    def test_cli_writes_deterministic_json_file(self) -> None:
        path = self.write("LE.EXE", synthetic_le())
        output = self.tmp / "record.json"
        args = [
            str(path),
            "--id",
            "candidate-en",
            "--label",
            "candidate",
            "--output",
            str(output),
        ]
        self.assertEqual(0, it.main(args))
        first = output.read_text(encoding="utf-8")
        self.assertEqual(0, it.main(args))
        self.assertEqual(first, output.read_text(encoding="utf-8"))
        parsed = json.loads(first)
        self.assertEqual(1, parsed["schema"])
        self.assertEqual("candidate-en", parsed["targets"][0]["id"])
        self.assertEqual(it.TOOL_VERSION, parsed["targets"][0]["capture"]["version"])

    def test_output_cannot_be_the_input_file(self) -> None:
        original = synthetic_le()
        path = self.write("LE.EXE", original)
        self.assertEqual(2, it.main([str(path), "--output", str(path)]))
        self.assertEqual(original, path.read_bytes())

    def test_output_cannot_be_a_hardlink_to_input(self) -> None:
        original = synthetic_le()
        path = self.write("LE.EXE", original)
        alias = self.tmp / "record.json"
        os.link(path, alias)
        self.assertEqual(2, it.main([str(path), "--output", str(alias)]))
        self.assertEqual(original, path.read_bytes())
        self.assertEqual(original, alias.read_bytes())

    def test_output_cannot_be_a_symlink_to_input(self) -> None:
        original = synthetic_le()
        path = self.write("LE.EXE", original)
        alias = self.tmp / "record.json"
        try:
            alias.symlink_to(path)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        self.assertEqual(2, it.main([str(path), "--output", str(alias)]))
        self.assertEqual(original, path.read_bytes())
        self.assertEqual(original, alias.read_bytes())

    def test_missing_input_fails(self) -> None:
        self.assertEqual(2, it.main([str(self.tmp / "missing.exe")]))

    def test_directory_input_fails(self) -> None:
        self.assertEqual(2, it.main([str(self.tmp)]))


class TestCommittedMetadataFiles(unittest.TestCase):
    def test_schema_and_example_are_valid_json(self) -> None:
        schema = json.loads(
            (ROOT / "tools" / "target-manifest.schema.json").read_text(encoding="utf-8")
        )
        example = json.loads(
            (ROOT / "docs" / "re" / "target-manifest.example.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(1, schema["properties"]["schema"]["const"])
        self.assertEqual(1, example["schema"])
        self.assertEqual(1, len(example["targets"]))
        self.assertEqual(
            "synthetic example; not a game binary", example["targets"][0]["label"]
        )


if __name__ == "__main__":
    unittest.main()
