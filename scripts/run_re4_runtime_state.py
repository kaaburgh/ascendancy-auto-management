#!/usr/bin/env python3
"""Run the bounded RE4 Managed-state experiment against canonical Antagonizer."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any

TARGET_SHA256 = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
TARGET_SIZE = 610863
STATE_OFFSET = 0x5A
RECORD_SIZE = 0x7B
NAME_OFFSET = 0x24
MANUAL = b"\x00\x00\x00\x00"
MANAGED = b"\xff\xff\xff\xff"
# Canonical runtime bytes beginning at RE2's 0x37915 read/NOT/write sequence.
TOGGLE_PATTERN = [
    0x8B, 0x52, 0x5A, 0xA1, None, None, None, None,
    0xF7, 0xD2, 0x89, 0x50, 0x5A, 0xE9, 0x32, 0x01, 0x00, 0x00,
    0x83, 0x3D,
]
SELF_MANAGED_REGION = (280, 73, 100, 8)
SELF_MANAGED_RGB_SHA256 = "66df0c5f9a6774156363abc9cd878ec683b64aabd54c4d781387236cd1fff160"
EXPECTED_FRAME = (640, 480)


class RE4Error(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_masked(data: bytes, pattern: list[int | None]) -> list[int]:
    prefix = bytes(v for v in pattern[:4] if v is not None)
    if len(prefix) != 4:
        raise ValueError("pattern requires a four-byte fixed prefix")
    out: list[int] = []
    start = 0
    while True:
        at = data.find(prefix, start)
        if at < 0:
            return out
        if at + len(pattern) <= len(data) and all(v is None or data[at + i] == v for i, v in enumerate(pattern)):
            out.append(at)
        start = at + 1


def _record_name(record: bytes) -> str | None:
    tail = record[NAME_OFFSET:NAME_OFFSET + 32]
    nul = tail.find(b"\0")
    if nul <= 0:
        return None
    raw = tail[:nul]
    if not all(0x20 <= b <= 0x7E for b in raw) or not any(chr(b).isalpha() for b in raw):
        return None
    return raw.decode("ascii")


def find_transition_record(
    before: bytes, managed: bytes, restored: bytes, expected_name: str | None = None,
) -> dict[str, Any]:
    if not (len(before) == len(managed) == len(restored)):
        raise RE4Error("snapshot sizes differ")
    candidates: list[tuple[int, str]] = []
    for match in re.finditer(b"\xff{4}", managed):
        field = match.start()
        if before[field:field + 4] != MANUAL or restored[field:field + 4] != MANUAL:
            continue
        base = field - STATE_OFFSET
        if base < 0 or base + RECORD_SIZE > len(before):
            continue
        name = _record_name(before[base:base + RECORD_SIZE])
        if name is None or (expected_name is not None and name != expected_name):
            continue
        candidates.append((field, name))
    if len(candidates) != 1:
        label = expected_name if expected_name is not None else "planet-like"
        raise RE4Error(
            f"expected exactly one {label!r} record with 0->ffffffff->0 at +0x{STATE_OFFSET:x}; "
            f"structured={len(candidates)}"
        )
    field, name = candidates[0]
    base = field - STATE_OFFSET
    return {
        "record_offset_in_snapshot": base,
        "field_offset_in_snapshot": field,
        "record_size": RECORD_SIZE,
        "name_offset": NAME_OFFSET,
        "state_offset": STATE_OFFSET,
        "planet_name": name,
        "before": before[field:field + 4].hex(),
        "managed": managed[field:field + 4].hex(),
        "restored": restored[field:field + 4].hex(),
    }


def verify_fixture(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != 1 or not isinstance(manifest.get("files"), list):
        raise RE4Error("unsupported retail manifest")
    files = {p.name.casefold(): p for p in root.iterdir() if p.is_file()}
    verified = []
    for entry in manifest["files"]:
        p = files.get(entry["name"].casefold())
        if p is None:
            raise RE4Error(f"fixture file missing: {entry['name']}")
        if p.stat().st_size != entry["size"] or sha256_file(p) != entry["sha256"]:
            raise RE4Error(f"fixture identity mismatch: {entry['name']}")
        verified.append(entry["name"])
    exe = files.get("antag.exe")
    if exe is None or exe.stat().st_size != TARGET_SIZE or sha256_file(exe) != TARGET_SHA256:
        raise RE4Error("canonical ANTAG.EXE identity mismatch")
    return {"id": manifest.get("id"), "verified_files": len(verified)}


def proc_rw_mappings(pid: int) -> list[tuple[int, int]]:
    out = []
    for line in Path(f"/proc/{pid}/maps").read_text().splitlines():
        cols = line.split(maxsplit=5)
        lo_s, hi_s = cols[0].split("-")
        lo, hi = int(lo_s, 16), int(hi_s, 16)
        perms = cols[1]
        if "r" in perms and "w" in perms and hi - lo <= 64 * 1024 * 1024:
            out.append((lo, hi))
    return out


def read_process(pid: int, address: int, size: int) -> bytes:
    fd = os.open(f"/proc/{pid}/mem", os.O_RDONLY)
    try:
        return os.pread(fd, size, address)
    finally:
        os.close(fd)


def find_unique_runtime_anchor(pid: int) -> dict[str, Any]:
    hits: list[tuple[int, int, int, bytes]] = []
    for lo, hi in proc_rw_mappings(pid):
        try:
            data = read_process(pid, lo, hi - lo)
        except OSError:
            continue
        for off in find_masked(data, TOGGLE_PATTERN):
            hits.append((lo, hi, off, data[off:off + 32]))
    if len(hits) != 1:
        raise RE4Error(f"runtime toggle signature must match once, got {len(hits)}")
    lo, hi, off, raw = hits[0]
    return {
        "map_start": lo,
        "map_end": hi,
        "map_size": hi - lo,
        "anchor_offset": off,
        "anchor_bytes": raw.hex(),
    }


def snapshot_anchor_map(pid: int, anchor: dict[str, Any]) -> bytes:
    lo, hi = anchor["map_start"], anchor["map_end"]
    current = proc_rw_mappings(pid)
    if (lo, hi) not in current:
        raise RE4Error("runtime anchor mapping changed during experiment")
    data = read_process(pid, lo, hi - lo)
    if len(data) != hi - lo:
        raise RE4Error("short process-memory snapshot")
    return data


class XInput:
    def __init__(self, display: str, window: int):
        self.x11 = ctypes.CDLL("libX11.so.6")
        self.xtst = ctypes.CDLL("libXtst.so.6")
        self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x11.XOpenDisplay.restype = ctypes.c_void_p
        self.x11.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        self.x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
        self.x11.XStringToKeysym.restype = ctypes.c_ulong
        self.x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.x11.XKeysymToKeycode.restype = ctypes.c_uint
        self.x11.XFlush.argtypes = [ctypes.c_void_p]
        self.x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.xtst.XTestFakeRelativeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
        self.xtst.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.display = self.x11.XOpenDisplay(display.encode())
        if not self.display:
            raise RE4Error(f"XOpenDisplay failed: {display}")
        self.window = window
        self.x11.XSetInputFocus(self.display, window, 1, 0)
        self.x11.XFlush(self.display)

    def move(self, dx: int, dy: int) -> None:
        self.xtst.XTestFakeRelativeMotionEvent(self.display, dx, dy, 0)
        self.x11.XFlush(self.display)

    def move_to(self, x: int, y: int) -> None:
        # DOSBox/game owns relative motion. Clamp at the guest's top-left, then move to a known coordinate.
        self.move(-2000, -2000)
        self.move(x, y)

    def click(self) -> None:
        self.xtst.XTestFakeButtonEvent(self.display, 1, 1, 0)
        self.x11.XFlush(self.display)
        time.sleep(0.05)
        self.xtst.XTestFakeButtonEvent(self.display, 1, 0, 0)
        self.x11.XFlush(self.display)

    def key(self, name: str) -> None:
        sym = self.x11.XStringToKeysym(name.encode())
        code = self.x11.XKeysymToKeycode(self.display, sym)
        if not code:
            raise RE4Error(f"no X keycode for {name}")
        self.xtst.XTestFakeKeyEvent(self.display, code, 1, 0)
        self.xtst.XTestFakeKeyEvent(self.display, code, 0, 0)
        self.x11.XFlush(self.display)

    def close(self) -> None:
        if self.display:
            self.x11.XCloseDisplay(self.display)
            self.display = None


def choose_display() -> str:
    for n in range(99, 79, -1):
        if not Path(f"/tmp/.X11-unix/X{n}").exists():
            return f":{n}"
    raise RE4Error("no free X display")


def wait_window(display: str, env: dict[str, str], proc: subprocess.Popen[Any], timeout: float = 20.0) -> int:
    deadline = time.monotonic() + timeout
    regex = re.compile(r'^\s*(0x[0-9a-fA-F]+)\s+"DOSBox ')
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RE4Error(f"DOSBox exited before window: rc={proc.returncode}")
        cp = subprocess.run(["xwininfo", "-root", "-tree"], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        for line in cp.stdout.splitlines():
            m = regex.match(line)
            if m:
                return int(m.group(1), 16)
        time.sleep(0.1)
    raise RE4Error("timed out waiting for DOSBox window")


def geometry(window: int, env: dict[str, str]) -> tuple[int, int, int, int]:
    out = subprocess.check_output(["xwininfo", "-id", hex(window)], env=env, text=True)

    def val(pattern: str) -> int:
        m = re.search(pattern, out)
        if not m:
            raise RE4Error("cannot parse DOSBox geometry")
        return int(m.group(1))

    return val(r"Absolute upper-left X:\s+(-?\d+)"), val(r"Absolute upper-left Y:\s+(-?\d+)"), val(r"Width:\s+(\d+)"), val(r"Height:\s+(\d+)")


def wait_game_geometry(window: int, env: dict[str, str], proc: subprocess.Popen[Any], timeout: float = 20.0) -> tuple[int, int, int, int]:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RE4Error(f"DOSBox exited before 640x480: rc={proc.returncode}")
        try:
            last = geometry(window, env)
        except Exception:
            time.sleep(0.1)
            continue
        if last[2:] == EXPECTED_FRAME:
            return last
        time.sleep(0.1)
    raise RE4Error(f"timed out waiting for 640x480; last={last}")


def capture(path: Path, display: str, geom: tuple[int, int, int, int], env: dict[str, str]) -> str:
    x, y, w, h = geom
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "x11grab", "-draw_mouse", "0",
        "-video_size", f"{w}x{h}", "-i", f"{display}.0+{x},{y}", "-frames:v", "1", "-y", str(path),
    ], env=env, check=True, timeout=10)
    return sha256_file(path)


def rgb_region_sha256(path: Path, x: int, y: int, width: int, height: int) -> str:
    cp = subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=10)
    raw = cp.stdout
    row = EXPECTED_FRAME[0] * 3
    h = hashlib.sha256()
    for yy in range(y, y + height):
        start = yy * row + x * 3
        h.update(raw[start:start + width * 3])
    return h.hexdigest()


def wait_field(pid: int, address: int, expected: bytes, timeout: float = 0.25) -> float:
    start = time.perf_counter()
    deadline = start + timeout
    while time.perf_counter() < deadline:
        if read_process(pid, address, 4) == expected:
            return (time.perf_counter() - start) * 1000.0
        time.sleep(0.0005)
    raise RE4Error(f"field did not reach {expected.hex()} within {timeout * 1000:.0f} ms")


def scenario_steps(inp: XInput, kind: str) -> None:
    # Game intro -> 640x480 main menu is handled by caller.
    inp.click()  # first click captures DOSBox mouse; it must not activate a menu item.
    time.sleep(0.25)
    if kind == "resume":
        inp.move_to(320, 333)  # Return to Current Game
        inp.click()
        time.sleep(1.5)
    elif kind == "new-snovemdomas":
        inp.move_to(320, 293)  # New Game
        inp.click()
        time.sleep(1.5)
        inp.move_to(560, 210)  # Snovemdomas (second visible species)
        inp.click()
        time.sleep(0.5)
        inp.move_to(570, 460)  # Begin New Game
        inp.click()
        time.sleep(3.0)
        inp.key("Escape")
        time.sleep(1.5)  # leave species intro
    else:
        raise RE4Error(f"unknown scenario {kind}")
    inp.move_to(520, 140)  # Planets
    inp.click()
    time.sleep(1.0)


def run_scenario(root: Path, dosbox: str, artifacts: Path, kind: str, expected_name: str | None) -> dict[str, Any]:
    display = choose_display()
    tmp = tempfile.TemporaryDirectory(prefix="re4-runtime-")
    mount = Path(tmp.name) / "game"
    shutil.copytree(root, mount)
    env = os.environ.copy()
    env.update({"DISPLAY": display, "SDL_AUDIODRIVER": "dummy"})
    xvfb = subprocess.Popen(["Xvfb", display, "-screen", "0", "1024x768x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc: subprocess.Popen[Any] | None = None
    inp: XInput | None = None
    try:
        time.sleep(0.35)
        proc = subprocess.Popen([dosbox, "-noconsole", "-c", f"mount c {mount}", "-c", "c:", "-c", "ANTAG.EXE"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        window = wait_window(display, env, proc)
        inp = XInput(display, window)
        time.sleep(5.0)
        inp.key("space")
        geom = wait_game_geometry(window, env, proc)
        time.sleep(3.5)
        scenario_steps(inp, kind)

        manual_list = artifacts / f"{kind}-manual-list.png"
        manual_list_sha = capture(manual_list, display, geom, env)
        inp.move_to(205, 125)  # selected planet image
        inp.click()
        time.sleep(1.0)

        anchor = find_unique_runtime_anchor(proc.pid)
        before = snapshot_anchor_map(proc.pid, anchor)
        inp.key("m")
        time.sleep(0.10)
        managed = snapshot_anchor_map(proc.pid, anchor)
        inp.key("m")
        time.sleep(0.10)
        restored = snapshot_anchor_map(proc.pid, anchor)
        record = find_transition_record(before, managed, restored, expected_name)

        field_host = anchor["map_start"] + record["field_offset_in_snapshot"]
        if read_process(proc.pid, field_host, 4) != MANUAL:
            raise RE4Error("field is not restored to Manual before latency probe")
        t0 = time.perf_counter()
        inp.key("m")
        managed_ms = wait_field(proc.pid, field_host, MANAGED)
        injection_to_managed_ms = (time.perf_counter() - t0) * 1000.0
        inp.key("m")
        restored_ms = wait_field(proc.pid, field_host, MANUAL)

        # Leave the planet managed and prove the existing renderer exposes the same semantic state.
        inp.key("m")
        wait_field(proc.pid, field_host, MANAGED)
        inp.key("Escape")
        time.sleep(0.8)
        managed_list = artifacts / f"{kind}-managed-list.png"
        managed_list_sha = capture(managed_list, display, geom, env)
        region_hash = rgb_region_sha256(managed_list, *SELF_MANAGED_REGION)
        if region_hash != SELF_MANAGED_RGB_SHA256:
            raise RE4Error(f"Self-Managed renderer oracle mismatch: {region_hash}")

        # Restore Manual before teardown; do not leave the temporary runtime copy modified in state.
        inp.move_to(205, 125)
        inp.click()
        time.sleep(0.5)
        inp.key("m")
        wait_field(proc.pid, field_host, MANUAL)

        return {
            "scenario": kind,
            "planet": record["planet_name"],
            "runtime_anchor": {
                "mapping_size": anchor["map_size"],
                "anchor_offset_in_mapping": anchor["anchor_offset"],
                "anchor_bytes": anchor["anchor_bytes"],
                "host_addresses_are_ephemeral": True,
            },
            "state_record": record,
            "timing": {
                "input_to_managed_observation_ms": round(injection_to_managed_ms, 3),
                "poll_to_managed_ms": round(managed_ms, 3),
                "poll_to_manual_ms": round(restored_ms, 3),
                "no_turn_advanced": True,
            },
            "visual": {
                "manual_planet_list_sha256": manual_list_sha,
                "managed_planet_list_sha256": managed_list_sha,
                "self_managed_region": list(SELF_MANAGED_REGION),
                "self_managed_region_rgb_sha256": region_hash,
            },
        }
    finally:
        if inp is not None:
            inp.close()
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        if xvfb.poll() is None:
            xvfb.terminate()
            try:
                xvfb.wait(timeout=2)
            except subprocess.TimeoutExpired:
                xvfb.kill()
        tmp.cleanup()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-dir", type=Path, required=True)
    ap.add_argument("--dosbox", required=True)
    ap.add_argument("--fixture-manifest", type=Path, required=True)
    ap.add_argument("--scenario", choices=("resume", "new-snovemdomas"), required=True)
    ap.add_argument("--resume-sha256", help="Exact operator-supplied resume.gam hash; required for --scenario resume")
    ap.add_argument("--artifacts", type=Path, required=True)
    ns = ap.parse_args()
    root = ns.game_dir.resolve()
    if not root.is_dir():
        ap.error("game-dir must exist")
    fixture = verify_fixture(root, ns.fixture_manifest)
    resume = next((p for p in root.iterdir() if p.is_file() and p.name.casefold() == "resume.gam"), None)
    resume_info = None
    if ns.scenario == "resume":
        if not ns.resume_sha256:
            ap.error("--resume-sha256 is required for --scenario resume")
        if resume is None or sha256_file(resume) != ns.resume_sha256.lower():
            ap.error("resume.gam identity mismatch")
        resume_info = {"filename": "resume.gam", "size": resume.stat().st_size, "sha256": sha256_file(resume)}
    for tool in (ns.dosbox, "Xvfb", "xwininfo", "ffmpeg"):
        if shutil.which(tool) is None and not Path(tool).is_file():
            ap.error(f"required tool not found: {tool}")
    ns.artifacts.mkdir(parents=True, exist_ok=True)

    expected = "Xerxes I" if ns.scenario == "resume" else None
    result: dict[str, Any] = {
        "schema": 1,
        "roadmap_item": "RE4",
        "scenario_name": ns.scenario,
        "blind_re_provenance": "clean",
        "target": {"filename": "ANTAG.EXE", "size": TARGET_SIZE, "sha256": TARGET_SHA256},
        "fixture": fixture,
    }
    if resume_info is not None:
        result["resume"] = resume_info
    try:
        result["scenario"] = run_scenario(root, ns.dosbox, ns.artifacts, ns.scenario, expected)
        result["status"] = "passed"
    except Exception as exc:
        result["status"] = "failed"
        result["failure"] = f"{type(exc).__name__}: {exc}"
    (ns.artifacts / "run.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if result["status"] != "passed":
        print(f"RE4 {ns.scenario}: FAIL: {result['failure']}")
        return 1
    print(f"RE4 {ns.scenario}: PASS ({result['scenario']['planet']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
