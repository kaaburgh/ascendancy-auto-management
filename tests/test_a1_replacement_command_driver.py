from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from a1_replacement_command_driver import (
    A1ReplacementCommandDriver,
    A1ReplacementCommandDriverError,
)


class _Completed:
    def __init__(self, *, returncode=0, stdout='{"completed":true}', stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class ReplacementCommandDriverTests(unittest.TestCase):
    def _driver(self):
        return A1ReplacementCommandDriver(
            {
                "new-game-reset": ["helper", "--new-game"],
                "save-load-replacement": ["helper", "--save-load"],
            }
        )

    @patch("a1_replacement_command_driver._run_bounded_process")
    def test_sends_bounded_json_request_without_shell(self, run):
        run.return_value = _Completed(stdout='{"completed":true,"lifecycle_signal":null}')
        got = self._driver()(step_id="reset", mechanism="new-game-reset", timeout_seconds=3)
        self.assertTrue(got["completed"])
        args = run.call_args.args
        self.assertEqual(args[0], ("helper", "--new-game"))
        self.assertEqual(args[2], 3.0)
        request = json.loads(args[1])
        self.assertEqual(request["step_id"], "reset")
        self.assertEqual(request["mechanism"], "new-game-reset")
        self.assertEqual(request["timeout_seconds"], 3.0)

    def test_requires_exact_mechanism_set(self):
        with self.assertRaisesRegex(A1ReplacementCommandDriverError, "define exactly"):
            A1ReplacementCommandDriver({"new-game-reset": ["helper"]})

    @patch("a1_replacement_command_driver._run_bounded_process")
    def test_nonzero_helper_exit_fails_closed(self, run):
        run.return_value = _Completed(returncode=7, stdout="")
        with self.assertRaisesRegex(A1ReplacementCommandDriverError, "exited 7"):
            self._driver()(step_id="load", mechanism="save-load-replacement", timeout_seconds=2)

    @patch("a1_replacement_command_driver._run_bounded_process")
    def test_invalid_json_fails_closed(self, run):
        run.return_value = _Completed(stdout="not-json")
        with self.assertRaisesRegex(A1ReplacementCommandDriverError, "valid JSON"):
            self._driver()(step_id="load", mechanism="save-load-replacement", timeout_seconds=2)

    @patch("a1_replacement_command_driver._run_bounded_process")
    def test_completed_must_be_boolean(self, run):
        run.return_value = _Completed(stdout='{"completed":"yes"}')
        with self.assertRaisesRegex(A1ReplacementCommandDriverError, "completed"):
            self._driver()(step_id="load", mechanism="save-load-replacement", timeout_seconds=2)

    @patch("a1_replacement_command_driver._run_bounded_process")
    def test_lifecycle_signal_must_be_object_or_null(self, run):
        run.return_value = _Completed(stdout='{"completed":true,"lifecycle_signal":"late"}')
        with self.assertRaisesRegex(A1ReplacementCommandDriverError, "lifecycle_signal"):
            self._driver()(step_id="reset", mechanism="new-game-reset", timeout_seconds=2)

    @patch("a1_replacement_command_driver._run_bounded_process")
    def test_timeout_is_normalized(self, run):
        run.side_effect = subprocess.TimeoutExpired(cmd=["helper"], timeout=1)
        with self.assertRaisesRegex(A1ReplacementCommandDriverError, "bounded timeout"):
            self._driver()(step_id="reset", mechanism="new-game-reset", timeout_seconds=1)

    @unittest.skipUnless(hasattr(os, "killpg"), "requires POSIX process groups")
    def test_timeout_kills_helper_descendants(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "descendant-survived"
            child_code = (
                "import pathlib,time; "
                "time.sleep(0.4); "
                f"pathlib.Path({str(marker)!r}).write_text('alive')"
            )
            helper_code = (
                "import subprocess,sys,time; "
                f"subprocess.Popen([sys.executable, '-c', {child_code!r}]); "
                "time.sleep(30)"
            )
            command = [sys.executable, "-c", helper_code]
            driver = A1ReplacementCommandDriver(
                {
                    "new-game-reset": command,
                    "save-load-replacement": command,
                }
            )
            with self.assertRaisesRegex(A1ReplacementCommandDriverError, "bounded timeout"):
                driver(step_id="reset", mechanism="new-game-reset", timeout_seconds=0.1)
            time.sleep(0.6)
            self.assertFalse(marker.exists(), "timed-out helper descendant remained alive")


if __name__ == "__main__":
    unittest.main()
