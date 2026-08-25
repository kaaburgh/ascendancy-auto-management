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

ROOT = Path(__file__).resolve().parents[1]
RETAIL_MANIFEST = ROOT / "tools" / "retail-runtime-manifest.json"
RETAIL_MANIFEST_SHA256 = "814c37ea8683e9c32ce494bcb9568d08a33d3ef8e6d91b99ac07f37958269852"
RETAIL_FIXTURE_ID = "ascendancy-retail-en-canonical-antagonizer-runtime-fixture"
RETAIL_FIXTURE_FILE_COUNT = 17
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
PLANET_LIST_FIRST_ROW_Y = 125
PLANET_LIST_ROW_HEIGHT = 145
PLANET_LIST_RENDER_ROW_HEIGHT = 141
PLANET_LIST_VISIBLE_ROWS = 3


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


def _casefold_file_map(root: Path) -> dict[str, Path]:
    by_name: dict[str, Path] = {}
    collisions: list[str] = []
    for candidate in root.iterdir():
        if not candidate.is_file():
            continue
        key = candidate.name.casefold()
        previous = by_name.get(key)
        if previous is not None:
            collisions.append(f"{previous.name}/{candidate.name}")
        else:
            by_name[key] = candidate
    if collisions:
        raise RE4Error(
            "retail tree has ambiguous case-insensitive filenames: " + ", ".join(sorted(collisions))
        )
    return by_name


def verify_fixture(root: Path, manifest_path: Path) -> dict[str, Any]:
    if not RETAIL_MANIFEST.is_file() or sha256_file(RETAIL_MANIFEST) != RETAIL_MANIFEST_SHA256:
        raise RE4Error("committed retail manifest identity mismatch")
    if not manifest_path.is_file() or sha256_file(manifest_path) != RETAIL_MANIFEST_SHA256:
        raise RE4Error("fixture manifest must exactly match the committed retail runtime manifest")

    manifest = json.loads(RETAIL_MANIFEST.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != 1
        or manifest.get("id") != RETAIL_FIXTURE_ID
        or not isinstance(manifest.get("files"), list)
        or len(manifest["files"]) != RETAIL_FIXTURE_FILE_COUNT
    ):
        raise RE4Error("committed retail manifest contract is malformed")

    files = _casefold_file_map(root)
    verified = []
    expected_keys: set[str] = set()
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or not all(k in entry for k in ("name", "size", "sha256")):
            raise RE4Error("committed retail manifest contains malformed file entry")
        key = str(entry["name"]).casefold()
        if key in expected_keys:
            raise RE4Error(f"committed retail manifest has duplicate filename: {entry['name']}")
        expected_keys.add(key)
        p = files.get(key)
        if p is None:
            raise RE4Error(f"fixture file missing: {entry['name']}")
        if p.stat().st_size != entry["size"] or sha256_file(p) != entry["sha256"]:
            raise RE4Error(f"fixture identity mismatch: {entry['name']}")
        verified.append(entry["name"])

    exe = files.get("antag.exe")
    if exe is None or exe.stat().st_size != TARGET_SIZE or sha256_file(exe) != TARGET_SHA256:
        raise RE4Error("canonical ANTAG.EXE identity mismatch")
    return {
        "id": manifest["id"],
        "verified_files": len(verified),
        "manifest_sha256": RETAIL_MANIFEST_SHA256,
    }


def validate_renderer_transition(manual_hash: str, managed_hash: str, restored_hash: str) -> dict[str, Any]:
    if managed_hash != SELF_MANAGED_RGB_SHA256:
        raise RE4Error(f"Self-Managed renderer oracle mismatch: {managed_hash}")
    if manual_hash == managed_hash:
        raise RE4Error("renderer oracle is not differential: Manual and Managed regions are identical")
    if restored_hash != manual_hash:
        raise RE4Error(
            "renderer oracle did not return to the Manual region after restoring planet+0x5a to zero"
        )
    return {
        "manual_region_rgb_sha256": manual_hash,
        "managed_region_rgb_sha256": managed_hash,
        "restored_region_rgb_sha256": restored_hash,
        "managed_matches_pinned_oracle": True,
        "manual_differs_from_managed": True,
        "restored_matches_manual": True,
    }


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
        data = os.pread(fd, size, address)
    finally:
        os.close(fd)
    if len(data) != size:
        raise RE4Error(
            f"short process-memory read at 0x{address:x}: expected {size} bytes, got {len(data)}"
        )
    return data


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


