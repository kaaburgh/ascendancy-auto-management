#!/usr/bin/env python3
"""Drive a bounded Ascendancy UI scenario under Xvfb and capture evidence."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import tempfile
import time
from typing import Any

ACTION_SCHEMA = 2
RUN_SCHEMA = 2
MAX_PRE_VIDEO_CHORDS = 8
MAX_STEPS = 64
MAX_CAPTURES = 16
MAX_ORACLES_PER_CAPTURE = 4
MAX_SETTLE_SECONDS = 10.0
MAX_RUNTIME_SECONDS = 180.0
EXPECTED_FRAME = (640, 480)
SAFE_CAPTURE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DOSBOX_WINDOW_RE = re.compile(r'^\s*(0x[0-9a-fA-F]+)\s+"DOSBox ')


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _bounded_number(value: Any, *, low: float, high: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not (low <= float(value) <= high):
        raise ValueError(f"{label} must be between {low:g} and {high:g}")
    return float(value)


def _bounded_int(value: Any, *, low: int, high: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not (low <= value <= high):
        raise ValueError(f"{label} must be between {low} and {high}")
    return value


def _casefold_index(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for p in root.iterdir():
        if not p.is_file():
            continue
        key = p.name.casefold()
        if key in out:
            raise ValueError(f"ambiguous case-insensitive filename: {p.name}")
        out[key] = p
    return out


def verify_fixture(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != 1 or not isinstance(manifest.get("files"), list):
        raise ValueError("unsupported fixture manifest")
    index = _casefold_index(root)
    verified = []
    for entry in manifest["files"]:
        name = entry.get("name")
        if not isinstance(name, str):
            raise ValueError("manifest file entry is missing name")
        p = index.get(name.casefold())
        if p is None:
            raise ValueError(f"fixture file missing: {name}")
        size = p.stat().st_size
        digest = sha256_file(p)
        if size != entry.get("size"):
            raise ValueError(f"fixture size mismatch for {name}: {size}")
        if digest != entry.get("sha256"):
            raise ValueError(f"fixture sha256 mismatch for {name}: {digest}")
        verified.append({"name": name, "size": size, "sha256": digest})
    return {"id": manifest.get("id"), "schema": 1, "files": verified}


def _validate_oracle(oracle: Any, *, step_index: int, oracle_index: int) -> None:
    label = f"step {step_index} oracle {oracle_index}"
    if not isinstance(oracle, dict) or oracle.get("type") != "rgb_region_sha256":
        raise ValueError(f"{label}: unsupported oracle")
    x = _bounded_int(oracle.get("x"), low=0, high=EXPECTED_FRAME[0] - 1, label=f"{label} x")
    y = _bounded_int(oracle.get("y"), low=0, high=EXPECTED_FRAME[1] - 1, label=f"{label} y")
    width = _bounded_int(oracle.get("width"), low=1, high=EXPECTED_FRAME[0], label=f"{label} width")
    height = _bounded_int(oracle.get("height"), low=1, high=EXPECTED_FRAME[1], label=f"{label} height")
    if x + width > EXPECTED_FRAME[0] or y + height > EXPECTED_FRAME[1]:
        raise ValueError(f"{label}: region exceeds {EXPECTED_FRAME[0]}x{EXPECTED_FRAME[1]} frame")
    digest = oracle.get("sha256")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        raise ValueError(f"{label}: sha256 must be 64 lowercase hex characters")


def _validate_settle(step: dict[str, Any], *, step_index: int) -> None:
    if "settle_seconds" in step:
        _bounded_number(
            step["settle_seconds"], low=0, high=MAX_SETTLE_SECONDS,
            label=f"step {step_index} settle_seconds",
        )


def load_actions(path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if cfg.get("schema") != ACTION_SCHEMA:
        raise ValueError(f"unsupported action schema; expected {ACTION_SCHEMA}")
    if not isinstance(cfg.get("name"), str) or not cfg["name"]:
        raise ValueError("action config requires a name")
    startup = _bounded_number(
        cfg.get("startup_wait_seconds", 0), low=0, high=60,
        label="startup_wait_seconds",
    )
    max_runtime = _bounded_number(
        cfg.get("max_runtime_seconds", 90), low=5, high=MAX_RUNTIME_SECONDS,
        label="max_runtime_seconds",
    )
    pre_video = cfg.get("pre_video_key_chords", [])
    if not isinstance(pre_video, list) or len(pre_video) > MAX_PRE_VIDEO_CHORDS:
        raise ValueError(f"pre_video_key_chords must be a list with at most {MAX_PRE_VIDEO_CHORDS} entries")
    for i, keys in enumerate(pre_video):
        if not isinstance(keys, list) or not (1 <= len(keys) <= 4) or not all(isinstance(k, str) and k for k in keys):
            raise ValueError(f"pre_video_key_chords[{i}] requires 1..4 key names")
    steps = cfg.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("action config requires non-empty steps")
    if len(steps) > MAX_STEPS:
        raise ValueError(f"action config has too many steps; maximum is {MAX_STEPS}")

    capture_names: set[str] = set()
    capture_steps: list[dict[str, Any]] = []
    oracle_count = 0
    estimated_sleep = startup + 0.5 * len(pre_video)
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"step {i} is not an object")
        action = step.get("action")
        if action == "wait":
            seconds = _bounded_number(step.get("seconds"), low=0, high=30, label=f"step {i} wait seconds")
            estimated_sleep += seconds
        elif action == "capture":
            name = step.get("name")
            if not isinstance(name, str) or not SAFE_CAPTURE_RE.fullmatch(name):
                raise ValueError(f"step {i}: unsafe capture name")
            if name in capture_names:
                raise ValueError(f"step {i}: duplicate capture name {name!r}")
            capture_names.add(name)
            capture_steps.append(step)
            if len(capture_steps) > MAX_CAPTURES:
                raise ValueError(f"action config has too many captures; maximum is {MAX_CAPTURES}")
            oracles = step.get("oracles", [])
            if not isinstance(oracles, list) or len(oracles) > MAX_ORACLES_PER_CAPTURE:
                raise ValueError(f"step {i}: oracles must be a list with at most {MAX_ORACLES_PER_CAPTURE} entries")
            for j, oracle in enumerate(oracles):
                _validate_oracle(oracle, step_index=i, oracle_index=j)
            oracle_count += len(oracles)
            if "min_change_ratio_from_previous" in step:
                _bounded_number(
                    step["min_change_ratio_from_previous"], low=0, high=1,
                    label=f"step {i} min_change_ratio_from_previous",
                )
        elif action == "mouse_capture":
            _validate_settle(step, step_index=i)
            estimated_sleep += float(step.get("settle_seconds", 0.4))
        elif action == "mouse_move":
            for key in ("dx", "dy"):
                value = step.get(key)
                if isinstance(value, bool) or not isinstance(value, int) or not (-2000 <= value <= 2000):
                    raise ValueError(f"step {i}: {key} out of range")
            _validate_settle(step, step_index=i)
            estimated_sleep += float(step.get("settle_seconds", 0.25))
        elif action == "click":
            button = step.get("button", 1)
            if isinstance(button, bool) or not isinstance(button, int) or not (1 <= button <= 5):
                raise ValueError(f"step {i}: invalid mouse button")
            _validate_settle(step, step_index=i)
            estimated_sleep += float(step.get("settle_seconds", 0.4))
        elif action == "key_chord":
            keys = step.get("keys")
            if not isinstance(keys, list) or not (1 <= len(keys) <= 4) or not all(isinstance(k, str) and k for k in keys):
                raise ValueError(f"step {i}: key_chord requires 1..4 key names")
            _validate_settle(step, step_index=i)
            estimated_sleep += float(step.get("settle_seconds", 0.25))
        else:
            raise ValueError(f"step {i}: unknown action {action!r}")

    if len(capture_steps) < 2:
        raise ValueError("action config must capture at least two frames")
    if "min_change_ratio_from_previous" in capture_steps[0]:
        raise ValueError("first capture cannot require change from a previous frame")
    if oracle_count < 1:
        raise ValueError("action config must include at least one screen-specific capture oracle")
    if estimated_sleep >= max_runtime:
        raise ValueError(
            f"declared waits/settles ({estimated_sleep:.3f}s) leave no runtime budget within max_runtime_seconds={max_runtime:g}"
        )
    return cfg


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"not a PNG: {path.name}")
    return struct.unpack(">II", data[16:24])


def _remaining(deadline: float, context: str, cap: float | None = None) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeError(f"scenario runtime deadline exceeded during {context}")
    if cap is not None:
        remaining = min(remaining, cap)
    return max(0.05, remaining)


def _sleep_bounded(seconds: float, deadline: float, context: str) -> None:
    if seconds <= 0:
        return
    remaining = _remaining(deadline, context)
    if seconds > remaining:
        raise RuntimeError(f"scenario runtime deadline would be exceeded during {context}")
    time.sleep(seconds)


def _run_checked(
    argv: list[str], *, env: dict[str, str] | None = None,
    deadline: float | None = None, timeout_cap: float = 5.0,
) -> str:
    timeout = timeout_cap if deadline is None else _remaining(deadline, "subprocess", timeout_cap)
    cp = subprocess.run(
        argv, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=True, timeout=timeout,
    )
    return cp.stdout


def find_dosbox_window(display: str, timeout: float, env: dict[str, str], proc: subprocess.Popen[str], deadline: float) -> str:
    local_deadline = min(deadline, time.monotonic() + timeout)
    while time.monotonic() < local_deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"DOSBox exited before opening a window: rc={proc.returncode}")
        command_timeout = max(0.05, min(2.0, local_deadline - time.monotonic()))
        out = subprocess.run(
            ["xwininfo", "-root", "-tree"], env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=command_timeout,
        ).stdout
        for line in out.splitlines():
            m = DOSBOX_WINDOW_RE.match(line)
            if m:
                return m.group(1)
        delay = min(0.2, max(0.0, local_deadline - time.monotonic()))
        if delay > 0:
            time.sleep(delay)
    if time.monotonic() >= deadline:
        raise RuntimeError("scenario runtime deadline exceeded while waiting for DOSBox window")
    raise RuntimeError(f"timed out waiting for DOSBox window on {display}")


def window_geometry(window_id: str, env: dict[str, str], deadline: float) -> tuple[int, int, int, int]:
    out = _run_checked(["xwininfo", "-id", window_id], env=env, deadline=deadline, timeout_cap=2.0)
    vals = {}
    patterns = {
        "x": r"Absolute upper-left X:\s+(-?\d+)",
        "y": r"Absolute upper-left Y:\s+(-?\d+)",
        "w": r"Width:\s+(\d+)",
        "h": r"Height:\s+(\d+)",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, out)
        if not m:
            raise RuntimeError(f"cannot parse {key} from xwininfo")
        vals[key] = int(m.group(1))
    return vals["x"], vals["y"], vals["w"], vals["h"]


def wait_for_window_geometry(
    window_id: str, env: dict[str, str], proc: subprocess.Popen[str], timeout: float,
    expected: tuple[int, int], deadline: float,
) -> tuple[int, int, int, int]:
    local_deadline = min(deadline, time.monotonic() + timeout)
    last = None
    while time.monotonic() < local_deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"DOSBox exited before game video mode: rc={proc.returncode}")
        try:
            last = window_geometry(window_id, env, local_deadline)
        except (RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            delay = min(0.2, max(0.0, local_deadline - time.monotonic()))
            if delay > 0:
                time.sleep(delay)
            continue
        if last[2:] == expected:
            return last
        delay = min(0.2, max(0.0, local_deadline - time.monotonic()))
        if delay > 0:
            time.sleep(delay)
    if time.monotonic() >= deadline:
        raise RuntimeError("scenario runtime deadline exceeded while waiting for game video mode")
    raise RuntimeError(f"timed out waiting for DOSBox {expected[0]}x{expected[1]} game window; last={last}")


class XTestInput:
    def __init__(self, display: str, window_id: str):
        self.x11 = ctypes.CDLL("libX11.so.6")
        self.xtst = ctypes.CDLL("libXtst.so.6")
        self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x11.XOpenDisplay.restype = ctypes.c_void_p
        self.x11.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        self.x11.XFlush.argtypes = [ctypes.c_void_p]
        self.x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
        self.x11.XStringToKeysym.restype = ctypes.c_ulong
        self.x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.x11.XKeysymToKeycode.restype = ctypes.c_uint
        self.xtst.XTestFakeRelativeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
        self.xtst.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.display = self.x11.XOpenDisplay(display.encode())
        if not self.display:
            raise RuntimeError(f"XOpenDisplay failed for {display}")
        self.window = int(window_id, 16)
        self.focus()

    def flush(self) -> None:
        self.x11.XFlush(self.display)

    def focus(self) -> None:
        self.x11.XSetInputFocus(self.display, self.window, 1, 0)
        self.flush()

    def mouse_move(self, dx: int, dy: int) -> None:
        self.xtst.XTestFakeRelativeMotionEvent(self.display, dx, dy, 0)
        self.flush()

    def click(self, button: int = 1) -> None:
        self.xtst.XTestFakeButtonEvent(self.display, button, 1, 0)
        self.flush()
        time.sleep(0.05)
        self.xtst.XTestFakeButtonEvent(self.display, button, 0, 0)
        self.flush()

    def key_chord(self, names: list[str]) -> None:
        codes = []
        for name in names:
            keysym = self.x11.XStringToKeysym(name.encode())
            if not keysym and len(name) == 1:
                keysym = ord(name)
            if not keysym:
                raise ValueError(f"unknown X keysym: {name}")
            code = self.x11.XKeysymToKeycode(self.display, keysym)
            if not code:
                raise ValueError(f"no keycode for X keysym: {name}")
            codes.append(code)
        for code in codes:
            self.xtst.XTestFakeKeyEvent(self.display, code, 1, 0)
        for code in reversed(codes):
            self.xtst.XTestFakeKeyEvent(self.display, code, 0, 0)
        self.flush()


def choose_display() -> str:
    for n in range(99, 79, -1):
        if not Path(f"/tmp/.X11-unix/X{n}").exists():
            return f":{n}"
    raise RuntimeError("no free X display in :80..:99")


def capture_frame(
    name: str, artifact_dir: Path, display: str, geometry: tuple[int, int, int, int],
    env: dict[str, str], deadline: float,
) -> dict[str, Any]:
    x, y, w, h = geometry
    path = artifact_dir / f"{name}.png"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "x11grab", "-draw_mouse", "0",
            "-video_size", f"{w}x{h}", "-i", f"{display}.0+{x},{y}", "-frames:v", "1", "-y", str(path),
        ],
        env=env,
        check=True,
        timeout=_remaining(deadline, f"capture {name}"),
    )
    dims = png_dimensions(path)
    if dims != (w, h):
        raise RuntimeError(f"captured frame has wrong dimensions: {dims} != {(w, h)}")
    return {"name": name, "file": path.name, "width": w, "height": h, "sha256": sha256_file(path), "size": path.stat().st_size}


def _decode_rgb(path: Path, deadline: float, context: str) -> bytes:
    cp = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        timeout=_remaining(deadline, context),
    )
    return cp.stdout


def hash_rgb_region(raw: bytes, frame_width: int, frame_height: int, x: int, y: int, width: int, height: int) -> str:
    expected = frame_width * frame_height * 3
    if len(raw) != expected:
        raise ValueError(f"RGB byte count mismatch: {len(raw)} != {expected}")
    row_bytes = frame_width * 3
    crop_row_bytes = width * 3
    h = hashlib.sha256()
    for row in range(y, y + height):
        start = row * row_bytes + x * 3
        h.update(raw[start:start + crop_row_bytes])
    return h.hexdigest()


def verify_frame_oracles(frame: dict[str, Any], step: dict[str, Any], artifact_dir: Path, deadline: float) -> None:
    oracles = step.get("oracles", [])
    if not oracles:
        return
    path = artifact_dir / frame["file"]
    raw = _decode_rgb(path, deadline, f"oracle decode for {frame['name']}")
    results = []
    for oracle in oracles:
        actual = hash_rgb_region(
            raw, frame["width"], frame["height"], oracle["x"], oracle["y"], oracle["width"], oracle["height"]
        )
        result = {
            "type": "rgb_region_sha256",
            "region": [oracle["x"], oracle["y"], oracle["width"], oracle["height"]],
            "expected_sha256": oracle["sha256"],
            "actual_sha256": actual,
            "matched": actual == oracle["sha256"],
        }
        results.append(result)
        frame["oracles"] = results
        if not result["matched"]:
            raise RuntimeError(
                f"screen oracle mismatch for {frame['name']} region {result['region']}: {actual} != {oracle['sha256']}"
            )


def frame_change_ratio(a: Path, b: Path, deadline: float) -> float:
    left = _decode_rgb(a, deadline, f"frame comparison {a.name}")
    right = _decode_rgb(b, deadline, f"frame comparison {b.name}")
    if len(left) != len(right) or not left:
        raise RuntimeError("cannot compare captured frames")
    changed = sum(x != y for x, y in zip(left, right))
    return changed / len(left)


def sanitize(text: str, replacements: list[tuple[str, str]]) -> str:
    for old, new in replacements:
        if old:
            text = text.replace(old, new)
    return text


def _file_identity(path: Path, logical_name: str) -> dict[str, Any]:
    return {"name": logical_name, "size": path.stat().st_size, "sha256": sha256_file(path)}


def _dosbox_identity(command: str) -> dict[str, Any]:
    resolved_text = shutil.which(command) or (str(Path(command).resolve()) if Path(command).is_file() else "")
    if not resolved_text:
        raise ValueError(f"required tool not found: {command}")
    resolved = Path(resolved_text)
    cp = subprocess.run(
        [command, "-version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=5, check=False,
    )
    version = next((line.strip() for line in cp.stdout.splitlines() if line.strip()), "unknown")[:200]
    identity = {"command": Path(command).name, "resolved_filename": resolved.name, "version": version}
    if resolved.is_file():
        identity.update({"size": resolved.stat().st_size, "sha256": sha256_file(resolved)})
    return identity


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-dir", type=Path, required=True)
    ap.add_argument("--dosbox", default="dosbox")
    ap.add_argument("--exe", required=True)
    ap.add_argument("--expected-exe-sha256", required=True)
    ap.add_argument("--fixture-manifest", type=Path, required=True)
    ap.add_argument("--actions", type=Path, required=True)
    ap.add_argument("--artifacts", type=Path, required=True)
    ap.add_argument("--window-timeout", type=float, default=20.0)
    ns = ap.parse_args(argv)
    if not (0 < ns.window_timeout <= 60):
        ap.error("window-timeout must be > 0 and <= 60 seconds")

    source = ns.game_dir.resolve()
    if not source.is_dir():
        ap.error(f"game directory does not exist: {source}")
    cfg = load_actions(ns.actions)
    fixture = verify_fixture(source, ns.fixture_manifest)
    index = _casefold_index(source)
    exe_source = index.get(ns.exe.casefold())
    if exe_source is None:
        ap.error(f"executable not found: {ns.exe}")
    exe_hash = sha256_file(exe_source)
    if exe_hash != ns.expected_exe_sha256.lower():
        ap.error(f"executable sha256 mismatch: {exe_hash}")

    for tool in (ns.dosbox, "Xvfb", "xwininfo", "ffmpeg"):
        if shutil.which(tool) is None and not Path(tool).is_file():
            ap.error(f"required tool not found: {tool}")

    provenance = {
        "actions": _file_identity(ns.actions.resolve(), ns.actions.name) | {"schema": cfg["schema"]},
        "fixture_manifest": _file_identity(ns.fixture_manifest.resolve(), ns.fixture_manifest.name),
        "harness": _file_identity(Path(__file__).resolve(), "scripts/run_cf4_ui_validation.py"),
        "python": {"version": platform.python_version()},
        "dosbox": _dosbox_identity(ns.dosbox),
    }

    ns.artifacts.mkdir(parents=True, exist_ok=True)
    display = choose_display()
    xvfb: subprocess.Popen[str] | None = None
    dosbox: subprocess.Popen[str] | None = None
    tmp: tempfile.TemporaryDirectory[str] | None = None
    frames: list[dict[str, Any]] = []
    status = "failed"
    failure: str | None = None
    dosbox_stdout = ""
    dosbox_stderr = ""
    geometry: tuple[int, int, int, int] | None = None
    started = time.monotonic()
    deadline = started + float(cfg.get("max_runtime_seconds", 90))
    try:
        tmp = tempfile.TemporaryDirectory(prefix="cf4-ui-")
        mount = Path(tmp.name) / "game"
        shutil.copytree(source, mount)
        copied_index = _casefold_index(mount)
        exe = copied_index[ns.exe.casefold()]
        if sha256_file(exe) != exe_hash:
            raise RuntimeError("copy isolation changed executable bytes")

        xvfb = subprocess.Popen(["Xvfb", display, "-screen", "0", "1024x768x24", "-nolisten", "tcp"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _sleep_bounded(0.5, deadline, "Xvfb startup")
        if xvfb.poll() is not None:
            out, err = xvfb.communicate()
            raise RuntimeError(f"Xvfb failed: {out}{err}")

        env = os.environ.copy()
        env.update({"DISPLAY": display, "SDL_AUDIODRIVER": "dummy"})
        dosbox = subprocess.Popen(
            [ns.dosbox, "-noconsole", "-c", f"mount c {mount}", "-c", "c:", "-c", ns.exe],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        window = find_dosbox_window(display, ns.window_timeout, env, dosbox, deadline)
        input_dev = XTestInput(display, window)
        for keys in cfg.get("pre_video_key_chords", []):
            input_dev.key_chord(keys)
            _sleep_bounded(0.5, deadline, "pre-video key settle")
        geometry = wait_for_window_geometry(window, env, dosbox, ns.window_timeout, EXPECTED_FRAME, deadline)
        _sleep_bounded(float(cfg.get("startup_wait_seconds", 0)), deadline, "startup wait")
        if dosbox.poll() is not None:
            raise RuntimeError(f"DOSBox exited during startup wait: rc={dosbox.returncode}")

        capture_steps: list[dict[str, Any]] = []
        for i, step in enumerate(cfg["steps"]):
            _remaining(deadline, f"step {i}")
            if dosbox.poll() is not None:
                raise RuntimeError(f"DOSBox exited before step {i}: rc={dosbox.returncode}")
            action = step["action"]
            if action == "wait":
                _sleep_bounded(float(step["seconds"]), deadline, f"step {i} wait")
            elif action == "capture":
                frame = capture_frame(step["name"], ns.artifacts, display, geometry, env, deadline)
                frames.append(frame)
                capture_steps.append(step)
                verify_frame_oracles(frame, step, ns.artifacts, deadline)
            elif action == "mouse_capture":
                input_dev.focus()
                input_dev.click(1)
                _sleep_bounded(float(step.get("settle_seconds", 0.4)), deadline, f"step {i} mouse_capture settle")
            elif action == "mouse_move":
                input_dev.mouse_move(step["dx"], step["dy"])
                _sleep_bounded(float(step.get("settle_seconds", 0.25)), deadline, f"step {i} mouse_move settle")
            elif action == "click":
                input_dev.click(step.get("button", 1))
                _sleep_bounded(float(step.get("settle_seconds", 0.4)), deadline, f"step {i} click settle")
            elif action == "key_chord":
                input_dev.key_chord(step["keys"])
                _sleep_bounded(float(step.get("settle_seconds", 0.25)), deadline, f"step {i} key_chord settle")

        for index, (prev, cur) in enumerate(zip(frames, frames[1:]), start=1):
            ratio = frame_change_ratio(ns.artifacts / prev["file"], ns.artifacts / cur["file"], deadline)
            cur["change_ratio_from_previous"] = round(ratio, 6)
            threshold = capture_steps[index].get("min_change_ratio_from_previous")
            if threshold is not None:
                cur["min_change_ratio_required"] = float(threshold)
                if ratio < float(threshold):
                    raise RuntimeError(
                        f"UI transition too small between {prev['name']} and {cur['name']}: {ratio:.6f} < {float(threshold):.6f}"
                    )
        _remaining(deadline, "scenario completion")
        status = "passed"
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        if dosbox is not None:
            if dosbox.poll() is None:
                dosbox.terminate()
                try:
                    dosbox.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    dosbox.kill()
            out, err = dosbox.communicate()
            dosbox_stdout = out or ""
            dosbox_stderr = err or ""
        if xvfb is not None:
            if xvfb.poll() is None:
                xvfb.terminate()
                try:
                    xvfb.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    xvfb.kill()
        replacements = [(str(source), "<source>"), (tmp.name if tmp else "", "<run-temp>")]
        (ns.artifacts / "dosbox.stdout.log").write_text(sanitize(dosbox_stdout, replacements), encoding="utf-8")
        (ns.artifacts / "dosbox.stderr.log").write_text(sanitize(dosbox_stderr, replacements), encoding="utf-8")
        result = {
            "schema": RUN_SCHEMA,
            "roadmap_item": "CF4",
            "status": status,
            "failure": failure,
            "scenario": cfg["name"],
            "runtime_seconds": round(time.monotonic() - started, 3),
            "max_runtime_seconds": float(cfg.get("max_runtime_seconds", 90)),
            "target": {"filename": ns.exe, "size": exe_source.stat().st_size, "sha256": exe_hash},
            "fixture": {"id": fixture.get("id"), "verified_file_count": len(fixture["files"])},
            "provenance": provenance,
            "display": {"driver": "Xvfb", "geometry": list(geometry) if geometry else None},
            "input": "X11 XTEST relative mouse/button/key events",
            "capture": "ffmpeg x11grab cropped to DOSBox window",
            "frames": frames,
        }
        (ns.artifacts / "run.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if tmp is not None:
            tmp.cleanup()

    if status != "passed":
        print(f"CF4 UI validation: FAIL: {failure}")
        return 1
    print(f"CF4 UI validation: PASS ({len(frames)} frames, {cfg['name']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
