#!/usr/bin/env python3
"""Generate the repo-safe T2 static-analysis handoff from pinned Ascendancy targets."""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGETS = {
    "antag-en": ("ANTAG_EN.EXE", 610863, "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"),
    "antag-intl": ("ANTAG_INTL.EXE", 610863, "9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c"),
    "patch-en": ("PATCH_EN.EXE", 587451, "7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b"),
    "patch-intl": ("PATCH_INTL.EXE", 587451, "16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b"),
}
CANONICAL = ("antag-en", "patch-en")
SCHEMA = "ascendancy.t2-static-analysis-bundle/v1"
WDUMP_SCHEMA = "ascendancy.t2-wdump-comparison/v1"
HEX_VALUE_RE = re.compile(r"^\s*(.*?)\s+=\s+([0-9A-F]+)H\s*$")
OBJECT_START_RE = re.compile(r"^object\s+(\d+):\s+virtual memory size\s+=\s+([0-9A-F]+)H\s*$")
OBJECT_FIELD_RE = re.compile(r"^\s*(relocation base address|object flag bits|object page table index|# of object page table entries)\s+=\s+([0-9A-F]+)H\s*$")
PAGE_RE = re.compile(r"^\s*page #\s*(\d+)\s+map page =\s*([0-9A-F]+)H file ofs =\s*([0-9A-F]+)H flgs =\s*([0-9A-F]+)H")

HEADER_MAP = {
    "file offset": ("container", "mz_lfanew"),
    "linear EXE format level": ("container", "format_level"),
    "cpu type": ("container", "cpu"),
    "os type (1==OS/2, 2==Windows, 3==DOS4, 4==Win386)": ("container", "os_type"),
    "module version": ("container", "module_version"),
    "module flags": ("container", "module_flags"),
    "# module pages": ("pages", "count"),
    "object # for initial EIP": ("entry", "object"),
    "initial EIP": ("entry", "eip"),
    "object # for initial ESP": ("entry", "stack_object"),
    "initial ESP": ("entry", "esp"),
    "page size": ("pages", "size"),
    "last page size (LE)/page shift (LX)": ("pages", "last_page_size"),
    "fixup section size": ("loader", "fixup_size"),
    "loader section size": ("loader", "loader_size"),
    "object iterated data map offset": ("loader", "iterated_map_offset"),
    "offset of import module name table": ("loader", "import_module_offset"),
    "offset of import procedure name table": ("loader", "import_procedure_offset"),
    "offset of enumerated data pages": ("pages", "data_offset"),
    "offset of non-resident names table (rel file)": ("loader", "nonresident_offset"),
    "size of non-resident names table": ("loader", "nonresident_size"),
    "object # for automatic data object": ("loader", "autodata_object"),
    "offset of the debugging information": ("loader", "debug_offset"),
    "size of the debugging information": ("loader", "debug_size"),
}

