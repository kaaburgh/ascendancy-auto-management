#!/usr/bin/env python3
"""Collect bounded static evidence for A1 planet identity/lifetime.

The probe verifies the canonical target, reconstructs LE object 1, and emits only
compact decoded metadata around already-supported anchors. It re-establishes the
initializer-shaped +0x5a zeroing routine by instruction invariants, inventories
its direct callers, references to the selected-container/selected-record globals,
and 0x7b arithmetic/control-flow occurrences. These are investigation leads; the
probe does not infer a reuse-safe identity contract by itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import le_image  # noqa: E402

SCHEMA = "ascendancy.a1-planet-identity-static-census/v2"
TARGET_SIZE = 610863
TARGET_SHA256 = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
KNOWN_STRIDE = 0x7B
SELECTED_CONTAINER_GLOBAL = 0x43660
SELECTED_RECORD_GLOBAL = 0x43664
KNOWN_INITIALIZER_WRITE = 0x22421
KNOWN_INITIALIZER_ENTRY = 0x22400
WINDOW_RADIUS = 5
WINDOWS = {
    "turn_planet_loop": (0x20C94, 0x20E30),
    "owned_planet_loop": (0x3BF80, 0x3C130),
}
INSTRUCTION_RE = re.compile(r"^\s*([0-9a-f]+):\s+(?:[0-9a-f]{2}\s+)+\s*([a-z][a-z0-9.]*)\s*(.*)$")
HEX_RE = re.compile(r"0x([0-9a-fA-F]+)")
REGISTER_FIELD_ZERO_RE = re.compile(
    r"(?:DWORD PTR )?\[(?:e(?:ax|bx|cx|dx|si|di|bp|sp))\+0x5a\]|0x5a\(%e(?:ax|bx|cx|dx|si|di|bp|sp)\)",
    re.I,
)
CALL_TARGET_RE = re.compile(r"(?:^|[\s,*])(?:0x)?([0-9a-fA-F]{4,8})(?:\s|$)")


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
                "mnemonic": mnemonic.lower(),
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


def normalized_window(instructions: list[dict[str, Any]], index: int, radius: int = WINDOW_RADIUS) -> list[dict[str, Any]]:
    start = max(0, index - radius)
    stop = min(len(instructions), index + radius + 1)
    return instructions[start:stop]


def literal_values(operands: str) -> set[int]:
    return {int(value, 16) for value in HEX_RE.findall(operands)}


def is_zero_field_write(item: dict[str, Any]) -> bool:
    if not item["mnemonic"].startswith("mov"):
        return False
    operands = item["operands"].lower()
    field_match = REGISTER_FIELD_ZERO_RE.search(operands)
    if field_match is None:
        return False
    return bool(re.search(r"(?:\$?0x0\b|\b0\b)", operands[: field_match.start()]))


def reestablish_initializer(instructions: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [(idx, item) for idx, item in enumerate(instructions) if is_zero_field_write(item)]
    if len(candidates) != 1:
        raise ProbeError(
            "initializer anchor is ambiguous: expected one decoded mov-zero to record+0x5a, "
            f"found {len(candidates)}"
        )
    idx, write = candidates[0]
    if write["address"] != KNOWN_INITIALIZER_WRITE:
        raise ProbeError(
            f"initializer invariant moved unexpectedly: decoded write=0x{write['address']:x}, "
            f"supported write=0x{KNOWN_INITIALIZER_WRITE:x}"
        )
    preceding = [item for item in instructions if KNOWN_INITIALIZER_ENTRY <= item["address"] <= write["address"]]
    if not preceding or preceding[0]["address"] != KNOWN_INITIALIZER_ENTRY:
        raise ProbeError("could not reconstruct supported initializer entry-to-write instruction span")
    return {
        "entry": KNOWN_INITIALIZER_ENTRY,
        "zero_write": write["address"],
        "invariant": "unique decoded mov-immediate-zero to base-register+0x5a plus supported entry/write span",
        "window": normalized_window(instructions, idx),
    }


def parse_direct_call_target(item: dict[str, Any]) -> int | None:
    if not item["mnemonic"].startswith("call"):
        return None
    match = CALL_TARGET_RE.search(item["operands"])
    if match is None:
        return None
    return int(match.group(1), 16)


def collect_census(instructions: list[dict[str, Any]], initializer_entry: int) -> dict[str, Any]:
    callers = []
    globals_by_value: dict[int, list[dict[str, Any]]] = {
        SELECTED_CONTAINER_GLOBAL: [],
        SELECTED_RECORD_GLOBAL: [],
    }
    stride_contexts = []

    for idx, item in enumerate(instructions):
        target = parse_direct_call_target(item)
        if target == initializer_entry:
            callers.append({"call_site": item["address"], "target": target, "window": normalized_window(instructions, idx)})

        values = literal_values(item["operands"])
        for global_value in globals_by_value:
            if global_value in values:
                globals_by_value[global_value].append(
                    {"address": item["address"], "window": normalized_window(instructions, idx)}
                )

        if KNOWN_STRIDE in values:
            stride_contexts.append(
                {
                    "address": item["address"],
                    "mnemonic": item["mnemonic"],
                    "operands": item["operands"],
                    "window": normalized_window(instructions, idx),
                    "classification": "triage-only",
                }
            )

    if not callers:
        raise ProbeError("no direct decoded caller reaches the re-established initializer entry")
    for value, refs in globals_by_value.items():
        if not refs:
            raise ProbeError(f"no decoded references found for supported global 0x{value:x}")
    if not stride_contexts:
        raise ProbeError("no decoded 0x7b arithmetic/control-flow triage occurrences found")

    return {
        "initializer_direct_callers": callers,
        "selected_globals": {
            f"0x{value:x}": {"reference_count": len(refs), "references": refs}
            for value, refs in globals_by_value.items()
        },
        "stride_0x7b_contexts": stride_contexts,
        "identity_contract_established": False,
    }


def run_objdump(code: bytes, code_base: int) -> tuple[str, str]:
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
    version = subprocess.run(["objdump", "--version"], check=False, text=True, capture_output=True)
    if version.returncode != 0 or not version.stdout.strip():
        raise ProbeError("could not identify objdump version")
    return result.stdout, version.stdout.splitlines()[0]


def probe(target: pathlib.Path, checkout_sha: str | None = None) -> dict[str, Any]:
    checkout_sha = checkout_sha or os.environ.get("GITHUB_SHA")
    if not target.is_file():
        raise ProbeError(f"target not found: {target}")
    size = target.stat().st_size
    digest = sha256_file(target)
    if (size, digest) != (TARGET_SIZE, TARGET_SHA256):
        raise ProbeError(
            f"unsupported target: size={size} sha256={digest}; "
            f"expected size={TARGET_SIZE} sha256={TARGET_SHA256}"
        )
    if checkout_sha is not None and re.fullmatch(r"[0-9a-f]{40}", checkout_sha) is None:
        raise ProbeError("--checkout-sha must be a full lowercase 40-hex commit SHA")

    image = le_image.LEImage(target.read_bytes(), target.name)
    if image.object_count != 2:
        raise ProbeError(f"expected 2 LE objects, found {image.object_count}")
    code_obj, data_obj = image.objects
    if code_obj.kind != "code" or data_obj.kind != "data":
        raise ProbeError("expected object 1 code and object 2 data")
    for label, (start, stop) in WINDOWS.items():
        if not code_obj.base_address <= start < stop <= code_obj.end_address:
            raise ProbeError(f"{label} window is outside code object")

    disassembly, objdump_version = run_objdump(image.object_bytes(1), code_obj.base_address)
    parsed = parse_disassembly(disassembly)
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

    initializer = reestablish_initializer(parsed)
    census = collect_census(parsed, initializer["entry"])
    return {
        "schema": SCHEMA,
        "evidence_class": "static",
        "blind_re_provenance": "clean",
        "checkout_sha": checkout_sha,
        "target": {"filename": target.name, "size": size, "sha256": digest},
        "le_layout": {"code_object": code_obj.to_dict(), "data_object": data_obj.to_dict()},
        "tool": {
            "producer": "scripts/probe_a1_planet_array_indexing.py",
            "objdump": objdump_version,
            "method": "exact-target decoded static census around supported A1 identity/lifetime anchors",
            "material_inputs": {
                "producer_sha256": sha256_file(pathlib.Path(__file__)),
                "le_image_sha256": sha256_file(ROOT / "tools" / "le_image.py"),
            },
        },
        "anchor_reestablishment": {"initializer": initializer},
        "census": census,
        "windows": windows,
        "relationship": summarize_relationship(windows),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", type=pathlib.Path)
    parser.add_argument("--checkout-sha")
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = probe(args.target, args.checkout_sha)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ProbeError, le_image.LEError, subprocess.SubprocessError) as exc:
        print(f"a1-planet-identity-static-census: FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("A1 planet identity/lifetime static census: PASS")
    print(f"initializer_callers={len(result['census']['initializer_direct_callers'])}")
    print(f"selected_container_refs={result['census']['selected_globals']['0x43660']['reference_count']}")
    print(f"selected_record_refs={result['census']['selected_globals']['0x43664']['reference_count']}")
    print(f"stride_contexts={len(result['census']['stride_0x7b_contexts'])}")
    print("identity_contract_established=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
