#!/usr/bin/env python3
"""Validate the save-fixture declarations in `tools/validation-fixtures.json`.

A fixture payload may be committed (`storage: repository`) or maintainer-supplied
and referenced by hash (`storage: operator-supplied`), so this check has two
independent halves:

* the declaration is always checked — schema, required fields, role
  requirements, and evidence level;
* payload identity is checked by size and SHA-256 whenever the payload is
  reachable. A committed payload must always be present; a maintainer-supplied
  one is verified only when a fixture directory actually provides it.

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
REPOSITORY_STORAGE = "repository"
OPERATOR_STORAGE = "operator-supplied"
SUPPORTED_STORAGE = (REPOSITORY_STORAGE, OPERATOR_STORAGE)
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
        if fixture["storage"] not in SUPPORTED_STORAGE:
            raise FixtureDeclarationError(
                f"fixture {identifier!r} declares unknown storage {fixture['storage']!r}; "
                f"expected one of {list(SUPPORTED_STORAGE)}"
            )
        if fixture["storage"] == REPOSITORY_STORAGE:
            repository_path = fixture.get("repository_path")
            if not repository_path:
                raise FixtureDeclarationError(
                    f"fixture {identifier!r} declares storage {REPOSITORY_STORAGE!r} "
                    "without a repository_path"
                )
            if Path(repository_path).is_absolute() or ".." in Path(repository_path).parts:
                raise FixtureDeclarationError(
                    f"fixture {identifier!r} repository_path must be a relative path "
                    "inside the repository"
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

        fixture["_role_status"] = check_role_requirements(identifier, fixture, requirements)

    return fixtures


def check_role_requirements(
    identifier: str, fixture: dict[str, Any], requirements: dict[str, Any]
) -> dict[str, Any]:
    """Decide whether a fixture may be used for its declared role.

    A fixture whose runtime properties are still `unverified` is a legitimate
    declaration — that is how a save enters the repository before a runtime
    experiment confirms it — but it never satisfies a role. Declared-but-wrong
    properties are a different matter and fail closed: if a fixture claims
    verified evidence, its numbers must support the role it claims.
    """
    required = requirements.get(fixture["role"])
    if required is None:
        return {"role": fixture["role"], "satisfied": True, "reason": "role has no requirements"}
    properties = fixture["runtime_properties"]
    if properties["evidence"] == "unverified":
        return {
            "role": fixture["role"],
            "satisfied": False,
            "reason": "runtime properties are unverified; confirm them in a named runtime "
            "experiment before any consumer relies on this fixture",
        }
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
                f"fixture {identifier!r} declares verified properties that contradict role "
                f"{fixture['role']!r}: {key} is {observed[key]}, requires at least {minimum}"
            )
    return {"role": fixture["role"], "satisfied": True, "reason": "verified"}


def check_payloads(
    fixtures: list[dict[str, Any]], fixture_dir: Path | None, require_present: bool
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for fixture in fixtures:
        entry: dict[str, Any] = {"id": fixture["id"], "filename": fixture["filename"]}
        committed = fixture["storage"] == REPOSITORY_STORAGE
        if committed:
            path = ROOT / fixture["repository_path"]
        else:
            path = None if fixture_dir is None else fixture_dir / fixture["filename"]
        if path is None or not path.is_file():
            if committed:
                raise FixtureDeclarationError(
                    f"fixture {fixture['id']!r} declares storage {REPOSITORY_STORAGE!r} "
                    f"but {fixture['filename']} is not in the repository"
                )
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
    parser.add_argument(
        "--require-role",
        default=None,
        help="Fail unless at least one fixture satisfies this role with verified properties.",
    )
    args = parser.parse_args(argv)

    try:
        document = json.loads(args.declaration.read_text(encoding="utf-8"))
        fixtures = check_declaration(document)
        results = check_payloads(fixtures, args.fixture_dir, args.require_present)
        if args.require_role is not None:
            satisfying = [
                fixture["id"]
                for fixture in fixtures
                if fixture["role"] == args.require_role and fixture["_role_status"]["satisfied"]
            ]
            if not satisfying:
                raise FixtureDeclarationError(
                    f"no fixture satisfies role {args.require_role!r} with verified "
                    "runtime properties"
                )
    except (FixtureDeclarationError, json.JSONDecodeError, OSError) as exc:
        print(f"validation-fixtures: FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    status = {fixture["id"]: fixture["_role_status"] for fixture in fixtures}
    for entry in results:
        role = status[entry["id"]]
        mark = "usable" if role["satisfied"] else "NOT usable"
        print(
            f"  {entry['id']}: {entry['filename']} payload={entry['payload']} "
            f"role={role['role']} ({mark})"
        )
        if not role["satisfied"]:
            print(f"      {role['reason']}")
    print(f"validation-fixtures: PASS ({len(results)} declared)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
