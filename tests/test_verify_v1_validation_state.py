#!/usr/bin/env python3
"""Tests for the V1 operator-supplied validation-state verifier."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_v1_validation_state as v1  # noqa: E402


class V1VerifierCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)
        self.input_dir = self.tmp / "inputs"
        self.input_dir.mkdir()
        self.manual = b"\x00\x01shared synthetic suffix"
        self.resume = b"\x02\x03shared synthetic suffix"
        (self.input_dir / "02.SAV").write_bytes(self.manual)
        (self.input_dir / "resume.gam").write_bytes(self.resume)
        self.manifest = self.tmp / "manifest.json"
        self.manifest.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "id": v1.MANIFEST_ID,
                    "files": [
                        {
                            "name": "02.SAV",
                            "role": "manual_save",
                            "size": len(self.manual),
                            "sha256": hashlib.sha256(self.manual).hexdigest(),
                        },
                        {
                            "name": "resume.gam",
                            "role": "resume_companion",
                            "size": len(self.resume),
                            "sha256": hashlib.sha256(self.resume).hexdigest(),
                        },
                    ],
                    "pair_observation": {
                        "differing_byte_count": 2,
                        "highest_differing_offset": "0x1",
                        "identical_from_offset": "0x2",
                        "identical_suffix_sha256": hashlib.sha256(self.manual[2:]).hexdigest(),
                    },
                }
            ),
            encoding="utf-8",
        )

    def run_tool(self) -> int:
        with contextlib.redirect_stdout(io.StringIO()):
            return v1.main(
                ["--input-dir", str(self.input_dir)], manifest_path=self.manifest
            )


class TestHappyPath(V1VerifierCase):
    def test_synthetic_pair_passes_through_internal_manifest_seam(self) -> None:
        self.assertEqual(0, self.run_tool())

    def test_tampered_input_fails_closed(self) -> None:
        (self.input_dir / "02.SAV").write_bytes(self.manual + b"tampered")
        with self.assertRaises(v1.VerificationError):
            self.run_tool()


class TestManifestOverrideIsNotExposed(V1VerifierCase):
    def test_cli_rejects_manifest_option(self) -> None:
        with self.assertRaises(SystemExit):
            v1.main(
                [
                    "--manifest",
                    str(self.manifest),
                    "--input-dir",
                    str(self.input_dir),
                ]
            )

    def test_parser_exposes_no_manifest_naming_flags(self) -> None:
        flags = {
            option
            for action in v1.build_parser()._actions
            for option in action.option_strings
        }
        for forbidden in ("--manifest", "--sha256", "--file"):
            self.assertNotIn(forbidden, flags)

    def test_cli_default_is_repository_manifest(self) -> None:
        self.assertEqual(
            ROOT / "tools" / "v1-validation-state-manifest.json",
            v1.MANIFEST_PATH,
        )
        committed = v1.load_manifest(v1.MANIFEST_PATH)
        self.assertEqual(v1.MANIFEST_ID, committed["id"])


if __name__ == "__main__":
    unittest.main()
