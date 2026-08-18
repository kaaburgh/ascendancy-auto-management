from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import validate_validation_fixtures as fixtures  # noqa: E402


class T3ProducerHarnessProvenanceValidationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(fixtures.ROOT)
        self.evidence_dir = self.root / "docs/experiments/_synthetic_t3_producer_validator"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, self.evidence_dir, ignore_errors=True)

        self.fixture = {
            "id": "synthetic-target-written",
            "size": 17,
            "sha256": "a" * 64,
        }
        self.method = "synthetic ordinary-game save"
        self.artifact_path = self.evidence_dir / "producer-run.json"

        source_names = [
            "run_t3_target_written_fixture.py",
            "run_t3_multi_planet_fixture.py",
            "run_re4_runtime_state.py",
            "run_re5_runtime_turn_path.py",
            "run_re5_override_witness.py",
            "le_image.py",
        ]
        snapshots = {}
        hashes = {}
        for name in source_names:
            source = self.root / "scripts" / name
            data = source.read_bytes()
            snapshot = self.evidence_dir / name
            snapshot.write_bytes(data)
            snapshots[name] = snapshot.relative_to(self.root).as_posix()
            hashes[name] = fixtures.sha256_file(snapshot)

        primary = "run_t3_target_written_fixture.py"
        self.artifact = {
            "artifact_schema": fixtures.PRODUCTION_RUN_ARTIFACT_SCHEMA,
            "scenario_contract": fixtures.PRODUCTION_RUN_CONTRACT,
            "blind_re_provenance": "clean",
            "evidence_class": "runtime",
            "status": "passed",
            "target": {
                "filename": "ANTAG.EXE",
                "size": fixtures.CANONICAL_TARGET_SIZE,
                "sha256": fixtures.CANONICAL_TARGET_SHA256,
            },
            "retail_fixture": {
                "id": fixtures.CANONICAL_RETAIL_FIXTURE_ID,
                "manifest_sha256": fixtures.CANONICAL_RETAIL_FIXTURE_MANIFEST_SHA256,
                "verified_files": fixtures.CANONICAL_RETAIL_FIXTURE_VERIFIED_FILES,
            },
            "fixture": {
                "id": self.fixture["id"],
                "size": self.fixture["size"],
                "sha256": self.fixture["sha256"],
                "target_written_exact_bytes": True,
            },
            "runtime_environment": {
                "dosbox": {
                    "filename": "dosbox",
                    "size": 1234,
                    "sha256": "b" * 64,
                    "version_output": "DOSBox synthetic",
                },
                "configuration": {"cpu_core": "normal", "cycles": "max"},
            },
            "harness": {
                "source": "scripts/run_t3_target_written_fixture.py",
                "source_sha256": hashes[primary],
                "source_snapshot": snapshots[primary],
                "dependencies": {
                    name: digest for name, digest in hashes.items() if name != primary
                },
                "source_snapshots": snapshots,
            },
            "execution": {
                "ordinary_game_method": self.method,
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
                "output_sha256": self.fixture["sha256"],
                "output_size": self.fixture["size"],
            },
        }

    def validate(self) -> str | None:
        self.artifact_path.write_text(
            json.dumps(self.artifact, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        relative = self.artifact_path.relative_to(self.root).as_posix()
        return fixtures.check_production_run_artifact(
            relative,
            fixtures.sha256_file(self.artifact_path),
            self.fixture,
            self.method,
        )

    def test_complete_producer_harness_closure_is_accepted(self):
        self.assertIsNone(self.validate())

    def test_missing_producer_dependency_is_rejected(self):
        self.artifact["harness"]["dependencies"].pop("le_image.py")
        problem = self.validate()
        self.assertIsNotNone(problem)
        self.assertIn("complete T3 producer dependency set", problem)

    def test_missing_producer_source_snapshot_is_rejected(self):
        self.artifact["harness"]["source_snapshots"].pop("run_re5_override_witness.py")
        problem = self.validate()
        self.assertIsNotNone(problem)
        self.assertIn("complete producer source snapshot set", problem)

    def test_tampered_producer_dependency_snapshot_is_rejected(self):
        snapshot = self.evidence_dir / "run_re4_runtime_state.py"
        snapshot.write_text("# tampered after producer run\n", encoding="utf-8")
        problem = self.validate()
        self.assertIsNotNone(problem)
        self.assertIn("does not match pinned", problem)


if __name__ == "__main__":
    unittest.main()
