#!/usr/bin/env python3
"""Capture deterministic, repo-safe metadata for a candidate target executable.

The inspector is intentionally shallow. It fingerprints a supplied file and
parses only executable-container metadata needed to identify supported targets.
It is not a disassembler and does not build the static-RE pipeline owned by CF2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shlex
import struct
import sys
from typing import Any

TOOL_NAME = "inspect_target.py"
TOOL_VERSION = "1.0.0"
SCHEMA_VERSION = 1
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

# Values used by the LE/LX header in Open Watcom's exeflat.h. Do not infer an
# architecture for values not named here: the format also permits non-x86 CPUs.
CPU_TYPES = {
    1: "Intel 80286",
    2: "Intel 80386",
    3: "Intel 80486",
}

# Only values explicitly named by the primary header source used for this
# parser are mapped. The numeric os_type is always preserved even when unmapped.
OS_TYPES = {
    1: "OS/2",
    4: "Windows 386",
}

EXTENDER_MARKERS = (
    (b"DOS/4GW", "DOS/4GW"),
    (b"DOS/4G", "DOS/4G"),
)


class InspectError(Exception):
    """The requested input cannot be fingerprinted."""


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def hex32(value: int) -> str:
    return f"0x{value:08x}"


def inspect_mz(data: bytes, warnings: list[str]) -> dict[str, Any] | None:
    if len(data) < 2 or data[:2] != b"MZ":
        return None

    mz: dict[str, Any] = {"magic": "MZ"}
    if len(data) < 0x40:
        warnings.append(
            "MZ signature is present but the DOS header is truncated before e_lfanew"
        )
        return mz

    mz.update(
        {
            "bytes_in_last_page": u16(data, 0x02),
            "pages_in_file": u16(data, 0x04),
            "relocation_count": u16(data, 0x06),
            "header_paragraphs": u16(data, 0x08),
            "initial_ss": u16(data, 0x0E),
            "initial_sp": u16(data, 0x10),
            "initial_ip": u16(data, 0x14),
            "initial_cs": u16(data, 0x16),
            "relocation_table_offset": u16(data, 0x18),
            "overlay_number": u16(data, 0x1A),
            "secondary_header_offset": u32(data, 0x3C),
        }
    )
    return mz


def detect_extender(data: bytes, mz: dict[str, Any] | None) -> dict[str, str] | None:
    """Identify a small set of bound-extender markers in the DOS stub.

    This is evidence from an ASCII marker, not a claim about runtime behavior.
    Absence of a marker means only that this detector did not identify one.
    """
    if not mz or "secondary_header_offset" not in mz:
        return None
    stub_end = min(int(mz["secondary_header_offset"]), len(data))
    stub = data[:stub_end]
    for marker, name in EXTENDER_MARKERS:
        if marker in stub:
            return {
                "name": name,
                "evidence": f"ASCII marker {marker.decode('ascii')} found in DOS stub",
            }
    return None


def inspect_le(data: bytes, offset: int, warnings: list[str]) -> dict[str, Any] | None:
    if offset < 0 or offset + 2 > len(data):
        warnings.append(
            f"secondary header offset {hex32(offset)} is outside the file"
        )
        return None

    if data[offset : offset + 2] != b"LE":
        return None

    # Fields through data_pages_offset (0x80) are enough for T0 target identity
    # and basic load-layout metadata. Object/page-table contents, disassembly,
    # xrefs, and function analysis remain outside T0 (and the latter belong CF2).
    required = 0x84
    available = len(data) - offset
    if available < required:
        warnings.append(
            f"LE signature is present but the header is truncated: "
            f"need {required} bytes, have {available}"
        )
        return {"magic": "LE"}

    cpu_type = u16(data, offset + 0x08)
    os_type = u16(data, offset + 0x0A)
    return {
        "magic": "LE",
        "byte_order": data[offset + 0x02],
        "word_order": data[offset + 0x03],
        "format_level": u32(data, offset + 0x04),
        "cpu_type": cpu_type,
        "cpu_name": CPU_TYPES.get(cpu_type),
        "os_type": os_type,
        "os_name": OS_TYPES.get(os_type),
        "module_version": u32(data, offset + 0x0C),
        "module_flags": hex32(u32(data, offset + 0x10)),
        "module_pages": u32(data, offset + 0x14),
        "entry_object": u32(data, offset + 0x18),
        "entry_offset": hex32(u32(data, offset + 0x1C)),
        "stack_object": u32(data, offset + 0x20),
        "stack_offset": hex32(u32(data, offset + 0x24)),
        "page_size": u32(data, offset + 0x28),
        "bytes_on_last_page": u32(data, offset + 0x2C),
        "fixup_section_size": u32(data, offset + 0x30),
        "loader_section_size": u32(data, offset + 0x38),
        "object_table_offset": hex32(u32(data, offset + 0x40)),
        "object_count": u32(data, offset + 0x44),
        "object_page_map_offset": hex32(u32(data, offset + 0x48)),
        "fixup_page_table_offset": hex32(u32(data, offset + 0x68)),
        "fixup_record_table_offset": hex32(u32(data, offset + 0x6C)),
        "import_module_table_offset": hex32(u32(data, offset + 0x70)),
        "import_module_count": u32(data, offset + 0x74),
        "import_procedure_table_offset": hex32(u32(data, offset + 0x78)),
        "data_pages_offset": hex32(u32(data, offset + 0x80)),
    }


def architecture_from_le(le: dict[str, Any] | None) -> str | None:
    if not le:
        return None
    cpu_name = le.get("cpu_name")
    return f"x86 ({cpu_name})" if cpu_name else None


def format_from_headers(mz: dict[str, Any] | None, le: dict[str, Any] | None) -> str:
    if le:
        return "DOS MZ + Linear Executable (LE)"
    if mz:
        return "DOS MZ"
    return "unknown"


def sanitized_command(
    input_arg: str,
    target_id: str | None,
    label: str | None,
    output_arg: str | None,
) -> str:
    """Return the command used with host directory names reduced to basenames."""
    parts = ["python3", "tools/inspect_target.py", pathlib.Path(input_arg).name]
    if target_id is not None:
        parts.extend(["--id", target_id])
    if label is not None:
        parts.extend(["--label", label])
    if output_arg is not None:
        parts.extend(["--output", pathlib.Path(output_arg).name])
    return shlex.join(parts)


def build_target_record(
    path: pathlib.Path,
    input_arg: str,
    label: str | None,
    output_arg: str | None = None,
    target_id: str | None = None,
) -> dict[str, Any]:
    if not path.is_file():
        raise InspectError(f"input is not a regular file: {path}")
    if target_id is not None and not ID_RE.fullmatch(target_id):
        raise InspectError(
            "target id must match [a-z0-9][a-z0-9._-]*; "
            f"got {target_id!r}"
        )

    try:
        data = path.read_bytes()
    except OSError as exc:
        raise InspectError(f"cannot read {path}: {exc}") from exc

    warnings: list[str] = []
    mz = inspect_mz(data, warnings)
    le = None
    if mz and "secondary_header_offset" in mz:
        le = inspect_le(data, int(mz["secondary_header_offset"]), warnings)

    container: dict[str, Any] = {
        "detected_format": format_from_headers(mz, le),
        "architecture": architecture_from_le(le),
    }
    if mz:
        container["mz"] = mz
    if le:
        container["le"] = le
    extender = detect_extender(data, mz)
    if extender:
        container["extender"] = extender

    return {
        "id": target_id,
        "filename": path.name,
        "label": label,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "container": container,
        "capture": {
            "tool": TOOL_NAME,
            "version": TOOL_VERSION,
            "command": sanitized_command(input_arg, target_id, label, output_arg),
            "path_policy": (
                "input/output paths are reduced to basenames to avoid leaking host paths"
            ),
        },
        "warnings": warnings,
    }


def build_manifest(target: dict[str, Any]) -> dict[str, Any]:
    return {"schema": SCHEMA_VERSION, "targets": [target]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", help="candidate executable supplied outside git")
    parser.add_argument(
        "--id",
        help=(
            "stable manifest id such as antagonizer-en; lowercase letters, digits, "
            "dot, underscore and dash only"
        ),
    )
    parser.add_argument(
        "--label",
        help="user-supplied release/version/candidate label; never inferred from filename",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        help="write JSON to this path instead of stdout",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = pathlib.Path(args.input)
    output_arg = str(args.output) if args.output else None
    try:
        target = build_target_record(
            path, args.input, args.label, output_arg, target_id=args.id
        )
    except InspectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(build_manifest(target), indent=2, sort_keys=True) + "\n"
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
