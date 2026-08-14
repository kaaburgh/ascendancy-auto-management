#!/usr/bin/env python3
"""Verify the exact operator-supplied V1 validation-state files.

This intentionally verifies identity and the recorded byte relationship only.
It does not claim save-format semantics; runtime V1 must re-establish the
required game-state properties on the canonical target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class VerificationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def casefold_map(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for p in root.iterdir():
        if not p.is_file():
            continue
        key = p.name.casefold()
        if key in result:
            raise VerificationError(
                f"ambiguous case-insensitive filename: {result[key].name}/{p.name}"
            )
        result[key] = p
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--input-dir", type=Path, required=True)
    ns = ap.parse_args()

    manifest = json.loads(ns.manifest.read_text(encoding="utf-8"))
    if manifest.get("schema") != 1 or manifest.get("id") != "v1-operator-validation-state-2026-08-14":
        raise VerificationError("unexpected manifest schema/id")

    root = ns.input_dir.resolve()
    if not root.is_dir():
        raise VerificationError("input-dir is not a directory")
    files = casefold_map(root)

    verified: dict[str, Path] = {}
    for entry in manifest["files"]:
        p = files.get(entry["name"].casefold())
        if p is None:
            raise VerificationError(f"missing input file: {entry['name']}")
        if p.stat().st_size != entry["size"]:
            raise VerificationError(f"size mismatch: {entry['name']}")
        digest = sha256_file(p)
        if digest != entry["sha256"]:
            raise VerificationError(f"SHA-256 mismatch: {entry['name']}")
        verified[entry["role"]] = p

    manual = verified["manual_save"].read_bytes()
    resume = verified["resume_companion"].read_bytes()
    pair = manifest["pair_observation"]
    start = int(pair["identical_from_offset"], 0)
    if len(manual) != len(resume):
        raise VerificationError("paired save files no longer have equal size")
    diff_count = sum(a != b for a, b in zip(manual, resume))
    highest = max((i for i, (a, b) in enumerate(zip(manual, resume)) if a != b), default=-1)
    if diff_count != pair["differing_byte_count"]:
        raise VerificationError("paired save differing-byte count mismatch")
    if highest != int(pair["highest_differing_offset"], 0):
        raise VerificationError("paired save highest differing offset mismatch")
    if manual[start:] != resume[start:]:
        raise VerificationError("paired save suffix is not byte-identical")
    if hashlib.sha256(manual[start:]).hexdigest() != pair["identical_suffix_sha256"]:
        raise VerificationError("paired save suffix SHA-256 mismatch")

    print(
        "V1 operator validation-state identity: PASS "
        f"({len(manifest['files'])} files; suffix identical from {pair['identical_from_offset']})"
    )
    print("Runtime game-state verification is still required by V1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
