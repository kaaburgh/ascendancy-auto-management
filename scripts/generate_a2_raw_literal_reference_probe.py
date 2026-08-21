#!/usr/bin/env python3
"""Probe A2 candidate ranges for raw file-backed 32-bit address literals.

This is an independent structural lead generator, not proof of reads or reuse.
It intentionally does not consume the Stage 1 zero-run inventory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import le_image  # noqa: E402

SCHEMA = "ascendancy.a2-raw-literal-reference-probe/v1"
CANONICAL_SHA256 = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
CANDIDATES = (
    {"id": "object2-0x96c10", "start": 0x96C10, "size": 6206},
    {"id": "object2-0x988dc", "start": 0x988DC, "size": 3052},
)


class LiteralProbeError(Exception):
    pass


def candidate_for(value: int, candidates: tuple[dict, ...] = CANDIDATES) -> dict | None:
    for candidate in candidates:
        if candidate["start"] <= value < candidate["start"] + candidate["size"]:
            return candidate
    return None


def scan_literal_dwords(data: bytes, base_address: int, candidates: tuple[dict, ...] = CANDIDATES) -> list[dict]:
    """Return every overlapping little-endian dword whose value lands in a candidate range."""
    hits: list[dict] = []
    for offset in range(max(0, len(data) - 3)):
        value = int.from_bytes(data[offset : offset + 4], "little")
        candidate = candidate_for(value, candidates)
        if candidate is not None:
            hits.append(
                {
                    "site_address": base_address + offset,
                    "literal_value": value,
                    "candidate_id": candidate["id"],
                    "candidate_offset": value - candidate["start"],
                }
            )
    return hits


def validate_output_path(target: pathlib.Path, output: pathlib.Path | None) -> None:
    if output is None:
        return
    if target.expanduser().resolve(strict=True) == output.expanduser().resolve(strict=False):
        raise LiteralProbeError("output path aliases immutable target input")


def build_probe(image: le_image.LEImage, *, expected_sha256: str = CANONICAL_SHA256) -> dict:
    if image.sha256 != expected_sha256:
        raise LiteralProbeError(
            f"target SHA-256 mismatch: expected {expected_sha256}, found {image.sha256}"
        )

    hits: list[dict] = []
    for obj in image.objects:
        data = image.object_bytes(obj.index)
        for hit in scan_literal_dwords(data, obj.base_address):
            site = hit["site_address"]
            first = image.va_to_file_offset(site)
            last = image.va_to_file_offset(site + 3)
            if first is None or last is None or last != first + 3:
                continue
            record = dict(hit)
            record.update(
                {
                    "source_object": obj.index,
                    "source_object_kind": obj.kind,
                    "source_file_offset": first,
                }
            )
            hits.append(record)

    producer_path = pathlib.Path(__file__).resolve()
    return {
        "schema": SCHEMA,
        "target": {"name": image.name, "sha256": image.sha256, "file_size": image.size},
        "producer": {
            "path": "scripts/generate_a2_raw_literal_reference_probe.py",
            "sha256": hashlib.sha256(producer_path.read_bytes()).hexdigest(),
            "le_parser": "tools/le_image.py",
        },
        "method": {
            "scan": "all overlapping file-backed little-endian 32-bit words in mapped LE objects",
            "semantics": (
                "a hit is only a raw literal lead; it does not establish an executed/read reference. "
                "absence of hits does not exclude computed, narrower, indirect, or runtime references"
            ),
        },
        "candidates": list(CANDIDATES),
        "literal_hits": hits,
        "literal_hit_count": len(hits),
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
        probe = build_probe(le_image.load(args.target))
    except (LiteralProbeError, le_image.LEError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(probe, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote A2 raw-literal probe to {args.output}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
