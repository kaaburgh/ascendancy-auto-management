#!/usr/bin/env python3
"""Compare two LE code inventories at candidate-function level.

A raw byte diff of these images is close to useless: inserting code shifts
everything after it, so almost every byte appears "changed". This tool compares
the normalized per-function signatures produced by `le_disasm` instead. Those
signatures exclude in-image addresses, so a function that merely moved still
matches.

Results land in three buckets. Matched code is identical once addresses are
masked. `constant_only_differences` share an instruction shape but differ in
constants: this build reaches data through DS-relative offsets that relocate
with the data layout, and no value-based rule tells those apart from a genuine
threshold change, so they are reported as their own class instead of guessed at.
Everything else is structurally different.

The output is a *starting point for RE1*, not a finding. Unmatched functions are
candidates for inspection, and the reasons a candidate can be spurious are real:
the inventory comes from a linear sweep, boundaries are inferred from call
targets, and a compiler or build difference unrelated to behavior will also
change a signature. Ranking here is by size and call count, which is a
convenience, not evidence of relevance.
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import le_disasm  # noqa: E402
import le_image  # noqa: E402
from le_disasm import DisasmError  # noqa: E402
from le_image import LEError  # noqa: E402


def load_inventory(path: pathlib.Path, objdump: str | None = None) -> dict:
    """Accept either a le_disasm JSON inventory or an LE executable."""
    if path.suffix.lower() == ".json":
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DisasmError(f"cannot read inventory {path}: {exc}") from exc
        for key in ("source", "functions"):
            if key not in report:
                raise DisasmError(f"{path} is not a le_disasm inventory (no {key!r})")
        return report
    return le_disasm.analyse(path, None, objdump or le_disasm.find_objdump())


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


def compare(left: dict, right: dict) -> dict:
    """Match functions in two passes, separating relocation noise from changes.

    Pass 1 matches on the strict signature, where only values inside the image's
    object ranges are masked. Pass 2 matches the leftovers on the shape
    signature, where every constant is masked.

    The second pass exists because this build reaches data through DS-relative
    offsets (`mov ebx,0x59d8`) that are far too small to look like addresses.
    They are relocations that shift with the data layout, yet by value they are
    indistinguishable from a genuine threshold. Collapsing them into "matched"
    would hide real constant changes; calling them "changed" would bury the
    signal under hundreds of relocations. So they get their own bucket.
    """
    functions_left = left["functions"]
    functions_right = right["functions"]

    strict_pairs, rest_left, rest_right = match_pass(
        functions_left, functions_right, "signature"
    )
    shape_pairs, only_left, only_right = match_pass(
        rest_left, rest_right, "shape_signature"
    )

    moved = sum(1 for a, b in strict_pairs if a["address"] != b["address"])
    matched = [
        {
            "signature": a["signature"],
            "left_address": a["address"],
            "right_address": b["address"],
            "instruction_count": a["instruction_count"],
            "byte_length": a["byte_length"],
            "moved": a["address"] != b["address"],
        }
        for a, b in strict_pairs
    ]
    constant_only = sorted(
        (
            {
                "left_address": a["address"],
                "right_address": b["address"],
                "instruction_count": a["instruction_count"],
                "byte_length": a["byte_length"],
                "callers": a["callers"],
            }
            for a, b in shape_pairs
        ),
        key=lambda f: (-f["byte_length"], f["left_address"]),
    )

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

    return {
        "left": {**{k: left["source"][k] for k in ("name", "sha256", "object")},
                 **coverage(left, only_left)},
        "right": {**{k: right["source"][k] for k in ("name", "sha256", "object")},
                  **coverage(right, only_right)},
        "matched_function_count": len(matched),
        "moved_but_identical_count": moved,
        "constant_only_difference_count": len(constant_only),
        "constant_only_differences": constant_only,
        "only_in_left": only_left,
        "only_in_right": only_right,
        "note": "Three buckets. Matched: identical instruction text once "
                "in-image addresses are masked, so relocated code still "
                "matches. constant_only_differences: same instruction shape, "
                "differing constants — a mix of DS-relative data relocations "
                "and any genuine threshold/flag change, which this tool cannot "
                "separate by value alone. only_in_left/right: structurally "
                "different. All three are candidates for RE1 to inspect, not "
                "established differences.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("left", type=pathlib.Path,
                        help="LE executable or le_disasm JSON (e.g. the Antagonizer)")
    parser.add_argument("right", type=pathlib.Path,
                        help="LE executable or le_disasm JSON (e.g. the baseline)")
    parser.add_argument("--objdump", default=None)
    parser.add_argument("-o", "--output", type=pathlib.Path, default=None)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument(
        "--top", type=int, default=10,
        help="how many unmatched functions to show in the summary (default: 10)",
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
            print(f"{side:5s} {info['name']} object {info['object']}: "
                  f"{info['function_count']} candidate functions, "
                  f"{info['unmatched_function_count']} unmatched "
                  f"({info['unmatched_bytes']} bytes)")
        print(f"matched: {report['matched_function_count']} "
              f"({report['moved_but_identical_count']} identical but relocated)")
        print(f"constant-only differences: "
              f"{report['constant_only_difference_count']} "
              f"(same shape, differing constants: data relocations mixed with "
              f"any real threshold change)")
        print(f"\ntop {args.top} structurally different in left "
              f"({report['left']['name']}), largest first:")
        for function in report["only_in_left"][: args.top]:
            print(f"  0x{function['address']:08x}  {function['byte_length']:6d} bytes  "
                  f"{function['instruction_count']:5d} insns  "
                  f"{function['callers']:3d} callers")
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
