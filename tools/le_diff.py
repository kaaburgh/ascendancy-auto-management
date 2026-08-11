#!/usr/bin/env python3
"""Compare two LE code inventories at candidate-function level.

A raw byte diff of these images is close to useless: inserting code shifts
everything after it, so almost every byte appears "changed". This tool compares
the per-function signatures produced by `le_disasm` instead.

Matching is deliberately conservative and runs in three passes:

1. exact `signature` — all operands are preserved, so only identical instruction
   text matches;
2. `reference_signature` — in-image reference values are masked, yielding a
   `reference_only_differences` bucket rather than calling changed references
   identical;
3. `shape_signature` — every hex operand is masked, yielding the
   `constant_only_differences` bucket.

Everything left after those passes is structurally different. The two middle
buckets are intentionally unresolved classes: a changed in-image reference can
be benign relocation noise *or* a behavioral retarget, while a changed small
constant can be a DS-relative layout shift *or* a genuine threshold/flag change.
The tool reports those uncertainties instead of guessing them away.

The output is a *starting point for RE1*, not a finding. Candidate boundaries
come from a linear sweep and direct-call starts, so they are not verified
function boundaries and indirect-only callees can be folded into a preceding
span. Ranking by size/call count is a convenience, not evidence of relevance.
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import le_disasm  # noqa: E402
import le_image  # noqa: E402
from le_disasm import DisasmError  # noqa: E402
from le_image import LEError  # noqa: E402

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def validate_inventory(report: dict, source_name: str = "inventory") -> None:
    """Fail closed on serialized inventories from incompatible analysis models."""
    if report.get("schema") != le_disasm.INVENTORY_SCHEMA:
        raise DisasmError(
            f"{source_name} has unsupported inventory schema "
            f"{report.get('schema')!r}; expected {le_disasm.INVENTORY_SCHEMA!r}. "
            "Regenerate it with the current le_disasm.py instead of reusing a "
            "pre-correction or otherwise incompatible JSON artifact."
        )

    source = report.get("source")
    functions = report.get("functions")
    if not isinstance(source, dict) or not isinstance(functions, list):
        raise DisasmError(
            f"{source_name} is not a le_disasm inventory (source/functions missing)"
        )

    required_source = (
        "name",
        "sha256",
        "object",
        "object_sha256",
        "parser_layout",
        "page_offset_header_offset",
        "data_page_offset",
    )
    missing_source = [key for key in required_source if key not in source]
    if missing_source:
        raise DisasmError(
            f"{source_name} is missing source fingerprint fields: "
            f"{', '.join(missing_source)}"
        )
    if source["parser_layout"] != le_disasm.PARSER_LAYOUT_ID:
        raise DisasmError(
            f"{source_name} was produced with parser layout "
            f"{source['parser_layout']!r}; expected {le_disasm.PARSER_LAYOUT_ID!r}"
        )
    if source["page_offset_header_offset"] != le_image.H_DATAPAGE:
        raise DisasmError(
            f"{source_name} records page_off header offset "
            f"0x{source['page_offset_header_offset']:x}; current parser requires "
            f"0x{le_image.H_DATAPAGE:x}"
        )
    for key in ("sha256", "object_sha256"):
        value = source[key]
        if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
            raise DisasmError(
                f"{source_name} has invalid {key} fingerprint {value!r}"
            )

    required_function = (
        "address",
        "end",
        "instruction_count",
        "byte_length",
        "callers",
        "signature",
        "reference_signature",
        "shape_signature",
    )
    for index, function in enumerate(functions):
        if not isinstance(function, dict):
            raise DisasmError(f"{source_name} function {index} is not an object")
        missing = [key for key in required_function if key not in function]
        if missing:
            raise DisasmError(
                f"{source_name} function {index} is missing: {', '.join(missing)}"
            )


def load_inventory(path: pathlib.Path, objdump: str | None = None) -> dict:
    """Accept either a current le_disasm JSON inventory or an LE executable."""
    if path.suffix.lower() == ".json":
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DisasmError(f"cannot read inventory {path}: {exc}") from exc
        validate_inventory(report, str(path))
        return report

    report = le_disasm.analyse(path, None, objdump or le_disasm.find_objdump())
    validate_inventory(report, str(path))
    return report


def group(functions: list[dict], key: str) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = collections.defaultdict(list)
    for function in functions:
        grouped[function[key]].append(function)
    return grouped


def match_pass(
    lefts: list[dict], rights: list[dict], key: str
) -> tuple[list[tuple[dict, dict]], list[dict], list[dict]]:
    """Multiset-match two function lists on one signature key."""
    left_by = group(lefts, key)
    right_by = group(rights, key)

    pairs: list[tuple[dict, dict]] = []
    for signature, items in left_by.items():
        pairs.extend(zip(items, right_by.get(signature, [])))

    def leftovers(primary: dict[str, list[dict]], other: dict[str, list[dict]]):
        out = []
        for signature, items in primary.items():
            keep = len(items) - min(len(items), len(other.get(signature, [])))
            if keep:
                out.extend(items[len(items) - keep :])
        return out

    return pairs, leftovers(left_by, right_by), leftovers(right_by, left_by)


def _difference_entries(pairs: list[tuple[dict, dict]]) -> list[dict]:
    return sorted(
        (
            {
                "left_address": a["address"],
                "right_address": b["address"],
                "instruction_count": a["instruction_count"],
                "byte_length": a["byte_length"],
                "callers": a["callers"],
                "moved": a["address"] != b["address"],
            }
            for a, b in pairs
        ),
        key=lambda f: (-f["byte_length"], f["left_address"]),
    )


def compare(left: dict, right: dict) -> dict:
    """Match functions conservatively without hiding reference retargets.

    Exact matches are the only candidates labelled identical. Reference-only
    matches are emitted separately because an operand moving from one valid
    in-image target to another can be a real change in callee/global/table use.
    Shape-only matches are also separate because DS-relative relocations and
    genuine constant retuning are indistinguishable without fixup semantics.
    """
    validate_inventory(left, "left inventory")
    validate_inventory(right, "right inventory")

    functions_left = left["functions"]
    functions_right = right["functions"]

    exact_pairs, rest_left, rest_right = match_pass(
        functions_left, functions_right, "signature"
    )
    reference_pairs, rest_left, rest_right = match_pass(
        rest_left, rest_right, "reference_signature"
    )
    shape_pairs, only_left, only_right = match_pass(
        rest_left, rest_right, "shape_signature"
    )

    exact_moved = sum(1 for a, b in exact_pairs if a["address"] != b["address"])
    matched = [
        {
            "signature": a["signature"],
            "left_address": a["address"],
            "right_address": b["address"],
            "instruction_count": a["instruction_count"],
            "byte_length": a["byte_length"],
            "moved": a["address"] != b["address"],
        }
        for a, b in exact_pairs
    ]
    reference_only = _difference_entries(reference_pairs)
    constant_only = _difference_entries(shape_pairs)

    only_left = sorted(only_left, key=lambda f: (-f["byte_length"], f["address"]))
    only_right = sorted(only_right, key=lambda f: (-f["byte_length"], f["address"]))

    def coverage(report: dict, unmatched: list[dict]) -> dict:
        total_bytes = sum(f["byte_length"] for f in report["functions"])
        unmatched_bytes = sum(f["byte_length"] for f in unmatched)
        return {
            "function_count": len(report["functions"]),
            "unmatched_function_count": len(unmatched),
            "attributed_bytes": total_bytes,
            "unmatched_bytes": unmatched_bytes,
            "matched_byte_fraction": (
                round(1 - unmatched_bytes / total_bytes, 6) if total_bytes else None
            ),
        }

    source_keys = ("name", "sha256", "object", "object_sha256", "parser_layout")
    return {
        "schema": "ascendancy.le-diff.report/v2",
        "left": {
            **{k: left["source"][k] for k in source_keys},
            **coverage(left, only_left),
        },
        "right": {
            **{k: right["source"][k] for k in source_keys},
            **coverage(right, only_right),
        },
        "matched_function_count": len(matched),
        "moved_but_identical_count": exact_moved,
        "reference_only_difference_count": len(reference_only),
        "reference_only_differences": reference_only,
        "constant_only_difference_count": len(constant_only),
        "constant_only_differences": constant_only,
        "only_in_left": only_left,
        "only_in_right": only_right,
        "note": (
            "Four classes. Matched: exact normalized instruction text, operands "
            "included. reference_only_differences: same text after masking only "
            "in-image references; this mixes benign relocation with possible "
            "callee/global/table retargets and is never called identical. "
            "constant_only_differences: same shape after masking all hex operands; "
            "this mixes DS-relative layout movement with possible threshold/flag "
            "changes. only_in_left/right: structurally different. All difference "
            "classes are candidates for RE1, not established behavioral changes."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "left", type=pathlib.Path,
        help="LE executable or current le_disasm JSON (e.g. the Antagonizer)",
    )
    parser.add_argument(
        "right", type=pathlib.Path,
        help="LE executable or current le_disasm JSON (e.g. the baseline)",
    )
    parser.add_argument("--objdump", default=None)
    parser.add_argument("-o", "--output", type=pathlib.Path, default=None)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument(
        "--top", type=int, default=10,
        help="how many structurally unmatched functions to show (default: 10)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        left = load_inventory(args.left, args.objdump)
        right = load_inventory(args.right, args.objdump)
        report = compare(left, right)
    except (LEError, DisasmError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.summary:
        for side in ("left", "right"):
            info = report[side]
            print(
                f"{side:5s} {info['name']} object {info['object']}: "
                f"{info['function_count']} candidate functions, "
                f"{info['unmatched_function_count']} structurally unmatched "
                f"({info['unmatched_bytes']} bytes)"
            )
        print(
            f"exact matches: {report['matched_function_count']} "
            f"({report['moved_but_identical_count']} moved with exact operands)"
        )
        print(
            f"reference-only differences: "
            f"{report['reference_only_difference_count']} "
            f"(in-image operands changed; relocation and retargets are mixed)"
        )
        print(
            f"constant-only differences: "
            f"{report['constant_only_difference_count']} "
            f"(same shape; DS-relative relocations mixed with real constants)"
        )
        print(
            f"\ntop {args.top} structurally different in left "
            f"({report['left']['name']}), largest first:"
        )
        for function in report["only_in_left"][: args.top]:
            print(
                f"  0x{function['address']:08x}  {function['byte_length']:6d} bytes  "
                f"{function['instruction_count']:5d} insns  "
                f"{function['callers']:3d} callers"
            )
        return 0

    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
