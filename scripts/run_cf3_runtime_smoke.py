#!/usr/bin/env python3
"""Run a bounded headless DOSBox runtime probe and package its evidence.

This is a CF3 feasibility harness, not a feature-validation driver. It provides
only timed key injection plus framebuffer snapshots. Later UI automation is
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
RETAIL_MANIFEST = ROOT / "tools" / "retail-runtime-manifest.json"
ARTIFACTS = ROOT / "artifacts"
MODE_RE = re.compile(r"CF3SDL mode (\d+)x(\d+) bpp=(\d+) ok=([01])")


class SmokeError(Exception):
    pass


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest_tree(path: pathlib.Path, manifest_path: pathlib.Path, label: str) -> None:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("schema") != 1 or not isinstance(data.get("files"), list):
        raise SmokeError(f"{label} manifest is malformed: {manifest_path}")

    by_name: dict[str, pathlib.Path] = {}
    duplicates: list[str] = []
    for candidate in path.iterdir():
        if not candidate.is_file():
            continue
        key = candidate.name.casefold()
        if key in by_name:
            duplicates.append(candidate.name)
        else:
            by_name[key] = candidate
    if duplicates:
        raise SmokeError(f"{label} tree has ambiguous case-insensitive filenames: {', '.join(sorted(duplicates))}")

    errors = []
    for item in data["files"]:
        candidate = by_name.get(item["name"].casefold())
        if candidate is None:
            errors.append(f"missing {item['name']}")
            continue
        if candidate.stat().st_size != item["size"] or sha256_file(candidate) != item["sha256"]:
            errors.append(f"mismatch {item['name']}")
    if errors:
        raise SmokeError(f"{label} tree failed pinned verification: " + ", ".join(errors))


def verify_demo_tree(path: pathlib.Path) -> None:
    verify_manifest_tree(path, DEMO_MANIFEST, "demo")


def verify_retail_tree(path: pathlib.Path) -> None:
    verify_manifest_tree(path, RETAIL_MANIFEST, "retail")


def compile_probe(build_dir: pathlib.Path) -> pathlib.Path:
    compiler = shutil.which("gcc")
    if not compiler:
        raise SmokeError("gcc is required to build the SDL 1.2 probe")
    output = build_dir / "cf3_sdl12_probe.so"
    command = [compiler, "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Werror", "-o", str(output), str(PROBE_SOURCE), "-ldl"]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode:
        raise SmokeError(f"probe build failed ({completed.returncode}):\n{completed.stderr}")
    return output


def materialize_overlay(game_dir: pathlib.Path, executable: pathlib.Path, mount_dir: pathlib.Path) -> pathlib.Path:
    for source in game_dir.iterdir():
        if source.is_file():
            # Never hardlink a maintainer-owned installation: guest writes to a
            # hardlink would mutate the source inode. The temporary overlay is
            # intentionally an independent copy so the source tree is read-only
            # from the experiment's point of view.
            shutil.copy2(source, mount_dir / source.name)
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
    fixture = p.add_mutually_exclusive_group()
    fixture.add_argument("--verify-demo", action="store_true", help="require the mounted data tree to match the pinned official demo")
    fixture.add_argument("--verify-retail", action="store_true", help="require the mounted data tree to match the pinned maintainer-supplied retail runtime fixture")
    p.add_argument("--key-events", default="", help="semicolon-separated TIME_MS:KEY events; supported keys: space, enter, escape, alt-pause, one character")
    p.add_argument("--captures-ms", default="5000,8000,12000", help="comma-separated framebuffer capture times")
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--expect-mode", default="", help="require a successful video mode such as 640x480")
    termination = p.add_mutually_exclusive_group()
    termination.add_argument("--expect-timeout", action="store_true", help="require the guest to remain alive until the bounded timeout")
    termination.add_argument("--expect-exit-code", action="append", type=int, dest="expected_exit_codes", help="require clean termination with this exit code; may be repeated")
    p.add_argument("--artifact", type=pathlib.Path, help="output zip (default artifacts/run-CF3-<timestamp>.zip)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.expect_mode and not (args.expect_timeout or args.expected_exit_codes):
            raise SmokeError("--expect-mode requires explicit termination semantics: --expect-timeout or --expect-exit-code")

        dosbox = args.dosbox.resolve()
        game_dir = args.game_dir.resolve()
        if not dosbox.is_file():
            raise SmokeError(f"DOSBox launcher not found: {dosbox}")
        if not game_dir.is_dir():
            raise SmokeError(f"game directory not found: {game_dir}")
        if args.verify_demo:
            verify_demo_tree(game_dir)
        if args.verify_retail:
            verify_retail_tree(game_dir)
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

            video_modes = [
                {"width": int(a), "height": int(b), "bpp": int(c), "ok": d == "1"}
                for a, b, c, d in MODE_RE.findall(stderr)
            ]
            expected_mode_ok = True
            if args.expect_mode:
                try:
                    width, height = [int(part) for part in args.expect_mode.lower().split("x", 1)]
                except ValueError as exc:
                    raise SmokeError(f"invalid --expect-mode {args.expect_mode!r}") from exc
                expected_mode_ok = any(
                    mode["width"] == width and mode["height"] == height and mode["ok"]
                    for mode in video_modes
                )

            termination_expectation = None
            termination_ok = True
            if args.expect_timeout:
                termination_expectation = {"kind": "timeout"}
                termination_ok = timed_out
            elif args.expected_exit_codes:
                termination_expectation = {"kind": "exit_code", "allowed": args.expected_exit_codes}
                termination_ok = (not timed_out) and returncode in args.expected_exit_codes

            metadata = {
                "schema": 2,
                "experiment": "CF3-runtime-smoke",
                "executable": {"name": executable.name, "sha256": exe_sha, "size": executable.stat().st_size},
                "game_dir_demo_verified": bool(args.verify_demo),
                "game_dir_retail_verified": bool(args.verify_retail),
                "dosbox": {"name": dosbox.name, "sha256": sha256_file(dosbox), "size": dosbox.stat().st_size},
                "command": ["dosbox", "-c", "mount c <TEMP_MOUNT>", "-c", "c:", "-c", mounted_exe.name],
                "environment": {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"},
                "timeout_seconds": args.timeout,
                "timed_out": timed_out,
                "returncode": returncode,
                "video_modes": video_modes,
                "expected_mode": args.expect_mode or None,
                "expected_mode_observed": expected_mode_ok,
                "termination_expectation": termination_expectation,
                "termination_expectation_met": termination_ok,
                "capture_count": len(list(captures.glob("*.ppm"))),
                "key_events": args.key_events,
            }
            make_artifact(run, metadata, artifact.resolve())

            failures = []
            if args.expect_mode and not expected_mode_ok:
                failures.append(f"successful mode {args.expect_mode} was not observed")
            if termination_expectation and not termination_ok:
                if args.expect_timeout:
                    failures.append(f"process terminated before the required {args.timeout:g}s timeout (returncode={returncode})")
                else:
                    failures.append(f"process exit did not match allowed codes {args.expected_exit_codes} (returncode={returncode}, timed_out={timed_out})")
            if failures:
                raise SmokeError("; ".join(failures) + f"; artifact: {artifact}")

            print(f"runtime smoke PASS; artifact: {artifact}")
            return 0
    except SmokeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
