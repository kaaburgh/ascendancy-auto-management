#!/usr/bin/env python3
"""Bounded X11 helper for A1 logical-selection input actions."""
from __future__ import annotations

import argparse
import ctypes
import json
import sys
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

REQUEST_SCHEMA = "ascendancy.a1-selection-action-request/v1"
EXPECTED_WIDTH = 640
EXPECTED_HEIGHT = 480
ROW_X = 205
FIRST_ROW_Y = 125
ROW_HEIGHT = 145
VISIBLE_ROWS = 3


class A1PlanetRowSelectionError(RuntimeError):
    """Fail-closed helper error."""


def parse_label_rows(values: Sequence[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    used_rows: set[int] = set()
    for raw in values:
        if "=" not in raw:
            raise A1PlanetRowSelectionError("label-row entries must use LABEL=ROW")
        label, row_text = raw.rsplit("=", 1)
        if not label:
            raise A1PlanetRowSelectionError("logical labels must be non-empty")
        if label in mapping:
            raise A1PlanetRowSelectionError(f"duplicate logical label: {label!r}")
        try:
            row = int(row_text, 10)
        except ValueError as exc:
            raise A1PlanetRowSelectionError(f"row must be an integer: {row_text!r}") from exc
        if row < 0 or row >= VISIBLE_ROWS:
            raise A1PlanetRowSelectionError(
                f"row must be in [0, {VISIBLE_ROWS - 1}], got {row}"
            )
        if row in used_rows:
            raise A1PlanetRowSelectionError(f"duplicate visible row mapping: {row}")
        mapping[label] = row
        used_rows.add(row)
    if not mapping:
        raise A1PlanetRowSelectionError("at least one --label-row mapping is required")
    return mapping


def validate_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise A1PlanetRowSelectionError("request must be a JSON object")
    if value.get("schema") != REQUEST_SCHEMA:
        raise A1PlanetRowSelectionError("unsupported request schema")
    step_id = value.get("step_id")
    logical_label = value.get("logical_label")
    timeout_seconds = value.get("timeout_seconds")
    if not isinstance(step_id, str) or not step_id.strip():
        raise A1PlanetRowSelectionError("step_id must be non-empty")
    if not isinstance(logical_label, str) or not logical_label:
        raise A1PlanetRowSelectionError("logical_label must be non-empty")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or timeout_seconds <= 0
    ):
        raise A1PlanetRowSelectionError("timeout_seconds must be positive")
    return value


@dataclass(frozen=True)
class WindowGeometry:
    width: int
    height: int


class X11SelectionBackend:
    """Minimal X11/XTest backend. No target semantics are inferred here."""

    def __init__(self, display_name: str, window_id: int) -> None:
        try:
            self._x11 = ctypes.CDLL("libX11.so.6")
            self._xtst = ctypes.CDLL("libXtst.so.6")
        except OSError as exc:
            raise A1PlanetRowSelectionError(f"X11/XTest libraries unavailable: {exc}") from exc

        self._x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self._x11.XOpenDisplay.restype = ctypes.c_void_p
        self._x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self._x11.XGetGeometry.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
        ]
        self._x11.XGetGeometry.restype = ctypes.c_int
        self._x11.XSetInputFocus.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong
        ]
        self._x11.XFlush.argtypes = [ctypes.c_void_p]
        self._xtst.XTestFakeRelativeMotionEvent.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_ulong
        ]
        self._xtst.XTestFakeButtonEvent.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong
        ]

        self._display = self._x11.XOpenDisplay(display_name.encode())
        if not self._display:
            raise A1PlanetRowSelectionError(f"XOpenDisplay failed: {display_name}")
        self._window_id = window_id

    def close(self) -> None:
        if self._display:
            self._x11.XCloseDisplay(self._display)
            self._display = None

    def geometry(self) -> WindowGeometry:
        root = ctypes.c_ulong()
        x = ctypes.c_int()
        y = ctypes.c_int()
        width = ctypes.c_uint()
        height = ctypes.c_uint()
        border = ctypes.c_uint()
        depth = ctypes.c_uint()
        ok = self._x11.XGetGeometry(
            self._display,
            self._window_id,
            ctypes.byref(root),
            ctypes.byref(x),
            ctypes.byref(y),
            ctypes.byref(width),
            ctypes.byref(height),
            ctypes.byref(border),
            ctypes.byref(depth),
        )
        if not ok:
            raise A1PlanetRowSelectionError(
                f"XGetGeometry failed for window {self._window_id:#x}"
            )
        return WindowGeometry(width=width.value, height=height.value)

    def click(self, x: int, y: int) -> None:
        self._x11.XSetInputFocus(self._display, self._window_id, 1, 0)
        self._xtst.XTestFakeRelativeMotionEvent(self._display, -2000, -2000, 0)
        self._xtst.XTestFakeRelativeMotionEvent(self._display, x, y, 0)
        self._xtst.XTestFakeButtonEvent(self._display, 1, 1, 0)
        self._xtst.XTestFakeButtonEvent(self._display, 1, 0, 0)
        self._x11.XFlush(self._display)


def handle_request(
    request: Any,
    label_rows: Mapping[str, int],
    backend: Any,
) -> dict[str, Any]:
    value = validate_request(request)
    logical_label = value["logical_label"]
    if logical_label not in label_rows:
        raise A1PlanetRowSelectionError(
            f"logical label is not configured: {logical_label!r}"
        )
    row = label_rows[logical_label]
    if not isinstance(row, int) or isinstance(row, bool) or not 0 <= row < VISIBLE_ROWS:
        raise A1PlanetRowSelectionError("configured row is outside the visible-row contract")

    geometry = backend.geometry()
    if (geometry.width, geometry.height) != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
        raise A1PlanetRowSelectionError(
            f"expected {EXPECTED_WIDTH}x{EXPECTED_HEIGHT} target window, "
            f"got {geometry.width}x{geometry.height}"
        )

    y = FIRST_ROW_Y + row * ROW_HEIGHT
    backend.click(ROW_X, y)
    return {
        "action_completed": True,
        "logical_label": logical_label,
        "step_id": value["step_id"],
        "visible_row": row,
    }


def _window_id(value: str) -> int:
    try:
        parsed = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("window must be an integer or 0x-prefixed integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("window must be positive")
    return parsed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--display", required=True)
    parser.add_argument("--window", required=True, type=_window_id)
    parser.add_argument("--label-row", action="append", default=[])
    args = parser.parse_args(argv)

    backend = None
    try:
        label_rows = parse_label_rows(args.label_row)
        try:
            request = json.load(sys.stdin)
        except json.JSONDecodeError as exc:
            raise A1PlanetRowSelectionError("stdin is not valid JSON") from exc
        backend = X11SelectionBackend(args.display, args.window)
        result = handle_request(request, label_rows, backend)
        json.dump(result, sys.stdout, separators=(",", ":"))
        sys.stdout.write("\n")
        return 0
    except A1PlanetRowSelectionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        if backend is not None:
            backend.close()


if __name__ == "__main__":
    raise SystemExit(main())
