#!/usr/bin/env python3
"""Reproduce the bounded T1 Antagonizer/bug-patch lineage measurements.

This is intentionally not a general LE/static-RE pipeline. It verifies the exact
four CF1 candidate hashes, parses only the LE header/object-table fields needed
for T1, and reproduces the unique printable-ASCII string displacement evidence
used to select the canonical comparison baseline.

Reproduce from a normal CF1 fetch:

    python3 tools/t1_lineage_probe.py \
      binaries/ANTAG_EN.EXE binaries/ANTAG_INTL.EXE \
      binaries/PATCH_EN.EXE binaries/PATCH_INTL.EXE \
      --output artifacts/t1-lineage-probe.json

The reviewed expected output for the four pinned inputs is committed as
``docs/re/t1-lineage-probe.expected.json``.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import re
import struct
import sys
from typing import Any

TOOL_NAME = "t1_lineage_probe.py"
TOOL_VERSION = "1.0.0"
ASCII_MIN_LEN = 8
ASCII_RUN_RE = re.compile(rb"[ -~]{8,}")

EXPECTED = {
    "antagonizer-en": {
        "filename": "ANTAG_EN.EXE",
        "size": 610863,
        "sha256": "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00",
    },
    "antagonizer-intl": {
        "filename": "ANTAG_INTL.EXE",
        "size": 610863,
        "sha256": "9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c",
    },
    "bugpatch-en": {
        "filename": "PATCH_EN.EXE",
        "size": 587451,
        "sha256": "7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b",
    },
    "bugpatch-intl": {
        "filename": "PATCH_INTL.EXE",
        "size": 587451,
        "sha256": "16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b",
    },
}


class ProbeError(Exception):
    """Input bytes do not satisfy the narrow T1 probe contract."""


def u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise ProbeError(f"u16 read outside file at 0x{offset:x}")
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ProbeError(f"u32 read outside file at 0x{offset:x}")
    return struct.unpack_from("<I", data, offset)[0]


def verify_identity(path: pathlib.Path, target_id: str) -> bytes:
    expected = EXPECTED[target_id]
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ProbeError(f"cannot read {target_id} from {path}: {exc}") from exc
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != expected["size"] or digest != expected["sha256"]:
        raise ProbeError(
            f"{target_id} identity mismatch: got size={len(data)} sha256={digest}; "
            f"expected size={expected['size']} sha256={expected['sha256']}"
        )
    return data


def parse_layout(data: bytes) -> dict[str, Any]:
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ProbeError("missing/truncated DOS MZ header")
    le_offset = u32(data, 0x3C)
    if le_offset + 0x84 > len(data) or data[le_offset : le_offset + 2] != b"LE":
        raise ProbeError(f"missing/truncated LE header at 0x{le_offset:x}")
    if data[le_offset + 2] != 0 or data[le_offset + 3] != 0:
        raise ProbeError("unsupported LE byte/word ordering")

    object_table_rel = u32(data, le_offset + 0x40)
    object_count = u32(data, le_offset + 0x44)
    if object_count != 2:
        raise ProbeError(f"T1 expects exactly 2 LE objects, got {object_count}")
    table = le_offset + object_table_rel
    if table < le_offset or table + object_count * 24 > len(data):
        raise ProbeError("LE object table lies outside the file")

    objects: list[dict[str, int]] = []
    for index in range(object_count):
        off = table + index * 24
        virtual_size, relocation_base, flags, page_map_index, page_count, reserved = (
            struct.unpack_from("<6I", data, off)
        )
        objects.append(
            {
                "index": index + 1,
                "virtual_size": virtual_size,
                "relocation_base": relocation_base,
                "flags": flags,
                "page_map_index": page_map_index,
                "page_count": page_count,
                "reserved": reserved,
            }
        )

    return {
        "le_offset": le_offset,
        "module_pages": u32(data, le_offset + 0x14),
        "entry_object": u32(data, le_offset + 0x18),
        "entry_offset": u32(data, le_offset + 0x1C),
        "stack_object": u32(data, le_offset + 0x20),
        "stack_offset": u32(data, le_offset + 0x24),
        "object_table_offset": object_table_rel,
        "object_count": object_count,
        "objects": objects,
    }


def unique_ascii_offsets(data: bytes) -> dict[bytes, int]:
    """Map exact printable-ASCII runs (len >= 8) occurring once to file offsets."""
    runs = [(match.group(0), match.start()) for match in ASCII_RUN_RE.finditer(data)]
    counts = collections.Counter(value for value, _ in runs)
    return {value: offset for value, offset in runs if counts[value] == 1}


def displacement_evidence(antag: bytes, patch: bytes) -> dict[str, Any]:
    antag_offsets = unique_ascii_offsets(antag)
    patch_offsets = unique_ascii_offsets(patch)
    common = set(antag_offsets) & set(patch_offsets)
    histogram = collections.Counter(
        antag_offsets[value] - patch_offsets[value] for value in common
    )
    ordered_histogram = dict(sorted(histogram.items()))
    canonical = json.dumps(
        ordered_histogram, sort_keys=True, separators=(",", ":")
    ).encode("ascii")
    return {
        "common_unique_ascii_strings": len(common),
        "common_string_sha256": hashlib.sha256(b"\0".join(sorted(common))).hexdigest(),
        "histogram": [
            {"delta": delta, "count": count}
            for delta, count in ordered_histogram.items()
        ],
        "histogram_canonical_json_sha256": hashlib.sha256(canonical).hexdigest(),
        "_common": common,
    }


def delta(left: dict[str, Any], right: dict[str, Any]) -> dict[str, int]:
    """Return left - right for the T1 layout fields."""
    return {
        "module_pages": left["module_pages"] - right["module_pages"],
        "entry_offset": left["entry_offset"] - right["entry_offset"],
        "stack_offset": left["stack_offset"] - right["stack_offset"],
        "executable_virtual_size": (
            left["objects"][0]["virtual_size"] - right["objects"][0]["virtual_size"]
        ),
        "executable_pages": (
            left["objects"][0]["page_count"] - right["objects"][0]["page_count"]
        ),
        "writable_virtual_size": (
            left["objects"][1]["virtual_size"] - right["objects"][1]["virtual_size"]
        ),
        "writable_pages": (
            left["objects"][1]["page_count"] - right["objects"][1]["page_count"]
        ),
    }


def build_report(files: dict[str, bytes]) -> dict[str, Any]:
    layouts = {target_id: parse_layout(data) for target_id, data in files.items()}

    stub_hashes = {
        hashlib.sha256(data[: layouts[target_id]["le_offset"]]).hexdigest()
        for target_id, data in files.items()
    }
    if len(stub_hashes) != 1:
        raise ProbeError("candidate MZ regions are not byte-identical")

    en = displacement_evidence(files["antagonizer-en"], files["bugpatch-en"])
    intl = displacement_evidence(
        files["antagonizer-intl"], files["bugpatch-intl"]
    )
    common_sets_equal = en.pop("_common") == intl.pop("_common")
    histograms_equal = en["histogram"] == intl["histogram"]

    locale_antag = delta(layouts["antagonizer-intl"], layouts["antagonizer-en"])
    locale_patch = delta(layouts["bugpatch-intl"], layouts["bugpatch-en"])
    antag_vs_patch_en = delta(layouts["antagonizer-en"], layouts["bugpatch-en"])
    antag_vs_patch_intl = delta(
        layouts["antagonizer-intl"], layouts["bugpatch-intl"]
    )

    return {
        "schema": 1,
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "input_contract": {
            target_id: {
                "size": EXPECTED[target_id]["size"],
                "sha256": EXPECTED[target_id]["sha256"],
            }
            for target_id in EXPECTED
        },
        "ascii_rule": {
            "bytes": "0x20..0x7e inclusive",
            "minimum_run_length": ASCII_MIN_LEN,
            "uniqueness": "exact extracted run occurs exactly once within each file",
            "comparison": "intersection by exact run bytes; delta = Antagonizer file offset - bug-patch file offset",
        },
        "shared_mz_stub_sha256": next(iter(stub_hashes)),
        "layouts": layouts,
        "layout_deltas": {
            "intl_minus_en_antagonizer": locale_antag,
            "intl_minus_en_bugpatch": locale_patch,
            "antagonizer_minus_bugpatch_en": antag_vs_patch_en,
            "antagonizer_minus_bugpatch_intl": antag_vs_patch_intl,
            "locale_delta_equal": locale_antag == locale_patch,
            "antagonizer_delta_equal_across_locales": (
                antag_vs_patch_en == antag_vs_patch_intl
            ),
        },
        "string_displacements": {
            "english": en,
            "international": intl,
            "common_string_sets_equal": common_sets_equal,
            "histograms_equal": histograms_equal,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("antagonizer_en", type=pathlib.Path)
    parser.add_argument("antagonizer_intl", type=pathlib.Path)
    parser.add_argument("bugpatch_en", type=pathlib.Path)
    parser.add_argument("bugpatch_intl", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inputs = {
        "antagonizer-en": args.antagonizer_en,
        "antagonizer-intl": args.antagonizer_intl,
        "bugpatch-en": args.bugpatch_en,
        "bugpatch-intl": args.bugpatch_intl,
    }
    try:
        files = {
            target_id: verify_identity(path, target_id)
            for target_id, path in inputs.items()
        }
        report = build_report(files)
    except ProbeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        try:
            args.output.write_text(payload, encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write {args.output}: {exc}", file=sys.stderr)
            return 2
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
