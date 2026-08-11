#!/usr/bin/env python3
"""Fetch the freely redistributed Ascendancy executables into an ignored directory.

This tool exists so a clean cloud environment can obtain candidate target bytes
reproducibly. It only ever downloads artifacts listed in
``tools/free-target-sources.json`` and it fails closed: an entry produces an
output file only after the downloaded archive *and* the extracted member both
match their pinned size and SHA-256.

It deliberately cannot be pointed at an arbitrary URL. Adding a source means
editing the manifest, which is reviewable.

See ``docs/experiments/CF1-cloud-target-access.md`` for provenance and the
repository policy that governs what may be listed in the manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "tools" / "free-target-sources.json"
DEFAULT_DEST = ROOT / "binaries"

# Repository-root directories that .gitignore keeps out of version control.
# Downloaded executables must land in one of these so proprietary or
# redistribution-restricted bytes can never be committed by accident.
IGNORED_ROOTS = ("binaries", "reference", "game", "artifacts", "captures", "dumps")

CHUNK = 64 * 1024
TIMEOUT = 120


class FetchError(Exception):
    """A source or entry failed verification. Nothing was written."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_bare_filename(name: str) -> bool:
    """True when ``name`` is a plain filename under POSIX *and* Windows rules.

    Both must be checked. ``PurePosixPath`` treats ``..\\tracked.exe`` and
    ``C:\\tracked.exe`` as single components, but the destination is joined with
    a native ``Path``, so on Windows a backslash or drive prefix would escape
    the git-ignored output directory. This tool is expected to run on the
    maintainer's Windows machine as well as in cloud.
    """
    if not name:
        return False
    return (
        pathlib.PurePosixPath(name).name == name
        and pathlib.PureWindowsPath(name).name == name
    )


def load_manifest(path: pathlib.Path) -> list[dict]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FetchError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FetchError(f"manifest is not valid JSON: {path}: {exc}") from exc

    if raw.get("schema") != 1:
        raise FetchError(f"unsupported manifest schema: {raw.get('schema')!r}")

    entries = raw.get("entries")
    if not isinstance(entries, list) or not entries:
        raise FetchError("manifest contains no entries")

    required = ("id", "output", "member_size", "member_sha256", "sources")
    seen_ids: set[str] = set()
    seen_outputs: set[str] = set()

    for entry in entries:
        missing = [key for key in required if key not in entry]
        if missing:
            raise FetchError(
                f"manifest entry {entry.get('id', '<unnamed>')!r} is missing: "
                f"{', '.join(missing)}"
            )
        if entry["id"] in seen_ids:
            raise FetchError(f"duplicate manifest id: {entry['id']!r}")
        if entry["output"] in seen_outputs:
            raise FetchError(f"duplicate manifest output name: {entry['output']!r}")
        if not entry["sources"]:
            raise FetchError(f"manifest entry {entry['id']!r} has no sources")
        if not is_bare_filename(entry["output"]):
            raise FetchError(
                f"manifest entry {entry['id']!r} output must be a bare filename, "
                f"got {entry['output']!r}"
            )
        seen_ids.add(entry["id"])
        seen_outputs.add(entry["output"])

    return entries


def resolve_dest(dest: pathlib.Path, allow_unignored: bool) -> pathlib.Path:
    dest = dest.resolve()
    if allow_unignored:
        return dest

    try:
        relative = dest.relative_to(ROOT.resolve())
    except ValueError:
        # Outside the repository: git cannot track it, so it is safe by default.
        return dest

    if not relative.parts or relative.parts[0] not in IGNORED_ROOTS:
        raise FetchError(
            f"refusing to write target bytes to {dest}: paths inside the "
            f"repository must be under one of the git-ignored roots "
            f"({', '.join(IGNORED_ROOTS)}). Pass --allow-unignored-dest only if "
            f"you are certain the destination is not tracked by git."
        )
    return dest


def download(url: str, expected_size: int) -> bytes:
    """Download ``url``, refusing anything larger than the pinned size."""
    limit = expected_size + 1
    buffer = io.BytesIO()
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                buffer.write(chunk)
                if buffer.tell() > limit:
                    raise FetchError(
                        f"response exceeds pinned size {expected_size} bytes"
                    )
    except FetchError:
        raise
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise FetchError(f"download failed: {exc}") from exc

    data = buffer.getvalue()
    if len(data) != expected_size:
        raise FetchError(
            f"size mismatch: expected {expected_size} bytes, got {len(data)}"
        )
    return data


