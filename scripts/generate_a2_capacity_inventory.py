#!/usr/bin/env python3
"""Generate a fail-closed A2 mapped-capacity inventory for an LE target.

This is an investigation tool, not a cave finder.  Zero/padding runs are emitted
only as candidate capacity; lack of a direct linear-sweep control-flow reference
must never be interpreted as proof that a range is semantically unused.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Iterable

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import le_disasm  # noqa: E402
import le_image  # noqa: E402

SCHEMA = "ascendancy.a2-capacity-inventory/v1"
CANONICAL_SHA256 = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
DEFAULT_MIN_ZERO_RUN = 16

KNOWN_SEAMS = (
    {
        "id": "planet-window-handler",
        "address": 0x37568,
        "provenance": "docs/re/auto-management-ui-state.md",
    },
    {
        "id": "managed-mirror-write",
        "address": 0x3791F,
        "provenance": "docs/re/auto-management-ui-state.md",
    },
    {
        "id": "managed-render-check",
        "address": 0x3AFCA,
        "provenance": "docs/re/auto-management-ui-state.md",
    },
    {
        "id": "player-automation-gate",
        "address": 0x3B5B8,
        "provenance": "docs/re/auto-management-turn-path.md",
    },
    {
        "id": "automation-policy-candidate",
        "address": 0x3D8F0,
        "provenance": "docs/re/auto-management-turn-path.md",
    },
)


class CapacityInventoryError(Exception):
    """The requested inventory cannot be produced without weakening evidence."""


def find_zero_runs(data: bytes, minimum: int) -> list[tuple[int, int]]:
    if minimum <= 0:
        raise ValueError("minimum zero-run length must be positive")
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(data):
        if value == 0:
            if start is None:
                start = index
            continue
        if start is not None and index - start >= minimum:
            runs.append((start, index - start))
        start = None
    if start is not None and len(data) - start >= minimum:
        runs.append((start, len(data) - start))
    return runs


def direct_control_flow_references(
    instructions: Iterable[tuple[int, int, str]],
) -> list[dict]:
    references: list[dict] = []
    for address, _length, text in instructions:
        target: int | None = None
        kind: str | None = None
        call = le_disasm.CALL_RE.match(text)
        if call:
            target = int(call.group(1), 16)
            kind = "call"
        else:
            branch = le_disasm.BRANCH_RE.match(text)
            if branch:
                target = int(branch.group(1), 16)
                kind = "branch"
        if target is not None:
            references.append({"site": address, "target": target, "kind": kind})
    return references


def _file_spans(
    image: le_image.LEImage, start_address: int, length: int
) -> list[dict]:
    """Describe file-backed chunks without assuming LE pages are contiguous."""
    end_address = start_address + length
    spans: list[dict] = []
    cursor = start_address
    while cursor < end_address:
        obj = image.object_containing(cursor)
        if obj is None:
            break
        delta = cursor - obj.base_address
        page_index = delta // image.page_size
        if page_index >= obj.page_count:
            break
        page_number = image.page_numbers[obj.first_page - 1 + page_index]
        offset_in_page = delta % image.page_size
        page_length = image.page_length(page_number)
        if offset_in_page >= page_length:
            break
        chunk = min(end_address - cursor, page_length - offset_in_page)
        file_offset = image.page_file_offset(page_number) + offset_in_page
        spans.append(
            {
                "address": cursor,
                "file_offset": file_offset,
                "size": chunk,
            }
        )
        cursor += chunk
    return spans


def build_inventory(
    image: le_image.LEImage,
    *,
    expected_sha256: str,
    minimum_zero_run: int = DEFAULT_MIN_ZERO_RUN,
    objdump: str | None = None,
) -> dict:
    if image.sha256 != expected_sha256:
        raise CapacityInventoryError(
            f"target SHA-256 mismatch: expected {expected_sha256}, found {image.sha256}"
        )

    objdump_path = le_disasm.find_objdump(objdump)
    object_records: list[dict] = []
    candidates: list[dict] = []
    all_references: list[dict] = []

    for obj in image.objects:
        object_records.append(
            {
                "index": obj.index,
                "kind": obj.kind,
                "base_address": obj.base_address,
                "end_address": obj.end_address,
                "virtual_size": obj.virtual_size,
                "flags": obj.flags,
                "flag_names": obj.names,
                "first_page": obj.first_page,
                "page_count": obj.page_count,
            }
        )
        data = image.object_bytes(obj.index)
        references: list[dict] = []
        if obj.flags & 0x0004:
            instructions = le_disasm.disassemble(
                data, obj.base_address, objdump_path, arch="i386"
            )
            references = direct_control_flow_references(instructions)
            all_references.extend(references)

        for offset, size in find_zero_runs(data, minimum_zero_run):
            address = obj.base_address + offset
            file_spans = _file_spans(image, address, size)
            file_backed_size = sum(span["size"] for span in file_spans)
            incoming = [
                reference
                for reference in references
                if address <= reference["target"] < address + size
            ]
            candidates.append(
                {
                    "object": obj.index,
                    "object_kind": obj.kind,
                    "address": address,
                    "object_offset": offset,
                    "size": size,
                    "file_backed_size": file_backed_size,
                    "fully_file_backed": file_backed_size == size,
                    "file_spans": file_spans,
                    "incoming_direct_control_flow": incoming,
                    "classification": "candidate-zero-capacity-only",
                    "reusable": False,
                    "reuse_evidence": "not established",
                }
            )

    seams: list[dict] = []
    for seam in KNOWN_SEAMS:
        obj = image.object_containing(seam["address"])
        if obj is None:
            raise CapacityInventoryError(
                f"known seam {seam['id']} at 0x{seam['address']:x} is outside mapped objects"
            )
        record = dict(seam)
        record["object"] = obj.index
        record["object_offset"] = seam["address"] - obj.base_address
        record["file_offset"] = image.va_to_file_offset(seam["address"])
        seams.append(record)

    producer_path = pathlib.Path(__file__).resolve()
    producer_sha256 = hashlib.sha256(producer_path.read_bytes()).hexdigest()
    return {
        "schema": SCHEMA,
        "target": {
            "name": image.name,
            "sha256": image.sha256,
            "file_size": image.size,
        },
        "producer": {
            "path": "scripts/generate_a2_capacity_inventory.py",
            "sha256": producer_sha256,
            "le_parser_layout": le_disasm.PARSER_LAYOUT_ID,
            "disassembler": le_disasm.objdump_version(objdump_path),
        },
        "method": {
            "minimum_zero_run": minimum_zero_run,
            "control_flow_model": "GNU objdump i386 linear sweep; direct call/branch targets only",
            "capacity_semantics": (
                "zero/padding runs are investigation candidates only; absence of a direct "
                "reference is not evidence that bytes are semantically unused"
            ),
        },
        "objects": object_records,
        "known_seams": seams,
        "candidate_zero_regions": candidates,
        "direct_control_flow_reference_count": len(all_references),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--minimum-zero-run", type=int, default=DEFAULT_MIN_ZERO_RUN)
    parser.add_argument("--expected-sha256", default=CANONICAL_SHA256)
    parser.add_argument("--objdump")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        image = le_image.load(args.target)
        inventory = build_inventory(
            image,
            expected_sha256=args.expected_sha256,
            minimum_zero_run=args.minimum_zero_run,
            objdump=args.objdump,
        )
    except (CapacityInventoryError, le_image.LEError, le_disasm.DisasmError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(inventory, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(
            f"wrote A2 capacity inventory for {inventory['target']['sha256']} to {args.output}"
        )
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
