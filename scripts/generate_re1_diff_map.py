#!/usr/bin/env python3
"""Generate the machine-readable RE1 product/locale differential map.

The script reuses the conservative matcher in tools/le_diff.py instead of
introducing a looser similarity model. Full inventories stay under ignored
artifacts/; the compact report contains candidate addresses, class, size,
incoming direct-call-site count, and conservative cross-locale corroboration.
Candidate starts remain linear-sweep/direct-call analysis regions, not verified
functions.

Address-level mappings are stricter than le_diff's multiset counts: a candidate
is mapped across a product or locale pair only when the signature used at that
match stage is unique on both sides of that stage. Duplicate signatures remain
unmapped instead of inheriting an arbitrary zip pairing.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import le_diff  # noqa: E402

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
PAIR_SPECS = {
    "product-en": ("antag-en", "patch-en"),
    "product-intl": ("antag-intl", "patch-intl"),
    "antag-locale": ("antag-en", "antag-intl"),
    "patch-locale": ("patch-en", "patch-intl"),
}
PAIR_CLASSES = ("exact", "reference_only", "constant_only")
MATCH_KEYS = {
    "exact": "signature",
    "reference_only": "reference_signature",
    "constant_only": "shape_signature",
}
EXPECTED_PAIR_COUNTS = {
    "product-en": {
        "exact": 72,
        "reference_only": 613,
        "constant_only": 525,
        "structural_left": 116,
        "structural_right": 87,
    },
    "product-intl": {
        "exact": 72,
        "reference_only": 611,
        "constant_only": 520,
        "structural_left": 123,
        "structural_right": 93,
    },
    "antag-locale": {
        "exact": 114,
        "reference_only": 1107,
        "constant_only": 46,
        "structural_left": 59,
        "structural_right": 59,
    },
    "patch-locale": {
        "exact": 114,
        "reference_only": 1076,
        "constant_only": 56,
        "structural_left": 51,
        "structural_right": 50,
    },
}
SCHEMA = "ascendancy.re1-differential-map/v2"


class RE1Error(RuntimeError):
    pass


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_targets(directory: pathlib.Path) -> dict[str, pathlib.Path]:
    resolved: dict[str, pathlib.Path] = {}
    for target_id, (name, size, expected_sha) in TARGETS.items():
        path = directory / name
        if not path.is_file():
            raise RE1Error(f"missing pinned target {path}")
        actual = (path.stat().st_size, sha256_file(path))
        expected = (size, expected_sha)
        if actual != expected:
            raise RE1Error(
                f"unsupported {name}: size={actual[0]} sha256={actual[1]}; "
                f"expected size={size} sha256={expected_sha}"
            )
        resolved[target_id] = path
    return resolved


def run_inventory(
    path: pathlib.Path, output: pathlib.Path, objdump: str | None
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(ROOT / "tools/le_disasm.py"),
        str(path),
        "-o",
        str(output),
    ]
    if objdump:
        command.extend(["--objdump", objdump])
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RE1Error(f"le_disasm failed for {path.name}: {result.stderr.strip()}")
    try:
        payload = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RE1Error(f"cannot read inventory {output}: {exc}") from exc
    le_diff.validate_inventory(payload, str(output))
    return payload


def compare_with_pairs(
    left: dict[str, Any], right: dict[str, Any]
) -> dict[str, Any]:
    """Expose the exact pairings that le_diff.compare intentionally summarizes."""
    le_diff.validate_inventory(left, "left inventory")
    le_diff.validate_inventory(right, "right inventory")
    le_diff.require_matching_decoder(left, right)
    exact, rest_left, rest_right = le_diff.match_pass(
        left["functions"], right["functions"], "signature"
    )
    reference, rest_left, rest_right = le_diff.match_pass(
        rest_left, rest_right, "reference_signature"
    )
    constant, only_left, only_right = le_diff.match_pass(
        rest_left, rest_right, "shape_signature"
    )
    return {
        "exact": exact,
        "reference_only": reference,
        "constant_only": constant,
        "structural_left": only_left,
        "structural_right": only_right,
    }


def counts(diff: dict[str, Any]) -> dict[str, int]:
    return {
        "exact": len(diff["exact"]),
        "reference_only": len(diff["reference_only"]),
        "constant_only": len(diff["constant_only"]),
        "structural_left": len(diff["structural_left"]),
        "structural_right": len(diff["structural_right"]),
    }


def validate_pair_counts(pair_counts: dict[str, dict[str, int]]) -> None:
    if pair_counts != EXPECTED_PAIR_COUNTS:
        raise RE1Error(
            "conservative differential counts drifted on the pinned targets; "
            f"expected {EXPECTED_PAIR_COUNTS}, got {pair_counts}. "
            "Update RE1 evidence and this gate together if the analysis model "
            "changes intentionally."
        )


def stage_pool(
    diff: dict[str, Any], stage_index: int, side: int
) -> list[dict[str, Any]]:
    pool: list[dict[str, Any]] = []
    for cls in PAIR_CLASSES[stage_index:]:
        pool.extend(pair[side] for pair in diff[cls])
    pool.extend(diff["structural_left" if side == 0 else "structural_right"])
    return pool


def unambiguous_pair_map(
    diff: dict[str, Any],
) -> tuple[dict[int, tuple[int, str]], dict[str, int]]:
    """Map left addresses only when the stage signature is unique on both sides.

    le_diff deliberately multiset-matches duplicate signatures because that is
    correct for aggregate counts. Candidate-level address mapping has a stronger
    requirement: if two candidates share the same stage signature, choosing one
    right-side address by list order would manufacture evidence. Such pairs are
    counted as ambiguous and omitted from the address map.
    """
    result: dict[int, tuple[int, str]] = {}
    ambiguous: dict[str, int] = {cls: 0 for cls in PAIR_CLASSES}

    for stage_index, cls in enumerate(PAIR_CLASSES):
        key = MATCH_KEYS[cls]
        left_counts = collections.Counter(
            function[key] for function in stage_pool(diff, stage_index, 0)
        )
        right_counts = collections.Counter(
            function[key] for function in stage_pool(diff, stage_index, 1)
        )
        for left, right in diff[cls]:
            signature = left[key]
            if signature != right[key]:
                raise RE1Error(
                    f"{cls} pairing violates its {key} invariant at "
                    f"0x{int(left['address']):x}"
                )
            if left_counts[signature] != 1 or right_counts[signature] != 1:
                ambiguous[cls] += 1
                continue
            result[int(left["address"])] = (int(right["address"]), cls)

    return result, ambiguous


def resolve_product_pair(
    mapping: dict[int, tuple[int, str]], left_address: int, cls: str
) -> tuple[int | None, str]:
    """Return a right address only for an unambiguous product-pair identity."""
    pair = mapping.get(left_address)
    if pair is None:
        return None, "ambiguous"
    right_address, mapped_class = pair
    if mapped_class != cls:
        raise RE1Error(
            f"product pair class mismatch at 0x{left_address:x}: "
            f"expected {cls}, got {mapped_class}"
        )
    return right_address, "unambiguous"


def cross_locale_status(
    antag_en: int,
    patch_en: int | None,
    cls: str,
    antag_locale: dict[int, tuple[int, str]],
    patch_locale: dict[int, tuple[int, str]],
    intl_product: dict[int, tuple[int, str]],
    intl_structural: set[int],
) -> dict[str, Any]:
    antag = antag_locale.get(antag_en)
    if cls == "structural":
        corroborated = bool(antag and antag[0] in intl_structural)
        return {
            "corroborated": corroborated,
            "antag_intl_address": antag[0] if antag else None,
            "patch_intl_address": None,
            "intl_product_class": "structural" if corroborated else None,
        }

    patch = patch_locale.get(patch_en) if patch_en is not None else None
    if not antag or not patch:
        return {
            "corroborated": False,
            "antag_intl_address": antag[0] if antag else None,
            "patch_intl_address": patch[0] if patch else None,
            "intl_product_class": None,
        }

    product = intl_product.get(antag[0])
    intl_class = product[1] if product and product[0] == patch[0] else None
    return {
        "corroborated": intl_class == cls,
        "antag_intl_address": antag[0],
        "patch_intl_address": patch[0],
        "intl_product_class": intl_class,
    }


def candidate_sort_key(item: dict[str, Any]) -> tuple[bool, int, int, int, int]:
    class_order = {"structural": 0, "constant_only": 1, "reference_only": 2}
    return (
        not bool(item["cross_locale"]["corroborated"]),
        class_order[item["class"]],
        -int(item["incoming_call_sites"]),
        -int(item["byte_length"]),
        int(item["antag_en_address"]),
    )


def generate(args: argparse.Namespace) -> dict[str, Any]:
    targets = verify_targets(args.binaries)
    args.artifact_output.mkdir(parents=True, exist_ok=True)
    inventories: dict[str, dict[str, Any]] = {}
    for target_id, path in targets.items():
        inventory_path = args.artifact_output / f"{target_id}.code-inventory.json"
        inventories[target_id] = run_inventory(path, inventory_path, args.objdump)
        expected_sha = TARGETS[target_id][2]
        if inventories[target_id]["source"]["sha256"] != expected_sha:
            raise RE1Error(f"inventory source hash drift for {target_id}")

    diffs = {
        name: compare_with_pairs(inventories[left], inventories[right])
        for name, (left, right) in PAIR_SPECS.items()
    }
    pair_counts = {name: counts(diff) for name, diff in diffs.items()}
    validate_pair_counts(pair_counts)

    product_en_map, product_en_ambiguous = unambiguous_pair_map(
        diffs["product-en"]
    )
    antag_locale, antag_ambiguous = unambiguous_pair_map(diffs["antag-locale"])
    patch_locale, patch_ambiguous = unambiguous_pair_map(diffs["patch-locale"])
    intl_product, intl_product_ambiguous = unambiguous_pair_map(
        diffs["product-intl"]
    )
    intl_structural = {
        int(function["address"])
        for function in diffs["product-intl"]["structural_left"]
    }

    candidates: list[dict[str, Any]] = []
    product_en = diffs["product-en"]
    for cls in ("reference_only", "constant_only"):
        for left, _right in product_en[cls]:
            antag_address = int(left["address"])
            patch_address, product_pair_status = resolve_product_pair(
                product_en_map, antag_address, cls
            )
            candidates.append(
                {
                    "class": cls,
                    "antag_en_address": antag_address,
                    "patch_en_address": patch_address,
                    "product_en_pair_status": product_pair_status,
                    "byte_length": int(left["byte_length"]),
                    "instruction_count": int(left["instruction_count"]),
                    # le_disasm's legacy `callers` field counts direct call sites,
                    # not distinct caller regions. Preserve the underlying value
                    # but publish it with an unambiguous RE1 name.
                    "incoming_call_sites": int(left["callers"]),
                    "cross_locale": cross_locale_status(
                        antag_address,
                        patch_address,
                        cls,
                        antag_locale,
                        patch_locale,
                        intl_product,
                        intl_structural,
                    ),
                }
            )
    for left in product_en["structural_left"]:
        antag_address = int(left["address"])
        candidates.append(
            {
                "class": "structural",
                "antag_en_address": antag_address,
                "patch_en_address": None,
                "product_en_pair_status": "structural_unpaired",
                "byte_length": int(left["byte_length"]),
                "instruction_count": int(left["instruction_count"]),
                "incoming_call_sites": int(left["callers"]),
                "cross_locale": cross_locale_status(
                    antag_address,
                    None,
                    "structural",
                    antag_locale,
                    patch_locale,
                    intl_product,
                    intl_structural,
                ),
            }
        )

    candidates.sort(key=candidate_sort_key)
    class_summary = {
        cls: {
            "count": sum(item["class"] == cls for item in candidates),
            "cross_locale_corroborated": sum(
                item["class"] == cls
                and bool(item["cross_locale"]["corroborated"])
                for item in candidates
            ),
        }
        for cls in ("reference_only", "constant_only", "structural")
    }

    return {
        "schema": SCHEMA,
        "blind_re_provenance": "clean",
        "targets": {
            target_id: {
                "filename": values[0],
                "size": values[1],
                "sha256": values[2],
            }
            for target_id, values in TARGETS.items()
        },
        "pair_counts": pair_counts,
        "address_mapping": {
            "product-en": {
                "unambiguous_pairs": len(product_en_map),
                "ambiguous_pairs_by_class": product_en_ambiguous,
            },
            "antag-en-to-intl": {
                "unambiguous_pairs": len(antag_locale),
                "ambiguous_pairs_by_class": antag_ambiguous,
            },
            "patch-en-to-intl": {
                "unambiguous_pairs": len(patch_locale),
                "ambiguous_pairs_by_class": patch_ambiguous,
            },
            "intl-product": {
                "unambiguous_pairs": len(intl_product),
                "ambiguous_pairs_by_class": intl_product_ambiguous,
            },
        },
        "class_summary": class_summary,
        "candidates": candidates,
        "notes": [
            "All EN unresolved Antagonizer candidates are included before ordering.",
            "Ordering is triage only: cross-locale corroboration, then class, incoming direct-call-site count, size, address.",
            "Every emitted product/locale right-hand address requires a unique stage signature on both sides; ambiguous duplicate signatures remain unmapped.",
            "The incoming_call_sites field is the legacy le_disasm callers value: direct call sites targeting the candidate, not distinct caller regions.",
            "Structural entries have no invented baseline pair; fuzzy alignments belong in human RE notes as hypotheses.",
            "Candidate starts remain linear-sweep/direct-call analysis regions, not verified functions.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--binaries", type=pathlib.Path, default=ROOT / "binaries")
    parser.add_argument(
        "--artifact-output",
        type=pathlib.Path,
        default=ROOT / "artifacts/re1-diff-map",
    )
    parser.add_argument(
        "--repo-output",
        type=pathlib.Path,
        default=ROOT / "artifacts/re1-diff-map/candidate-map.json",
    )
    parser.add_argument("--objdump", default=None)
    args = parser.parse_args(argv)
    try:
        report = generate(args)
        args.repo_output.parent.mkdir(parents=True, exist_ok=True)
        args.repo_output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(
            f"RE1 differential map: PASS ({len(report['candidates'])} EN unresolved candidates)"
        )
        for pair_name, pair_count in report["pair_counts"].items():
            print(f"  {pair_name}: {pair_count}")
        for mapping_name, mapping in report["address_mapping"].items():
            print(
                f"  {mapping_name} address map: "
                f"{mapping['unambiguous_pairs']} unambiguous; "
                f"ambiguous {mapping['ambiguous_pairs_by_class']}"
            )
        for cls, summary in report["class_summary"].items():
            print(
                f"  {cls}: {summary['count']} candidates, "
                f"{summary['cross_locale_corroborated']} cross-locale corroborated"
            )
        return 0
    except (RE1Error, le_diff.DisasmError, OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
