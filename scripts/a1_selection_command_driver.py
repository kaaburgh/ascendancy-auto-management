"""Bounded command transport for A1 exact-target logical-selection input actions."""
from __future__ import annotations

import json
import os
import signal
import subprocess
from typing import Any, Sequence


class A1SelectionCommandDriverError(RuntimeError):
    """Fail-closed command-driver failure."""


def _run_bounded_process(
    command: Sequence[str], request_text: str, timeout_seconds: float
) -> subprocess.CompletedProcess[str]:
    if not hasattr(os, "killpg"):
        raise A1SelectionCommandDriverError(
            "selection helper process-group cleanup requires POSIX process groups"
        )

    proc = subprocess.Popen(
        tuple(command),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        shell=False,
    )
    try:
        stdout, stderr = proc.communicate(input=request_text, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        raise

    return subprocess.CompletedProcess(tuple(command), proc.returncode, stdout, stderr)


class A1SelectionCommandDriver:
    """Run one preconfigured helper command for a bounded logical selection action."""

    def __init__(self, command: Sequence[str]) -> None:
        if isinstance(command, (str, bytes)) or not isinstance(command, Sequence) or not command:
            raise A1SelectionCommandDriverError("command must be a non-empty argv sequence")
        argv: list[str] = []
        for item in command:
            if not isinstance(item, str) or not item:
                raise A1SelectionCommandDriverError(
                    "command argv entries must be non-empty strings"
                )
            argv.append(item)
        self._command = tuple(argv)

    def __call__(
        self, *, step_id: str, logical_label: str, timeout_seconds: float
    ) -> dict[str, Any]:
        if not isinstance(step_id, str) or not step_id.strip():
            raise A1SelectionCommandDriverError("step_id must be non-empty")
        if not isinstance(logical_label, str) or not logical_label.strip():
            raise A1SelectionCommandDriverError("logical_label must be non-empty")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or timeout_seconds <= 0
        ):
            raise A1SelectionCommandDriverError("timeout_seconds must be positive")

        request = {
            "schema": "ascendancy.a1-selection-action-request/v1",
            "step_id": step_id,
            "logical_label": logical_label,
            "timeout_seconds": float(timeout_seconds),
        }
        request_text = json.dumps(request, separators=(",", ":")) + "\n"
        try:
            completed = _run_bounded_process(
                self._command, request_text, float(timeout_seconds)
            )
        except subprocess.TimeoutExpired as exc:
            raise A1SelectionCommandDriverError(
                "selection helper exceeded bounded timeout"
            ) from exc
        except OSError as exc:
            raise A1SelectionCommandDriverError(
                f"selection helper could not start: {exc}"
            ) from exc

        if completed.returncode != 0:
            raise A1SelectionCommandDriverError(
                f"selection helper exited {completed.returncode}"
            )
        stdout = completed.stdout.strip()
        if not stdout:
            raise A1SelectionCommandDriverError("selection helper produced no result")
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise A1SelectionCommandDriverError(
                "selection helper result is not valid JSON"
            ) from exc
        if not isinstance(result, dict):
            raise A1SelectionCommandDriverError("selection helper result must be an object")
        if not isinstance(result.get("action_completed"), bool):
            raise A1SelectionCommandDriverError(
                "selection helper result.action_completed must be boolean"
            )
        if result.get("action_completed") is True:
            if result.get("logical_label") != logical_label:
                raise A1SelectionCommandDriverError(
                    "selection helper completed an action for a different logical label"
                )
        return result
