#!/usr/bin/env python3
"""Run the CF2 corrected pipeline end-to-end on the four hash-pinned targets.

This is the checkout-level regression that closes CF2's real-target validation
gap. It invokes the repository CLIs (not a reimplementation), validates the
serialized inventory contract, checks reconstructed object fingerprints, and
compares the exact metrics recorded in the CF2 experiment documents.

By default the four binaries must already exist under ``binaries/``. Pass
``--fetch`` in a clean cloud checkout to run ``tools/fetch_free_targets.py``
first. The targets remain git-ignored and are never committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import le_disasm  # noqa: E402
import le_image  # noqa: E402

TARGETS = {
    "ANTAG_EN.EXE": {
        "sha256": "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00",
        "objects": {
            1: "7772d00e6e36d5a2828d43410c59c601ca2149e3dcee33187b53d7a2d278c8e8",
            2: "3bb3ddc418aa5eaceedd2de0cc8d20034b3fa99c3db36181d08de2992e1c4797",
        },
        "inventory": (144696, 1326, 7472, 11059, 4259),
    },
    "ANTAG_INTL.EXE": {
        "sha256": "9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c",
        "objects": {
            1: "f86803f21c9144f10b02f558ff9b30378812dd497061ef05b31cb1b3e29bde15",
            2: "6397503cf6a093f5a9bb60117e6bc3044395363c46a59c25eb30f1d8167f79fe",
        },
        "inventory": (144691, 1326, 7477, 11018, 4260),
    },
    "PATCH_EN.EXE": {
        "sha256": "7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b",
        "objects": {
            1: "9a6055067d153af08c40c4d368c339881a2a50f06e3a8c41500a1748737a84a2",
            2: "5eb4889b6c23dff80464e5686fa84a4e1269402b8e3d58070ce3869ec91e3c6a",
        },
        "inventory": (139093, 1297, 7251, 10433, 4162),
    },
    "PATCH_INTL.EXE": {
        "sha256": "16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b",
        "objects": {
            1: "be79ae2b1e393af4de5b32682432ff4f4664a96531d6f90473a26310b905e4b6",
            2: "4506b1c9c569f0d9c2145e9b49887b1dcce6e42bd962457bcf4856377587fa96",
        },
        "inventory": (139129, 1296, 7255, 10448, 4162),
    },
}

DIFFS = {
    ("ANTAG_EN.EXE", "PATCH_EN.EXE"): {
        "matched_function_count": 72,
        "moved_but_identical_count": 50,
        "reference_only_difference_count": 613,
        "constant_only_difference_count": 525,
        "left_unmatched": 116,
        "right_unmatched": 87,
        "left_fraction": 0.765115,
        "right_fraction": 0.798235,
    },
    ("ANTAG_INTL.EXE", "PATCH_INTL.EXE"): {
        "matched_function_count": 72,
        "moved_but_identical_count": 50,
        "reference_only_difference_count": 611,
        "constant_only_difference_count": 520,
        "left_unmatched": 123,
        "right_unmatched": 93,
        "left_fraction": 0.759166,
        "right_fraction": 0.792016,
    },
    ("ANTAG_EN.EXE", "ANTAG_INTL.EXE"): {
        "matched_function_count": 114,
        "moved_but_identical_count": 67,
        "reference_only_difference_count": 1107,
        "constant_only_difference_count": 46,
        "left_unmatched": 59,
        "right_unmatched": 59,
        "left_fraction": 0.838974,
        "right_fraction": 0.838684,
    },
    ("PATCH_EN.EXE", "PATCH_INTL.EXE"): {
        "matched_function_count": 114,
        "moved_but_identical_count": 67,
        "reference_only_difference_count": 1076,
        "constant_only_difference_count": 56,
        "left_unmatched": 51,
        "right_unmatched": 50,
        "left_fraction": 0.855931,
        "right_fraction": 0.855623,
    },
}


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def check_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise SystemExit(f"CF2 regression mismatch: {label}: {actual!r} != {expected!r}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fetch", action="store_true", help="fetch pinned targets first")
    parser.add_argument(
        "--binaries", type=pathlib.Path, default=ROOT / "binaries",
        help="directory containing the four target executables",
    )
    args = parser.parse_args(argv)

    if args.fetch:
        run([sys.executable, "tools/fetch_free_targets.py"])
    run([sys.executable, "tools/fetch_free_targets.py", "--verify"])

    with tempfile.TemporaryDirectory(prefix="cf2-real-") as tmp_text:
        tmp = pathlib.Path(tmp_text)
        inventories: dict[str, pathlib.Path] = {}

        for name, expected in TARGETS.items():
            path = args.binaries / name
            image = le_image.load(path)
            check_equal(f"{name} sha256", image.sha256, expected["sha256"])
            check_equal(f"{name} page_off field", le_image.H_DATAPAGE, 0x80)
            check_equal(f"{name} page-data exact EOF", image.page_data_end, image.size)

            for index, object_hash in expected["objects"].items():
                check_equal(
                    f"{name} object {index} sha256",
                    sha256(image.object_bytes(index)),
                    object_hash,
                )

            out = tmp / f"{name}.inventory.json"
            run([sys.executable, "tools/le_disasm.py", str(path), "-o", str(out)])
            report = json.loads(out.read_text(encoding="utf-8"))
            check_equal(f"{name} schema", report["schema"], le_disasm.INVENTORY_SCHEMA)
            check_equal(
                f"{name} parser layout",
                report["source"]["parser_layout"],
                le_disasm.PARSER_LAYOUT_ID,
            )
            check_equal(
                f"{name} code object fingerprint",
                report["source"]["object_sha256"],
                expected["objects"][1],
            )
            actual_inventory = (
                report["instruction_count"],
                report["candidate_function_count"],
                report["call_site_count"],
                report["branch_target_count"],
                len(report["call_edges"]),
            )
            check_equal(f"{name} inventory metrics", actual_inventory, expected["inventory"])
            inventories[name] = out

        for (left_name, right_name), expected in DIFFS.items():
            out = tmp / f"{left_name}--{right_name}.diff.json"
            run([
                sys.executable,
                "tools/le_diff.py",
                str(inventories[left_name]),
                str(inventories[right_name]),
                "-o",
                str(out),
            ])
            report = json.loads(out.read_text(encoding="utf-8"))
            for key in (
                "matched_function_count",
                "moved_but_identical_count",
                "reference_only_difference_count",
                "constant_only_difference_count",
            ):
                check_equal(f"{left_name}/{right_name} {key}", report[key], expected[key])
            check_equal(
                f"{left_name}/{right_name} left structural count",
                len(report["only_in_left"]),
                expected["left_unmatched"],
            )
            check_equal(
                f"{left_name}/{right_name} right structural count",
                len(report["only_in_right"]),
                expected["right_unmatched"],
            )
            check_equal(
                f"{left_name}/{right_name} left structural fraction",
                report["left"]["matched_byte_fraction"],
                expected["left_fraction"],
            )
            check_equal(
                f"{left_name}/{right_name} right structural fraction",
                report["right"]["matched_byte_fraction"],
                expected["right_fraction"],
            )

    print("CF2 real-target regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
