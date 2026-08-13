#!/usr/bin/env python3
"""Drive a bounded Ascendancy UI scenario under Xvfb and capture evidence."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import time
from typing import Any

SAFE_CAPTURE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
DOSBOX_WINDOW_RE = re.compile(r'^\s*(0x[0-9a-fA-F]+)\s+"DOSBox ')


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def load_actions(path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if cfg.get("schema") != 1:
        raise ValueError("unsupported action schema")
    if not isinstance(cfg.get("name"), str) or not cfg["name"]:
        raise ValueError("action config requires a name")
    startup = cfg.get("startup_wait_seconds", 0)
    if not isinstance(startup, (int, float)) or not (0 <= startup <= 60):
        raise ValueError("startup_wait_seconds must be between 0 and 60")
    pre_video = cfg.get("pre_video_key_chords", [])
    if not isinstance(pre_video, list):
        raise ValueError("pre_video_key_chords must be a list")
    for i, keys in enumerate(pre_video):
        if not isinstance(keys, list) or not (1 <= len(keys) <= 4) or not all(isinstance(k, str) and k for k in keys):
            raise ValueError(f"pre_video_key_chords[{i}] requires 1..4 key names")
    steps = cfg.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("action config requires non-empty steps")
    captures = 0
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"step {i} is not an object")
        action = step.get("action")
        if action == "wait":
            seconds = step.get("seconds")
            if not isinstance(seconds, (int, float)) or not (0 <= seconds <= 30):
                raise ValueError(f"step {i}: wait seconds out of range")
        elif action == "capture":
            name = step.get("name")
            if not isinstance(name, str) or not SAFE_CAPTURE_RE.fullmatch(name):
                raise ValueError(f"step {i}: unsafe capture name")
            captures += 1
        elif action == "mouse_capture":
            pass
        elif action == "mouse_move":
            for key in ("dx", "dy"):
                value = step.get(key)
                if not isinstance(value, int) or not (-2000 <= value <= 2000):
                    raise ValueError(f"step {i}: {key} out of range")
        elif action == "click":
            button = step.get("button", 1)
            if not isinstance(button, int) or not (1 <= button <= 5):
                raise ValueError(f"step {i}: invalid mouse button")
        elif action == "key_chord":
            keys = step.get("keys")
            if not isinstance(keys, list) or not (1 <= len(keys) <= 4) or not all(isinstance(k, str) and k for k in keys):
                raise ValueError(f"step {i}: key_chord requires 1..4 key names")
        else:
            raise ValueError(f"step {i}: unknown action {action!r}")
    if captures < 2:
        raise ValueError("action config must capture at least two frames")
    return cfg


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"not a PNG: {path.name}")
    return struct.unpack(">II", data[16:24])


def _run_checked(argv: list[str], *, env: dict[str, str] | None = None) -> str:
    cp = subprocess.run(argv, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
    return cp.stdout


def find_dosbox_window(display: str, timeout: float, env: dict[str, str], proc: subprocess.Popen[str]) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"DOSBox exited before opening a window: rc={proc.returncode}")
        out = subprocess.run(["xwininfo", "-root", "-tree"], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout
        for line in out.splitlines():
            m = DOSBOX_WINDOW_RE.match(line)
            if m:
                return m.group(1)
        time.sleep(0.2)
    raise RuntimeError(f"timed out waiting for DOSBox window on {display}")


def window_geometry(window_id: str, env: dict[str, str]) -> tuple[int, int, int, int]:
    out = _run_checked(["xwininfo", "-id", window_id], env=env)
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


def wait_for_window_geometry(window_id: str, env: dict[str, str], proc: subprocess.Popen[str], timeout: float, expected: tuple[int, int]) -> tuple[int, int, int, int]:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"DOSBox exited before game video mode: rc={proc.returncode}")
        try:
            last = window_geometry(window_id, env)
        except (RuntimeError, subprocess.CalledProcessError):
            time.sleep(0.2)
            continue
        if last[2:] == expected:
            return last
        time.sleep(0.2)
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


def capture_frame(name: str, artifact_dir: Path, display: str, geometry: tuple[int, int, int, int], env: dict[str, str]) -> dict[str, Any]:
    x, y, w, h = geometry
    path = artifact_dir / f"{name}.png"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "x11grab", "-draw_mouse", "0",
            "-video_size", f"{w}x{h}", "-i", f"{display}.0+{x},{y}", "-frames:v", "1", "-y", str(path),
        ],
        env=env,
        check=True,
    )
    dims = png_dimensions(path)
    if dims != (w, h):
        raise RuntimeError(f"captured frame has wrong dimensions: {dims} != {(w, h)}")
    return {"name": name, "file": path.name, "width": w, "height": h, "sha256": sha256_file(path), "size": path.stat().st_size}


def frame_change_ratio(a: Path, b: Path) -> float:
    def raw(path: Path) -> bytes:
        cp = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return cp.stdout
    left, right = raw(a), raw(b)
    if len(left) != len(right) or not left:
        raise RuntimeError("cannot compare captured frames")
    changed = sum(x != y for x, y in zip(left, right))
    return changed / len(left)


def sanitize(text: str, replacements: list[tuple[str, str]]) -> str:
    for old, new in replacements:
        if old:
            text = text.replace(old, new)
    return text


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
    try:
        tmp = tempfile.TemporaryDirectory(prefix="cf4-ui-")
        mount = Path(tmp.name) / "game"
        shutil.copytree(source, mount)
        copied_index = _casefold_index(mount)
        exe = copied_index[ns.exe.casefold()]
        if sha256_file(exe) != exe_hash:
            raise RuntimeError("copy isolation changed executable bytes")

        xvfb = subprocess.Popen(["Xvfb", display, "-screen", "0", "1024x768x24", "-nolisten", "tcp"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.5)
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
        window = find_dosbox_window(display, ns.window_timeout, env, dosbox)
        input_dev = XTestInput(display, window)
        for keys in cfg.get("pre_video_key_chords", []):
            input_dev.key_chord(keys)
            time.sleep(0.5)
        geometry = wait_for_window_geometry(window, env, dosbox, ns.window_timeout, (640, 480))
        time.sleep(float(cfg.get("startup_wait_seconds", 0)))
        if dosbox.poll() is not None:
            raise RuntimeError(f"DOSBox exited during startup wait: rc={dosbox.returncode}")

        for i, step in enumerate(cfg["steps"]):
            if dosbox.poll() is not None:
                raise RuntimeError(f"DOSBox exited before step {i}: rc={dosbox.returncode}")
            action = step["action"]
            if action == "wait":
                time.sleep(float(step["seconds"]))
            elif action == "capture":
                frames.append(capture_frame(step["name"], ns.artifacts, display, geometry, env))
            elif action == "mouse_capture":
                input_dev.focus()
                input_dev.click(1)
                time.sleep(float(step.get("settle_seconds", 0.4)))
            elif action == "mouse_move":
                input_dev.mouse_move(step["dx"], step["dy"])
                time.sleep(float(step.get("settle_seconds", 0.25)))
            elif action == "click":
                input_dev.click(step.get("button", 1))
                time.sleep(float(step.get("settle_seconds", 0.4)))
            elif action == "key_chord":
                input_dev.key_chord(step["keys"])
                time.sleep(float(step.get("settle_seconds", 0.25)))

        if len({f["sha256"] for f in frames}) < 2:
            raise RuntimeError("captured frames did not demonstrate a UI transition")
        for prev, cur in zip(frames, frames[1:]):
            ratio = frame_change_ratio(ns.artifacts / prev["file"], ns.artifacts / cur["file"])
            cur["change_ratio_from_previous"] = round(ratio, 6)
            if ratio < 0.01:
                raise RuntimeError(f"UI transition too small between {prev['name']} and {cur['name']}: {ratio:.6f}")
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
            "schema": 1,
            "roadmap_item": "CF4",
            "status": status,
            "failure": failure,
            "scenario": cfg["name"],
            "target": {"filename": ns.exe, "size": exe_source.stat().st_size, "sha256": exe_hash},
            "fixture": {"id": fixture.get("id"), "verified_file_count": len(fixture["files"])},
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
