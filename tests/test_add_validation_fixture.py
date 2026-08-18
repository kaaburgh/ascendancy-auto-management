from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import add_validation_fixture as adder  # noqa: E402
import validate_validation_fixtures as validator  # noqa: E402


class AddValidationFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.save = self.directory / "resume-multi.gam"
        self.save.write_bytes(b"pretend save payload")
        self.declaration = self.directory / "validation-fixtures.json"
        shutil.copy2(validator.DEFAULT_DECLARATION, self.declaration)
        self.runtime_source_relative = "docs/experiments/_synthetic_add_fixture_record.md"
        self.runtime_source = Path(validator.ROOT) / self.runtime_source_relative
        runtime_properties = {
            "player_race_id": 0,
            "player_owned_planet_count": 2,
            "player_planet_names": ["Alpha I", "Beta II"],
            "planets_with_empty_current_action_at_load": ["Beta II"],
        }
        self.current_artifact_relative = "docs/experiments/_synthetic_add_fixture_current.json"
        self.current_artifact = Path(validator.ROOT) / self.current_artifact_relative
        self.current_snapshot_dir = Path(validator.ROOT) / "docs/experiments/_synthetic_add_current_harness"
        self.current_snapshot_dir.mkdir(parents=True, exist_ok=True)
        current_snapshot_names = [
            "run_t3_multi_planet_fixture.py",
            "run_re4_runtime_state.py",
            "run_re5_runtime_turn_path.py",
            "run_re5_override_witness.py",
            "le_image.py",
        ]
        current_snapshot_paths = {}
        current_snapshot_hashes = {}
        for index, name in enumerate(current_snapshot_names):
            snapshot = self.current_snapshot_dir / name
            snapshot.write_text(f"# synthetic add current harness {index}: {name}\n", encoding="utf-8")
            self.addCleanup(snapshot.unlink, missing_ok=True)
            current_snapshot_paths[name] = str(snapshot.relative_to(validator.ROOT))
            current_snapshot_hashes[name] = validator.sha256_file(snapshot)
        current_artifact = {
            "artifact_schema": validator.CURRENT_STATE_RUN_ARTIFACT_SCHEMA,
            "scenario_contract": validator.CURRENT_STATE_RUN_CONTRACT,
            "blind_re_provenance": "clean",
            "evidence_class": "runtime",
            "status": "passed",
            "candidate_fixture": {
                "id": "resume-en-multi-planet",
                "sha256": validator.sha256_file(self.save),
                "size": self.save.stat().st_size,
                "source_unchanged": True,
                "storage": "operator-supplied",
            },
            "diagnostic_guest_code_writes": False,
            "diagnostic_guest_data_writes": False,
            "source_inputs_modified": False,
            "runner_source_sha256": current_snapshot_hashes["run_t3_multi_planet_fixture.py"],
            "harness_dependencies": {
                name: current_snapshot_hashes[name]
                for name in current_snapshot_names
                if name != "run_t3_multi_planet_fixture.py"
            },
            "harness_source_snapshots": current_snapshot_paths,
            "runtime_environment": {
                "dosbox": {
                    "filename": "dosbox", "size": 1234, "sha256": "a" * 64,
                    "version_output": "DOSBox version synthetic",
                },
                "dosbox_config": {"cpu_core": "normal", "cycles": "max"},
            },
            "target": {
                "filename": "ANTAG.EXE", "size": validator.CANONICAL_TARGET_SIZE,
                "sha256": validator.CANONICAL_TARGET_SHA256,
            },
            "retail_fixture": {
                "id": validator.CANONICAL_RETAIL_FIXTURE_ID,
                "manifest_sha256": validator.CANONICAL_RETAIL_FIXTURE_MANIFEST_SHA256,
                "verified_files": validator.CANONICAL_RETAIL_FIXTURE_VERIFIED_FILES,
            },
            "role_claim": {"role": "m1-multi-planet", **runtime_properties},
            "verification": {
                "status": "passed",
                "process_stopped_for_coherent_snapshot": True,
                "save_unchanged_by_verification_load": True,
                "runtime_mapping": {"status": "passed"},
                "observation": {
                    "status": "passed", "checks": {"synthetic": True},
                    "current_player_id": runtime_properties["player_race_id"],
                    "player_owned_planet_count": runtime_properties["player_owned_planet_count"],
                    "player_planet_names": runtime_properties["player_planet_names"],
                    "planets_with_empty_current_action_at_load": runtime_properties["planets_with_empty_current_action_at_load"],
                },
            },
        }
        self.current_artifact.write_text(
            json.dumps(current_artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.addCleanup(self.current_artifact.unlink, missing_ok=True)
        observations = {
            "schema": validator.OBSERVATION_BLOCK_SCHEMA,
            "fixture_sha256": validator.sha256_file(self.save),
            "target_sha256": validator.CANONICAL_TARGET_SHA256,
            "runtime_properties": runtime_properties,
            "artifact": self.current_artifact_relative,
            "artifact_sha256": validator.sha256_file(self.current_artifact),
        }
        self.producer_harness_relative = "scripts/_synthetic_add_fixture_producer.py"
        self.producer_harness = Path(validator.ROOT) / self.producer_harness_relative
        self.producer_harness.write_text("# synthetic add-fixture producer harness\n", encoding="utf-8")
        self.addCleanup(self.producer_harness.unlink, missing_ok=True)
        self.producer_harness_snapshot_relative = (
            "docs/experiments/_synthetic_add_fixture_producer_harness.py"
        )
        self.producer_harness_snapshot = (
            Path(validator.ROOT) / self.producer_harness_snapshot_relative
        )
        self.producer_harness_snapshot.write_bytes(self.producer_harness.read_bytes())
        self.addCleanup(self.producer_harness_snapshot.unlink, missing_ok=True)
        producer_snapshot_dir = (
            Path(validator.ROOT) / "docs/experiments/_synthetic_add_fixture_producer_sources"
        )
        producer_snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, producer_snapshot_dir, ignore_errors=True)
        producer_dependency_names = (
            "run_t3_multi_planet_fixture.py",
            "run_re4_runtime_state.py",
            "run_re5_runtime_turn_path.py",
            "run_re5_override_witness.py",
            "le_image.py",
        )
        producer_source_snapshots = {}
        producer_dependency_hashes = {}
        primary_snapshot = producer_snapshot_dir / "run_t3_target_written_fixture.py"
        primary_snapshot.write_bytes(self.producer_harness.read_bytes())
        producer_source_snapshots[primary_snapshot.name] = str(
            primary_snapshot.relative_to(validator.ROOT)
        )
        for index, name in enumerate(producer_dependency_names):
            snapshot = producer_snapshot_dir / name
            snapshot.write_text(
                f"# synthetic add producer dependency {index}: {name}\n", encoding="utf-8"
            )
            producer_source_snapshots[name] = str(snapshot.relative_to(validator.ROOT))
            producer_dependency_hashes[name] = validator.sha256_file(snapshot)
        self.producer_artifact_relative = "docs/experiments/_synthetic_add_fixture_producer.json"
        self.producer_artifact = Path(validator.ROOT) / self.producer_artifact_relative
        producer_artifact = {
            "artifact_schema": validator.PRODUCTION_RUN_ARTIFACT_SCHEMA,
            "scenario_contract": validator.PRODUCTION_RUN_CONTRACT,
            "blind_re_provenance": "clean",
            "evidence_class": "runtime",
            "status": "passed",
            "target": {
                "filename": "ANTAG.EXE",
                "size": validator.CANONICAL_TARGET_SIZE,
                "sha256": validator.CANONICAL_TARGET_SHA256,
            },
            "retail_fixture": {
                "id": validator.CANONICAL_RETAIL_FIXTURE_ID,
                "manifest_sha256": validator.CANONICAL_RETAIL_FIXTURE_MANIFEST_SHA256,
                "verified_files": validator.CANONICAL_RETAIL_FIXTURE_VERIFIED_FILES,
            },
            "fixture": {
                "size": self.save.stat().st_size,
                "sha256": validator.sha256_file(self.save),
                "target_written_exact_bytes": True,
            },
            "runtime_environment": {
                "dosbox": {
                    "filename": "dosbox",
                    "size": 1234,
                    "sha256": "1" * 64,
                    "version_output": "DOSBox version synthetic",
                },
                "configuration": {"cpu_core": "normal", "cycles": "max", "display": "Xvfb"},
            },
            "harness": {
                "source": self.producer_harness_relative,
                "source_sha256": validator.sha256_file(self.producer_harness),
                "source_snapshot": self.producer_harness_snapshot_relative,
                "dependencies": producer_dependency_hashes,
                "source_snapshots": producer_source_snapshots,
            },
            "execution": {
                "ordinary_game_method": "synthetic ordinary-game save",
                "diagnostic_guest_code_writes": False,
                "diagnostic_guest_data_writes": False,
                "source_inputs_modified": False,
                "termination": {
                    "status": "completed",
                    "save_write_completed": True,
                    "output_observed_after_save": True,
                },
            },
            "oracle": {
                "status": "passed",
                "exact_byte_match": True,
                "output_sha256": validator.sha256_file(self.save),
                "output_size": self.save.stat().st_size,
            },
        }
        self.producer_artifact.write_text(
            json.dumps(producer_artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.addCleanup(self.producer_artifact.unlink, missing_ok=True)
        production = {
            "schema": validator.PRODUCTION_BLOCK_SCHEMA,
            "fixture_sha256": validator.sha256_file(self.save),
            "target_sha256": validator.CANONICAL_TARGET_SHA256,
            "target_written_exact_bytes": True,
            "method": "synthetic ordinary-game save",
            "artifact": self.producer_artifact_relative,
            "artifact_sha256": validator.sha256_file(self.producer_artifact),
        }
        self.runtime_source.write_text(
            "\n".join([
                "# synthetic fixture runtime record", "", validator.RUNTIME_EVIDENCE_MARKER,
                f"Target SHA-256 `{validator.CANONICAL_TARGET_SHA256}`.",
                f"Pinned save SHA-256 `{validator.sha256_file(self.save)}`.", "",
                validator.OBSERVATION_BLOCK_MARKER, "```json", json.dumps(observations, indent=2), "```", "",
                validator.PRODUCTION_BLOCK_MARKER, "```json", json.dumps(production, indent=2), "```", "",
            ]), encoding="utf-8")
        self.addCleanup(self.runtime_source.unlink, missing_ok=True)
        self.addCleanup(self.temp.cleanup)

    def run_adder(self, *extra: str) -> int:
        return adder.main(
            [
                "--save",
                str(self.save),
                "--id",
                "resume-en-multi-planet",
                "--role",
                "m1-multi-planet",
                "--declaration",
                str(self.declaration),
                "--player-planet",
                "Alpha I",
                "--player-planet",
                "Beta II",
                "--empty-action-planet",
                "Beta II",
                *extra,
            ]
        )

    def declared(self) -> list[dict]:
        return json.loads(self.declaration.read_text(encoding="utf-8"))["fixtures"]

    def test_operator_supplied_fixture_is_appended_with_computed_identity(self):
        self.assertEqual(self.run_adder("--storage", "operator-supplied"), 0)
        entry = next(item for item in self.declared() if item["id"] == "resume-en-multi-planet")
        self.assertEqual(entry["size"], self.save.stat().st_size)
        self.assertEqual(entry["sha256"], validator.sha256_file(self.save))
        self.assertEqual(entry["runtime_properties"]["player_owned_planet_count"], 2)
        self.assertEqual(entry["runtime_properties"]["evidence"], "unverified")
        self.assertNotIn("repository_path", entry)

    def test_dry_run_writes_nothing(self):
        before = self.declaration.read_text(encoding="utf-8")
        self.assertEqual(self.run_adder("--storage", "operator-supplied", "--dry-run"), 0)
        self.assertEqual(self.declaration.read_text(encoding="utf-8"), before)

    def test_committed_storage_requires_a_repository_path(self):
        self.assertEqual(self.run_adder("--storage", "repository"), 1)

    def test_runtime_evidence_requires_a_valid_verifying_record(self):
        self.assertEqual(
            self.run_adder("--storage", "operator-supplied", "--evidence", "runtime"), 1
        )
        self.assertEqual(
            self.run_adder(
                "--storage",
                "operator-supplied",
                "--evidence",
                "runtime",
                "--verified-by",
                "docs/experiments/X-fixture.md",
            ),
            1,
        )
        self.assertEqual(
            self.run_adder(
                "--storage",
                "operator-supplied",
                "--evidence",
                "runtime",
                "--verified-by",
                self.runtime_source_relative,
                "--producer-evidence",
                "runtime",
                "--producer-verified-by",
                self.runtime_source_relative,
            ),
            0,
        )

    def test_runtime_promotion_accepts_reported_producer_provenance_as_unusable(self):
        self.assertEqual(self.run_adder(
            "--storage", "operator-supplied", "--evidence", "runtime",
            "--verified-by", self.runtime_source_relative,
            "--producer-evidence", "reported",
            "--producer-verified-by", "tools/v1-validation-state-manifest.json",
        ), 0)
        entry = next(item for item in self.declared() if item["id"] == "resume-en-multi-planet")
        self.assertEqual(entry["runtime_properties"]["evidence"], "runtime")
        self.assertEqual(entry["producer_provenance"]["evidence"], "reported")
        checked = validator.check_declaration(
            json.loads(self.declaration.read_text(encoding="utf-8"))
        )
        status = next(item for item in checked if item["id"] == "resume-en-multi-planet")["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("producer provenance is 'reported'", status["reason"])

    def test_runtime_promotion_rejects_properties_not_observed_by_record(self):
        self.assertEqual(
            self.run_adder(
                "--storage",
                "operator-supplied",
                "--evidence",
                "runtime",
                "--verified-by",
                self.runtime_source_relative,
                "--producer-evidence",
                "runtime",
                "--producer-verified-by",
                self.runtime_source_relative,
                "--player-planet",
                "Gamma III",
            ),
            1,
        )

    def test_existing_id_is_not_silently_overwritten(self):
        self.assertEqual(self.run_adder("--storage", "operator-supplied"), 0)
        self.assertEqual(self.run_adder("--storage", "operator-supplied"), 1)
        self.assertEqual(self.run_adder("--storage", "operator-supplied", "--replace"), 0)
        matches = [item for item in self.declared() if item["id"] == "resume-en-multi-planet"]
        self.assertEqual(len(matches), 1)

    def test_a_save_without_named_planets_is_refused(self):
        self.assertEqual(
            adder.main(
                [
                    "--save",
                    str(self.save),
                    "--id",
                    "nameless",
                    "--role",
                    "m1-multi-planet",
                    "--storage",
                    "operator-supplied",
                    "--declaration",
                    str(self.declaration),
                ]
            ),
            1,
        )

    def test_missing_save_is_refused(self):
        self.assertEqual(
            adder.main(
                [
                    "--save",
                    str(self.directory / "absent.gam"),
                    "--id",
                    "absent",
                    "--role",
                    "m1-multi-planet",
                    "--storage",
                    "operator-supplied",
                    "--player-planet",
                    "Alpha I",
                    "--declaration",
                    str(self.declaration),
                ]
            ),
            1,
        )

    def test_repository_path_escaping_the_repo_copies_nothing(self):
        outside = self.directory / "outside.gam"
        self.assertEqual(
            self.run_adder(
                "--storage", "repository", "--repository-path", f"../{outside.name}"
            ),
            1,
        )
        self.assertFalse(outside.exists())
        self.assertNotIn(
            "resume-en-multi-planet", [item["id"] for item in self.declared()]
        )

    def test_existing_repository_destination_is_never_overwritten(self):
        root = Path(adder.ROOT)
        readme = root / "README.md"
        before = readme.read_bytes()
        self.assertEqual(
            self.run_adder("--storage", "repository", "--repository-path", "README.md"), 1
        )
        self.assertEqual(readme.read_bytes(), before)

    def test_committed_payload_is_placed_and_declared_together(self):
        relative = "fixtures/saves/test-add-fixture-tmp.gam"
        destination = Path(adder.ROOT) / relative

        def cleanup() -> None:
            destination.unlink(missing_ok=True)
            for parent in (destination.parent, destination.parent.parent):
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()

        self.addCleanup(cleanup)
        self.assertEqual(
            self.run_adder("--storage", "repository", "--repository-path", relative), 0
        )
        self.assertTrue(destination.is_file())
        self.assertEqual(destination.read_bytes(), self.save.read_bytes())
        entry = next(item for item in self.declared() if item["id"] == "resume-en-multi-planet")
        self.assertEqual(entry["repository_path"], relative)

    def test_promotion_of_a_committed_fixture_reuses_its_own_destination(self):
        relative = "fixtures/saves/test-promote-tmp.gam"
        destination = Path(adder.ROOT) / relative

        def cleanup() -> None:
            destination.unlink(missing_ok=True)
            for parent in (destination.parent, destination.parent.parent):
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()

        self.addCleanup(cleanup)
        self.assertEqual(
            self.run_adder("--storage", "repository", "--repository-path", relative), 0
        )
        # The promotion run supplies the same save from its original path, so the
        # destination already exists and must not be treated as a foreign file.
        self.assertEqual(
            self.run_adder(
                "--replace",
                "--storage",
                "repository",
                "--repository-path",
                relative,
                "--evidence",
                "runtime",
                "--verified-by",
                self.runtime_source_relative,
                "--producer-evidence",
                "runtime",
                "--producer-verified-by",
                self.runtime_source_relative,
            ),
            0,
        )
        entry = next(item for item in self.declared() if item["id"] == "resume-en-multi-planet")
        self.assertEqual(entry["runtime_properties"]["evidence"], "runtime")

    def test_replacing_a_committed_fixture_with_different_bytes_is_refused(self):
        relative = "fixtures/saves/test-swap-tmp.gam"
        destination = Path(adder.ROOT) / relative

        def cleanup() -> None:
            destination.unlink(missing_ok=True)
            for parent in (destination.parent, destination.parent.parent):
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()

        self.addCleanup(cleanup)
        self.assertEqual(
            self.run_adder("--storage", "repository", "--repository-path", relative), 0
        )
        original = destination.read_bytes()
        self.save.write_bytes(b"a different save entirely")
        self.assertEqual(
            self.run_adder("--replace", "--storage", "repository", "--repository-path", relative),
            1,
        )
        self.assertEqual(destination.read_bytes(), original)

    def test_rebinding_an_id_to_different_bytes_is_refused_at_a_new_path(self):
        """A fresh repository_path must not become a way around the identity guard."""
        self.assertEqual(self.run_adder("--storage", "operator-supplied"), 0)
        original_sha = validator.sha256_file(self.save)
        self.save.write_bytes(b"a different save entirely")
        self.assertEqual(
            self.run_adder(
                "--replace", "--storage", "repository", "--repository-path",
                "fixtures/saves/test-rebind-tmp.gam",
            ),
            1,
        )
        self.assertFalse((Path(adder.ROOT) / "fixtures/saves/test-rebind-tmp.gam").exists())
        entry = next(item for item in self.declared() if item["id"] == "resume-en-multi-planet")
        self.assertEqual(entry["sha256"], original_sha)

    def test_rebinding_an_id_is_refused_when_the_committed_payload_is_the_source(self):
        relative = "fixtures/saves/test-selfsource-tmp.gam"
        destination = Path(adder.ROOT) / relative

        def cleanup() -> None:
            destination.unlink(missing_ok=True)
            for parent in (destination.parent, destination.parent.parent):
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()

        self.addCleanup(cleanup)
        self.assertEqual(
            self.run_adder("--storage", "repository", "--repository-path", relative), 0
        )
        # Someone edits the committed payload in place and re-runs with it as --save,
        # so destination == save and the destination-based guard never fires.
        destination.write_bytes(b"tampered payload")
        self.assertEqual(
            adder.main(
                [
                    "--save", str(destination), "--id", "resume-en-multi-planet",
                    "--role", "m1-multi-planet", "--declaration", str(self.declaration),
                    "--player-planet", "Alpha I", "--player-planet", "Beta II",
                    "--empty-action-planet", "Beta II", "--replace",
                    "--storage", "repository", "--repository-path", relative,
                ]
            ),
            1,
        )

    def test_a_failed_write_does_not_delete_a_pre_existing_payload(self):
        relative = "fixtures/saves/test-rollback-tmp.gam"
        destination = Path(adder.ROOT) / relative

        def cleanup() -> None:
            destination.unlink(missing_ok=True)
            for parent in (destination.parent, destination.parent.parent):
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()

        self.addCleanup(cleanup)
        self.assertEqual(
            self.run_adder("--storage", "repository", "--repository-path", relative), 0
        )
        original = destination.read_bytes()

        def explode(*args, **kwargs):
            raise validator.FixtureDeclarationError("simulated failure after placement")

        real_check = validator.check_payloads
        validator.check_payloads = explode
        self.addCleanup(setattr, validator, "check_payloads", real_check)
        self.assertEqual(
            self.run_adder("--replace", "--storage", "repository", "--repository-path", relative),
            1,
        )
        self.assertTrue(destination.is_file(), "pre-existing payload was deleted by rollback")
        self.assertEqual(destination.read_bytes(), original)

    def test_declaration_stays_valid_after_the_write(self):
        self.assertEqual(self.run_adder("--storage", "operator-supplied"), 0)
        document = json.loads(self.declaration.read_text(encoding="utf-8"))
        self.assertTrue(validator.check_declaration(document))


if __name__ == "__main__":
    unittest.main()