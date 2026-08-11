#!/usr/bin/env python3
"""Disassemble an LE object headlessly and derive a reviewable code inventory.

`objdump` cannot read the LE container, but it can disassemble a flat byte
range at a chosen virtual address. This tool bridges the two: it rebuilds an
object with `le_image`, hands the bytes to `objdump -b binary`, and turns the
listing into small derived artifacts rather than a bulk disassembly dump.

What it emits is deliberately a *derived representation*: candidate function
starts, a call graph, and two normalized signatures per candidate function. That
keeps committed artifacts small and avoids republishing the game's code, while
still giving later tasks something to match and diff against.

The two signatures are the point of the design. `signature` masks only values
inside the image's own object ranges, so it preserves constants; the
`shape_signature` masks every constant. Comparing both lets `le_diff` separate
structural change from "same code, different constants" without having to guess
which small values are data relocations.

Two limits to keep in mind when reading the output:

- This is a **linear sweep**. Data embedded in the code object disassembles as
  nonsense instructions, and a misaligned start can desynchronise a stretch of
  output. Instruction counts are therefore upper bounds, not truth.
- "Functions" are **candidates** derived from direct call targets plus the entry
  point. They are not verified boundaries. Treat them as leads to confirm, and
  do not name one after a behavior without separate evidence.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import le_image  # noqa: E402
from le_image import LEError  # noqa: E402

OBJDUMP_ENV = {"LC_ALL": "C"}

# "   783c1:\t66 26 8b 03          \tmov    ax,WORD PTR es:[ebx]"
LINE_RE = re.compile(r"^\s*([0-9a-f]+):\t((?:[0-9a-f]{2} )+)\s*\t(.*)$")
HEX_RE = re.compile(r"0x[0-9a-f]+")
CALL_RE = re.compile(r"^call\s+0x([0-9a-f]+)$")
BRANCH_RE = re.compile(r"^(?:j\w+|loop\w*)\s+0x([0-9a-f]+)$")


class DisasmError(Exception):
    """Disassembly could not be produced or parsed."""


def find_objdump(explicit: str | None = None) -> str:
    candidates = [explicit] if explicit else ["objdump", "i386-elf-objdump", "gobjdump"]
    for name in candidates:
        if name and shutil.which(name):
            return name
    raise DisasmError(
        "no objdump found on PATH. Install GNU binutils, or pass --objdump. "
        "A clean cloud image normally already has it."
    )


def objdump_version(objdump: str) -> str:
    result = subprocess.run(
        [objdump, "--version"], capture_output=True, text=True, check=False
    )
    return result.stdout.splitlines()[0].strip() if result.stdout else "unknown"


def normalize(text: str, address_ranges: tuple[tuple[int, int], ...] = ()) -> str:
    """Mask relocated addresses while preserving semantic constants.

    Only hex values that land inside one of the image's own object ranges are
    masked. Everything else survives verbatim, which matters: masking *every*
    hex operand would give `cmp eax,0x1` and `cmp eax,0x2` the same signature,
    so a change consisting only of a threshold, size, bias or flag would be
    reported as "identical" and dropped from the candidate list — hiding
    precisely the kind of difference this project is looking for.

    A constant that happens to fall inside an image range is still masked, and
    a value inside one image's range but not the other's normalizes differently
    between them. Both residual cases push toward reporting a *mismatch*, which
    costs a candidate to inspect rather than concealing a real change.

    With no ranges supplied nothing is masked, so callers must pass the ranges
    to get relocation tolerance.
    """
    collapsed = " ".join(text.split())
    if not address_ranges:
        return collapsed

    def mask(match: re.Match[str]) -> str:
        value = int(match.group(0), 16)
        for low, high in address_ranges:
            if low <= value < high:
                return "ADDR"
        return match.group(0)

    return HEX_RE.sub(mask, collapsed)


def normalize_shape(text: str) -> str:
    """Mask every hex value, keeping only the instruction's shape.

    Deliberately lossy, and never used alone. Paired with `normalize` it lets
    the diff separate "structurally different" from "same code, different
    constants" — which matters because this build references data through
    DS-relative offsets far too small to look like addresses (`mov ebx,0x59d8`,
    `cmp DWORD PTR ds:0x9d90,0x0`). Those are relocations that move when the
    data layout moves, and they are indistinguishable by value from a genuine
    threshold. Rather than guess, the diff reports that class separately.
    """
    return HEX_RE.sub("IMM", " ".join(text.split()))


def disassemble(
    data: bytes, base_address: int, objdump: str, arch: str = "i386"
) -> list[tuple[int, int, str]]:
    """Return (address, length, text) per decoded instruction."""
    with tempfile.TemporaryDirectory() as tmp:
        raw = pathlib.Path(tmp) / "object.bin"
        raw.write_bytes(data)
        command = [
            objdump,
            "-D",
            "-b", "binary",
            "-m", arch,
            "-M", "intel",
            f"--adjust-vma=0x{base_address:x}",
            str(raw),
        ]
        result = subprocess.run(
            command, capture_output=True, text=True, check=False, env=OBJDUMP_ENV
        )
    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()
        raise DisasmError(
            f"{objdump} failed with exit {result.returncode}: "
            f"{detail[0] if detail else 'no stderr'}"
        )

    decoded: list[tuple[int, str]] = []
    for line in result.stdout.splitlines():
        match = LINE_RE.match(line)
        if not match:
            continue
        decoded.append((int(match.group(1), 16), match.group(3).strip()))

    if not decoded:
        raise DisasmError(
            f"{objdump} produced no decodable instructions; the object may be "
            f"empty or the architecture wrong"
        )

    # Instruction length comes from the gap to the next address, not from the
    # byte column: objdump wraps the byte listing at 7 bytes per line, and the
    # continuation lines carry no disassembly text. Counting the printed bytes
    # would silently undercount every instruction longer than 7 bytes.
    end = base_address + len(data)
    instructions = []
    for i, (address, text) in enumerate(decoded):
        following = decoded[i + 1][0] if i + 1 < len(decoded) else end
        instructions.append((address, max(0, following - address), text))
    return instructions


def build_inventory(
    instructions: list[tuple[int, int, str]],
    seed_address: int,
    entry_address: int | None,
    low: int,
    high: int,
    address_ranges: tuple[tuple[int, int], ...] = (),
) -> dict:
    """Derive candidate functions, a call graph, and per-function signatures.

    ``seed_address`` starts the candidate list and must lie in ``[low, high)``.
    ``entry_address`` is only used to flag which candidate is the image entry,
    and is None when the entry point is not in the object being analysed.
    """
    if not low <= seed_address < high:
        raise DisasmError(
            f"seed address 0x{seed_address:x} is outside the analysed range "
            f"0x{low:x}..0x{high:x}"
        )
    call_sites: list[tuple[int, int]] = []
    branch_targets: set[int] = set()
    mnemonics: collections.Counter = collections.Counter()

    for address, _length, text in instructions:
        mnemonics[text.split()[0] if text else "?"] += 1
        call = CALL_RE.match(text)
        if call:
            target = int(call.group(1), 16)
            if low <= target < high:
                call_sites.append((address, target))
            continue
        branch = BRANCH_RE.match(text)
        if branch:
            target = int(branch.group(1), 16)
            if low <= target < high:
                branch_targets.add(target)

    starts = sorted({seed_address} | {target for _, target in call_sites})

    # Attribute each instruction to the candidate function that precedes it.
    bounds = {start: (starts[i + 1] if i + 1 < len(starts) else high)
              for i, start in enumerate(starts)}

    def owner(address: int) -> int | None:
        # starts is sorted; find the greatest start <= address
        lo, hi = 0, len(starts) - 1
        best = None
        while lo <= hi:
            mid = (lo + hi) // 2
            if starts[mid] <= address:
                best = starts[mid]
                lo = mid + 1
            else:
                hi = mid - 1
        return best

    per_function: dict[int, list[str]] = collections.defaultdict(list)
    per_function_shape: dict[int, list[str]] = collections.defaultdict(list)
    per_function_bytes: collections.Counter = collections.Counter()
    for address, length, text in instructions:
        start = owner(address)
        if start is None:
            continue
        per_function[start].append(normalize(text, address_ranges))
        per_function_shape[start].append(normalize_shape(text))
        per_function_bytes[start] += length

    incoming: collections.Counter = collections.Counter()
    edges: collections.Counter = collections.Counter()
    for site, target in call_sites:
        incoming[target] += 1
        caller = owner(site)
        if caller is not None:
            edges[(caller, target)] += 1

    def digest(lines: list[str]) -> str:
        return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

    functions = []
    for start in starts:
        body = per_function.get(start, [])
        functions.append(
            {
                "address": start,
                "end": bounds[start],
                "instruction_count": len(body),
                "byte_length": per_function_bytes.get(start, 0),
                "callers": incoming.get(start, 0),
                "is_entry": entry_address is not None and start == entry_address,
                "signature": digest(body),
                "shape_signature": digest(per_function_shape.get(start, [])),
            }
        )

    return {
        "instruction_count": len(instructions),
        "candidate_function_count": len(functions),
        "call_site_count": len(call_sites),
        "branch_target_count": len(branch_targets),
        "top_mnemonics": mnemonics.most_common(25),
        "functions": functions,
        "call_edges": [
            {"from": caller, "to": target, "count": count}
            for (caller, target), count in sorted(edges.items())
        ],
    }


def analyse(
    path: pathlib.Path, object_index: int | None, objdump: str, arch: str = "i386"
) -> dict:
    image = le_image.load(path)

    if object_index is None:
        object_index = image.start_object
    if not 1 <= object_index <= image.object_count:
        raise DisasmError(
            f"no object {object_index}; {path.name} has {image.object_count}"
        )
    obj = image.objects[object_index - 1]
    if not obj.flags & 0x0004:
        raise DisasmError(
            f"object {object_index} of {path.name} is not executable "
            f"(flags 0x{obj.flags:04x}); refusing to present a data object as code"
        )

    data = image.object_bytes(object_index)
    instructions = disassemble(data, obj.base_address, objdump, arch)

    # Seed the sweep inside the object being analysed. The image entry point
    # only qualifies when it actually lands in this object; for any other
    # executable object it is an unrelated address, and using it would create a
    # candidate outside the object's bounds that swallows every instruction
    # before the first in-object call target.
    entry_in_object = obj.base_address <= image.entry_address < obj.end_address
    seed = image.entry_address if entry_in_object else obj.base_address

    # Masking is driven by the whole image's object ranges, not just this
    # object's: code here legitimately references data-object addresses, and
    # those relocate between builds too.
    address_ranges = tuple(
        (other.base_address, other.end_address) for other in image.objects
    )

    inventory = build_inventory(
        instructions,
        seed,
        image.entry_address if entry_in_object else None,
        obj.base_address,
        obj.end_address,
        address_ranges,
    )

    return {
        "source": {
            "name": image.name,
            "sha256": image.sha256,
            "object": object_index,
            "base_address": obj.base_address,
            "end_address": obj.end_address,
            "virtual_size": obj.virtual_size,
            "entry_address": image.entry_address,
        },
        "tool": {
            "objdump": objdump_version(objdump),
            "arch": arch,
            "method": "linear sweep of the whole object; candidate functions are "
                      "direct call targets plus a seed at the entry point when "
                      "it lies in this object, otherwise the object base",
            "seed_address": seed,
            "normalization": "hex operands inside the image's object ranges are "
                             "masked as ADDR; all other constants are preserved",
        },
        **inventory,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", type=pathlib.Path)
    parser.add_argument(
        "--object", type=int, default=None,
        help="object to disassemble (default: the entry object)",
    )
    parser.add_argument(
        "--arch", default="i386", help="objdump -m architecture (default: i386)",
    )
    parser.add_argument("--objdump", default=None, help="objdump binary to use")
    parser.add_argument(
        "-o", "--output", type=pathlib.Path, default=None,
        help="write the inventory JSON here instead of stdout",
    )
    parser.add_argument(
        "--summary", action="store_true",
        help="print a short human summary instead of JSON",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        objdump = find_objdump(args.objdump)
        report = analyse(args.file, args.object, objdump, args.arch)
    except (LEError, DisasmError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.summary:
        source = report["source"]
        print(f"{source['name']} object {source['object']} "
              f"(0x{source['base_address']:x}-0x{source['end_address']:x})")
        print(f"  instructions decoded  : {report['instruction_count']}")
        print(f"  candidate functions   : {report['candidate_function_count']}")
        print(f"  direct call sites     : {report['call_site_count']}")
        print(f"  call graph edges      : {len(report['call_edges'])}")
        print(f"  objdump               : {report['tool']['objdump']}")
        return 0

    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.output} ({report['candidate_function_count']} candidate "
              f"functions, {report['instruction_count']} instructions)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
