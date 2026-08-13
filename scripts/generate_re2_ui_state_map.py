#!/usr/bin/env python3
"""Regenerate the RE2 static auto-management UI/state seam map.

The analysis is intentionally narrow and fail-closed. It verifies exact target
hashes, rebuilds the LE code/data objects through tools/le_image.py, locates a
small set of independently meaningful instruction patterns, and records only
addresses/invariants needed by RE4. It does not execute the game and does not
trace the per-turn self-management path (RE3/RE5 scope).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import le_image  # noqa: E402

SCHEMA = "ascendancy.re2-ui-state-map/v1"
TARGETS = {
    "antag-en": (
        "ANTAG_EN.EXE",
        610863,
        "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00",
    ),
    "patch-en": (
        "PATCH_EN.EXE",
        587451,
        "7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b",
    ),
    "antag-intl": (
        "ANTAG_INTL.EXE",
        610863,
        "9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c",
    ),
    "patch-intl": (
        "PATCH_INTL.EXE",
        587451,
        "16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b",
    ),
}
RETAIL_COB = (
    377589,
    "7a17cf776b0128c4f716ff6efb38d130470c5316fd9937c500803a97f85472aa",
)

PATTERNS = {
    "handler": (
        "56 57 55 89 e5 81 ec 18 01 00 00 89 45 f8 66 89 55 fc "
        "89 5d f0 89 4d e8"
    ),
    "key_dispatch": (
        "8b 45 e8 83 f8 17 72 2e 0f 86 ?? ?? ?? ?? 83 f8 1f 72 18 76 ae "
        "83 f8 31 72 37 0f 86 ?? ?? ?? ?? 83 f8 32 0f 84 ?? ?? ?? ?? eb 26"
    ),
    "toggle": (
        "83 3d ?? ?? ?? ?? 00 74 20 83 3d ?? ?? ?? ?? 00 0f 84 ?? ?? ?? ?? "
        "a1 ?? ?? ?? ?? 66 ff 40 55 e8 ?? ?? ?? ?? e9 ?? ?? ?? ?? "
        "8b 15 ?? ?? ?? ?? 8b 52 5a a1 ?? ?? ?? ?? f7 d2 89 50 5a"
    ),
    "render": (
        "a1 ?? ?? ?? ?? 8a 50 57 3a 15 ?? ?? ?? ?? 75 51 "
        "8b 70 5a 83 fe ff 75 49"
    ),
    "shift_probe": (
        "b4 02 88 e6 cd 16 75 09 80 e6 0f fe ce 75 02 29 c0 89 c3 89 c2 "
        "30 e7 66 a3 ?? ?? ?? ?? 80 e3 01 81 e3 ff ff 00 00 75 0d 30 e6 "
        "80 e2 02 81 e2 ff ff 00 00 74 0c c7 05 ?? ?? ?? ?? ff ff ff ff "
        "eb 06 89 1d ?? ?? ?? ??"
    ),
    "selected_assignment": (
        "a1 ?? ?? ?? ?? 8b 50 58 c1 fa 10 39 da 0f 8c ?? ?? ?? ?? "
        "89 da b9 01 00 00 00 8b 44 90 42 bb 11 00 00 00 a3 ?? ?? ?? ??"
    ),
    "state_consult_1": "83 7e 5a 00 75 ?? ba 01 00 00 00",
    "state_consult_2": "83 7e 5a 00 75 ?? ?? ?? 54 ?? ?? ??",
    "zero_initializer_candidate": (
        "c7 00 00 00 00 00 c7 40 04 00 00 00 00 c7 40 08 00 00 00 00 "
        "66 c7 40 1a 00 00 c7 40 10 00 00 00 00 c7 40 5a 00 00 00 00 c3"
    ),
    "sprintf_call": (
        "53 68 ?? ?? ?? ?? 8d 54 24 08 52 83 c1 02 e8 ?? ?? ?? ?? "
        "8d 54 24 0c 83 c4 0c"
    ),
}
SPRINTF_CALLEE_PREFIX = (
    "53 51 52 83 ec 04 8d 44 24 1c 8b 54 24 18 89 e3 b9 ?? ?? ?? ?? "
    "89 04 24 8b 44 24 14 e8 ?? ?? ?? ??"
)


class RE2Error(RuntimeError):
    pass


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_pattern(text: str) -> tuple[bytes, bytes]:
    values: list[int] = []
    masks: list[int] = []
    for token in text.split():
        if token in {"?", "??"}:
            values.append(0)
            masks.append(0)
            continue
        if len(token) != 2:
            raise RE2Error(f"invalid pattern token {token!r}")
        try:
            values.append(int(token, 16))
        except ValueError as exc:
            raise RE2Error(f"invalid pattern token {token!r}") from exc
        masks.append(0xFF)
    return bytes(values), bytes(masks)


def pattern_matches(data: bytes, offset: int, values: bytes, masks: bytes) -> bool:
    if offset + len(values) > len(data):
        return False
    return all(not masks[i] or data[offset + i] == values[i] for i in range(len(values)))


def find_all(data: bytes, pattern: str) -> list[int]:
    values, masks = parse_pattern(pattern)
    if not values:
        raise RE2Error("empty pattern")
    return [
        offset
        for offset in range(0, len(data) - len(values) + 1)
        if pattern_matches(data, offset, values, masks)
    ]


def find_unique(data: bytes, pattern: str, label: str) -> int:
    matches = find_all(data, pattern)
    if len(matches) != 1:
        rendered = ", ".join(f"0x{x:x}" for x in matches[:8]) or "none"
        raise RE2Error(
            f"{label}: expected exactly one pattern match, got {len(matches)} ({rendered})"
        )
    return matches[0]


def read_u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise RE2Error(f"u32 read at 0x{offset:x} is outside buffer")
    return struct.unpack_from("<I", data, offset)[0]


def rel32_target(code: bytes, opcode_offset: int, code_base: int) -> int:
    if code[opcode_offset] != 0xE8:
        raise RE2Error(f"expected CALL rel32 at 0x{code_base + opcode_offset:x}")
    disp = struct.unpack_from("<i", code, opcode_offset + 1)[0]
    return code_base + opcode_offset + 5 + disp


def jcc_rel32_target(code: bytes, opcode_offset: int, code_base: int) -> int:
    if code[opcode_offset : opcode_offset + 2] != b"\x0f\x84":
        raise RE2Error(f"expected JE rel32 at 0x{code_base + opcode_offset:x}")
    disp = struct.unpack_from("<i", code, opcode_offset + 2)[0]
    return code_base + opcode_offset + 6 + disp


def c_string(data: bytes, offset: int, limit: int = 256) -> bytes:
    if not 0 <= offset < len(data):
        raise RE2Error(f"string offset 0x{offset:x} is outside data object")
    stop = data.find(b"\0", offset, min(len(data), offset + limit))
    if stop < 0:
        raise RE2Error(f"unterminated bounded string at data+0x{offset:x}")
    return data[offset:stop]


def verify_targets(directory: pathlib.Path) -> dict[str, pathlib.Path]:
    result: dict[str, pathlib.Path] = {}
    for target_id, (filename, size, expected_sha) in TARGETS.items():
        path = directory / filename
        if not path.is_file():
            raise RE2Error(f"missing pinned target {path}")
        actual = (path.stat().st_size, sha256_file(path))
        if actual != (size, expected_sha):
            raise RE2Error(
                f"unsupported {filename}: size={actual[0]} sha256={actual[1]}; "
                f"expected size={size} sha256={expected_sha}"
            )
        result[target_id] = path
    return result


def verify_user_facing_text(payload: bytes) -> dict[str, bool]:
    resource = b'// 98\r\n"Self Managed"\r\n'
    tutorial_a = b'Pressing "M"\r\n'
    tutorial_b = b'will toggle the Managed feature\r\n'
    if resource not in payload:
        raise RE2Error("retail COB does not contain the pinned resource-98 Self Managed marker")
    if tutorial_a not in payload or tutorial_b not in payload:
        raise RE2Error("retail COB does not contain the bounded M/Managed tutorial markers")
    return {"resource_98_self_managed": True, "tutorial_m_toggle": True}


def scan_code_data(code: bytes, data: bytes, code_base: int, target_id: str) -> dict[str, Any]:
    located = {
        name: find_unique(code, pattern, f"{target_id}:{name}")
        for name, pattern in PATTERNS.items()
    }

    handler = located["handler"]
    planlist_offset = read_u32(code, handler + 0x19)
    plsquare_offset = read_u32(code, handler + 0x2A)
    if c_string(data, planlist_offset) != b"PLANLIST":
        raise RE2Error(f"{target_id}: handler PLANLIST anchor failed")
    if c_string(data, plsquare_offset) != b"PLSQUARE":
        raise RE2Error(f"{target_id}: handler PLSQUARE anchor failed")

    dispatch = located["key_dispatch"]
    m_branch = dispatch + 0x23
    toggle = located["toggle"]
    if jcc_rel32_target(code, m_branch, code_base) != code_base + toggle:
        raise RE2Error(f"{target_id}: scan-code 0x32 branch does not reach toggle seam")

    shift_global = read_u32(code, toggle + 2)
    if code[toggle + 7 : toggle + 9] != b"\x74\x20":
        raise RE2Error(f"{target_id}: expected Shift==0 short JE at toggle seam")
    toggle_core = toggle + 9 + struct.unpack_from("<b", code, toggle + 8)[0]
    if code[toggle_core : toggle_core + 2] != b"\x8b\x15":
        raise RE2Error(f"{target_id}: toggle core does not load selected object")
    selected_global = read_u32(code, toggle_core + 2)
    state_offset = code[toggle_core + 8]
    if state_offset != 0x5A:
        raise RE2Error(f"{target_id}: unexpected managed-state offset 0x{state_offset:x}")
    if code[toggle_core + 9] != 0xA1 or read_u32(code, toggle_core + 10) != selected_global:
        raise RE2Error(f"{target_id}: toggle read/write use different selected globals")
    if code[toggle_core + 14 : toggle_core + 19] != b"\xf7\xd2\x89\x50\x5a":
        raise RE2Error(f"{target_id}: toggle is not NOT + dword write at +0x5a")

    shift_probe = located["shift_probe"]
    shift_window = code[shift_probe : shift_probe + 0x70]
    flag_true = b"\xc7\x05" + struct.pack("<I", shift_global) + b"\xff\xff\xff\xff"
    flag_false = b"\x89\x1d" + struct.pack("<I", shift_global)
    if shift_window.count(flag_true) != 1 or shift_window.count(flag_false) != 1:
        raise RE2Error(f"{target_id}: BIOS shift probe does not produce the toggle modifier global")

    selected_assignment = located["selected_assignment"]
    assign_opcode = code.find(b"\xa3", selected_assignment, selected_assignment + 0x40)
    if assign_opcode < 0 or read_u32(code, assign_opcode + 1) != selected_global:
        raise RE2Error(f"{target_id}: selected-list path does not assign the toggle object global")

    render = located["render"]
    if read_u32(code, render + 1) != selected_global:
        raise RE2Error(f"{target_id}: managed-state renderer uses a different selected object global")
    resource_hits = []
    needle = b"\xb8\x62\x00\x00\x00"
    start = render
    end = min(len(code), render + 0x90)
    pos = start
    while True:
        pos = code.find(needle, pos, end)
        if pos < 0:
            break
        resource_hits.append(pos)
        pos += 1
    if len(resource_hits) != 1:
        raise RE2Error(f"{target_id}: expected one resource-id 98 load near managed-state renderer")

    sprintf_call = located["sprintf_call"]
    format_offset = read_u32(code, sprintf_call + 2)
    format_text = c_string(data, format_offset)
    if format_text != b"data\\planal%02d.shp":
        raise RE2Error(f"{target_id}: known-arity format anchor changed: {format_text!r}")
    sprintf_target = rel32_target(code, sprintf_call + 14, code_base)
    callee_offset = sprintf_target - code_base
    prefix_values, prefix_masks = parse_pattern(SPRINTF_CALLEE_PREFIX)
    callee = code[callee_offset : callee_offset + len(prefix_values)]
    if len(callee) != len(prefix_values) or not all(
        not prefix_masks[i] or callee[i] == prefix_values[i]
        for i in range(len(prefix_values))
    ):
        raise RE2Error(f"{target_id}: sprintf-like callee no longer reads stack arguments as expected")

    return {
        "code_object_base": code_base,
        "handler": {
            "address": code_base + handler,
            "anchors": ["PLANLIST", "PLSQUARE"],
            "incoming_argument_evidence": ["EAX", "DX", "EBX", "ECX"],
        },
        "managed_key_dispatch": {
            "address": code_base + dispatch,
            "scan_code": 0x32,
            "toggle_branch_address": code_base + m_branch,
            "shift_flag_ds_offset": shift_global,
            "toggle_when_shift_zero": True,
        },
        "managed_state": {
            "selected_object_ds_offset": selected_global,
            "selected_assignment_address": code_base + assign_opcode,
            "object_relative_offset": state_offset,
            "toggle_read_address": code_base + toggle_core + 6,
            "toggle_write_address": code_base + toggle_core + 16,
            "toggle_operation": "bitwise_not_dword",
            "zero_initializer_candidate_address": code_base + located["zero_initializer_candidate"],
            "render_check_address": code_base + render + 16,
            "render_resource_id": 98,
            "state_consult_addresses": [
                code_base + located["state_consult_1"],
                code_base + located["state_consult_2"],
            ],
        },
        "modifier_probe": {
            "bios_int16_ah02_address": code_base + shift_probe,
            "shift_flag_ds_offset": shift_global,
        },
        "calling_convention_observation": {
            "known_arity_call_site": code_base + sprintf_call,
            "callee": sprintf_target,
            "format_data_offset": format_offset,
            "format": format_text.decode("ascii"),
            "stack_argument_count": 3,
            "caller_cleanup_bytes": 12,
            "internal_handler_register_inputs": ["EAX", "DX", "EBX", "ECX"],
            "conclusion": "mixed: cdecl-style stack variadic runtime call plus register-passed internal handler inputs",
        },
    }


def scan_target(path: pathlib.Path, target_id: str) -> dict[str, Any]:
    image = le_image.load(path)
    if image.sha256 != TARGETS[target_id][2]:
        raise RE2Error(f"{target_id}: LE parser source hash mismatch")
    executable = [obj for obj in image.objects if obj.flags & 0x0004]
    writable = [obj for obj in image.objects if obj.flags & 0x0002 and not obj.flags & 0x0004]
    if len(executable) != 1 or len(writable) != 1:
        raise RE2Error(
            f"{target_id}: expected one executable and one writable data object, got {len(executable)} and {len(writable)}"
        )
    code_obj = executable[0]
    data_obj = writable[0]
    result = scan_code_data(
        image.object_bytes(code_obj.index),
        image.object_bytes(data_obj.index),
        code_obj.base_address,
        target_id,
    )
    result["source"] = {
        "filename": path.name,
        "size": path.stat().st_size,
        "sha256": image.sha256,
    }
    return result


def generate(args: argparse.Namespace) -> dict[str, Any]:
    targets = verify_targets(args.binaries)
    results = {target_id: scan_target(path, target_id) for target_id, path in targets.items()}

    state_offsets = {item["managed_state"]["object_relative_offset"] for item in results.values()}
    resource_ids = {item["managed_state"]["render_resource_id"] for item in results.values()}
    scan_codes = {item["managed_key_dispatch"]["scan_code"] for item in results.values()}
    if state_offsets != {0x5A} or resource_ids != {98} or scan_codes != {0x32}:
        raise RE2Error("cross-build UI/state seam invariants drifted")

    retail = None
    if args.retail_cob is not None:
        path = args.retail_cob
        if not path.is_file():
            raise RE2Error(f"missing retail COB {path}")
        actual = (path.stat().st_size, sha256_file(path))
        if actual != RETAIL_COB:
            raise RE2Error(
                f"unsupported retail COB: size={actual[0]} sha256={actual[1]}; expected size={RETAIL_COB[0]} sha256={RETAIL_COB[1]}"
            )
        payload = path.read_bytes()
        retail = {
            "filename": path.name,
            "size": actual[0],
            "sha256": actual[1],
            "user_facing_markers": verify_user_facing_text(payload),
        }

    return {
        "schema": SCHEMA,
        "blind_re_provenance": "clean",
        "evidence_class": "static",
        "scope": "RE2 UI/state seam only; no per-turn decision-path tracing",
        "targets": results,
        "cross_build_invariants": {
            "managed_state_object_relative_offset": 0x5A,
            "managed_render_resource_id": 98,
            "managed_key_scan_code": 0x32,
            "toggle_operation": "0 <-> 0xffffffff via bitwise NOT; renderer recognizes 0xffffffff",
        },
        "retail_user_facing_evidence": retail,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binaries", type=pathlib.Path, default=ROOT / "binaries")
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "artifacts/re2-ui-state/map.json")
    parser.add_argument(
        "--retail-cob",
        type=pathlib.Path,
        help="optional exact ASCEND00.COB from the maintainer-supplied retail fixture",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = generate(args)
    except (RE2Error, le_image.LEError, OSError) as exc:
        print(f"RE2 UI/state map: FAIL: {exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    canonical = report["targets"]["antag-en"]
    state = canonical["managed_state"]
    print(
        "RE2 UI/state map: PASS "
        f"(ANTAG_EN handler=0x{canonical['handler']['address']:x} "
        f"M-toggle-write=0x{state['toggle_write_address']:x} "
        f"state=selected+0x{state['object_relative_offset']:x})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
