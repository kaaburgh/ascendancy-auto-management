#!/usr/bin/env python3
"""Validate the save-fixture declarations in `tools/validation-fixtures.json`.

The save payloads themselves are maintainer-supplied and never committed, so
this check has two independent halves:

* the declaration is always checked — schema, required fields, role
  requirements, and evidence level;
* the payload is checked only when it is actually present in a supplied
  fixture directory, by size and SHA-256.

Runtime properties recorded here are claims established by a named runtime
experiment. A fixture whose properties are still `unverified` may be declared,
but no role requirement is considered satisfied by it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DECLARATION = ROOT / "tools" / "validation-fixtures.json"
SUPPORTED_SCHEMA = 1
REQUIRED_FIXTURE_FIELDS = (
    "id",
    "filename",
    "role",
    "storage",
    "size",
    "sha256",
    "produced_by_target_sha256",
    "runtime_properties",
)
REQUIRED_PROPERTY_FIELDS = (
    "evidence",
    "player_race_id",
    "player_owned_planet_count",
    "player_planet_names",
    "planets_with_empty_current_action_at_load",
)


class FixtureDeclarationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_declaration(document: dict[str, Any]) -> list[dict[str, Any]]:
    if document.get("schema") != SUPPORTED_SCHEMA:
        raise FixtureDeclarationError(
            f"unsupported declaration schema {document.get('schema')!r}"
        )

    roles = document.get("roles")
    requirements = document.get("role_requirements")
    evidence_levels = document.get("evidence_levels")
    if not isinstance(roles, dict) or not isinstance(requirements, dict):
        raise FixtureDeclarationError("roles and role_requirements must both be objects")
    if not isinstance(evidence_levels, list) or not evidence_levels:
        raise FixtureDeclarationError("evidence_levels must be a non-empty list")
    unknown = sorted(set(requirements) - set(roles))
    if unknown:
        raise FixtureDeclarationError(f"role_requirements for undeclared roles: {unknown}")

    fixtures = document.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise FixtureDeclarationError("fixtures must be a non-empty list")

    seen: set[str] = set()
    for fixture in fixtures:
        missing = [field for field in REQUIRED_FIXTURE_FIELDS if field not in fixture]
        if missing:
            raise FixtureDeclarationError(
                f"fixture {fixture.get('id', '<unnamed>')!r} missing fields: {missing}"
            )
        identifier = fixture["id"]
        if identifier in seen:
            raise FixtureDeclarationError(f"duplicate fixture id {identifier!r}")
        seen.add(identifier)
        if fixture["role"] not in roles:
            raise FixtureDeclarationError(
                f"fixture {identifier!r} declares unknown role {fixture['role']!r}"
            )
        if not isinstance(fixture["size"], int) or fixture["size"] <= 0:
            raise FixtureDeclarationError(f"fixture {identifier!r} has a non-positive size")
        if len(fixture["sha256"]) != 64:
            raise FixtureDeclarationError(f"fixture {identifier!r} has a malformed sha256")

        properties = fixture["runtime_properties"]
        missing = [field for field in REQUIRED_PROPERTY_FIELDS if field not in properties]
        if missing:
            raise FixtureDeclarationError(
                f"fixture {identifier!r} runtime_properties missing: {missing}"
            )
        if properties["evidence"] not in evidence_levels:
            raise FixtureDeclarationError(
                f"fixture {identifier!r} declares unknown evidence level "
                f"{properties['evidence']!r}"
            )

        names = properties["player_planet_names"]
        if len(set(names)) != len(names):
            raise FixtureDeclarationError(
                f"fixture {identifier!r} repeats a player planet name; runtime record "
                "lookup requires unique names"
            )
        if len(names) != properties["player_owned_planet_count"]:
            raise FixtureDeclarationError(
                f"fixture {identifier!r} names {len(names)} player planets but declares "
                f"player_owned_planet_count={properties['player_owned_planet_count']}"
            )
        empty = properties["planets_with_empty_current_action_at_load"]
        unknown_names = sorted(set(empty) - set(names))
        if unknown_names:
            raise FixtureDeclarationError(
                f"fixture {identifier!r} lists empty-action planets that are not "
                f"player-owned: {unknown_names}"
            )

        check_role_requirements(identifier, fixture, requirements)

    return fixtures


def check_role_requirements(
    identifier: str, fixture: dict[str, Any], requirements: dict[str, Any]
) -> None:
    required = requirements.get(fixture["role"])
    if required is None:
        return
    properties = fixture["runtime_properties"]
    if properties["evidence"] == "unverified":
        raise FixtureDeclarationError(
            f"fixture {identifier!r} claims role {fixture['role']!r} on unverified "
            "runtime properties; verify them in a named runtime experiment first"
        )
    observed = {
        "min_player_owned_planets": properties["player_owned_planet_count"],
        "min_planets_with_empty_current_action_at_load": len(
            properties["planets_with_empty_current_action_at_load"]
        ),
    }
    for key, minimum in required.items():
        if key not in observed:
            raise FixtureDeclarationError(f"unknown role requirement {key!r}")
        if observed[key] < minimum:
            raise FixtureDeclarationError(
                f"fixture {identifier!r} does not satisfy role {fixture['role']!r}: "
                f"{key} is {observed[key]}, requires at least {minimum}"
            )


def check_payloads(
    fixtures: list[dict[str, Any]], fixture_dir: Path | None, require_present: bool
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for fixture in fixtures:
        entry: dict[str, Any] = {"id": fixture["id"], "filename": fixture["filename"]}
        path = None if fixture_dir is None else fixture_dir / fixture["filename"]
        if path is None or not path.is_file():
            if require_present:
                raise FixtureDeclarationError(
                    f"fixture {fixture['id']!r} payload not found; "
                    f"{fixture['filename']} is maintainer-supplied and must be provided"
                )
            entry["payload"] = "absent"
            results.append(entry)
            continue
        size = path.stat().st_size
        digest = sha256_file(path)
        if size != fixture["size"] or digest != fixture["sha256"]:
            raise FixtureDeclarationError(
                f"fixture {fixture['id']!r} payload identity mismatch: "
                f"size {size} sha256 {digest}"
            )
        entry["payload"] = "verified"
        results.append(entry)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--declaration", type=Path, default=DEFAULT_DECLARATION)
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=None,
        help="Directory holding maintainer-supplied save payloads.",
    )
    parser.add_argument(
        "--require-present",
        action="store_true",
        help="Fail when a declared payload is missing instead of reporting it absent.",
    )
    args = parser.parse_args(argv)

    try:
        document = json.loads(args.declaration.read_text(encoding="utf-8"))
        fixtures = check_declaration(document)
        results = check_payloads(fixtures, args.fixture_dir, args.require_present)
    except (FixtureDeclarationError, json.JSONDecodeError, OSError) as exc:
        print(f"validation-fixtures: FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    for entry in results:
        print(f"  {entry['id']}: {entry['filename']} payload={entry['payload']}")
    print(f"validation-fixtures: PASS ({len(results)} declared)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
