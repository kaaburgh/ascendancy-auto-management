#!/usr/bin/env python3
"""Run a bounded headless DOSBox runtime probe and package its evidence.

This is a CF3 feasibility harness, not a feature-validation driver.  It provides
only timed key injection plus framebuffer snapshots.  Later UI automation is
intentionally left to CF4.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE_SOURCE = ROOT / "tools" / "cf3_sdl12_probe.c"
DEMO_MANIFEST = ROOT / "tools" / "demo-runtime-manifest.json"
ARTIFACTS = ROOT / "artifacts"
CANONICAL_ANTAG_SHA256 = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
DEMO_EXE_SHA256 = "0183b75cb44ce52b52ba57baf2b9521e21a7611e487a1ebb5b768067441960a9"
MODE_RE = re.compile(r"CF3SDL mode (\d+)x(\d+) bpp=(\d+)")


class SmokeError(Exception):
    pass


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_demo_tree(path: pathlib.Path) -> None:
    data = json.loads(DEMO_MANIFEST.read_text(encoding="utf-8"))
    errors = []
    for item in data["files"]:
        candidate = path / item["name"]
        if not candidate.is_file():
            errors.append(f"missing {item['name']}")
            continue
        if candidate.stat().st_size != item["size"] or sha256_file(candidate) != item["sha256"]:
            errors.append(f"mismatch {item['name']}")
    if errors:
        raise SmokeError("demo tree failed pinned verification: " + ", ".join(errors))


def compile_probe(build_dir: pathlib.Path) -> pathlib.Path:
    compiler = shutil.which("gcc")
    if not compiler:
        raise SmokeError("gcc is required to build the SDL 1.2 probe")
    output = build_dir / "cf3_sdl12_probe.so"
    command = [compiler, "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Werror", "-pthread", "-o", str(output), str(PROBE_SOURCE), "-ldl"]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode:
        raise SmokeError(f"probe build failed ({completed.returncode}):\n{completed.stderr}")
    return output


def materialize_overlay(game_dir: pathlib.Path, executable: pathlib.Path, mount_dir: pathlib.Path) -> pathlib.Path:
    for source in game_dir.iterdir():
        if not source.is_file():
            continue
        destination = mount_dir / source.name
        try:
            os.link(source, destination)
        except OSError:
            shutil.copy2(source, destination)
    target = mount_dir / executable.name.upper()
    if target.exists():
        target.unlink()
    shutil.copy2(executable, target)
    return target


def make_artifact(run_dir: pathlib.Path, metadata: dict, destination: pathlib.Path) -> None:
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(run_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(run_dir))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dosbox", type=pathlib.Path, required=True, help="DOSBox launcher/wrapper")
    p.add_argument("--game-dir", type=pathlib.Path, required=True, help="data directory to mount as C:")
    p.add_argument("--exe", type=pathlib.Path, help="executable to overlay into the mounted tree; default game-dir/ASCEND.EXE")
    p.add_argument("--expected-exe-sha256", help="fail closed unless the executable has this SHA-256")
    p.add_argument("--verify-demo", action="store_true", help="require the mounted data tree to match the pinned official demo")
    p.add_argument("--key-events", default="", help="semicolon-separated TIME_MS:KEY events; supported keys: space, enter, escape, one character")
    p.add_argument("--captures-ms", default="5000,8000,12000", help="comma-separated framebuffer capture times")
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--expect-mode", default="", help="require a requested video mode such as 640x480")
    p.add_argument("--artifact", type=pathlib.Path, help="output zip (default artifacts/run-CF3-<timestamp>.zip)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        dosbox = args.dosbox.resolve()
        game_dir = args.game_dir.resolve()
        if not dosbox.is_file():
            raise SmokeError(f"DOSBox launcher not found: {dosbox}")
        if not game_dir.is_dir():
            raise SmokeError(f"game directory not found: {game_dir}")
        if args.verify_demo:
            verify_demo_tree(game_dir)
        executable = (args.exe.resolve() if args.exe else game_dir / "ASCEND.EXE")
        if not executable.is_file():
            raise SmokeError(f"executable not found: {executable}")
        exe_sha = sha256_file(executable)
        if args.expected_exe_sha256 and exe_sha.lower() != args.expected_exe_sha256.lower():
            raise SmokeError(f"executable sha256 {exe_sha} != expected {args.expected_exe_sha256}")

        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%SZ")
        artifact = args.artifact or (ARTIFACTS / f"run-CF3-{timestamp}.zip")
        with tempfile.TemporaryDirectory(prefix="cf3-runtime-") as temp_name:
            temp = pathlib.Path(temp_name)
            build = temp / "build"; build.mkdir()
            mount = temp / "mount"; mount.mkdir()
            run = temp / "artifact"; run.mkdir()
            captures = run / "captures"; captures.mkdir()
            probe = compile_probe(build)
            mounted_exe = materialize_overlay(game_dir, executable, mount)

            env = os.environ.copy()
            env.update({
                "SDL_VIDEODRIVER": "dummy",
                "SDL_AUDIODRIVER": "dummy",
                "LD_PRELOAD": str(probe),
                "CF3_CAPTURE_DIR": str(captures),
                "CF3_KEY_EVENTS": args.key_events,
                "CF3_CAPTURES_MS": args.captures_ms,
                "HOME": str(temp / "home"),
            })
            command = [str(dosbox), "-c", f"mount c {mount}", "-c", "c:", "-c", mounted_exe.name]
            timed_out = False
            try:
                completed = subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=args.timeout)
                returncode = completed.returncode
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                returncode = None
                stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            else:
                stdout, stderr = completed.stdout, completed.stderr
            (run / "dosbox.stdout.txt").write_text(stdout, encoding="utf-8", errors="replace")
            (run / "dosbox.stderr.txt").write_text(stderr, encoding="utf-8", errors="replace")
            modes = [[int(a), int(b), int(c)] for a, b, c in MODE_RE.findall(stderr)]
            expected_mode_ok = True
            if args.expect_mode:
                try:
                    width, height = [int(part) for part in args.expect_mode.lower().split("x", 1)]
                except ValueError as exc:
                    raise SmokeError(f"invalid --expect-mode {args.expect_mode!r}") from exc
                expected_mode_ok = any(mode[0] == width and mode[1] == height for mode in modes)
            metadata = {
                "schema": 1,
                "experiment": "CF3-runtime-smoke",
                "executable": {"name": executable.name, "sha256": exe_sha, "size": executable.stat().st_size},
                "game_dir_demo_verified": bool(args.verify_demo),
                "dosbox": str(dosbox),
                "command": command,
                "timeout_seconds": args.timeout,
                "timed_out": timed_out,
                "returncode": returncode,
                "requested_modes": modes,
                "expected_mode": args.expect_mode or None,
                "expected_mode_observed": expected_mode_ok,
                "capture_count": len(list(captures.glob("*.ppm"))),
                "key_events": args.key_events,
            }
            make_artifact(run, metadata, artifact.resolve())
            if args.expect_mode and not expected_mode_ok:
                raise SmokeError(f"expected mode {args.expect_mode} was not observed; artifact: {artifact}")
            print(f"runtime smoke PASS; artifact: {artifact}")
            return 0
    except SmokeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
