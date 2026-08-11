#!/usr/bin/env python3
"""Validate repository-local Markdown links without fetching the network."""

from __future__ import annotations

import pathlib
import re
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "#")


def iter_markdown_files() -> list[pathlib.Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if ".git" not in path.parts and "artifacts" not in path.parts
    )


def link_target(raw: str) -> str:
    target = raw.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = target.split(" ", 1)[0]
    target = target.split("#", 1)[0]
    return urllib.parse.unquote(target)


def main() -> int:
    failures: list[str] = []

    for source in iter_markdown_files():
        text = source.read_text(encoding="utf-8")

        if text and not text.endswith("\n"):
            failures.append(f"{source.relative_to(ROOT)}: missing final newline")

        for match in LINK_RE.finditer(text):
            raw = match.group(1).strip()

            if not raw or raw.startswith(SKIP_PREFIXES):
                continue

            target = link_target(raw)
            if not target:
                continue

            resolved = (source.parent / target).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                failures.append(
                    f"{source.relative_to(ROOT)}: link escapes repository: {raw}"
                )
                continue

            if not resolved.exists():
                failures.append(
                    f"{source.relative_to(ROOT)}: broken link {raw} -> "
                    f"{resolved.relative_to(ROOT)}"
                )

    if failures:
        print("Documentation check failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    print(f"Checked {len(iter_markdown_files())} Markdown files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
