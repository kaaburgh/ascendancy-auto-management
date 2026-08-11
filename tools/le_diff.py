#!/usr/bin/env python3
"""Compare two LE code inventories at candidate-function level.

A raw byte diff of these images is close to useless: inserting code shifts
everything after it, so almost every byte appears "changed". This tool compares
the normalized per-function signatures produced by `le_disasm` instead. Those
signatures exclude absolute addresses, so a function that merely moved still
matches, and what is left over is the genuinely different code.

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


def compare(left: dict, right: dict) -> dict:
    """Match functions by normalized signature, multiset-style."""
    left_by_signature: dict[str, list[dict]] = collections.defaultdict(list)
    for function in left["functions"]:
        left_by_signature[function["signature"]].append(function)
    right_by_signature: dict[str, list[dict]] = collections.defaultdict(list)
    for function in right["functions"]:
        right_by_signature[function["signature"]].append(function)

    matched, moved = [], 0
    for signature, lefts in left_by_signature.items():
        rights = right_by_signature.get(signature, [])
        for a, b in zip(lefts, rights):
            if a["address"] != b["address"]:
                moved += 1
            matched.append(
                {
                    "signature": signature,
                    "left_address": a["address"],
                    "right_address": b["address"],
                    "instruction_count": a["instruction_count"],
                    "byte_length": a["byte_length"],
                    "moved": a["address"] != b["address"],
                }
            )

    def leftovers(primary: dict[str, list[dict]], other: dict[str, list[dict]]):
        out = []
        for signature, items in primary.items():
            keep = len(items) - min(len(items), len(other.get(signature, [])))
            if keep:
                out.extend(items[len(items) - keep :])
        return sorted(out, key=lambda f: (-f["byte_length"], f["address"]))

    only_left = leftovers(left_by_signature, right_by_signature)
    only_right = leftovers(right_by_signature, left_by_signature)

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
        "only_in_left": only_left,
        "only_in_right": only_right,
        "note": "Signatures exclude absolute addresses, so identical code that "
                "merely moved is reported as matched. Unmatched entries are "
                "candidates for RE1 to inspect, not established differences.",
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
        print(f"\ntop {args.top} unmatched in left ({report['left']['name']}), "
              f"largest first:")
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
