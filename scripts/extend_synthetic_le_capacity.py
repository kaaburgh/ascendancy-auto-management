#!/usr/bin/env python3
"""Prepare a target-neutral LE mapped-capacity growth control.

This is deliberately a synthetic-control transformer, not a production patcher.
It appends one physical page, inserts one logical page-map entry after a chosen
mapped object, and grows that object's virtual size just enough to expose the
supplied payload. The input must use the narrow LE subset already supported by
``tools/le_image.py`` and must have no loader/fixup/trailing structures that
would need relocation.

The canonical Ascendancy target is explicitly refused: A2 Stage 2 is capability
evidence only until independent readers and runtime execution validate the
control and a later exact-target experiment is separately approved.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct
import sys

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import le_image  # noqa: E402

CANONICAL_TARGET_SHA256 = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"


class GrowthError(RuntimeError):
    pass


def _page_entry(number: int) -> bytes:
    if not 1 <= number <= 0xFFFFFF:
        raise GrowthError(f"page number {number} cannot be encoded in an LE page-map entry")
    return bytes(((number >> 16) & 0xFF, (number >> 8) & 0xFF, number & 0xFF, 0))


def _require_control_subset(image: le_image.LEImage) -> None:
    if image.sha256 == CANONICAL_TARGET_SHA256:
        raise GrowthError("refusing the canonical Ascendancy target; this transformer is synthetic-control-only")
    if image.page_numbers != list(range(1, image.page_count + 1)):
        raise GrowthError("control requires sequential physical page numbering before growth")
    if image.last_page_size != image.page_size:
        raise GrowthError("control requires a full final physical page before appending another page")
    if image.page_data_end != image.size or image.trailing_size != 0:
        raise GrowthError("control requires enumerated page data to end exactly at EOF with no trailing structures")
    unsupported = {
        "fixup_size": image.fixup_size,
        "loader_size": image.loader_size,
        "iterated_map_offset": image.iterated_map_offset,
        "import_module_offset": image.import_module_offset,
        "import_procedure_offset": image.import_procedure_offset,
        "nonresident_size": image.nonresident_size,
        "debug_size": image.debug_size,
    }
    present = {name: value for name, value in unsupported.items() if value}
    if present:
        rendered = ", ".join(f"{name}={value}" for name, value in sorted(present.items()))
        raise GrowthError(f"control does not rewrite loader/fixup/auxiliary structures: {rendered}")
    if image.page_map_file_end + le_image.PAGE_MAP_ENTRY_SIZE > image.data_page_offset:
        raise GrowthError("page map has no room for one additional entry before enumerated page data")
    slack = image._data[image.page_map_file_end : image.data_page_offset]
    if any(slack):
        raise GrowthError("bytes between the page map and enumerated page data are not all zero; refusing to overwrite them")


def grow_mapped_object(data: bytes, object_index: int, payload: bytes) -> bytes:
    """Return a transformed synthetic LE image with one appended mapped page."""
    if not payload:
        raise GrowthError("payload must be non-empty")

    try:
        before = le_image.LEImage(data, name="synthetic-control-input")
    except le_image.LEError as exc:
        raise GrowthError(str(exc)) from exc
    _require_control_subset(before)

    if not 1 <= object_index <= before.object_count:
        raise GrowthError(f"object {object_index} is outside 1..{before.object_count}")
    if len(payload) > before.page_size:
        raise GrowthError(f"payload is {len(payload)} bytes; one control page holds at most {before.page_size}")

    target = before.objects[object_index - 1]
    if target.page_count <= 0:
        raise GrowthError("target object has no mapped pages")
    mapped_capacity = target.page_count * before.page_size
    if target.virtual_size > mapped_capacity:
        raise GrowthError("target object virtual size already exceeds its mapped-page capacity")

    logical_insert = target.first_page - 1 + target.page_count
    old_page_map_start = before.lfanew + before.page_map_offset
    old_page_map = data[old_page_map_start : before.page_map_file_end]
    new_physical_page = before.page_count + 1
    new_page_map = (
        old_page_map[: logical_insert * le_image.PAGE_MAP_ENTRY_SIZE]
        + _page_entry(new_physical_page)
        + old_page_map[logical_insert * le_image.PAGE_MAP_ENTRY_SIZE :]
    )

    output = bytearray(data)
    output[old_page_map_start : old_page_map_start + len(new_page_map)] = new_page_map

    header = before.lfanew
    struct.pack_into("<I", output, header + le_image.H_MPAGES, before.page_count + 1)
    struct.pack_into("<I", output, header + le_image.H_LASTPAGESIZE, before.page_size)

    object_table_start = before.lfanew + before.object_table_offset
    target_entry = object_table_start + (object_index - 1) * le_image.OBJECT_ENTRY_SIZE
    new_virtual_size = target.page_count * before.page_size + len(payload)
    struct.pack_into("<I", output, target_entry + 0, new_virtual_size)
    struct.pack_into("<I", output, target_entry + 16, target.page_count + 1)

    target_last_logical = target.first_page + target.page_count - 1
    for obj in before.objects:
        if obj.index == object_index or obj.first_page <= target_last_logical:
            continue
        entry = object_table_start + (obj.index - 1) * le_image.OBJECT_ENTRY_SIZE
        struct.pack_into("<I", output, entry + 12, obj.first_page + 1)

    output.extend(payload)
    output.extend(b"\x00" * (before.page_size - len(payload)))
    transformed = bytes(output)

    try:
        after = le_image.LEImage(transformed, name="synthetic-control-output")
    except le_image.LEError as exc:
        raise GrowthError(f"transformed image does not satisfy the repository LE parser: {exc}") from exc

    if after.page_count != before.page_count + 1:
        raise GrowthError("internal verification failed: page count did not increase by one")
    grown = after.objects[object_index - 1]
    if grown.page_count != target.page_count + 1:
        raise GrowthError("internal verification failed: target object page count did not increase by one")
    exposed = after.object_bytes(object_index)[target.page_count * before.page_size :]
    if exposed[: len(payload)] != payload:
        raise GrowthError("internal verification failed: appended payload is not mapped at the expected object offset")
    for obj in before.objects:
        if obj.index == object_index:
            old_prefix = before.object_bytes(obj.index)
            if after.object_bytes(obj.index)[: len(old_prefix)] != old_prefix:
                raise GrowthError("internal verification failed: target object's existing bytes changed")
        elif after.object_bytes(obj.index) != before.object_bytes(obj.index):
            raise GrowthError(f"internal verification failed: object {obj.index} bytes changed")
    return transformed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--object", type=int, required=True, dest="object_index")
    parser.add_argument("--payload-hex", required=True, help="Non-empty payload bytes encoded as hexadecimal")
    args = parser.parse_args(argv)

    try:
        if args.input.resolve() == args.output.resolve():
            raise GrowthError("output must not alias the immutable input fixture")
        if args.output.exists():
            raise GrowthError(f"output already exists: {args.output}")
        try:
            payload = bytes.fromhex(args.payload_hex)
        except ValueError as exc:
            raise GrowthError(f"payload hex is invalid: {exc}") from exc
        transformed = grow_mapped_object(args.input.read_bytes(), args.object_index, payload)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(transformed)
    except (GrowthError, OSError) as exc:
        print(f"a2-le-growth-control: FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(
        "a2-le-growth-control: PASS "
        f"input_sha256={hashlib.sha256(args.input.read_bytes()).hexdigest()} "
        f"output_sha256={hashlib.sha256(transformed).hexdigest()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
