from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import validate_validation_fixtures as fixtures  # noqa: E402


class ProducerProvenanceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        (self.root / "scripts").mkdir()
        (self.root / "docs" / "experiments").mkdir(parents=True)

        self.harness_source = "scripts/run_t3_target_written_fixture.py"
        self.harness_snapshot = "docs/experiments/run_t3_target_written_fixture.py"
        source_bytes = b"# exact executed producer harness\n"
        (self.root / self.harness_source).write_bytes(source_bytes)
        (self.root / self.harness_snapshot).write_bytes(source_bytes)
        self.harness_sha = hashlib.sha256(source_bytes).hexdigest()

        dependency_names = (
            "run_t3_multi_planet_fixture.py",
            "run_re4_runtime_state.py",
            "run_re5_runtime_turn_path.py",
            "run_re5_override_witness.py",
            "le_image.py",
        )
        self.dependency_hashes = {}
        self.source_snapshots = {
            "run_t3_target_written_fixture.py": self.harness_snapshot,
        }
        for index, name in enumerate(dependency_names):
            data = f"# exact executed dependency {index}: {name}\n".encode()
            snapshot = self.root / "docs" / "experiments" / name
            snapshot.write_bytes(data)
            self.dependency_hashes[name] = hashlib.sha256(data).hexdigest()
            self.source_snapshots[name] = snapshot.relative_to(self.root).as_posix()

        self.fixture = {
            "size": 23,
            "sha256": "b" * 64,
        }
        self.method = "ordinary Save Game"

    def _artifact(self, **harness_overrides):
        harness = {
            "source": self.harness_source,
            "source_sha256": self.harness_sha,
            "source_snapshot": self.harness_snapshot,
            "dependencies": dict(self.dependency_hashes),
            "source_snapshots": dict(self.source_snapshots),
        }
        harness.update(harness_overrides)
        return {
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
                "size": self.fixture["size"],
                "sha256": self.fixture["sha256"],
                "target_written_exact_bytes": True,
            },
            "runtime_environment": {
                "dosbox": {
                    "filename": "dosbox",
                    "size": 1234,
                    "sha256": "a" * 64,
                    "version_output": "DOSBox version synthetic",
                },
                "configuration": {"cpu_core": "normal", "cycles": "max"},
            },
            "harness": harness,
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

    def _check(self, artifact):
        artifact_path = self.root / "docs" / "experiments" / "producer-run.json"
        artifact_path.write_text(json.dumps(artifact, sort_keys=True) + "\n", encoding="utf-8")
        artifact_sha = fixtures.sha256_file(artifact_path)
        with mock.patch.object(fixtures, "ROOT", self.root):
            return fixtures.check_production_run_artifact(
                "docs/experiments/producer-run.json",
                artifact_sha,
                self.fixture,
                self.method,
            )

    def test_matching_preserved_source_snapshot_is_accepted(self):
        self.assertIsNone(self._check(self._artifact()))

    def test_missing_preserved_source_snapshot_fails_closed(self):
        artifact = self._artifact()
        artifact["harness"].pop("source_snapshot")
        problem = self._check(artifact)
        self.assertIsNotNone(problem)
        self.assertIn("source_snapshot", problem)

    def test_snapshot_bytes_must_match_recorded_source_hash(self):
        (self.root / self.harness_snapshot).write_text("# different bytes\n", encoding="utf-8")
        problem = self._check(self._artifact())
        self.assertIsNotNone(problem)
        self.assertIn("source_snapshot SHA-256", problem)


if __name__ == "__main__":
    unittest.main()
