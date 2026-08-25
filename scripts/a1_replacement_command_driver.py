"""Bounded command transport for A1 exact-target replacement actions."""
from __future__ import annotations

import json
import os
import signal
import subprocess
from typing import Any, Mapping, Sequence

_ALLOWED_MECHANISMS = ("new-game-reset", "save-load-replacement")


class A1ReplacementCommandDriverError(RuntimeError):
    """Fail-closed command-driver failure."""


def _run_bounded_process(
    command: Sequence[str], request_text: str, timeout_seconds: float
) -> subprocess.CompletedProcess[str]:
    if not hasattr(os, "killpg"):
        raise A1ReplacementCommandDriverError(
            "replacement helper process-group cleanup requires POSIX process groups"
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


class A1ReplacementCommandDriver:
    """Run one preconfigured helper command per replacement mechanism."""

    def __init__(self, commands: Mapping[str, Sequence[str]]) -> None:
        if not isinstance(commands, Mapping):
            raise A1ReplacementCommandDriverError("commands must be a mapping")
        normalized: dict[str, tuple[str, ...]] = {}
        if set(commands) != set(_ALLOWED_MECHANISMS):
            raise A1ReplacementCommandDriverError(
                "commands must define exactly: " + ", ".join(_ALLOWED_MECHANISMS)
            )
        for mechanism in _ALLOWED_MECHANISMS:
            raw = commands[mechanism]
            if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence) or not raw:
                raise A1ReplacementCommandDriverError(
                    f"{mechanism} command must be a non-empty argv sequence"
                )
            argv: list[str] = []
            for item in raw:
                if not isinstance(item, str) or not item:
                    raise A1ReplacementCommandDriverError(
                        f"{mechanism} command argv entries must be non-empty strings"
                    )
                argv.append(item)
            normalized[mechanism] = tuple(argv)
        self._commands = normalized

    def __call__(
        self, *, step_id: str, mechanism: str, timeout_seconds: float
    ) -> dict[str, Any]:
        if not isinstance(step_id, str) or not step_id.strip():
            raise A1ReplacementCommandDriverError("step_id must be non-empty")
        if mechanism not in self._commands:
            raise A1ReplacementCommandDriverError("unsupported replacement mechanism")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or timeout_seconds <= 0
        ):
            raise A1ReplacementCommandDriverError("timeout_seconds must be positive")

        request = {
            "schema": "ascendancy.a1-replacement-action-request/v1",
            "step_id": step_id,
            "mechanism": mechanism,
            "timeout_seconds": float(timeout_seconds),
        }
        request_text = json.dumps(request, separators=(",", ":")) + "\n"
        try:
            completed = _run_bounded_process(
                self._commands[mechanism], request_text, float(timeout_seconds)
            )
        except subprocess.TimeoutExpired as exc:
            raise A1ReplacementCommandDriverError(
                f"{mechanism} helper exceeded bounded timeout"
            ) from exc
        except OSError as exc:
            raise A1ReplacementCommandDriverError(
                f"{mechanism} helper could not start: {exc}"
            ) from exc

        if completed.returncode != 0:
            raise A1ReplacementCommandDriverError(
                f"{mechanism} helper exited {completed.returncode}"
            )
        stdout = completed.stdout.strip()
        if not stdout:
            raise A1ReplacementCommandDriverError(
                f"{mechanism} helper produced no result"
            )
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise A1ReplacementCommandDriverError(
                f"{mechanism} helper result is not valid JSON"
            ) from exc
        if not isinstance(result, dict):
            raise A1ReplacementCommandDriverError(
                f"{mechanism} helper result must be an object"
            )
        if result.get("step_id") != step_id:
            raise A1ReplacementCommandDriverError(
                f"{mechanism} helper result.step_id does not match request"
            )
        if result.get("mechanism") != mechanism:
            raise A1ReplacementCommandDriverError(
                f"{mechanism} helper result.mechanism does not match request"
            )
        if not isinstance(result.get("completed"), bool):
            raise A1ReplacementCommandDriverError(
                f"{mechanism} helper result.completed must be boolean"
            )
        if "lifecycle_signal" in result and result["lifecycle_signal"] is not None:
            if not isinstance(result["lifecycle_signal"], dict):
                raise A1ReplacementCommandDriverError(
                    f"{mechanism} helper lifecycle_signal must be object or null"
                )
        return result
