#!/usr/bin/env python3
"""Add or replace a save fixture in `tools/validation-fixtures.json`.

Takes the save file plus a description of what it contains, computes the
identity fields, optionally copies the payload into the repository, writes the
declaration, and refuses to write anything that would not pass
`scripts/validate_validation_fixtures.py`.

Runtime properties default to `unverified`: a save may enter the repository on
its description, but no consumer may rely on it until a named runtime
experiment confirms the properties on the exact target. Promoting a fixture is
a deliberate second step (`--evidence runtime --verified-by ...`).

Example:

    python scripts/add_validation_fixture.py \\
      --save /path/to/resume-multi.gam \\
      --id resume-en-multi-planet \\
      --role m1-multi-planet \\
      --storage repository \\
      --repository-path fixtures/saves/resume-multi.gam \\
      --player-planet "Alpha I" --player-planet "Beta II" \\
      --empty-action-planet "Beta II"
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_validation_fixtures as validator  # noqa: E402

CANONICAL_TARGET_SHA256 = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"


def build_entry(args: argparse.Namespace, save: Path) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "evidence": args.evidence,
        "player_race_id": args.player_race_id,
        "player_owned_planet_count": len(args.player_planet),
        "player_planet_names": list(args.player_planet),
        "planets_with_empty_current_action_at_load": list(args.empty_action_planet),
    }
    if args.verified_by:
        properties["source"] = args.verified_by

    entry: dict[str, Any] = {
        "id": args.id,
        "filename": save.name,
        "role": args.role,
        "storage": args.storage,
        "size": save.stat().st_size,
        "sha256": validator.sha256_file(save),
        "produced_by_target_sha256": args.produced_by_target_sha256,
        "runtime_properties": properties,
    }
    if args.storage == validator.REPOSITORY_STORAGE:
        entry["repository_path"] = args.repository_path
    if args.limitation:
        entry["limitations"] = list(args.limitation)
    if args.used_by:
        entry["used_by"] = list(args.used_by)
    return entry


def resolve_destination(
    entry: dict[str, Any], save: Path, previous: dict[str, Any] | None
) -> Path | None:
    """Resolve and containment-check the destination without touching the disk.

    An existing destination is accepted only when it is this fixture's own
    already-committed payload and its content matches the incoming save. That
    keeps promotion working — the second run supplies the same save from its
    original path — while still refusing to overwrite an unrelated file or to
    swap different bytes in under an identifier other work is pinned to.
    """
    if entry["storage"] != validator.REPOSITORY_STORAGE:
        return None
    destination = (ROOT / entry["repository_path"]).resolve()
    try:
        destination.relative_to(ROOT.resolve())
    except ValueError:
        raise validator.FixtureDeclarationError(
            f"repository_path escapes the repository: {entry['repository_path']}"
        ) from None
    if destination == save.resolve() or not destination.exists():
        return destination

    same_fixture = previous is not None and previous.get("repository_path") == entry["repository_path"]
    if not same_fixture:
        raise validator.FixtureDeclarationError(
            f"refusing to overwrite existing {entry['repository_path']}; it does not belong "
            f"to fixture {entry['id']!r}"
        )
    if validator.sha256_file(destination) != entry["sha256"]:
        raise validator.FixtureDeclarationError(
            f"{entry['repository_path']} already holds different bytes for fixture "
            f"{entry['id']!r}; declare a new fixture id rather than swapping the payload "
            "under one that existing evidence is pinned to"
        )
    return destination


def place_payload(save: Path, destination: Path | None) -> bool:
    """Copy the payload if needed; report whether this call created the file."""
    if destination is None or destination == save.resolve():
        return False
    if destination.exists():
        # Identical bytes by the time we get here, so there is nothing to write
        # and nothing this invocation would be entitled to roll back.
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(save, destination)
    except Exception:
        # copy2 may have created a partial destination before failing. It did
        # not exist on entry, so removing it cannot destroy prior repository
        # state.
        destination.unlink(missing_ok=True)
        raise
    return True


def merge_entry(
    document: dict[str, Any], entry: dict[str, Any], replace: bool
) -> dict[str, Any] | None:
    """Insert or replace the entry, returning the declaration it displaced."""
    fixtures = document["fixtures"]
    existing = [item for item in fixtures if item["id"] == entry["id"]]
    if existing and not replace:
        raise validator.FixtureDeclarationError(
            f"fixture {entry['id']!r} already declared; pass --replace to update it"
        )
    if existing:
        previous = existing[0]
        # The identity guard belongs to the fixture id, not to any path: other
        # evidence is pinned to this id, so the bytes behind it may never change
        # regardless of where the payload is read from or written to.
        if previous["sha256"] != entry["sha256"]:
            raise validator.FixtureDeclarationError(
                f"fixture {entry['id']!r} is declared with SHA-256 {previous['sha256']} and the "
                f"supplied save is {entry['sha256']}; declare a new fixture id rather than "
                "rebinding an identifier existing evidence is pinned to"
            )
        fixtures[fixtures.index(previous)] = entry
        return previous
    fixtures.append(entry)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--save", type=Path, required=True, help="Path to the save file.")
    parser.add_argument("--id", required=True, help="Stable fixture identifier.")
    parser.add_argument("--role", required=True)
    parser.add_argument(
        "--storage", choices=validator.SUPPORTED_STORAGE, default=validator.REPOSITORY_STORAGE
    )
    parser.add_argument(
        "--repository-path",
        default=None,
        help="Relative destination inside the repository; required for committed fixtures.",
    )
    parser.add_argument("--player-race-id", type=int, default=0)
    parser.add_argument(
        "--player-planet",
        action="append",
        default=[],
        metavar="NAME",
        help="Name of a player-owned planet; repeat once per planet.",
    )
    parser.add_argument(
        "--empty-action-planet",
        action="append",
        default=[],
        metavar="NAME",
        help="Player planet with no current action at load; repeat as needed.",
    )
    parser.add_argument("--evidence", choices=("unverified", "runtime", "static"), default="unverified")
    parser.add_argument(
        "--verified-by",
        default=None,
        help="Document establishing the runtime properties; required with --evidence runtime.",
    )
    parser.add_argument("--produced-by-target-sha256", default=CANONICAL_TARGET_SHA256)
    parser.add_argument("--limitation", action="append", default=[])
    parser.add_argument("--used-by", action="append", default=[])
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--declaration", type=Path, default=validator.DEFAULT_DECLARATION)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the entry without copying the payload or writing the file.",
    )
    args = parser.parse_args(argv)

    try:
        save = args.save.expanduser().resolve()
        if not save.is_file():
            raise validator.FixtureDeclarationError(f"save not found: {args.save}")
        if not args.player_planet:
            raise validator.FixtureDeclarationError(
                "at least one --player-planet is required; the declaration must say what the "
                "save actually contains"
            )
        if args.storage == validator.REPOSITORY_STORAGE and not args.repository_path:
            raise validator.FixtureDeclarationError(
                "--repository-path is required when the payload is committed"
            )
        if args.evidence == "runtime" and not args.verified_by:
            raise validator.FixtureDeclarationError(
                "--verified-by is required with --evidence runtime; name the experiment record "
                "that established the properties on the exact target"
            )

        document = json.loads(args.declaration.read_text(encoding="utf-8"))
        entry = build_entry(args, save)
        previous = merge_entry(document, entry, args.replace)

        # Everything that can reject the request runs before anything is
        # written, so a failed invocation leaves no copied payload behind and
        # no half-updated declaration.
        destination = resolve_destination(entry, save, previous)
        fixtures = validator.check_declaration(json.loads(json.dumps(document)))
        status = next(item for item in fixtures if item["id"] == entry["id"])["_role_status"]
        if args.evidence == validator.VERIFIED_EVIDENCE and not status["satisfied"]:
            raise validator.FixtureDeclarationError(
                f"runtime promotion for fixture {entry['id']!r} is not usable: "
                f"{status['reason']}"
            )

        if not args.dry_run:
            created = place_payload(save, destination)
            try:
                validator.check_payloads(fixtures, None, require_present=False)
                args.declaration.write_text(
                    json.dumps(document, indent=2, sort_keys=False) + "\n", encoding="utf-8"
                )
            except Exception:
                # Only undo what this invocation created; a payload that was
                # already committed belongs to the repository, not to this run.
                if created and destination is not None:
                    destination.unlink(missing_ok=True)
                raise
    except (validator.FixtureDeclarationError, json.JSONDecodeError, OSError) as exc:
        print(f"add-validation-fixture: FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    prefix = "would add" if args.dry_run else "added"
    print(f"add-validation-fixture: {prefix} {entry['id']}")
    print(f"  size {entry['size']} sha256 {entry['sha256']}")
    if destination is not None:
        print(f"  payload {'would be ' if args.dry_run else ''}committed at {entry['repository_path']}")
    else:
        print(f"  payload stays maintainer-supplied; provide {entry['filename']} at run time")
    if status["satisfied"]:
        print(f"  role {entry['role']}: usable")
    else:
        print(f"  role {entry['role']}: NOT usable yet — {status['reason']}")
        print("  next: run the fixture on the exact target, record the experiment, then re-run")
        print(f"        this script with --replace --evidence runtime --verified-by <doc>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