def planet_list_row_y(row: int) -> int:
    if row < 0 or row >= PLANET_LIST_VISIBLE_ROWS:
        raise RE4Error(
            f"planet-list row must be in [0, {PLANET_LIST_VISIBLE_ROWS - 1}], got {row}"
        )
    return PLANET_LIST_FIRST_ROW_Y + row * PLANET_LIST_ROW_HEIGHT


def select_planet_list_row(inp: "XInput", row: int) -> None:
    inp.move_to(205, planet_list_row_y(row))
    inp.click()


def self_managed_region(row: int) -> tuple[int, int, int, int]:
    x, y, width, height = SELF_MANAGED_REGION
    planet_list_row_y(row)  # validate the same bounded visible-row contract
    return x, y + row * PLANET_LIST_RENDER_ROW_HEIGHT, width, height


def scenario_steps(inp: XInput, kind: str) -> None:
    inp.click()
    time.sleep(0.25)
    if kind == "resume":
        inp.move_to(320, 333)
        inp.click()
        time.sleep(1.5)
    elif kind == "new-snovemdomas":
        inp.move_to(320, 293)
        inp.click()
        time.sleep(1.5)
        inp.move_to(560, 210)
        inp.click()
        time.sleep(0.5)
        inp.move_to(570, 460)
        inp.click()
        time.sleep(3.0)
        inp.key("Escape")
        time.sleep(1.5)
    else:
        raise RE4Error(f"unknown scenario {kind}")
    inp.move_to(520, 140)
    inp.click()
    time.sleep(1.0)


def run_scenario(
    root: Path,
    dosbox: str,
    artifacts: Path,
    kind: str,
    expected_name: str | None,
    planet_list_row: int = 0,
) -> dict[str, Any]:
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

        managed_region = self_managed_region(planet_list_row)
        manual_list = artifacts / f"{kind}-manual-list.png"
        manual_list_sha = capture(manual_list, display, geom, env)
        manual_region_hash = rgb_region_sha256(manual_list, *managed_region)
        select_planet_list_row(inp, planet_list_row)
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

        inp.key("m")
        wait_field(proc.pid, field_host, MANAGED)
        inp.key("Escape")
        time.sleep(0.8)
        managed_list = artifacts / f"{kind}-managed-list.png"
        managed_list_sha = capture(managed_list, display, geom, env)
        managed_region_hash = rgb_region_sha256(managed_list, *managed_region)

        select_planet_list_row(inp, planet_list_row)
        time.sleep(0.5)
        inp.key("m")
        wait_field(proc.pid, field_host, MANUAL)
        inp.key("Escape")
        time.sleep(0.8)
        restored_list = artifacts / f"{kind}-restored-manual-list.png"
        restored_list_sha = capture(restored_list, display, geom, env)
        restored_region_hash = rgb_region_sha256(restored_list, *managed_region)
        visual_transition = validate_renderer_transition(
            manual_region_hash, managed_region_hash, restored_region_hash
        )

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
                "restored_manual_planet_list_sha256": restored_list_sha,
                "self_managed_region": list(managed_region),
                **visual_transition,
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
    ap.add_argument(
        "--planet-name",
        default="Xerxes I",
        help="Expected selected planet name for --scenario resume (default: Xerxes I).",
    )
    ap.add_argument(
        "--planet-list-row",
        type=int,
        default=0,
        help="Visible Planets-list row to select for --scenario resume (0..2; default: 0).",
    )
    ap.add_argument("--artifacts", type=Path, required=True)
    ns = ap.parse_args()
    root = ns.game_dir.resolve()
    if not root.is_dir():
        ap.error("game-dir must exist")
    fixture = verify_fixture(root, ns.fixture_manifest.resolve())
    resume_candidates = [
        p for p in root.iterdir() if p.is_file() and p.name.casefold() == "resume.gam"
    ]
    if len(resume_candidates) > 1:
        ap.error("ambiguous case-insensitive resume.gam filenames")
    resume = resume_candidates[0] if resume_candidates else None
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

    if ns.scenario == "resume":
        try:
            planet_list_row_y(ns.planet_list_row)
        except RE4Error as exc:
            ap.error(str(exc))
    expected = ns.planet_name if ns.scenario == "resume" else None
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
        result["scenario"] = run_scenario(
            root, ns.dosbox, ns.artifacts, ns.scenario, expected, ns.planet_list_row
        )
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
