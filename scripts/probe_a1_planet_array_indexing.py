#!/usr/bin/env python3
"""Collect bounded static leads for A1 planet-array indexing.

This probe is intentionally conservative. It verifies the canonical target,
reconstructs LE object 1, disassembles only two already-supported planet-loop
windows, and records stride/data-object operands that can guide the remaining
A1 identity investigation. It does not infer an array base, count, or reusable
slot merely from literal overlap.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import le_image  # noqa: E402

SCHEMA = "ascendancy.a1-planet-array-indexing-probe/v1"
TARGET_SIZE = 610863
TARGET_SHA256 = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
KNOWN_STRIDE = 0x7B
WINDOWS = {
    "turn_planet_loop": (0x20C94, 0x20E30),
    "owned_planet_loop": (0x3BF80, 0x3C130),
}
INSTRUCTION_RE = re.compile(r"^\s*([0-9a-f]+):\s+(?:[0-9a-f]{2}\s+)+\s*([a-z][a-z0-9.]*)\s*(.*)$")
HEX_RE = re.compile(r"0x([0-9a-fA-F]+)")


class ProbeError(RuntimeError):
    pass


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_disassembly(text: str) -> list[dict[str, Any]]:
    instructions: list[dict[str, Any]] = []
    for line in text.splitlines():
        match = INSTRUCTION_RE.match(line)
        if not match:
            continue
        address, mnemonic, operands = match.groups()
        instructions.append(
            {
                "address": int(address, 16),
                "mnemonic": mnemonic,
                "operands": operands.strip(),
            }
        )
    if not instructions:
        raise ProbeError("objdump output contained no parseable instructions")
    return instructions


def analyze_window(
    instructions: list[dict[str, Any]],
    *,
    start: int,
    stop: int,
    data_start: int,
    data_end: int,
) -> dict[str, Any]:
    bounded = [item for item in instructions if start <= item["address"] < stop]
    if not bounded:
        raise ProbeError(f"no instructions in requested window 0x{start:x}..0x{stop:x}")

    stride_hits: list[dict[str, Any]] = []
    data_operands: dict[int, list[int]] = {}
    for item in bounded:
        literals = [int(value, 16) for value in HEX_RE.findall(item["operands"])]
        if KNOWN_STRIDE in literals:
            stride_hits.append(item)
        for value in literals:
            if data_start <= value < data_end:
                data_operands.setdefault(value, []).append(item["address"])

    return {
        "start": start,
        "stop": stop,
        "instruction_count": len(bounded),
        "stride_0x7b_hits": stride_hits,
        "data_object_absolute_operands": [
            {"value": value, "instruction_addresses": addresses}
            for value, addresses in sorted(data_operands.items())
        ],
    }


def summarize_relationship(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    operand_sets = []
    for window in windows.values():
        operand_sets.append({item["value"] for item in window["data_object_absolute_operands"]})
    shared = sorted(set.intersection(*operand_sets)) if operand_sets else []
    return {
        "status": "unestablished",
        "known_stride": KNOWN_STRIDE,
        "shared_data_object_operands": shared,
        "array_base": None,
        "array_count": None,
        "slot_indexing": None,
        "interpretation": (
            "Shared absolute operands and stride-bearing instructions are investigation leads only. "
            "This probe does not prove which operand is a planet-array base/count, does not prove "
            "pointer lifetime, and does not establish a reuse-safe A1 sidecar key."
        ),
    }


def run_objdump(code: bytes, code_base: int) -> str:
    with tempfile.NamedTemporaryFile(prefix="a1-code-", suffix=".bin") as tmp:
        tmp.write(code)
        tmp.flush()
        command = [
            "objdump",
            "-D",
            "-b",
            "binary",
            "-m",
            "i386",
            f"--adjust-vma=0x{code_base:x}",
            tmp.name,
        ]
        result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise ProbeError(f"objdump failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout


def probe(target: pathlib.Path) -> dict[str, Any]:
    if not target.is_file():
        raise ProbeError(f"target not found: {target}")
    size = target.stat().st_size
    digest = sha256_file(target)
    if (size, digest) != (TARGET_SIZE, TARGET_SHA256):
        raise ProbeError(
            f"unsupported target: size={size} sha256={digest}; "
            f"expected size={TARGET_SIZE} sha256={TARGET_SHA256}"
        )

    image = le_image.LEImage(target.read_bytes(), target.name)
    if image.object_count != 2:
        raise ProbeError(f"expected 2 LE objects, found {image.object_count}")
    code_obj, data_obj = image.objects
    if code_obj.kind != "code" or data_obj.kind != "data":
        raise ProbeError("expected object 1 code and object 2 data")
    for label, (start, stop) in WINDOWS.items():
        if not code_obj.base_address <= start < stop <= code_obj.end_address:
            raise ProbeError(f"{label} window is outside code object")

    parsed = parse_disassembly(run_objdump(image.object_bytes(1), code_obj.base_address))
    windows = {
        label: analyze_window(
            parsed,
            start=start,
            stop=stop,
            data_start=data_obj.base_address,
            data_end=data_obj.end_address,
        )
        for label, (start, stop) in WINDOWS.items()
    }
    if not all(window["stride_0x7b_hits"] for window in windows.values()):
        raise ProbeError("one or more supported planet-loop windows no longer contain a 0x7b stride operand")

    objdump_version = subprocess.run(
        ["objdump", "--version"], check=True, text=True, capture_output=True
    ).stdout.splitlines()[0]
    return {
        "schema": SCHEMA,
        "evidence_class": "static",
        "blind_re_provenance": "clean",
        "target": {"filename": target.name, "size": size, "sha256": digest},
        "le_layout": {
            "code_object": code_obj.to_dict(),
            "data_object": data_obj.to_dict(),
        },
        "tool": {
            "producer": "scripts/probe_a1_planet_array_indexing.py",
            "objdump": objdump_version,
            "method": "bounded disassembly operand collection from two previously established planet loops",
        },
        "windows": windows,
        "relationship": summarize_relationship(windows),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = probe(args.target)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ProbeError, le_image.LEError, subprocess.SubprocessError) as exc:
        print(f"a1-planet-array-indexing: FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    relationship = result["relationship"]
    print("A1 planet-array indexing probe: PASS")
    print(f"shared_data_object_operands={len(relationship['shared_data_object_operands'])}")
    print("slot_indexing=unestablished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
