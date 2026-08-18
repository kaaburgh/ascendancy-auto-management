from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import validate_validation_fixtures as fixtures  # noqa: E402

DECLARATION = json.loads(fixtures.DEFAULT_DECLARATION.read_text(encoding="utf-8"))


def multi_planet_fixture(**overrides):
    payload = b"multi-planet save payload"
    entry = {
        "id": "resume-multi-planet",
        "filename": "resume-multi.gam",
        "role": "m1-multi-planet",
        "storage": "operator-supplied",
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "produced_by_target_sha256": "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00",
        "producer_provenance": {"evidence": "runtime", "source": SYNTHETIC_SOURCE},
        "runtime_properties": {
            "evidence": "runtime",
            "source": SYNTHETIC_SOURCE,
            "player_race_id": 0,
            "player_owned_planet_count": 3,
            "player_planet_names": ["Alpha I", "Beta II", "Gamma III"],
            "planets_with_empty_current_action_at_load": ["Beta II"],
        },
    }
    entry.update(overrides)
    return entry, payload


SYNTHETIC_SOURCE = "docs/experiments/_synthetic_fixture_record.md"


def write_synthetic_source(
    case,
    entry: dict,
    *,
    directory: str = "experiments",
    target_sha256: str = fixtures.CANONICAL_TARGET_SHA256,
    runtime_marker: bool = True,
    include_observations: bool = True,
    mentioned_fixture_sha256: str | None = None,
    observed_fixture_sha256: str | None = None,
    observed_properties: dict | None = None,
    include_production: bool = True,
    target_written_exact_bytes: bool = True,
    materialize_production_artifact: bool = True,
    producer_artifact_status: str = "passed",
    producer_exact_match: bool | None = None,
    producer_harness_hash: str | None = None,
    producer_artifact_include_retail_fixture: bool = True,
    producer_artifact_retail_fixture: dict | None = None,
    materialize_current_artifact: bool = True,
    current_artifact_status: str = "passed",
    current_artifact_properties: dict | None = None,
    current_artifact_sha_override: str | None = None,
    current_artifact_include_retail_fixture: bool = True,
    current_artifact_retail_fixture: dict | None = None,
) -> str:
    """Create a throwaway runtime record carrying identities and observed properties."""
    relative = f"docs/{directory}/_synthetic_fixture_record.md"
    path = Path(fixtures.ROOT) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    fixture_sha256 = entry["sha256"]
    lines = ["# synthetic record", ""]
    if runtime_marker:
        lines.append(fixtures.RUNTIME_EVIDENCE_MARKER)
    lines.extend(
        [
            f"Target SHA-256 `{target_sha256}`.",
            f"Pinned save SHA-256 `{mentioned_fixture_sha256 or fixture_sha256}`.",
            "",
        ]
    )
    if include_observations:
        properties = observed_properties or {
            field: copy.deepcopy(entry["runtime_properties"][field])
            for field in fixtures.OBSERVED_RUNTIME_PROPERTY_FIELDS
        }
        current_artifact_relative = "docs/experiments/_synthetic_current_state_run.json"
        current_artifact_path = Path(fixtures.ROOT) / current_artifact_relative
        artifact_properties = copy.deepcopy(current_artifact_properties or properties)
        snapshot_dir = Path(fixtures.ROOT) / "docs/experiments/_synthetic_current_harness"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_names = [
            "run_t3_multi_planet_fixture.py",
            "run_re4_runtime_state.py",
            "run_re5_runtime_turn_path.py",
            "run_re5_override_witness.py",
            "le_image.py",
        ]
        snapshot_paths = {}
        snapshot_hashes = {}
        for index, name in enumerate(snapshot_names):
            snapshot = snapshot_dir / name
            snapshot.write_text(f"# synthetic current harness {index}: {name}\n", encoding="utf-8")
            case.addCleanup(snapshot.unlink, missing_ok=True)
            snapshot_paths[name] = str(snapshot.relative_to(fixtures.ROOT))
            snapshot_hashes[name] = fixtures.sha256_file(snapshot)
        current_artifact = {
            "artifact_schema": fixtures.CURRENT_STATE_RUN_ARTIFACT_SCHEMA,
            "scenario_contract": fixtures.CURRENT_STATE_RUN_CONTRACT,
            "blind_re_provenance": "clean",
            "evidence_class": "runtime",
            "status": current_artifact_status,
            "candidate_fixture": {
                "id": entry["id"], "sha256": fixture_sha256, "size": entry["size"],
                "source_unchanged": True, "storage": entry["storage"],
            },
            "diagnostic_guest_code_writes": False,
            "diagnostic_guest_data_writes": False,
            "source_inputs_modified": False,
            "runner_source_sha256": snapshot_hashes["run_t3_multi_planet_fixture.py"],
            "harness_dependencies": {
                name: snapshot_hashes[name]
                for name in snapshot_names
                if name != "run_t3_multi_planet_fixture.py"
            },
            "harness_source_snapshots": snapshot_paths,
            "runtime_environment": {
                "dosbox": {
                    "filename": "dosbox", "size": 1234, "sha256": "a" * 64,
                    "version_output": "DOSBox version synthetic",
                },
                "dosbox_config": {"cpu_core": "normal", "cycles": "max", "xvfb_screen": "1024x768x24"},
            },
            "target": {
                "filename": "ANTAG.EXE", "size": fixtures.CANONICAL_TARGET_SIZE,
                "sha256": target_sha256,
            },
            "role_claim": {
                "role": entry["role"],
                "player_race_id": artifact_properties["player_race_id"],
                "player_owned_planet_count": artifact_properties["player_owned_planet_count"],
                "player_planet_names": artifact_properties["player_planet_names"],
                "planets_with_empty_current_action_at_load": artifact_properties["planets_with_empty_current_action_at_load"],
            },
            "verification": {
                "status": "passed" if current_artifact_status == "passed" else "failed",
                "process_stopped_for_coherent_snapshot": True,
                "save_unchanged_by_verification_load": True,
                "runtime_mapping": {"status": "passed"},
                "observation": {
                    "status": "passed" if current_artifact_status == "passed" else "failed",
                    "checks": {"synthetic": current_artifact_status == "passed"},
                    "current_player_id": artifact_properties["player_race_id"],
                    "player_owned_planet_count": artifact_properties["player_owned_planet_count"],
                    "player_planet_names": artifact_properties["player_planet_names"],
                    "planets_with_empty_current_action_at_load": artifact_properties["planets_with_empty_current_action_at_load"],
                },
            },
        }
        if current_artifact_include_retail_fixture:
            current_artifact["retail_fixture"] = copy.deepcopy(
                current_artifact_retail_fixture
                or {
                    "id": fixtures.CANONICAL_RETAIL_FIXTURE_ID,
                    "manifest_sha256": fixtures.CANONICAL_RETAIL_FIXTURE_MANIFEST_SHA256,
                    "verified_files": fixtures.CANONICAL_RETAIL_FIXTURE_VERIFIED_FILES,
                }
            )
        if materialize_current_artifact:
            current_artifact_path.write_text(
                json.dumps(current_artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            current_artifact_sha = current_artifact_sha_override or fixtures.sha256_file(current_artifact_path)
            case.addCleanup(current_artifact_path.unlink, missing_ok=True)
        else:
            current_artifact_sha = current_artifact_sha_override or ("0" * 64)
        observations = {
            "schema": fixtures.OBSERVATION_BLOCK_SCHEMA,
            "fixture_sha256": observed_fixture_sha256 or fixture_sha256,
            "target_sha256": target_sha256,
            "runtime_properties": properties,
            "artifact": current_artifact_relative,
            "artifact_sha256": current_artifact_sha,
        }
        lines.extend(
            [
                fixtures.OBSERVATION_BLOCK_MARKER,
                "```json",
                json.dumps(observations, indent=2),
                "```",
                "",
            ]
        )
    if include_production:
        harness_relative = "scripts/_synthetic_producer_harness.py"
        harness_path = Path(fixtures.ROOT) / harness_relative
        harness_path.write_text("# synthetic producer harness\n", encoding="utf-8")
        case.addCleanup(harness_path.unlink, missing_ok=True)
        harness_sha = producer_harness_hash or fixtures.sha256_file(harness_path)
        harness_snapshot_relative = "docs/experiments/_synthetic_producer_harness.py"
        harness_snapshot_path = Path(fixtures.ROOT) / harness_snapshot_relative
        harness_snapshot_path.write_bytes(harness_path.read_bytes())
        case.addCleanup(harness_snapshot_path.unlink, missing_ok=True)
        artifact_relative = "docs/experiments/_synthetic_producer_run.json"
        artifact_path = Path(fixtures.ROOT) / artifact_relative
        exact_match = target_written_exact_bytes if producer_exact_match is None else producer_exact_match
        artifact = {
            "artifact_schema": fixtures.PRODUCTION_RUN_ARTIFACT_SCHEMA,
            "scenario_contract": fixtures.PRODUCTION_RUN_CONTRACT,
            "blind_re_provenance": "clean",
            "evidence_class": "runtime",
            "status": producer_artifact_status,
            "target": {"filename": "ANTAG.EXE", "size": fixtures.CANONICAL_TARGET_SIZE, "sha256": target_sha256},
            "fixture": {"size": entry["size"], "sha256": fixture_sha256, "target_written_exact_bytes": target_written_exact_bytes},
            "runtime_environment": {
                "dosbox": {
                    "filename": "dosbox", "size": 1234, "sha256": "1" * 64,
                    "version_output": "DOSBox version synthetic",
                },
                "configuration": {"cpu_core": "normal", "cycles": "max", "display": "Xvfb"},
            },
            "harness": {
                "source": harness_relative,
                "source_sha256": harness_sha,
                "source_snapshot": harness_snapshot_relative,
            },
            "execution": {
                "ordinary_game_method": "synthetic ordinary-game save",
                "diagnostic_guest_code_writes": False,
                "diagnostic_guest_data_writes": False,
                "source_inputs_modified": False,
                "termination": {
                    "status": "completed", "save_write_completed": True,
                    "output_observed_after_save": True,
                },
            },
            "oracle": {
                "status": "passed" if exact_match else "failed",
                "exact_byte_match": exact_match, "output_sha256": fixture_sha256,
                "output_size": entry["size"],
            },
        }
        if producer_artifact_include_retail_fixture:
            artifact["retail_fixture"] = copy.deepcopy(
                producer_artifact_retail_fixture
                or {
                    "id": fixtures.CANONICAL_RETAIL_FIXTURE_ID,
                    "manifest_sha256": fixtures.CANONICAL_RETAIL_FIXTURE_MANIFEST_SHA256,
                    "verified_files": fixtures.CANONICAL_RETAIL_FIXTURE_VERIFIED_FILES,
                }
            )
        if materialize_production_artifact:
            artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            artifact_sha = fixtures.sha256_file(artifact_path)
            case.addCleanup(artifact_path.unlink, missing_ok=True)
        else:
            artifact_sha = "0" * 64
        production = {
            "schema": fixtures.PRODUCTION_BLOCK_SCHEMA,
            "fixture_sha256": fixture_sha256,
            "target_sha256": target_sha256,
            "target_written_exact_bytes": target_written_exact_bytes,
            "method": "synthetic ordinary-game save",
            "artifact": artifact_relative,
            "artifact_sha256": artifact_sha,
        }
        lines.extend([fixtures.PRODUCTION_BLOCK_MARKER, "```json", json.dumps(production, indent=2), "```", ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    case.addCleanup(path.unlink, missing_ok=True)
    return relative


def document_with(entry) -> dict:
    document = copy.deepcopy(DECLARATION)
    document["fixtures"] = [entry]
    # Synthetic producer-contract tests intentionally opt back into the strict
    # exact-byte producer requirement. The committed T3 role no longer does.
    document["role_requirements"]["m1-multi-planet"][fixtures.PRODUCTION_REQUIREMENT_KEY] = True
    return document


class ValidationFixtureDeclarationTests(unittest.TestCase):
    def test_committed_declaration_is_valid(self):
        declared = fixtures.check_declaration(copy.deepcopy(DECLARATION))
        self.assertTrue(declared)

    def test_committed_declaration_records_the_single_planet_limitation(self):
        entry = next(
            item for item in DECLARATION["fixtures"] if item["filename"] == "resume.gam"
        )
        self.assertEqual(entry["runtime_properties"]["player_owned_planet_count"], 1)
        self.assertEqual(entry["role"], "single-planet-causal")
        self.assertTrue(entry["limitations"])

    def test_multi_planet_role_is_accepted_when_requirements_are_met(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(self, entry)
        declared = fixtures.check_declaration(document_with(entry))
        self.assertTrue(declared[0]["_role_status"]["satisfied"])

    def test_current_state_role_requires_detached_runtime_artifact(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(
            self, entry, materialize_current_artifact=False
        )
        status = fixtures.check_declaration(document_with(entry))[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("runtime observation artifact", status["reason"])

    def test_current_state_artifact_requires_transitive_le_parser_snapshot(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(self, entry)
        artifact_path = Path(fixtures.ROOT) / "docs/experiments/_synthetic_current_state_run.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["harness_dependencies"].pop("le_image.py")
        artifact["harness_source_snapshots"].pop("le_image.py")
        artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        source_path = Path(fixtures.ROOT) / entry["runtime_properties"]["source"]
        source = source_path.read_text(encoding="utf-8")
        marker = fixtures.OBSERVATION_BLOCK_MARKER
        head, tail = source.split(marker, 1)
        match = re.search(r"```json\n(.*?)\n```", tail, re.S)
        observations = json.loads(match.group(1))
        observations["artifact_sha256"] = fixtures.sha256_file(artifact_path)
        source = head + marker + tail[:match.start(1)] + json.dumps(observations, indent=2) + tail[match.end(1):]
        source_path.write_text(source, encoding="utf-8")
        status = fixtures.check_declaration(document_with(entry))[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("complete T3 harness dependency set", status["reason"])

    def test_current_state_artifact_snapshot_bytes_must_match_pinned_hash(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(self, entry)
        snapshot = Path(fixtures.ROOT) / "docs/experiments/_synthetic_current_harness/run_re4_runtime_state.py"
        snapshot.write_text("# tampered after artifact creation\n", encoding="utf-8")
        status = fixtures.check_declaration(document_with(entry))[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("harness snapshot", status["reason"])
        self.assertIn("does not match pinned", status["reason"])

    def test_current_state_artifact_hash_is_pinned(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(
            self, entry, current_artifact_sha_override="0" * 64
        )
        status = fixtures.check_declaration(document_with(entry))[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("does not match pinned", status["reason"])

    def test_current_state_artifact_observation_must_match_declaration(self):
        entry, _ = multi_planet_fixture()
        wrong = {
            "player_race_id": 0,
            "player_owned_planet_count": 2,
            "player_planet_names": ["Alpha I", "Beta II"],
            "planets_with_empty_current_action_at_load": ["Beta II"],
        }
        entry["runtime_properties"]["source"] = write_synthetic_source(
            self, entry, current_artifact_properties=wrong
        )
        status = fixtures.check_declaration(document_with(entry))[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("role claim", status["reason"])

    def test_current_state_artifact_must_be_a_passed_run(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(
            self, entry, current_artifact_status="failed"
        )
        status = fixtures.check_declaration(document_with(entry))[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("passed runtime record", status["reason"])

    def test_current_state_artifact_requires_canonical_retail_fixture_identity(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(
            self, entry, current_artifact_include_retail_fixture=False
        )
        status = fixtures.check_declaration(document_with(entry))[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("retail fixture identity", status["reason"])

    def test_current_state_artifact_retail_fixture_identity_must_match(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(
            self,
            entry,
            current_artifact_retail_fixture={
                "id": fixtures.CANONICAL_RETAIL_FIXTURE_ID,
                "manifest_sha256": "0" * 64,
                "verified_files": fixtures.CANONICAL_RETAIL_FIXTURE_VERIFIED_FILES,
            },
        )
        status = fixtures.check_declaration(document_with(entry))[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("canonical runtime fixture", status["reason"])

    def test_committed_multi_planet_fixture_is_usable_with_reported_producer(self):
        declared = fixtures.check_declaration(copy.deepcopy(DECLARATION))
        entry = next(item for item in declared if item["id"] == "resume-en-operator-multi-planet-2026-08-14")
        self.assertTrue(entry["_role_status"]["satisfied"])
        self.assertEqual(entry["producer_provenance"]["evidence"], "reported")

    def test_runtime_producer_evidence_requires_exact_byte_proof(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(self, entry, target_written_exact_bytes=False)
        status = fixtures.check_declaration(document_with(entry))[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("target_written_exact_bytes=true", status["reason"])

    def test_runtime_producer_evidence_without_production_block_fails_closed(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(self, entry, include_production=False)
        status = fixtures.check_declaration(document_with(entry))[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("structured production evidence", status["reason"])

    def test_producer_promotion_requires_detached_run_artifact(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(
            self, entry, materialize_production_artifact=False
        )
        status = fixtures.check_declaration(document_with(entry))[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("run artifact", status["reason"])

    def test_producer_run_artifact_requires_exact_byte_oracle(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(
            self, entry, producer_exact_match=False
        )
        status = fixtures.check_declaration(document_with(entry))[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("exact-byte oracle", status["reason"])

    def test_producer_run_artifact_binds_preserved_harness_source(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(
            self, entry, producer_harness_hash="0" * 64
        )
        status = fixtures.check_declaration(document_with(entry))[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("source_snapshot SHA-256", status["reason"])

    def test_producer_run_artifact_requires_canonical_retail_fixture_identity(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(
            self, entry, producer_artifact_include_retail_fixture=False
        )
        status = fixtures.check_declaration(document_with(entry))[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("retail fixture identity", status["reason"])

    def test_producer_run_artifact_retail_fixture_identity_must_match(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(
            self,
            entry,
            producer_artifact_retail_fixture={
                "id": fixtures.CANONICAL_RETAIL_FIXTURE_ID,
                "manifest_sha256": "0" * 64,
                "verified_files": fixtures.CANONICAL_RETAIL_FIXTURE_VERIFIED_FILES,
            },
        )
        status = fixtures.check_declaration(document_with(entry))[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("canonical runtime fixture", status["reason"])

    def test_source_outside_experiments_does_not_satisfy_a_role(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(self, entry, directory="re")
        declared = fixtures.check_declaration(document_with(entry))
        status = declared[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("experiments/", status["reason"])

    def test_source_not_naming_this_fixture_does_not_satisfy_a_role(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(self, entry, mentioned_fixture_sha256="0" * 64, observed_fixture_sha256="0" * 64)
        declared = fixtures.check_declaration(document_with(entry))
        status = declared[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("SHA-256", status["reason"])

    def test_experiment_without_runtime_marker_does_not_satisfy_a_role(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(self, entry, runtime_marker=False)
        declared = fixtures.check_declaration(document_with(entry))
        status = declared[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("Evidence class", status["reason"])

    def test_experiment_for_a_different_target_does_not_satisfy_a_role(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(self, entry, target_sha256="0" * 64)
        declared = fixtures.check_declaration(document_with(entry))
        status = declared[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("target SHA-256", status["reason"])

    def test_runtime_record_without_structured_observations_does_not_satisfy_a_role(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = write_synthetic_source(
            self, entry, include_observations=False
        )
        declared = fixtures.check_declaration(document_with(entry))
        status = declared[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("structured runtime observations", status["reason"])

    def test_runtime_record_must_match_declared_planet_names(self):
        entry, _ = multi_planet_fixture()
        observed = {
            field: copy.deepcopy(entry["runtime_properties"][field])
            for field in fixtures.OBSERVED_RUNTIME_PROPERTY_FIELDS
        }
        observed["player_planet_names"] = ["Alpha I", "Beta II", "Wrong III"]
        entry["runtime_properties"]["source"] = write_synthetic_source(
            self, entry, observed_properties=observed
        )
        declared = fixtures.check_declaration(document_with(entry))
        status = declared[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("player_planet_names", status["reason"])

    def test_runtime_record_must_match_declared_empty_action_planets(self):
        entry, _ = multi_planet_fixture()
        observed = {
            field: copy.deepcopy(entry["runtime_properties"][field])
            for field in fixtures.OBSERVED_RUNTIME_PROPERTY_FIELDS
        }
        observed["planets_with_empty_current_action_at_load"] = []
        entry["runtime_properties"]["source"] = write_synthetic_source(
            self, entry, observed_properties=observed
        )
        declared = fixtures.check_declaration(document_with(entry))
        status = declared[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("planets_with_empty_current_action_at_load", status["reason"])

    def test_a_policy_document_cannot_stand_in_for_an_experiment_record(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = "docs/re/validation-fixtures.md"
        declared = fixtures.check_declaration(document_with(entry))
        self.assertFalse(declared[0]["_role_status"]["satisfied"])

    def test_unverified_fixture_is_declarable_but_not_usable(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["evidence"] = "unverified"
        declared = fixtures.check_declaration(document_with(entry))
        status = declared[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("unverified", status["reason"])

    def test_static_evidence_does_not_satisfy_a_role(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["evidence"] = "static"
        declared = fixtures.check_declaration(document_with(entry))
        status = declared[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("runtime", status["reason"])

    def test_runtime_evidence_without_a_source_does_not_satisfy_a_role(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"].pop("source")
        declared = fixtures.check_declaration(document_with(entry))
        self.assertFalse(declared[0]["_role_status"]["satisfied"])

    def test_save_from_a_non_canonical_target_does_not_satisfy_a_role(self):
        entry, _ = multi_planet_fixture()
        entry["produced_by_target_sha256"] = (
            "7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b"
        )
        declared = fixtures.check_declaration(document_with(entry))
        status = declared[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("canonical", status["reason"])

    def test_source_naming_a_missing_record_does_not_satisfy_a_role(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = "docs/experiments/does-not-exist.md"
        declared = fixtures.check_declaration(document_with(entry))
        status = declared[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("does not resolve", status["reason"])

    def test_source_escaping_the_repository_does_not_satisfy_a_role(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = "../../etc/passwd"
        declared = fixtures.check_declaration(document_with(entry))
        self.assertFalse(declared[0]["_role_status"]["satisfied"])

    def test_verified_properties_contradicting_the_role_fail_closed(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["evidence"] = "runtime"
        entry["runtime_properties"]["player_owned_planet_count"] = 1
        entry["runtime_properties"]["player_planet_names"] = ["Alpha I"]
        entry["runtime_properties"]["planets_with_empty_current_action_at_load"] = ["Alpha I"]
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_require_role_rejects_a_declaration_with_only_unverified_candidates(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["evidence"] = "unverified"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "declaration.json"
            path.write_text(json.dumps(document_with(entry)), encoding="utf-8")
            self.assertEqual(
                fixtures.main(["--declaration", str(path), "--require-role", "m1-multi-planet"]), 1
            )
            self.assertEqual(fixtures.main(["--declaration", str(path)]), 0)

    def test_planet_count_must_match_the_named_planets(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["player_owned_planet_count"] = 4
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_duplicate_planet_names_are_rejected(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["player_planet_names"] = ["Alpha I", "Alpha I", "Gamma III"]
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_empty_action_planet_must_be_player_owned(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["planets_with_empty_current_action_at_load"] = ["Delta IV"]
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_absent_payload_is_reported_but_not_fatal(self):
        entry, _ = multi_planet_fixture()
        with tempfile.TemporaryDirectory() as directory:
            results = fixtures.check_payloads([entry], Path(directory), require_present=False)
        self.assertEqual(results[0]["payload"], "absent")

    def test_absent_payload_fails_closed_when_required(self):
        entry, _ = multi_planet_fixture()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(fixtures.FixtureDeclarationError):
                fixtures.check_payloads([entry], Path(directory), require_present=True)

    def test_present_payload_identity_is_verified(self):
        entry, payload = multi_planet_fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / entry["filename"]
            path.write_bytes(payload)
            results = fixtures.check_payloads([entry], Path(directory), require_present=True)
            self.assertEqual(results[0]["payload"], "verified")

            path.write_bytes(payload + b"drift")
            with self.assertRaises(fixtures.FixtureDeclarationError):
                fixtures.check_payloads([entry], Path(directory), require_present=True)

    def test_unknown_storage_is_rejected(self):
        entry, _ = multi_planet_fixture()
        entry["storage"] = "somewhere-else"
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_repository_storage_requires_a_repository_path(self):
        entry, _ = multi_planet_fixture()
        entry["storage"] = "repository"
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_repository_path_may_not_escape_the_repository(self):
        entry, _ = multi_planet_fixture()
        entry["storage"] = "repository"
        entry["repository_path"] = "../outside/resume-multi.gam"
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_committed_payload_must_exist_even_without_require_present(self):
        entry, _ = multi_planet_fixture()
        entry["storage"] = "repository"
        entry["repository_path"] = "tests/fixtures/definitely-absent.gam"
        fixtures.check_declaration(document_with(entry))
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_payloads([entry], None, require_present=False)

    def test_unknown_role_is_rejected(self):
        entry, _ = multi_planet_fixture()
        entry["role"] = "not-a-declared-role"
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_unsupported_schema_is_rejected(self):
        document = copy.deepcopy(DECLARATION)
        document["schema"] = 99
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document)


if __name__ == "__main__":
    unittest.main()
