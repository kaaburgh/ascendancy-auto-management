#!/usr/bin/env python3
"""Probe A2 Stage-1 capacity leads for raw 32-bit literal references.

The probe is deliberately narrower than a cave classifier.  It scans mapped LE
object bytes for little-endian 32-bit values that land inside selected candidate
ranges under either linear-VA or target-object-relative interpretation.  Hits are
investigation leads; absence of hits is not evidence that a range is unused.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys
from typing import Iterable

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import le_image  # noqa: E402

SCHEMA = "ascendancy.a2-literal-reference-probe/v1"
CANONICAL_SHA256 = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
CANDIDATES = (
    {"id": "object2-96c10", "object": 2, "address": 0x96C10, "size": 6206},
    {"id": "object2-988dc", "object": 2, "address": 0x988DC, "size": 3052},
)


class LiteralReferenceProbeError(Exception):
    pass


def validate_output_path(target: pathlib.Path, output: pathlib.Path | None) -> None:
    if output is None:
        return
    target_path = target.expanduser().resolve(strict=True)
    output_path = output.expanduser().resolve(strict=False)
    if output_path == target_path:
        raise LiteralReferenceProbeError(
            f"output path aliases immutable target input: {target_path}"
        )


def _candidate_models(candidate: dict, target_base: int) -> tuple[tuple[str, int, int], ...]:
    start = candidate["address"]
    end = start + candidate["size"]
    relative_start = start - target_base
    relative_end = end - target_base
    if relative_start < 0:
        raise LiteralReferenceProbeError(
            f"candidate {candidate['id']!r} starts before target object base"
        )
    return (
        ("linear-va", start, end),
        ("target-object-relative", relative_start, relative_end),
    )


def scan_u32_literals(
    source_objects: Iterable[tuple[int, int, bytes]],
    candidates: Iterable[dict],
    target_bases: dict[int, int],
) -> list[dict]:
    """Return deterministic raw literal-reference leads.

    The scan is intentionally byte-aligned rather than instruction-decoder based;
    this keeps it independent from the Stage-1 GNU-objdump control-flow model.
    False positives are expected and remain explicit leads rather than semantics.
    """
    candidate_list = list(candidates)
    models: list[tuple[dict, str, int, int, int]] = []
    for candidate in candidate_list:
        target_object = candidate["object"]
        if target_object not in target_bases:
            raise LiteralReferenceProbeError(
                f"candidate {candidate['id']!r} names missing object {target_object}"
            )
        target_base = target_bases[target_object]
        for interpretation, start, end in _candidate_models(candidate, target_base):
            models.append((candidate, interpretation, start, end, target_base))

    hits: list[dict] = []
    for source_object, source_base, data in source_objects:
        for offset in range(max(0, len(data) - 3)):
            value = struct.unpack_from("<I", data, offset)[0]
            for candidate, interpretation, start, end, target_base in models:
                if not (start <= value < end):
                    continue
                target_address = value if interpretation == "linear-va" else target_base + value
                hits.append(
                    {
                        "candidate": candidate["id"],
                        "interpretation": interpretation,
                        "source_object": source_object,
                        "source_address": source_base + offset,
                        "source_object_offset": offset,
                        "encoded_u32": value,
                        "target_address": target_address,
                        "target_offset_within_candidate": target_address - candidate["address"],
                    }
                )
    return sorted(
        hits,
        key=lambda hit: (
            hit["candidate"],
            hit["source_object"],
            hit["source_address"],
            hit["interpretation"],
            hit["encoded_u32"],
        ),
    )


def build_probe(
    image: le_image.LEImage,
    *,
    expected_sha256: str,
    candidates: Iterable[dict] = CANDIDATES,
) -> dict:
    if image.sha256 != expected_sha256:
        raise LiteralReferenceProbeError(
            f"target SHA-256 mismatch: expected {expected_sha256}, found {image.sha256}"
        )

    candidate_list = [dict(candidate) for candidate in candidates]
    target_bases = {obj.index: obj.base_address for obj in image.objects}
    for candidate in candidate_list:
        obj = next((item for item in image.objects if item.index == candidate["object"]), None)
        if obj is None:
            raise LiteralReferenceProbeError(
                f"candidate {candidate['id']!r} names missing object {candidate['object']}"
            )
        if not (
            obj.base_address <= candidate["address"]
            and candidate["address"] + candidate["size"] <= obj.end_address
        ):
            raise LiteralReferenceProbeError(
                f"candidate {candidate['id']!r} is outside object {obj.index}"
            )

    source_objects = [
        (obj.index, obj.base_address, image.object_bytes(obj.index)) for obj in image.objects
    ]
    hits = scan_u32_literals(source_objects, candidate_list, target_bases)
    by_candidate = []
    for candidate in candidate_list:
        candidate_hits = [hit for hit in hits if hit["candidate"] == candidate["id"]]
        by_candidate.append(
            {
                **candidate,
                "object_offset": candidate["address"] - target_bases[candidate["object"]],
                "literal_reference_count": len(candidate_hits),
                "literal_references": candidate_hits,
                "reusable": False,
                "reuse_evidence": "not established",
            }
        )

    producer = pathlib.Path(__file__).resolve()
    return {
        "schema": SCHEMA,
        "target": {
            "name": image.name,
            "sha256": image.sha256,
            "file_size": image.size,
        },
        "producer": {
            "path": "scripts/probe_a2_literal_references.py",
            "sha256": hashlib.sha256(producer.read_bytes()).hexdigest(),
        },
        "method": {
            "word": "little-endian u32",
            "alignment": "all byte offsets",
            "interpretations": ["linear-va", "target-object-relative"],
            "evidence_boundary": (
                "raw literal matches are investigation leads; absence of matches does not "
                "exclude relocations, computed/indirect references, runtime initialization, "
                "scratch use, sentinel semantics, or other consumers"
            ),
        },
        "candidates": by_candidate,
        "literal_reference_count": len(hits),
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
        image = le_image.load(args.target)
        result = build_probe(image, expected_sha256=CANONICAL_SHA256)
    except (LiteralReferenceProbeError, le_image.LEError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote A2 literal-reference probe to {args.output}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
