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
import re
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DECLARATION = ROOT / "tools" / "validation-fixtures.json"
SUPPORTED_SCHEMA = 1
CANONICAL_TARGET_SHA256 = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
VERIFIED_EVIDENCE = "runtime"
EXPERIMENT_RECORD_PREFIX = ("docs", "experiments")
RUNTIME_EVIDENCE_MARKER = "Evidence class: **runtime**"
OBSERVATION_BLOCK_MARKER = "<!-- validation-fixture-observations:v1 -->"
OBSERVATION_BLOCK_SCHEMA = 1
PRODUCTION_BLOCK_MARKER = "<!-- validation-fixture-production:v1 -->"
PRODUCTION_BLOCK_SCHEMA = 1
PRODUCTION_RUN_ARTIFACT_SCHEMA = "ascendancy.validation-fixture-producer/v1"
PRODUCTION_RUN_CONTRACT = "validation-fixture/canonical-target-exact-byte-producer/v1"
CANONICAL_TARGET_SIZE = 610863
PRODUCER_EVIDENCE_LEVELS = ("runtime", "reported", "unverified")
PRODUCTION_REQUIREMENT_KEY = "requires_runtime_canonical_target_production"
CURRENT_STATE_ARTIFACT_REQUIREMENT_KEY = "requires_detached_runtime_observation_artifact"
CURRENT_STATE_RUN_ARTIFACT_SCHEMA = "ascendancy.t3-multi-planet-fixture/v2"
CURRENT_STATE_RUN_CONTRACT = "t3/operator-save-runtime-verify/v2"
CANONICAL_RETAIL_FIXTURE_ID = "ascendancy-retail-en-canonical-antagonizer-runtime-fixture"
CANONICAL_RETAIL_FIXTURE_MANIFEST_SHA256 = "814c37ea8683e9c32ce494bcb9568d08a33d3ef8e6d91b99ac07f37958269852"
CANONICAL_RETAIL_FIXTURE_VERIFIED_FILES = 17
OBSERVED_RUNTIME_PROPERTY_FIELDS = (
    "player_race_id",
    "player_owned_planet_count",
    "player_planet_names",
    "planets_with_empty_current_action_at_load",
)
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

        producer = fixture.get("producer_provenance")
        if producer is not None:
            if not isinstance(producer, dict):
                raise FixtureDeclarationError(f"fixture {identifier!r} producer_provenance must be an object")
            evidence = producer.get("evidence")
            if evidence not in PRODUCER_EVIDENCE_LEVELS:
                raise FixtureDeclarationError(f"fixture {identifier!r} producer_provenance evidence must be one of {list(PRODUCER_EVIDENCE_LEVELS)}, got {evidence!r}")
            source = producer.get("source")
            if source is not None and (not isinstance(source, str) or not source.strip()):
                raise FixtureDeclarationError(f"fixture {identifier!r} producer_provenance source must be a non-empty string")
            if evidence != "unverified" and not source:
                raise FixtureDeclarationError(f"fixture {identifier!r} producer_provenance evidence {evidence!r} must name a source")

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


