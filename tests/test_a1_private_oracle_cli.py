from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ORACLE = ROOT / "scripts" / "_a1_sidecar_lifetime_oracle_core.py"
PUBLIC_ORACLE = ROOT / "scripts" / "a1_sidecar_lifetime_oracle.py"


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


if __name__ == "__main__":
    unittest.main()