def extract_member(archive: bytes, member: str) -> bytes:
    """Read exactly one unambiguously named member out of a zip archive."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(archive))
    except zipfile.BadZipFile as exc:
        raise FetchError(f"not a readable zip archive: {exc}") from exc

    with zf:
        # Reject case-insensitive collisions rather than silently picking one.
        matches = [
            info
            for info in zf.infolist()
            if not info.is_dir() and info.filename.lower() == member.lower()
        ]
        if not matches:
            names = ", ".join(sorted(info.filename for info in zf.infolist()))
            raise FetchError(f"member {member!r} not found in archive; has: {names}")
        if len(matches) > 1:
            raise FetchError(
                f"member {member!r} matches {len(matches)} archive entries: "
                f"{', '.join(info.filename for info in matches)}"
            )
        try:
            return zf.read(matches[0])
        except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
            raise FetchError(f"cannot read member {member!r}: {exc}") from exc


def fetch_entry(entry: dict, dest: pathlib.Path, force: bool) -> tuple[str, str]:
    """Materialise one manifest entry. Returns ``(status, detail)``."""
    output = dest / entry["output"]

    if output.exists():
        actual = sha256_file(output)
        if actual == entry["member_sha256"]:
            return "present", f"{output} already verified"
        if not force:
            raise FetchError(
                f"{output} exists with sha256 {actual}, expected "
                f"{entry['member_sha256']}. Refusing to overwrite; delete it or "
                f"pass --force."
            )

    failures: list[str] = []
    for source in entry["sources"]:
        url = source.get("url", "<missing url>")
        try:
            required = ("url", "archive_size", "archive_sha256", "member")
            missing = [key for key in required if key not in source]
            if missing:
                raise FetchError(f"source is missing: {', '.join(missing)}")

            archive = download(source["url"], source["archive_size"])

            actual = sha256_bytes(archive)
            if actual != source["archive_sha256"]:
                raise FetchError(
                    f"archive sha256 mismatch: expected "
                    f"{source['archive_sha256']}, got {actual}"
                )

            member = extract_member(archive, source["member"])

            if len(member) != entry["member_size"]:
                raise FetchError(
                    f"member size mismatch: expected {entry['member_size']} "
                    f"bytes, got {len(member)}"
                )

            actual = sha256_bytes(member)
            if actual != entry["member_sha256"]:
                raise FetchError(
                    f"member sha256 mismatch: expected "
                    f"{entry['member_sha256']}, got {actual}"
                )
        except FetchError as exc:
            failures.append(f"{url}: {exc}")
            continue

        dest.mkdir(parents=True, exist_ok=True)
        partial = output.with_name(output.name + ".part")
        try:
            partial.write_bytes(member)
            os.replace(partial, output)
        finally:
            partial.unlink(missing_ok=True)
        return "fetched", f"{output} from {url}"

    detail = "; ".join(failures)
    raise FetchError(f"all {len(entry['sources'])} sources failed for {entry['id']!r}: {detail}")


def verify_entry(entry: dict, dest: pathlib.Path) -> tuple[str, str]:
    output = dest / entry["output"]
    if not output.exists():
        raise FetchError(f"{output} is missing")
    actual = sha256_file(output)
    if actual != entry["member_sha256"]:
        raise FetchError(
            f"{output} sha256 {actual} does not match pinned "
            f"{entry['member_sha256']}"
        )
    return "ok", str(output)


def select_entries(entries: list[dict], ids: list[str] | None) -> list[dict]:
    if not ids:
        return entries
    by_id = {entry["id"]: entry for entry in entries}
    unknown = [name for name in ids if name not in by_id]
    if unknown:
        raise FetchError(
            f"unknown id(s): {', '.join(unknown)}. Known ids: "
            f"{', '.join(sorted(by_id))}"
        )
    return [by_id[name] for name in ids]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "ids",
        nargs="*",
        help="manifest ids to process (default: every entry)",
    )
    parser.add_argument(
        "--manifest", type=pathlib.Path, default=DEFAULT_MANIFEST,
        help="source manifest (default: tools/free-target-sources.json)",
    )
    parser.add_argument(
        "--dest", type=pathlib.Path, default=DEFAULT_DEST,
        help="output directory (default: binaries/, which is git-ignored)",
    )
    parser.add_argument(
        "--list", action="store_true", help="list manifest entries and exit",
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="verify already-downloaded files without using the network",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="replace an existing output whose hash does not match",
    )
    parser.add_argument(
        "--allow-unignored-dest", action="store_true",
        help="permit a destination inside the repository that git may track",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        entries = select_entries(load_manifest(args.manifest), args.ids)
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.list:
        for entry in entries:
            print(f"{entry['id']}")
            print(f"  role    : {entry.get('role', 'unspecified')}")
            print(f"  locale  : {entry.get('locale', 'unspecified')}")
            print(f"  output  : {entry['output']}")
            print(f"  size    : {entry['member_size']}")
            print(f"  sha256  : {entry['member_sha256']}")
            print(f"  sources : {len(entry['sources'])}")
        return 0

    try:
        dest = resolve_dest(args.dest, args.allow_unignored_dest)
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    failed = 0
    for entry in entries:
        try:
            if args.verify:
                status, detail = verify_entry(entry, dest)
            else:
                status, detail = fetch_entry(entry, dest, args.force)
        except FetchError as exc:
            failed += 1
            print(f"FAIL  {entry['id']}: {exc}", file=sys.stderr)
        else:
            print(f"{status:<8}{entry['id']}: {detail}")

    if failed:
        print(
            f"error: {failed} of {len(entries)} entries failed", file=sys.stderr
        )
        return 1

    print(f"{len(entries)} of {len(entries)} entries verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
