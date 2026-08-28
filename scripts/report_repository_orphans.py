#!/usr/bin/env python3
"""Report repository-level producer and ownership orphans.

This is intentionally a reporting check.  It does not fail CI because an orphan can
be a legitimate staged producer, standalone CLI, or historical experiment.  The
committed baseline and reasoned allowlist make the current state reviewable while
unit tests pin the detector's mechanics.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPORT_SCHEMA = "ascendancy.repository-orphan-report/v1"
ALLOWLIST_SCHEMA = "ascendancy.repository-orphan-allowlist/v1"
SCHEMA_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]+/v[0-9]+$")
SCHEMA_OUTPUT_KEYS = {"schema", "schema_id", "schema_version"}


@dataclass(frozen=True)
class SchemaConstant:
    identifier: str
    path: str
    symbol: str


def _python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for directory in ("scripts", "tools"):
        base = root / directory
        if base.is_dir():
            files.extend(sorted(base.rglob("*.py")))
    return files


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _parse(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return None


def _schema_constants(root: Path, files: Iterable[Path]) -> list[SchemaConstant]:
    result: list[SchemaConstant] = []
    for path in files:
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
                value = node.value
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                continue
            identifier = value.value
            if not SCHEMA_ID_RE.fullmatch(identifier):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and "SCHEMA" in target.id.upper():
                    result.append(
                        SchemaConstant(identifier, _relative(path, root), target.id)
                    )
    return sorted(set(result), key=lambda item: (item.identifier, item.path, item.symbol))


def _produced_schema_symbols(files: Iterable[Path]) -> tuple[set[str], set[str]]:
    symbols: set[str] = set()
    literals: set[str] = set()
    for path in files:
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if not (
                        isinstance(key, ast.Constant)
                        and key.value in SCHEMA_OUTPUT_KEYS
                    ):
                        continue
                    if isinstance(value, ast.Name):
                        symbols.add(value.id)
                    elif (
                        isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                        and SCHEMA_ID_RE.fullmatch(value.value)
                    ):
                        literals.add(value.value)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if not isinstance(target, ast.Subscript):
                        continue
                    index = target.slice
                    if not (
                        isinstance(index, ast.Constant)
                        and index.value in SCHEMA_OUTPUT_KEYS
                    ):
                        continue
                    if isinstance(node.value, ast.Name):
                        symbols.add(node.value.id)
                    elif (
                        isinstance(node.value, ast.Constant)
                        and isinstance(node.value.value, str)
                        and SCHEMA_ID_RE.fullmatch(node.value.value)
                    ):
                        literals.add(node.value.value)
    return symbols, literals


def _module_name(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    return ".".join(rel.parts)


def _has_main_guard(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
            continue
        left, right = test.left, test.comparators[0]
        pairs = ((left, right), (right, left))
        for maybe_name, maybe_value in pairs:
            if (
                isinstance(maybe_name, ast.Name)
                and maybe_name.id == "__name__"
                and isinstance(maybe_value, ast.Constant)
                and maybe_value.value == "__main__"
            ):
                return True
    return False


def _resolved_import_from_module(path: Path, root: Path, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""

    package = list(path.relative_to(root).with_suffix("").parts[:-1])
    ascend = node.level - 1
    if ascend > len(package):
        return ""
    if ascend:
        package = package[:-ascend]
    if node.module:
        package.extend(node.module.split("."))
    return ".".join(package)


def _imports_from_non_tests(root: Path) -> set[str]:
    imported: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        rel = _relative(path, root)
        if rel.startswith("tests/") or rel.startswith(".git/"):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = _resolved_import_from_module(path, root, node)
                if module:
                    imported.add(module)
                    imported.update(f"{module}.{alias.name}" for alias in node.names)
    return imported


def _module_is_imported(module: str, imported: set[str]) -> bool:
    return any(name == module or name.startswith(module + ".") for name in imported)


def _experiment_orphans(root: Path) -> list[str]:
    base = root / "docs" / "experiments"
    roadmap_path = root / "ROADMAP.md"
    if not base.is_dir() or not roadmap_path.is_file():
        return []
    roadmap = roadmap_path.read_text(encoding="utf-8")
    result: list[str] = []
    for path in sorted(base.glob("*.md")):
        rel = _relative(path, root)
        if rel not in roadmap and path.name not in roadmap:
            result.append(rel)
    return result


def detect(root: Path) -> dict[str, object]:
    root = root.resolve()
    files = _python_files(root)
    constants = _schema_constants(root, files)
    produced_symbols, produced_literals = _produced_schema_symbols(files)
    schema_orphans = [
        {"id": item.identifier, "path": item.path, "symbol": item.symbol}
        for item in constants
        if item.identifier not in produced_literals and item.symbol not in produced_symbols
    ]

    imported = _imports_from_non_tests(root)
    module_orphans: list[dict[str, str]] = []
    for path in files:
        tree = _parse(path)
        if tree is None or _has_main_guard(tree):
            continue
        module = _module_name(path, root)
        if not _module_is_imported(module, imported):
            module_orphans.append({"path": _relative(path, root), "module": module})

    return {
        "schema_version": REPORT_SCHEMA,
        "schema_orphans": schema_orphans,
        "module_orphans": module_orphans,
        "experiment_orphans": [{"path": path} for path in _experiment_orphans(root)],
    }


def _finding_key(category: str, finding: dict[str, str]) -> str:
    if category == "schema_orphans":
        return f"schema:{finding['id']}"
    return f"{category.removesuffix('_orphans')}:{finding['path']}"


def load_allowlist(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != ALLOWLIST_SCHEMA:
        raise ValueError(f"unsupported allowlist schema: {data.get('schema_version')!r}")
    entries = data.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("allowlist entries must be an object")
    result: dict[str, str] = {}
    for key, reason in entries.items():
        if not isinstance(key, str) or not isinstance(reason, str) or not reason.strip():
            raise ValueError("every allowlist entry requires a non-empty reason string")
        result[key] = reason.strip()
    return result


def annotate(report: dict[str, object], allowlist: dict[str, str]) -> dict[str, object]:
    annotated: dict[str, object] = {"schema_version": report["schema_version"]}
    seen: set[str] = set()
    for category in ("schema_orphans", "module_orphans", "experiment_orphans"):
        items: list[dict[str, str]] = []
        for raw in report[category]:  # type: ignore[index]
            finding = dict(raw)
            key = _finding_key(category, finding)
            seen.add(key)
            finding["allowlist_reason"] = allowlist.get(key, "")
            items.append(finding)
        annotated[category] = items
    annotated["stale_allowlist_entries"] = sorted(set(allowlist) - seen)
    return annotated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--allowlist", type=Path)
    parser.add_argument("--write-baseline", type=Path)
    args = parser.parse_args(argv)

    report = annotate(detect(args.root), load_allowlist(args.allowlist))
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.write_baseline:
        args.write_baseline.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
