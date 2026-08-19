#!/usr/bin/env python3
"""Inventory direct decoded references to planet_record+0x5a on canonical ANTAG_EN.

This is an investigation aid for A1's lossless Manual-transition invalidation
boundary. It deliberately does not claim exhaustive write coverage: computed or
indirect addressing and linear-disassembly limitations remain out of model.
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

SCHEMA = "ascendancy.a1-managed-field-reference-inventory/v1"
TARGET_SIZE = 610863
TARGET_SHA256 = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
FIELD_OFFSET = 0x5A
KNOWN_SITES = {
    0x22421: "zero-initializer-write",
    0x35473: "state-consult-1",
    0x356CC: "state-consult-2",
    0x37915: "plain-m-toggle-read",
    0x3791F: "plain-m-toggle-write",
    0x3AFCA: "renderer-read",
}
LINE_RE = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+(?:(?:[0-9a-fA-F]{2})\s+)+([a-zA-Z][a-zA-Z0-9.]*)\s*(.*?)\s*$"
)
FIELD_RE = re.compile(r"(?<![0-9a-fA-F])0x0*5a\(%(?:eax|ebx|ecx|edx|esi|edi|ebp|esp)\)", re.I)
READ_ONLY_PREFIXES = ("cmp", "test", "lea", "push")


class ProbeError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def parse_objdump(text: str) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for raw in text.splitlines():
        match = LINE_RE.match(raw)
        if not match:
            continue
        address = int(match.group(1), 16)
        mnemonic = match.group(2).lower()
        operands = match.group(3).strip()
        if not FIELD_RE.search(operands):
            continue
        parts = [part.strip() for part in operands.split(",") if part.strip()]
        destination = parts[-1] if parts else ""
        field_is_destination = FIELD_RE.search(destination) is not None
        potential_write = field_is_destination and not mnemonic.startswith(READ_ONLY_PREFIXES)
        refs.append(
            {
                "address": address,
                "mnemonic": mnemonic,
                "operands": operands,
                "field_is_destination": field_is_destination,
                "potential_write": potential_write,
            }
        )
    return refs


def validate_known_sites(refs: list[dict[str, Any]]) -> dict[str, Any]:
    by_address = {item["address"]: item for item in refs}
    missing = [address for address in KNOWN_SITES if address not in by_address]
    if missing:
        raise ProbeError(
            "decoded inventory missed established RE2 sites: "
            + ", ".join(f"0x{x:x}" for x in missing)
        )
    expected_writes = {0x22421, 0x3791F}
    bad = [address for address in expected_writes if not by_address[address]["potential_write"]]
    if bad:
        raise ProbeError(
            "established writer sites were not classified as potential writes: "
            + ", ".join(f"0x{x:x}" for x in bad)
        )
    return {
        f"0x{address:x}": {"role": role, "observed": True}
        for address, role in KNOWN_SITES.items()
    }


def run_objdump(code: bytes, code_base: int, objdump: str) -> tuple[str, str]:
    with tempfile.NamedTemporaryFile(prefix="a1-managed-field-", suffix=".bin") as handle:
        handle.write(code)
        handle.flush()
        command = [
            objdump,
            "-D",
            "-b",
            "binary",
            "-m",
            "i386",
            f"--adjust-vma=0x{code_base:x}",
            handle.name,
        ]
        proc = subprocess.run(command, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise ProbeError(f"objdump failed ({proc.returncode}): {proc.stderr.strip()}")
    version = subprocess.run(
        [objdump, "--version"], text=True, capture_output=True, check=False
    )
    if version.returncode != 0 or not version.stdout.strip():
        raise ProbeError("could not identify objdump version")
    return proc.stdout, version.stdout.splitlines()[0]


def build_result(target: pathlib.Path, objdump: str, checkout_sha: str | None) -> dict[str, Any]:
    payload = target.read_bytes()
    actual = (len(payload), sha256_bytes(payload))
    if actual != (TARGET_SIZE, TARGET_SHA256):
        raise ProbeError(
            f"unsupported target: size={actual[0]} sha256={actual[1]}; "
            f"expected size={TARGET_SIZE} sha256={TARGET_SHA256}"
        )
    image = le_image.LEImage(payload, target.name)
    if len(image.objects) < 1 or image.objects[0].kind != "code":
        raise ProbeError("LE object 1 is not the expected executable code object")
    code = image.object_bytes(1)
    code_base = image.objects[0].base_address
    disassembly, objdump_version = run_objdump(code, code_base, objdump)
    refs = parse_objdump(disassembly)
    known = validate_known_sites(refs)
    potential_writes = [item for item in refs if item["potential_write"]]

    if checkout_sha is not None and re.fullmatch(r"[0-9a-f]{40}", checkout_sha) is None:
        raise ProbeError("--checkout-sha must be a full lowercase 40-hex commit SHA")

    return {
        "schema": SCHEMA,
        "status": "incomplete-model",
        "evidence_class": "static",
        "blind_re_provenance": "clean",
        "checkout_sha": checkout_sha,
        "target": {"size": TARGET_SIZE, "sha256": TARGET_SHA256},
        "field_offset": FIELD_OFFSET,
        "analysis": {
            "code_object_base": code_base,
            "code_object_size": len(code),
            "objdump_version": objdump_version,
            "direct_decoded_reference_count": len(refs),
            "potential_write_count": len(potential_writes),
            "references": refs,
            "potential_writes": potential_writes,
            "known_site_checks": known,
        },
        "coverage": {
            "decoded_linear_code_object": True,
            "direct_base_plus_disp_field_operands": True,
            "computed_or_indirect_addressing": False,
            "semantic_execution_coverage": False,
            "complete_writer_inventory_established": False,
        },
        "a1_claim": {
            "lossless_manual_transition_invalidation_boundary": "unestablished",
            "interception_candidates_only": True,
        },
        "material_inputs": {
            "probe_sha256": sha256_file(pathlib.Path(__file__)),
            "le_image_sha256": sha256_file(ROOT / "tools" / "le_image.py"),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", type=pathlib.Path)
    parser.add_argument("--objdump", default="objdump")
    parser.add_argument("--checkout-sha")
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build_result(args.target, args.objdump, args.checkout_sha)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, le_image.LEError, ProbeError) as exc:
        print(f"a1-managed-field-writers: FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        "a1-managed-field-writers: PASS "
        f"references={result['analysis']['direct_decoded_reference_count']} "
        f"potential_writes={result['analysis']['potential_write_count']} "
        "completeness=unestablished"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
