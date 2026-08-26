from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ORACLE = ROOT / "scripts" / "_a1_sidecar_lifetime_oracle_core.py"
PUBLIC_ORACLE = ROOT / "scripts" / "a1_sidecar_lifetime_oracle.py"


def _incomplete_record() -> dict:
    return {
        "schema": "ascendancy.a1-sidecar-runtime-lifetime/v1",
        "outcome": "incomplete-harness",
        "claims": {
            "array_base_established": False,
            "array_count_established": False,
            "stable_index_established": False,
            "reuse_detector_established": False,
            "epoch_boundary_established": False,
            "manual_transition_invalidation_established": False,
        },
        "control": {"passed": False},
        "transitions": [],
    }


class A1PrivateOracleCliTests(unittest.TestCase):
    def test_private_core_refuses_direct_cli_execution(self) -> None:
        result = subprocess.run(
            [sys.executable, str(PRIVATE_ORACLE), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("private module is not a CLI", output)
        self.assertIn("scripts/a1_sidecar_lifetime_oracle.py", output)
        self.assertNotIn("positive_contract_accepted", output)

    def test_public_oracle_remains_the_cli_entry_point(self) -> None:
        result = subprocess.run(
            [sys.executable, str(PUBLIC_ORACLE), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--scenario-manifest", result.stdout)
        self.assertIn("--expected-source", result.stdout)

    def test_public_oracle_emits_json_for_nonpositive_record(self) -> None:
        with TemporaryDirectory() as tmpdir:
            record = Path(tmpdir) / "record.json"
            record.write_text(json.dumps(_incomplete_record()), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(PUBLIC_ORACLE), str(record)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["outcome"], "incomplete-harness")
        self.assertFalse(payload["positive_contract_accepted"])

    def test_public_oracle_preserves_parser_error_on_invalid_json(self) -> None:
        with TemporaryDirectory() as tmpdir:
            record = Path(tmpdir) / "broken.json"
            record.write_text("{", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(PUBLIC_ORACLE), str(record)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