class BundleError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_json(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise BundleError(f"command failed ({result.returncode}): {' '.join(command)}\n{result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise BundleError(f"command did not return JSON: {' '.join(command)}: {exc}") from exc


def verify_targets(directory: pathlib.Path) -> dict[str, pathlib.Path]:
    resolved: dict[str, pathlib.Path] = {}
    for target_id, (name, size, expected_sha) in TARGETS.items():
        path = directory / name
        if not path.is_file():
            raise BundleError(f"missing pinned target {path}")
        actual_size = path.stat().st_size
        actual_sha = sha256_file(path)
        if actual_size != size or actual_sha != expected_sha:
            raise BundleError(
                f"unsupported {name}: size={actual_size} sha256={actual_sha}; "
                f"expected size={size} sha256={expected_sha}"
            )
        resolved[target_id] = path
    return resolved


def parse_wdump(text: str) -> dict[str, Any]:
    header: dict[str, int] = {}
    objects: list[dict[str, int]] = []
    pages: list[dict[str, int]] = []
    in_linear_header = False
    current_object: dict[str, int] | None = None

    for line in text.splitlines():
        if "Linear EXE Header" in line:
            in_linear_header = True
            continue
        if "Object Table" in line:
            in_linear_header = False
            continue
        if in_linear_header:
            match = HEX_VALUE_RE.match(line)
            if match:
                header[match.group(1).strip()] = int(match.group(2), 16)
            continue

        match = OBJECT_START_RE.match(line)
        if match:
            current_object = {"index": int(match.group(1)), "virtual_size": int(match.group(2), 16)}
            objects.append(current_object)
            continue
        if current_object is not None:
            match = OBJECT_FIELD_RE.match(line)
            if match:
                key = {
                    "relocation base address": "base_address",
                    "object flag bits": "flags",
                    "object page table index": "first_page",
                    "# of object page table entries": "page_count",
                }[match.group(1)]
                current_object[key] = int(match.group(2), 16)
                continue
        match = PAGE_RE.match(line)
        if match:
            pages.append({
                "index": int(match.group(1)),
                "map_page": int(match.group(2), 16),
                "file_offset": int(match.group(3), 16),
                "flags": int(match.group(4), 16),
            })
    if not header or not objects or not pages:
        raise BundleError("wdump output did not contain an LE header, object table, and page map")
    return {"header": header, "objects": objects, "pages": pages}


def nested(info: dict[str, Any], path: tuple[str, str]) -> int:
    return int(info[path[0]][path[1]])


def compare_wdump(info: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    disagreements: list[dict[str, Any]] = []
    agreements: dict[str, int] = {}
    for label, path in HEADER_MAP.items():
        if label not in parsed["header"]:
            disagreements.append({"kind": "missing_wdump_header", "field": label})
            continue
        wdump_value = int(parsed["header"][label])
        repo_value = nested(info, path)
        if wdump_value != repo_value:
            disagreements.append({"kind": "header", "field": label, "wdump": wdump_value, "le_image": repo_value})
        else:
            agreements[label] = repo_value

    repo_objects = {int(obj["index"]): obj for obj in info["objects"]}
    for obj in parsed["objects"]:
        idx = obj["index"]
        expected = repo_objects.get(idx)
        if expected is None:
            disagreements.append({"kind": "unexpected_wdump_object", "object": idx})
            continue
        for key in ("virtual_size", "base_address", "flags", "first_page", "page_count"):
            if obj.get(key) != int(expected[key]):
                disagreements.append({"kind": "object", "object": idx, "field": key, "wdump": obj.get(key), "le_image": int(expected[key])})
    if len(parsed["objects"]) != len(repo_objects):
        disagreements.append({"kind": "object_count", "wdump": len(parsed["objects"]), "le_image": len(repo_objects)})

    page_count = int(info["pages"]["count"])
    page_size = int(info["pages"]["size"])
    data_offset = int(info["pages"]["data_offset"])
    if len(parsed["pages"]) != page_count:
        disagreements.append({"kind": "page_count", "wdump": len(parsed["pages"]), "le_image": page_count})
    for page in parsed["pages"]:
        index = page["index"]
        expected_map = index
        expected_offset = data_offset + (expected_map - 1) * page_size
        if page["map_page"] != expected_map:
            disagreements.append({"kind": "page_map", "page": index, "wdump": page["map_page"], "le_image": expected_map})
        if page["file_offset"] != expected_offset:
            disagreements.append({"kind": "page_file_offset", "page": index, "wdump": page["file_offset"], "le_image": expected_offset})
        if page["flags"] != 0:
            disagreements.append({"kind": "page_flags", "page": index, "wdump": page["flags"], "le_image": 0})

    return {
        "header_fields_compared": len(HEADER_MAP),
        "header_agreements": agreements,
        "objects_compared": len(parsed["objects"]),
        "page_entries_compared": len(parsed["pages"]),
        "page_numbers_are_sequential": bool(info["pages"]["numbers_are_sequential"]),
        "disagreements": disagreements,
        "result": "pass" if not disagreements else "fail",
    }


def wdump_version(wdump: str) -> str:
    result = subprocess.run([wdump], capture_output=True, text=True, check=False)
    text = (result.stdout + result.stderr).strip().splitlines()
    return " | ".join(line.strip() for line in text[:2]) if text else "unknown"


def run_wdump(wdump: str, target: pathlib.Path) -> tuple[str, dict[str, Any]]:
    result = subprocess.run([wdump, "-q", "-p", str(target)], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise BundleError(f"wdump failed for {target.name} ({result.returncode}): {result.stderr.strip()}")
    return result.stdout, parse_wdump(result.stdout)


def stable_json_sha(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def string_summary(payload: dict[str, Any]) -> dict[str, Any]:
    strings = payload["strings"]
    per_object: dict[str, int] = {}
    digest = hashlib.sha256()
    longest: list[dict[str, int]] = []
    indicators: list[dict[str, Any]] = []
    for item in strings:
        per_object[str(item["object"])] = per_object.get(str(item["object"]), 0) + 1
        digest.update(f"{item['object']}:{item['address']}:{item['length']}:".encode("ascii"))
        digest.update(item["text"].encode("ascii"))
        digest.update(b"\n")
        longest.append({"object": item["object"], "address": item["address"], "length": item["length"]})
        upper = item["text"].upper()
        matches = [token for token in ("WATCOM", "DOS/4G", "RATIONAL") if token in upper]
        if matches:
            indicators.append({
                "object": item["object"],
                "address": item["address"],
                "length": item["length"],
                "matched_tokens": matches,
                "text_sha256": sha256_bytes(item["text"].encode("ascii")),
            })
    longest.sort(key=lambda x: (-x["length"], x["address"]))
    return {
        "source_sha256": payload["sha256"],
        "minimum_length": 4,
        "string_count": len(strings),
        "count_by_object": per_object,
        "ordered_full_index_sha256": digest.hexdigest(),
        "longest_runs_without_text": longest[:20],
        "runtime_toolchain_indicators": indicators,
        "note": "Full target strings are regenerated on demand and are not committed in bulk.",
    }


def target_summary(info: dict[str, Any], inventory: dict[str, Any], strings: dict[str, Any], inventory_path: pathlib.Path) -> dict[str, Any]:
    functions = inventory["functions"]
    edges = inventory["call_edges"]
    return {
        "source": inventory["source"],
        "layout": info,
        "inventory": {
            "schema": inventory["schema"],
            "tool": inventory["tool"],
            "instruction_count": inventory["instruction_count"],
            "candidate_function_count": inventory["candidate_function_count"],
            "call_site_count": inventory["call_site_count"],
            "branch_target_count": inventory["branch_target_count"],
            "call_edge_count": len(edges),
            "top_mnemonics": inventory["top_mnemonics"],
            "candidate_starts": [item["address"] for item in functions],
            "candidate_records_sha256": stable_json_sha(functions),
            "call_edges_sha256": stable_json_sha(edges),
            "full_inventory_file_sha256": sha256_file(inventory_path),
            "note": "Full v2 le_disasm inventory is regenerated into artifacts/ and is not committed; this summary preserves start addresses, counts, provenance, and stable digests.",
        },
        "strings": string_summary(strings),
    }

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binaries", type=pathlib.Path, default=ROOT / "binaries")
    parser.add_argument("--artifact-output", type=pathlib.Path, default=ROOT / "artifacts/t2-static-analysis")
    parser.add_argument("--repo-output", type=pathlib.Path, default=ROOT / "docs/re/static-analysis/t2")
    parser.add_argument("--wdump", default=None, help="Open Watcom wdump executable; defaults to PATH")
    parser.add_argument("--objdump", default=None, help="GNU objdump passed to tools/le_disasm.py")
    args = parser.parse_args(argv)

    try:
        targets = verify_targets(args.binaries)
        wdump = shutil.which(args.wdump) if args.wdump else shutil.which("wdump")
        if not wdump and args.wdump and pathlib.Path(args.wdump).is_file():
            wdump = str(pathlib.Path(args.wdump).resolve())
        if not wdump:
            raise BundleError("wdump is required for T2; pass --wdump or put it on PATH")
        artifact_output = args.artifact_output
        repo_output = args.repo_output
        artifact_output.mkdir(parents=True, exist_ok=True)
        repo_output.mkdir(parents=True, exist_ok=True)

        infos: dict[str, dict[str, Any]] = {}
        for target_id, path in targets.items():
            infos[target_id] = run_json([sys.executable, str(ROOT / "tools/le_image.py"), "info", "--json", str(path)])

        repo_files: list[pathlib.Path] = []
        for target_id in CANONICAL:
            path = targets[target_id]
            layout_path = artifact_output / f"{target_id}.layout.json"
            write_json(layout_path, infos[target_id])

            strings_payload = run_json([sys.executable, str(ROOT / "tools/le_image.py"), "strings", "--json", str(path), "--min-length", "4"])
            strings_path = artifact_output / f"{target_id}.strings.json"
            write_json(strings_path, strings_payload)

            inventory_path = artifact_output / f"{target_id}.code-inventory.json"
            command = [sys.executable, str(ROOT / "tools/le_disasm.py"), str(path), "-o", str(inventory_path)]
            if args.objdump:
                command.extend(["--objdump", args.objdump])
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                raise BundleError(f"le_disasm failed for {path.name}: {result.stderr.strip()}")
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))

            summary_path = repo_output / f"{target_id}.summary.json"
            write_json(summary_path, target_summary(infos[target_id], inventory, strings_payload, inventory_path))
            repo_files.append(summary_path)

        comparisons: dict[str, Any] = {}
        for target_id, path in targets.items():
            raw, parsed = run_wdump(wdump, path)
            comparison = compare_wdump(infos[target_id], parsed)
            comparison["source_sha256"] = infos[target_id]["sha256"]
            comparison["wdump_output_sha256"] = sha256_bytes(raw.encode("utf-8"))
            comparisons[target_id] = comparison
            if comparison["result"] != "pass":
                raise BundleError(f"wdump disagreement for {target_id}: {comparison['disagreements']}")

        wdump_path = repo_output / "wdump-comparison.json"
        write_json(wdump_path, {
            "schema": WDUMP_SCHEMA,
            "wdump_version": wdump_version(wdump),
            "wdump_sha256": sha256_file(pathlib.Path(wdump)),
            "targets": comparisons,
        })
        repo_files.append(wdump_path)

        files = {path.relative_to(repo_output).as_posix(): {"sha256": sha256_file(path), "size": path.stat().st_size} for path in sorted(repo_files)}
        manifest = {
            "schema": SCHEMA,
            "blind_re_provenance": "clean",
            "canonical_targets": list(CANONICAL),
            "wdump_cross_check_targets": list(TARGETS),
            "source_targets": {key: {"filename": value[0], "size": value[1], "sha256": value[2]} for key, value in TARGETS.items()},
            "commands": {
                "full_bundle": "python3 scripts/generate_t2_static_bundle.py --wdump /path/to/wdump",
                "layout": "python3 tools/le_image.py info --json <target>",
                "strings": "python3 tools/le_image.py strings --json --min-length 4 <target>",
                "inventory": "python3 tools/le_disasm.py <target> -o <inventory.json>",
                "wdump": "wdump -q -p <target>",
            },
            "repo_files": files,
            "artifact_output": "artifacts/t2-static-analysis/ (ignored; full layouts, strings, and v2 le_disasm inventories)",
            "notes": [
                "Candidate starts are linear-sweep/direct-call analysis regions, not verified functions.",
                "No target executable, raw disassembly, or full string dump is committed.",
                "The wdump cross-check compares every emitted object and page-map entry plus LE fields also exposed by le_image info --json.",
                "The repo summaries contain the complete candidate-start inventories and digests of the full candidate records/call edges; regenerate artifacts/ for the complete v2 inventory.",
            ],
        }
        write_json(repo_output / "manifest.json", manifest)
        print(f"T2 static-analysis bundle: PASS ({len(repo_files) + 1} repo files; full artifacts in {artifact_output})")
        return 0
    except BundleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
