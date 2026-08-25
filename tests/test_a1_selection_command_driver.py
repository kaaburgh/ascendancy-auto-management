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

from a1_selection_command_driver import (
    A1SelectionCommandDriver,
    A1SelectionCommandDriverError,
)


class _Completed:
    def __init__(self, *, returncode=0, stdout='{"selected":true,"logical_label":"A"}', stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class SelectionCommandDriverTests(unittest.TestCase):
    def _driver(self):
        return A1SelectionCommandDriver(["helper", "--select"])

    @patch("a1_selection_command_driver._run_bounded_process")
    def test_sends_bounded_json_request_without_shell(self, run):
        run.return_value = _Completed()
        got = self._driver()(step_id="control-a", logical_label="A", timeout_seconds=3)
        self.assertTrue(got["selected"])
        args = run.call_args.args
        self.assertEqual(args[0], ("helper", "--select"))
        self.assertEqual(args[2], 3.0)
        request = json.loads(args[1])
        self.assertEqual(request["schema"], "ascendancy.a1-selection-action-request/v1")
        self.assertEqual(request["step_id"], "control-a")
        self.assertEqual(request["logical_label"], "A")
        self.assertEqual(request["timeout_seconds"], 3.0)

    def test_requires_argv_sequence(self):
        with self.assertRaisesRegex(A1SelectionCommandDriverError, "argv sequence"):
            A1SelectionCommandDriver("helper --select")

    @patch("a1_selection_command_driver._run_bounded_process")
    def test_nonzero_helper_exit_fails_closed(self, run):
        run.return_value = _Completed(returncode=7, stdout="")
        with self.assertRaisesRegex(A1SelectionCommandDriverError, "exited 7"):
            self._driver()(step_id="control-a", logical_label="A", timeout_seconds=2)

    @patch("a1_selection_command_driver._run_bounded_process")
    def test_invalid_json_fails_closed(self, run):
        run.return_value = _Completed(stdout="not-json")
        with self.assertRaisesRegex(A1SelectionCommandDriverError, "valid JSON"):
            self._driver()(step_id="control-a", logical_label="A", timeout_seconds=2)

    @patch("a1_selection_command_driver._run_bounded_process")
    def test_selected_must_be_boolean(self, run):
        run.return_value = _Completed(stdout='{"selected":"yes","logical_label":"A"}')
        with self.assertRaisesRegex(A1SelectionCommandDriverError, "selected"):
            self._driver()(step_id="control-a", logical_label="A", timeout_seconds=2)

    @patch("a1_selection_command_driver._run_bounded_process")
    def test_confirmed_selection_must_echo_requested_label(self, run):
        run.return_value = _Completed(stdout='{"selected":true,"logical_label":"B"}')
        with self.assertRaisesRegex(A1SelectionCommandDriverError, "different logical label"):
            self._driver()(step_id="control-a", logical_label="A", timeout_seconds=2)

    @patch("a1_selection_command_driver._run_bounded_process")
    def test_unconfirmed_selection_does_not_require_label_echo(self, run):
        run.return_value = _Completed(stdout='{"selected":false}')
        got = self._driver()(step_id="control-a", logical_label="A", timeout_seconds=2)
        self.assertFalse(got["selected"])

    @patch("a1_selection_command_driver._run_bounded_process")
    def test_timeout_is_normalized(self, run):
        run.side_effect = subprocess.TimeoutExpired(cmd=["helper"], timeout=1)
        with self.assertRaisesRegex(A1SelectionCommandDriverError, "bounded timeout"):
            self._driver()(step_id="control-a", logical_label="A", timeout_seconds=1)

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
            driver = A1SelectionCommandDriver([sys.executable, "-c", helper_code])
            with self.assertRaisesRegex(A1SelectionCommandDriverError, "bounded timeout"):
                driver(step_id="control-a", logical_label="A", timeout_seconds=0.1)
            time.sleep(0.6)
            self.assertFalse(marker.exists(), "timed-out helper descendant remained alive")


if __name__ == "__main__":
    unittest.main()