def parse_source_observations(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """Parse the single machine-readable runtime-property block from an experiment."""
    marker_count = text.count(OBSERVATION_BLOCK_MARKER)
    if marker_count != 1:
        return None, (
            f"runtime experiment must contain exactly one {OBSERVATION_BLOCK_MARKER!r} "
            f"block; found {marker_count}"
        )

    tail = text.split(OBSERVATION_BLOCK_MARKER, 1)[1].lstrip()
    lines = tail.splitlines()
    if not lines or lines[0].strip() != "```json":
        return None, "runtime observation marker must be followed by a fenced JSON block"
    try:
        fence_end = next(
            index for index, line in enumerate(lines[1:], start=1) if line.strip() == "```"
        )
    except StopIteration:
        return None, "runtime observation JSON block has no closing fence"

    payload = "\n".join(lines[1:fence_end])
    try:
        observations = json.loads(payload)
    except json.JSONDecodeError as exc:
        return None, f"runtime observation block is not valid JSON: {exc}"
    if not isinstance(observations, dict):
        return None, "runtime observation block must be a JSON object"
    return observations, None

def check_current_state_run_artifact(
    artifact_path_text: Any,
    artifact_sha256: Any,
    fixture: dict[str, Any],
) -> str | None:
    """Validate the detached run artifact behind role-critical current-state evidence."""
    if not isinstance(artifact_path_text, str) or not artifact_path_text.strip():
        return "runtime observation block must name a detached run artifact"
    if not isinstance(artifact_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", artifact_sha256) is None:
        return "runtime observation block must pin the detached run artifact with a lowercase SHA-256"

    artifact_path = Path(artifact_path_text)
    if artifact_path.is_absolute():
        return f"runtime observation artifact {artifact_path_text!r} must be repository-relative"
    resolved = (ROOT / artifact_path).resolve()
    try:
        relative = resolved.relative_to(ROOT.resolve())
    except ValueError:
        return f"runtime observation artifact {artifact_path_text!r} escapes the repository"
    if relative.parts[:2] != EXPERIMENT_RECORD_PREFIX or resolved.suffix.lower() != ".json":
        return (
            f"runtime observation artifact {artifact_path_text!r} must be a JSON record under "
            "docs/experiments/"
        )
    if not resolved.is_file():
        return f"runtime observation artifact {artifact_path_text!r} does not resolve in the supported repository state"
    actual_sha256 = sha256_file(resolved)
    if actual_sha256 != artifact_sha256:
        return (
            f"runtime observation artifact {artifact_path_text!r} sha256 {actual_sha256} "
            f"does not match pinned {artifact_sha256}"
        )

    try:
        artifact = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"runtime observation artifact {artifact_path_text!r} is not readable JSON: {exc}"
    if not isinstance(artifact, dict):
        return f"runtime observation artifact {artifact_path_text!r} must be a JSON object"
    if artifact.get("artifact_schema") != CURRENT_STATE_RUN_ARTIFACT_SCHEMA:
        return (
            f"runtime observation artifact schema is {artifact.get('artifact_schema')!r}; "
            f"expected {CURRENT_STATE_RUN_ARTIFACT_SCHEMA!r}"
        )
    if artifact.get("scenario_contract") != CURRENT_STATE_RUN_CONTRACT:
        return (
            f"runtime observation artifact contract is {artifact.get('scenario_contract')!r}; "
            f"expected {CURRENT_STATE_RUN_CONTRACT!r}"
        )
    if artifact.get("evidence_class") != VERIFIED_EVIDENCE or artifact.get("status") != "passed":
        return "runtime observation artifact must be a passed runtime record"
    if artifact.get("blind_re_provenance") != "clean":
        return "runtime observation artifact must declare clean blind-RE provenance"

    candidate = artifact.get("candidate_fixture")
    if not isinstance(candidate, dict):
        return "runtime observation artifact has no candidate fixture identity"
    if (
        candidate.get("id") != fixture["id"]
        or candidate.get("sha256") != fixture["sha256"]
        or candidate.get("size") != fixture["size"]
    ):
        return "runtime observation artifact is for a different fixture identity"
    if candidate.get("source_unchanged") is not True:
        return "runtime observation artifact does not prove the source fixture remained unchanged"

    target = artifact.get("target")
    if not isinstance(target, dict):
        return "runtime observation artifact has no target identity"
    if target.get("sha256") != CANONICAL_TARGET_SHA256 or target.get("size") != CANONICAL_TARGET_SIZE:
        return "runtime observation artifact target identity does not match canonical ANTAG.EXE"

    retail_fixture = artifact.get("retail_fixture")
    if not isinstance(retail_fixture, dict):
        return "runtime observation artifact has no canonical retail fixture identity"
    if (
        retail_fixture.get("id") != CANONICAL_RETAIL_FIXTURE_ID
        or retail_fixture.get("manifest_sha256") != CANONICAL_RETAIL_FIXTURE_MANIFEST_SHA256
        or retail_fixture.get("verified_files") != CANONICAL_RETAIL_FIXTURE_VERIFIED_FILES
    ):
        return "runtime observation artifact retail fixture identity does not match the canonical runtime fixture"

    if artifact.get("diagnostic_guest_code_writes") is not False:
        return "runtime observation artifact must record diagnostic_guest_code_writes=false"
    if artifact.get("diagnostic_guest_data_writes") is not False:
        return "runtime observation artifact must record diagnostic_guest_data_writes=false"
    if artifact.get("source_inputs_modified") is not False:
        return "runtime observation artifact must record source_inputs_modified=false"

    environment = artifact.get("runtime_environment")
    if not isinstance(environment, dict):
        return "runtime observation artifact has no runtime_environment"
    dosbox = environment.get("dosbox")
    if not isinstance(dosbox, dict):
        return "runtime observation artifact has no DOSBox identity"
    if not isinstance(dosbox.get("filename"), str) or not dosbox["filename"].strip():
        return "runtime observation artifact DOSBox identity has no filename"
    if not isinstance(dosbox.get("size"), int) or dosbox["size"] <= 0:
        return "runtime observation artifact DOSBox identity has no positive size"
    if not isinstance(dosbox.get("sha256"), str) or re.fullmatch(r"[0-9a-f]{64}", dosbox["sha256"]) is None:
        return "runtime observation artifact DOSBox identity has no valid SHA-256"
    if not isinstance(dosbox.get("version_output"), str) or not dosbox["version_output"].strip():
        return "runtime observation artifact DOSBox identity has no version output"
    dosbox_config = environment.get("dosbox_config")
    if not isinstance(dosbox_config, dict) or not dosbox_config:
        return "runtime observation artifact has no material DOSBox configuration"

    runner_source_sha256 = artifact.get("runner_source_sha256")
    if not isinstance(runner_source_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", runner_source_sha256) is None:
        return "runtime observation artifact has no valid runner source SHA-256"
    dependencies = artifact.get("harness_dependencies")
    required_dependencies = {
        "run_re4_runtime_state.py",
        "run_re5_runtime_turn_path.py",
        "run_re5_override_witness.py",
        "le_image.py",
    }
    if not isinstance(dependencies, dict) or set(dependencies) != required_dependencies:
        return "runtime observation artifact does not pin the complete T3 harness dependency set"
    for name, digest in dependencies.items():
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            return f"runtime observation artifact harness dependency {name!r} has no valid SHA-256"

    snapshots = artifact.get("harness_source_snapshots")
    required_snapshot_names = {"run_t3_multi_planet_fixture.py", *required_dependencies}
    if not isinstance(snapshots, dict) or set(snapshots) != required_snapshot_names:
        return "runtime observation artifact does not pin the complete execution harness source snapshot set"
    for name, snapshot_text in snapshots.items():
        if not isinstance(snapshot_text, str) or not snapshot_text.strip():
            return f"runtime observation artifact harness snapshot {name!r} has no path"
        snapshot_path = Path(snapshot_text)
        if snapshot_path.is_absolute():
            return f"runtime observation artifact harness snapshot {name!r} must be repository-relative"
        resolved_snapshot = (ROOT / snapshot_path).resolve()
        try:
            relative_snapshot = resolved_snapshot.relative_to(ROOT.resolve())
        except ValueError:
            return f"runtime observation artifact harness snapshot {name!r} escapes the repository"
        if relative_snapshot.parts[:2] != EXPERIMENT_RECORD_PREFIX:
            return f"runtime observation artifact harness snapshot {name!r} must live under docs/experiments/"
        if resolved_snapshot.name != name or not resolved_snapshot.is_file():
            return f"runtime observation artifact harness snapshot {name!r} does not resolve to the named source file"
        expected_digest = runner_source_sha256 if name == "run_t3_multi_planet_fixture.py" else dependencies[name]
        actual_digest = sha256_file(resolved_snapshot)
        if actual_digest != expected_digest:
            return (
                f"runtime observation artifact harness snapshot {name!r} sha256 {actual_digest} "
                f"does not match pinned {expected_digest}"
            )

    role_claim = artifact.get("role_claim")
    if not isinstance(role_claim, dict) or role_claim.get("role") != fixture["role"]:
        return "runtime observation artifact role claim does not match the fixture role"
    declared = fixture["runtime_properties"]
    role_pairs = (
        ("player_race_id", "player_race_id"),
        ("player_owned_planet_count", "player_owned_planet_count"),
        ("player_planet_names", "player_planet_names"),
        ("planets_with_empty_current_action_at_load", "planets_with_empty_current_action_at_load"),
    )
    for artifact_key, declared_key in role_pairs:
        if role_claim.get(artifact_key) != declared[declared_key]:
            return f"runtime observation artifact role claim {artifact_key!r} does not match the declaration"

    verification = artifact.get("verification")
    if not isinstance(verification, dict) or verification.get("status") != "passed":
        return "runtime observation artifact verification did not terminate successfully"
    if verification.get("process_stopped_for_coherent_snapshot") is not True:
        return "runtime observation artifact did not record a coherent stopped-process snapshot"
    if verification.get("save_unchanged_by_verification_load") is not True:
        return "runtime observation artifact did not prove the fixture remained unchanged after load"
    mapping = verification.get("runtime_mapping")
    if not isinstance(mapping, dict) or mapping.get("status") != "passed":
        return "runtime observation artifact runtime mapping did not pass"
    observation = verification.get("observation")
    if not isinstance(observation, dict) or observation.get("status") != "passed":
        return "runtime observation artifact observation oracle did not pass"
    checks = observation.get("checks")
    if not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
        return "runtime observation artifact observation checks are not all true"
    observed_pairs = (
        ("current_player_id", "player_race_id"),
        ("player_owned_planet_count", "player_owned_planet_count"),
        ("player_planet_names", "player_planet_names"),
        ("planets_with_empty_current_action_at_load", "planets_with_empty_current_action_at_load"),
    )
    for artifact_key, declared_key in observed_pairs:
        if observation.get(artifact_key) != declared[declared_key]:
            return f"runtime observation artifact observed {artifact_key!r} does not match the declaration"
    return None


def check_source_record(
    source: str, fixture: dict[str, Any], *, require_artifact: bool = False
) -> str | None:
    """Return why `source` does not establish this fixture's declared runtime properties.

    A runtime source must bind both identities and every role-critical property in
    a structured observation block. Merely mentioning the save/target hashes in
    prose is insufficient because a declaration could otherwise promote values
    that the experiment never observed.
    """
    fixture_sha256 = fixture["sha256"]
    target_sha256 = CANONICAL_TARGET_SHA256
    source_path = Path(source)
    if source_path.is_absolute():
        return f"source {source!r} must be a repository-relative path"
    resolved = (ROOT / source_path).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        return f"source {source!r} escapes the repository"
    if not resolved.is_file():
        return (
            f"source {source!r} does not resolve to a record in the supported repository "
            "state; a named path that does not exist is an assertion, not evidence"
        )
    relative = resolved.relative_to(ROOT.resolve())
    if relative.parts[:2] != EXPERIMENT_RECORD_PREFIX or resolved.suffix.lower() != ".md":
        return (
            f"source {source!r} is not a Markdown runtime experiment record under "
            "docs/experiments/; policy/RE prose cannot satisfy a runtime role"
        )
    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"source {source!r} could not be read: {exc}"
    if RUNTIME_EVIDENCE_MARKER not in text:
        return (
            f"source {source!r} does not declare {RUNTIME_EVIDENCE_MARKER!r}; "
            "an experiment path alone is not runtime evidence"
        )
    if fixture_sha256 not in text:
        return (
            f"source {source!r} never names this fixture's SHA-256, so it does not establish "
            "anything about this save"
        )
    if target_sha256 not in text:
        return (
            f"source {source!r} never names runtime target SHA-256 {target_sha256}; "
            "the current-state observations are not bound to the canonical target"
        )

    observations, observation_problem = parse_source_observations(text)
    if observation_problem is not None:
        return f"source {source!r} has no usable structured runtime observations: {observation_problem}"
    assert observations is not None
    if observations.get("schema") != OBSERVATION_BLOCK_SCHEMA:
        return (
            f"source {source!r} observation schema is {observations.get('schema')!r}; "
            f"expected {OBSERVATION_BLOCK_SCHEMA}"
        )
    if observations.get("fixture_sha256") != fixture_sha256:
        return f"source {source!r} structured observations are for a different fixture SHA-256"
    if observations.get("target_sha256") != target_sha256:
        return f"source {source!r} structured observations are for a different target SHA-256"

    observed_properties = observations.get("runtime_properties")
    if not isinstance(observed_properties, dict):
        return f"source {source!r} structured observations have no runtime_properties object"
    declared_properties = fixture["runtime_properties"]
    for field in OBSERVED_RUNTIME_PROPERTY_FIELDS:
        if field not in observed_properties:
            return f"source {source!r} structured observations omit {field!r}"
        if observed_properties[field] != declared_properties[field]:
            return (
                f"source {source!r} observed {field}={observed_properties[field]!r}, "
                f"but the fixture declares {declared_properties[field]!r}"
            )
    if require_artifact:
        artifact_problem = check_current_state_run_artifact(
            observations.get("artifact"), observations.get("artifact_sha256"), fixture
        )
        if artifact_problem:
            return f"source {source!r} detached runtime evidence is not usable: {artifact_problem}"
    return None


def parse_source_production(text: str) -> tuple[dict[str, Any] | None, str | None]:
    count = text.count(PRODUCTION_BLOCK_MARKER)
    if count != 1:
        return None, f"runtime producer experiment must contain exactly one {PRODUCTION_BLOCK_MARKER!r} block; found {count}"
    lines = text.split(PRODUCTION_BLOCK_MARKER, 1)[1].lstrip().splitlines()
    if not lines or lines[0].strip() != "```json":
        return None, "runtime producer marker must be followed by a fenced JSON block"
    try:
        end = next(i for i,line in enumerate(lines[1:],1) if line.strip()=="```")
    except StopIteration:
        return None, "runtime producer JSON block has no closing fence"
    try:
        value=json.loads("\n".join(lines[1:end]))
    except json.JSONDecodeError as exc:
        return None, f"runtime producer block is not valid JSON: {exc}"
    return (value,None) if isinstance(value,dict) else (None,"runtime producer block must be a JSON object")


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def check_production_run_artifact(
    artifact_path_text: str,
    artifact_sha256: str,
    fixture: dict[str, Any],
    method: str,
) -> str | None:
    """Validate the detached run record required for exact-byte producer promotion."""
    if not isinstance(artifact_path_text, str) or not artifact_path_text.strip():
        return "production block must name a detached run artifact"
    if not _valid_sha256(artifact_sha256):
        return "production block must pin the detached run artifact with a lowercase SHA-256"
    artifact_path = Path(artifact_path_text)
    if artifact_path.is_absolute():
        return f"producer run artifact {artifact_path_text!r} must be repository-relative"
    resolved = (ROOT / artifact_path).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        return f"producer run artifact {artifact_path_text!r} escapes the repository"
    relative = resolved.relative_to(ROOT.resolve())
    if relative.parts[:2] != EXPERIMENT_RECORD_PREFIX or resolved.suffix.lower() != ".json":
        return (
            f"producer run artifact {artifact_path_text!r} must be a JSON record under "
            "docs/experiments/"
        )
    if not resolved.is_file():
        return f"producer run artifact {artifact_path_text!r} does not resolve in the supported repository state"
    actual_artifact_sha256 = sha256_file(resolved)
    if actual_artifact_sha256 != artifact_sha256:
        return (
            f"producer run artifact {artifact_path_text!r} sha256 {actual_artifact_sha256} "
            f"does not match pinned {artifact_sha256}"
        )
    try:
        artifact = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"producer run artifact {artifact_path_text!r} is not readable JSON: {exc}"
    if not isinstance(artifact, dict):
        return f"producer run artifact {artifact_path_text!r} must be a JSON object"
    if artifact.get("artifact_schema") != PRODUCTION_RUN_ARTIFACT_SCHEMA:
        return (
            f"producer run artifact schema is {artifact.get('artifact_schema')!r}; "
            f"expected {PRODUCTION_RUN_ARTIFACT_SCHEMA!r}"
        )
    if artifact.get("scenario_contract") != PRODUCTION_RUN_CONTRACT:
        return (
            f"producer run artifact contract is {artifact.get('scenario_contract')!r}; "
            f"expected {PRODUCTION_RUN_CONTRACT!r}"
        )
    if artifact.get("evidence_class") != VERIFIED_EVIDENCE or artifact.get("status") != "passed":
        return "producer run artifact must be a passed runtime record"
    if artifact.get("blind_re_provenance") != "clean":
        return "producer run artifact must declare clean blind-RE provenance"

    target = artifact.get("target")
    if not isinstance(target, dict):
        return "producer run artifact has no target identity"
    if target.get("sha256") != CANONICAL_TARGET_SHA256 or target.get("size") != CANONICAL_TARGET_SIZE:
        return "producer run artifact target identity does not match canonical ANTAG.EXE"

    retail_fixture = artifact.get("retail_fixture")
    if not isinstance(retail_fixture, dict):
        return "producer run artifact has no canonical retail fixture identity"
    if (
        retail_fixture.get("id") != CANONICAL_RETAIL_FIXTURE_ID
        or retail_fixture.get("manifest_sha256") != CANONICAL_RETAIL_FIXTURE_MANIFEST_SHA256
        or retail_fixture.get("verified_files") != CANONICAL_RETAIL_FIXTURE_VERIFIED_FILES
    ):
        return "producer run artifact retail fixture identity does not match the canonical runtime fixture"

    produced = artifact.get("fixture")
    if not isinstance(produced, dict):
        return "producer run artifact has no produced fixture identity"
    if produced.get("sha256") != fixture["sha256"] or produced.get("size") != fixture["size"]:
        return "producer run artifact is for different fixture bytes"
    if produced.get("target_written_exact_bytes") is not True:
        return "producer run artifact does not assert target_written_exact_bytes=true"

    environment = artifact.get("runtime_environment")
    if not isinstance(environment, dict):
        return "producer run artifact has no runtime_environment"
    dosbox = environment.get("dosbox")
    if not isinstance(dosbox, dict):
        return "producer run artifact has no DOSBox identity"
    if not isinstance(dosbox.get("filename"), str) or not dosbox["filename"].strip():
        return "producer run artifact DOSBox identity has no filename"
    if not isinstance(dosbox.get("size"), int) or dosbox["size"] <= 0:
        return "producer run artifact DOSBox identity has no positive size"
    if not _valid_sha256(dosbox.get("sha256")):
        return "producer run artifact DOSBox identity has no valid SHA-256"
    if not isinstance(dosbox.get("version_output"), str) or not dosbox["version_output"].strip():
        return "producer run artifact DOSBox identity has no version output"
    configuration = environment.get("configuration")
    if not isinstance(configuration, dict) or not configuration:
        return "producer run artifact has no material runtime configuration"

    harness = artifact.get("harness")
    if not isinstance(harness, dict):
        return "producer run artifact has no harness identity"
    harness_source = harness.get("source")
    harness_sha256 = harness.get("source_sha256")
    if not isinstance(harness_source, str) or not harness_source.strip():
        return "producer run artifact harness has no repository source"
    if not _valid_sha256(harness_sha256):
        return "producer run artifact harness has no valid source SHA-256"
    harness_path = Path(harness_source)
    if harness_path.is_absolute():
        return "producer run artifact harness source must be repository-relative"
    harness_resolved = (ROOT / harness_path).resolve()
    try:
        harness_relative = harness_resolved.relative_to(ROOT.resolve())
    except ValueError:
        return "producer run artifact harness source escapes the repository"
    if not harness_resolved.is_file() or harness_relative.parts[:1] != ("scripts",) or harness_resolved.suffix != ".py":
        return "producer run artifact harness source must resolve to a Python script under scripts/"

    snapshot_text = harness.get("source_snapshot")
    if not isinstance(snapshot_text, str) or not snapshot_text.strip():
        return "producer run artifact harness must preserve the exact executed source_snapshot"
    snapshot_path = Path(snapshot_text)
    if snapshot_path.is_absolute():
        return "producer run artifact harness source_snapshot must be repository-relative"
    snapshot_resolved = (ROOT / snapshot_path).resolve()
    try:
        snapshot_relative = snapshot_resolved.relative_to(ROOT.resolve())
    except ValueError:
        return "producer run artifact harness source_snapshot escapes the repository"
    if snapshot_relative.parts[:2] != EXPERIMENT_RECORD_PREFIX:
        return "producer run artifact harness source_snapshot must live under docs/experiments/"
    if snapshot_resolved.suffix != ".py" or not snapshot_resolved.is_file():
        return "producer run artifact harness source_snapshot must resolve to a preserved Python source file"
    if sha256_file(snapshot_resolved) != harness_sha256:
        return "producer run artifact harness source_snapshot SHA-256 does not match source_sha256"

    dependencies = harness.get("dependencies")
    required_dependencies = {
        "run_t3_multi_planet_fixture.py",
        "run_re4_runtime_state.py",
        "run_re5_runtime_turn_path.py",
        "run_re5_override_witness.py",
        "le_image.py",
    }
    if not isinstance(dependencies, dict) or set(dependencies) != required_dependencies:
        return "producer run artifact harness does not pin the complete T3 producer dependency set"
    for name, digest in dependencies.items():
        if not _valid_sha256(digest):
            return f"producer run artifact harness dependency {name!r} has no valid SHA-256"

    source_snapshots = harness.get("source_snapshots")
    required_snapshot_names = {"run_t3_target_written_fixture.py", *required_dependencies}
    if not isinstance(source_snapshots, dict) or set(source_snapshots) != required_snapshot_names:
        return "producer run artifact harness does not pin the complete producer source snapshot set"
    for name, snapshot_value in source_snapshots.items():
        if not isinstance(snapshot_value, str) or not snapshot_value.strip():
            return f"producer run artifact harness snapshot {name!r} has no path"
        dependency_snapshot = Path(snapshot_value)
        if dependency_snapshot.is_absolute():
            return f"producer run artifact harness snapshot {name!r} must be repository-relative"
        dependency_resolved = (ROOT / dependency_snapshot).resolve()
        try:
            dependency_relative = dependency_resolved.relative_to(ROOT.resolve())
        except ValueError:
            return f"producer run artifact harness snapshot {name!r} escapes the repository"
        if dependency_relative.parts[:2] != EXPERIMENT_RECORD_PREFIX:
            return f"producer run artifact harness snapshot {name!r} must live under docs/experiments/"
        if dependency_resolved.name != name or not dependency_resolved.is_file():
            return f"producer run artifact harness snapshot {name!r} does not resolve to the named source file"
        expected_digest = (
            harness_sha256
            if name == "run_t3_target_written_fixture.py"
            else dependencies[name]
        )
        actual_digest = sha256_file(dependency_resolved)
        if actual_digest != expected_digest:
            return (
                f"producer run artifact harness snapshot {name!r} sha256 {actual_digest} "
                f"does not match pinned {expected_digest}"
            )

    execution = artifact.get("execution")
    if not isinstance(execution, dict):
        return "producer run artifact has no execution record"
    if execution.get("ordinary_game_method") != method:
        return "producer run artifact ordinary-game method does not match the production block"
    for flag in (
        "diagnostic_guest_code_writes",
        "diagnostic_guest_data_writes",
        "source_inputs_modified",
    ):
        if execution.get(flag) is not False:
            return f"producer run artifact requires {flag}=false"
    termination = execution.get("termination")
    if not isinstance(termination, dict) or termination.get("status") != "completed":
        return "producer run artifact does not record completed termination"
    if termination.get("save_write_completed") is not True or termination.get("output_observed_after_save") is not True:
        return "producer run artifact did not observe a completed ordinary save write"

    oracle = artifact.get("oracle")
    if not isinstance(oracle, dict) or oracle.get("status") != "passed":
        return "producer run artifact exact-byte oracle did not pass"
    if oracle.get("exact_byte_match") is not True:
        return "producer run artifact exact-byte oracle is not an exact match"
    if oracle.get("output_sha256") != fixture["sha256"] or oracle.get("output_size") != fixture["size"]:
        return "producer run artifact oracle output identity does not match the fixture"
    return None


def check_production_source_record(source: str, fixture: dict[str, Any]) -> str | None:
    path = Path(source)
    if path.is_absolute():
        return f"producer source {source!r} must be a repository-relative path"
    resolved = (ROOT / path).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        return f"producer source {source!r} escapes the repository"
    if not resolved.is_file():
        return f"producer source {source!r} does not resolve in the supported repository state"
    rel = resolved.relative_to(ROOT.resolve())
    if rel.parts[:2] != EXPERIMENT_RECORD_PREFIX or resolved.suffix.lower() != ".md":
        return f"producer source {source!r} is not a Markdown runtime experiment record under docs/experiments/"
    text = resolved.read_text(encoding="utf-8", errors="replace")
    if RUNTIME_EVIDENCE_MARKER not in text:
        return f"producer source {source!r} does not declare {RUNTIME_EVIDENCE_MARKER!r}; reported provenance is not runtime producer evidence"
    prod, problem = parse_source_production(text)
    if problem:
        return f"producer source {source!r} has no usable structured production evidence: {problem}"
    assert prod is not None
    if prod.get("schema") != PRODUCTION_BLOCK_SCHEMA:
        return f"producer source {source!r} production schema is {prod.get('schema')!r}; expected {PRODUCTION_BLOCK_SCHEMA}"
    if prod.get("fixture_sha256") != fixture["sha256"]:
        return f"producer source {source!r} production block is for different fixture bytes"
    if prod.get("target_sha256") != CANONICAL_TARGET_SHA256:
        return f"producer source {source!r} production block is for a different target"
    if prod.get("target_written_exact_bytes") is not True:
        return f"producer source {source!r} does not assert target_written_exact_bytes=true; load compatibility or a derived re-save is not exact-byte producer evidence"
    method = prod.get("method")
    if not isinstance(method, str) or not method.strip():
        return f"producer source {source!r} production block must name the ordinary-game method"
    artifact_problem = check_production_run_artifact(
        prod.get("artifact"), prod.get("artifact_sha256"), fixture, method
    )
    if artifact_problem:
        return f"producer source {source!r} run artifact is not usable: {artifact_problem}"
    return None


def check_role_requirements(identifier: str, fixture: dict[str, Any], requirements: dict[str, Any]) -> dict[str, Any]:
    """Evaluate current-state runtime evidence and producer provenance independently."""
    required=requirements.get(fixture["role"])
    if required is None: return {"role":fixture["role"],"satisfied":True,"reason":"role has no requirements"}
    props=fixture["runtime_properties"]
    if props["evidence"] != VERIFIED_EVIDENCE:
        return {"role":fixture["role"],"satisfied":False,"reason":f"evidence is {props['evidence']!r}; a role requires {VERIFIED_EVIDENCE!r} properties observed on the canonical target"}
    observed={"min_player_owned_planets":props["player_owned_planet_count"],"min_planets_with_empty_current_action_at_load":len(props["planets_with_empty_current_action_at_load"])}
    needs_prod=required.get(PRODUCTION_REQUIREMENT_KEY,False)
    if not isinstance(needs_prod,bool): raise FixtureDeclarationError(f"role requirement {PRODUCTION_REQUIREMENT_KEY!r} must be boolean")
    needs_runtime_artifact=required.get(CURRENT_STATE_ARTIFACT_REQUIREMENT_KEY,False)
    if not isinstance(needs_runtime_artifact,bool): raise FixtureDeclarationError(f"role requirement {CURRENT_STATE_ARTIFACT_REQUIREMENT_KEY!r} must be boolean")
    for key,minimum in required.items():
        if key in (PRODUCTION_REQUIREMENT_KEY,CURRENT_STATE_ARTIFACT_REQUIREMENT_KEY): continue
        if key not in observed: raise FixtureDeclarationError(f"unknown role requirement {key!r}")
        if not isinstance(minimum,int) or isinstance(minimum,bool): raise FixtureDeclarationError(f"role requirement {key!r} must be an integer")
        if observed[key] < minimum: raise FixtureDeclarationError(f"fixture {identifier!r} declares verified properties that contradict role {fixture['role']!r}: {key} is {observed[key]}, requires at least {minimum}")
    if fixture["produced_by_target_sha256"] != CANONICAL_TARGET_SHA256:
        return {"role":fixture["role"],"satisfied":False,"reason":f"declared producer target is not the canonical target ({CANONICAL_TARGET_SHA256[:12]}…); it cannot satisfy this role"}
    source=props.get("source")
    if not source: return {"role":fixture["role"],"satisfied":False,"reason":"runtime evidence names no source; record the experiment that established these properties"}
    problem=check_source_record(source,fixture,require_artifact=needs_runtime_artifact)
    if problem: return {"role":fixture["role"],"satisfied":False,"reason":problem}
    if needs_prod:
        producer=fixture.get("producer_provenance")
        if not isinstance(producer,dict): return {"role":fixture["role"],"satisfied":False,"reason":"role requires runtime evidence that the canonical target wrote the exact fixture bytes, but producer provenance is not classified"}
        if producer.get("evidence") != VERIFIED_EVIDENCE: return {"role":fixture["role"],"satisfied":False,"reason":f"producer provenance is {producer.get('evidence')!r}; role requires runtime evidence that the canonical target wrote the exact fixture bytes"}
        if not producer.get("source"): return {"role":fixture["role"],"satisfied":False,"reason":"runtime producer evidence names no source experiment"}
        problem=check_production_source_record(producer["source"],fixture)
        if problem: return {"role":fixture["role"],"satisfied":False,"reason":problem}
    return {"role":fixture["role"],"satisfied":True,"reason":"verified"}


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
        help="Fail unless at least one fixture satisfies this role with verified runtime properties and required producer provenance.",
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