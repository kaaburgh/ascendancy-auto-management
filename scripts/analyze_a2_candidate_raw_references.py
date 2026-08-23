#!/usr/bin/env python3
"""Produce a bounded raw-reference census for the two leading A2 capacity ranges.

This probe is intentionally independent of the Stage-1 zero-run/direct-control-flow
oracle. It scans the immutable target bytes for 32-bit little-endian values that
fall inside either candidate as a linear virtual address or as an object-2
relative offset. Matches are investigation leads only; absence of a match does
not establish semantic inactivity or reusable capacity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from dataclasses import dataclass

SCHEMA = "ascendancy.a2-candidate-raw-references/v1"
CANONICAL_SHA256 = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
OBJECT2_BASE = 0x90000
MAX_MATCHES = 10000


class RawReferenceError(ValueError):
    pass


@dataclass(frozen=True)
class Candidate:
    label: str
    address: int
    size: int
    object_base: int = OBJECT2_BASE

    @property
    def end(self) -> int:
        return self.address + self.size

    @property
    def object_offset(self) -> int:
        return self.address - self.object_base


CANDIDATES = (
    Candidate("object2-96c10", 0x96C10, 6206),
    Candidate("object2-988dc", 0x988DC, 3052),
)


def validate_output_path(target: pathlib.Path, output: pathlib.Path | None) -> None:
    if output is None:
        return
    target_path = target.expanduser().resolve(strict=True)
    output_path = output.expanduser().resolve(strict=False)
    if target_path == output_path:
        raise RawReferenceError(f"output path aliases immutable target input: {target_path}")


def _candidate_encodings(candidate: Candidate) -> tuple[tuple[str, int, int], ...]:
    if candidate.address < candidate.object_base:
        raise RawReferenceError(f"candidate {candidate.label} precedes its object base")
    return (
        ("linear-va", candidate.address, candidate.end),
        (
            "object-relative",
            candidate.object_offset,
            candidate.object_offset + candidate.size,
        ),
    )


def scan_raw_references(data: bytes, candidates: tuple[Candidate, ...] = CANDIDATES) -> list[dict]:
    matches: list[dict] = []
    encodings = [
        (candidate, encoding, start, end)
        for candidate in candidates
        for encoding, start, end in _candidate_encodings(candidate)
    ]
    if len(data) < 4:
        return matches

    for file_offset in range(len(data) - 3):
        value = int.from_bytes(data[file_offset : file_offset + 4], "little")
        for candidate, encoding, start, end in encodings:
            if start <= value < end:
                matches.append(
                    {
                        "file_offset": file_offset,
                        "value": value,
                        "candidate": candidate.label,
                        "encoding": encoding,
                        "candidate_delta": value - start,
                    }
                )
                if len(matches) > MAX_MATCHES:
                    raise RawReferenceError(
                        f"raw-reference census exceeded bounded match limit {MAX_MATCHES}"
                    )
    return matches


def build_report(data: bytes, *, name: str, expected_sha256: str) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise RawReferenceError(
            f"target SHA-256 mismatch: expected {expected_sha256}, found {digest}"
        )

    matches = scan_raw_references(data)
    counts: dict[str, dict[str, int]] = {
        candidate.label: {"linear-va": 0, "object-relative": 0}
        for candidate in CANDIDATES
    }
    for match in matches:
        counts[match["candidate"]][match["encoding"]] += 1

    return {
        "schema": SCHEMA,
        "target": {"name": name, "sha256": digest, "file_size": len(data)},
        "method": {
            "word_width_bits": 32,
            "byte_order": "little",
            "scan_stride_bytes": 1,
            "encodings": ["linear-va", "object-relative"],
            "object_2_base": OBJECT2_BASE,
            "semantics": (
                "matches are raw-byte investigation leads only; no match does not establish "
                "absence of computed, indirect, narrower-width, relocated, or runtime-only consumers"
            ),
        },
        "candidates": [
            {
                "label": candidate.label,
                "address": candidate.address,
                "size": candidate.size,
                "object_base": candidate.object_base,
                "object_offset": candidate.object_offset,
                "match_counts": counts[candidate.label],
                "reusable": False,
                "reuse_evidence": "not established",
            }
            for candidate in CANDIDATES
        ],
        "matches": matches,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        validate_output_path(args.target, args.output)
        data = args.target.read_bytes()
        report = build_report(
            data,
            name=args.target.name,
            expected_sha256=CANONICAL_SHA256,
        )
    except (OSError, RawReferenceError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(text)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote A2 raw-reference census to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
