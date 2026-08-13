#!/usr/bin/env python3
"""Fetch and verify the pinned official Ascendancy playable demo.

The committed manifest is the only network source of truth. The archive and
all extracted files are hash/size pinned, and extraction is fail-closed before
anything becomes the destination tree.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import pathlib
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tools" / "demo-runtime-manifest.json"
DEFAULT_DEST = ROOT / "game" / "demo"
IGNORED_ROOTS = {"game", "binaries", "reference", "artifacts", "captures", "dumps"}
CHUNK = 64 * 1024
TIMEOUT = 120


class DemoError(Exception):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: pathlib.Path = MANIFEST) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DemoError(f"cannot read manifest {path}: {exc}") from exc
    if data.get("schema") != 1:
        raise DemoError(f"unsupported manifest schema: {data.get('schema')!r}")
    archive = data.get("archive")
    files = data.get("files")
    if not isinstance(archive, dict) or not isinstance(files, list) or not files:
        raise DemoError("manifest must contain archive metadata and files")
    required_archive = {"size", "sha256", "sources"}
    if not required_archive <= archive.keys() or not archive["sources"]:
        raise DemoError("manifest archive metadata is incomplete")
    seen: set[str] = set()
    for entry in files:
        if not {"name", "size", "sha256"} <= entry.keys():
            raise DemoError("manifest file entry is incomplete")
        name = entry["name"]
        if pathlib.PurePosixPath(name).name != name or pathlib.PureWindowsPath(name).name != name:
            raise DemoError(f"manifest file must be a bare filename: {name!r}")
        folded = name.casefold()
        if folded in seen:
            raise DemoError(f"duplicate manifest filename: {name!r}")
        seen.add(folded)
    return data


def resolve_dest(dest: pathlib.Path, allow_unignored: bool) -> pathlib.Path:
    dest = dest.resolve()
    if allow_unignored:
        return dest
    try:
        relative = dest.relative_to(ROOT.resolve())
    except ValueError:
        return dest
    if not relative.parts or relative.parts[0] not in IGNORED_ROOTS:
        raise DemoError(
            f"refusing to write demo bytes to tracked repository path {dest}; "
            "use game/, binaries/, reference/, artifacts/, captures/, or dumps/"
        )
    return dest


def download(url: str, expected_size: int) -> bytes:
    buffer = io.BytesIO()
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                buffer.write(chunk)
                if buffer.tell() > expected_size:
                    raise DemoError(f"download exceeds pinned size {expected_size}")
    except DemoError:
        raise
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise DemoError(f"download failed: {exc}") from exc
    data = buffer.getvalue()
    if len(data) != expected_size:
        raise DemoError(f"archive size mismatch: expected {expected_size}, got {len(data)}")
    return data


def archive_bytes(manifest: dict, supplied: pathlib.Path | None) -> bytes:
    meta = manifest["archive"]
    if supplied is not None:
        try:
            data = supplied.read_bytes()
        except OSError as exc:
            raise DemoError(f"cannot read supplied archive {supplied}: {exc}") from exc
        source = f"local:{supplied}"
    else:
        failures: list[str] = []
        data = None
        source = ""
        for candidate in meta["sources"]:
            url = candidate.get("url")
            if not url:
                failures.append("manifest source missing url")
                continue
            try:
                data = download(url, meta["size"])
            except DemoError as exc:
                failures.append(f"{url}: {exc}")
                continue
            source = url
            break
        if data is None:
            raise DemoError("all reviewed demo sources failed: " + "; ".join(failures))
    if len(data) != meta["size"]:
        raise DemoError(f"{source}: archive size mismatch: expected {meta['size']}, got {len(data)}")
    actual = sha256_bytes(data)
    if actual != meta["sha256"]:
        raise DemoError(f"{source}: archive sha256 mismatch: expected {meta['sha256']}, got {actual}")
    return data


def extract_verified(archive: bytes, manifest: dict, dest: pathlib.Path) -> None:
    try:
        zf = zipfile.ZipFile(io.BytesIO(archive))
    except zipfile.BadZipFile as exc:
        raise DemoError(f"archive is not a readable zip: {exc}") from exc
    with zf, tempfile.TemporaryDirectory(prefix="cf3-demo-") as temp_name:
        temp = pathlib.Path(temp_name)
        infos = [info for info in zf.infolist() if not info.is_dir()]
        by_basename: dict[str, list[zipfile.ZipInfo]] = {}
        for info in infos:
            basename = pathlib.PurePosixPath(info.filename).name
            by_basename.setdefault(basename.casefold(), []).append(info)
        for expected in manifest["files"]:
            matches = by_basename.get(expected["name"].casefold(), [])
            if len(matches) != 1:
                raise DemoError(
                    f"expected exactly one archive member named {expected['name']!r}, got {len(matches)}"
                )
            data = zf.read(matches[0])
            if len(data) != expected["size"] or sha256_bytes(data) != expected["sha256"]:
                raise DemoError(f"archive member verification failed: {expected['name']}")
            (temp / expected["name"]).write_bytes(data)
        dest.parent.mkdir(parents=True, exist_ok=True)
        staging = dest.with_name(dest.name + ".part")
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(temp, staging)
        if dest.exists():
            shutil.rmtree(dest)
        os.replace(staging, dest)


def verify_tree(dest: pathlib.Path, manifest: dict) -> list[str]:
    errors: list[str] = []
    for expected in manifest["files"]:
        path = dest / expected["name"]
        if not path.is_file():
            errors.append(f"missing {expected['name']}")
            continue
        size = path.stat().st_size
        digest = sha256_file(path)
        if size != expected["size"] or digest != expected["sha256"]:
            errors.append(
                f"{expected['name']}: expected {expected['size']} / {expected['sha256']}, "
                f"got {size} / {digest}"
            )
    return errors


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dest", type=pathlib.Path, default=DEFAULT_DEST)
    p.add_argument("--archive", type=pathlib.Path, help="verify/extract this local archive instead of downloading")
    p.add_argument("--verify", action="store_true", help="verify an already extracted demo tree")
    p.add_argument("--allow-unignored-dest", action="store_true")
    return p


def main(argv: list[str] | None = None, manifest_path: pathlib.Path = MANIFEST) -> int:
    args = parser().parse_args(argv)
    try:
        manifest = load_manifest(manifest_path)
        dest = resolve_dest(args.dest, args.allow_unignored_dest)
        if args.verify:
            errors = verify_tree(dest, manifest)
            if errors:
                raise DemoError("demo verification failed: " + "; ".join(errors))
            print(f"verified {len(manifest['files'])} demo files in {dest}")
            return 0
        data = archive_bytes(manifest, args.archive)
        extract_verified(data, manifest, dest)
        errors = verify_tree(dest, manifest)
        if errors:
            raise DemoError("post-extraction verification failed: " + "; ".join(errors))
        print(f"fetched and verified {len(manifest['files'])} demo files in {dest}")
        return 0
    except DemoError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
