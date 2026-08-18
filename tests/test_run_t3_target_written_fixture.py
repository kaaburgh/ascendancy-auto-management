from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_t3_target_written_fixture",
    ROOT / "scripts" / "run_t3_target_written_fixture.py",
)
assert SPEC is not None and SPEC.loader is not None
producer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(producer)


class ScenarioTests(unittest.TestCase):
    def write_scenario(self, root: Path, value: dict) -> Path:
        path = root / "scenario.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def valid(self) -> dict:
        return {
            "schema": 1,
            "name": "load-qualified-state-and-save-slot-1",
            "ordinary_game_method": "Resume qualified state, then ordinary Save Game to empty slot 1",
            "output_slot": 1,
            "max_runtime_seconds": 30,
            "steps": [
                {"action": "move_to", "x": 320, "y": 200},
                {"action": "click"},
                {"action": "wait", "seconds": 0.5},
                {"action": "key", "name": "Escape"},
            ],
        }

    def test_accepts_bounded_ordinary_ui_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            parsed = producer.load_action_scenario(self.write_scenario(Path(td), self.valid()))
        self.assertEqual(parsed["output_slot"], 1)
        self.assertEqual(parsed["max_runtime_seconds"], 30.0)

    def test_rejects_unknown_action(self) -> None:
        value = self.valid()
        value["steps"] = [{"action": "write_memory", "address": 1}]
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(producer.ProducerError, "unsupported action"):
                producer.load_action_scenario(self.write_scenario(Path(td), value))

    def test_rejects_unbounded_wait_budget(self) -> None:
        value = self.valid()
        value["max_runtime_seconds"] = 5
        value["steps"] = [{"action": "wait", "seconds": 5}, {"action": "click"}]
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(producer.ProducerError, "entire runtime budget"):
                producer.load_action_scenario(self.write_scenario(Path(td), value))

    def test_rejects_out_of_frame_pointer_target(self) -> None:
        value = self.valid()
        value["steps"] = [{"action": "move_to", "x": 640, "y": 20}, {"action": "click"}]
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(producer.ProducerError, "outside 640x480"):
                producer.load_action_scenario(self.write_scenario(Path(td), value))


class OutputSelectionTests(unittest.TestCase):
    def test_accepts_exactly_one_expected_numbered_save(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = b"target-written-save"
            (root / "01.SAV").write_bytes(payload)
            name, actual = producer.read_unambiguous_output(root, 1)
        self.assertEqual(name, "01.SAV")
        self.assertEqual(actual, payload)

    def test_rejects_multiple_numbered_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "01.SAV").write_bytes(b"one")
            (root / "02.SAV").write_bytes(b"two")
            with self.assertRaisesRegex(producer.ProducerError, "exactly one"):
                producer.read_unambiguous_output(root, 1)

    def test_rejects_wrong_slot(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "02.SAV").write_bytes(b"two")
            with self.assertRaisesRegex(producer.ProducerError, "expected 01.SAV"):
                producer.read_unambiguous_output(root, 1)


class PathSafetyTests(unittest.TestCase):
    def test_rejects_operator_payload_inside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            game = Path(td) / "game"
            game.mkdir()
            with self.assertRaisesRegex(producer.ProducerError, "outside the repository"):
                producer.validate_operator_output_path(ROOT / "artifacts" / "fixture.sav", game)

    def test_rejects_operator_payload_inside_source_tree(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            game = Path(td) / "game"
            game.mkdir()
            with self.assertRaisesRegex(producer.ProducerError, "outside the source game tree"):
                producer.validate_operator_output_path(game / "fixture.sav", game)

    def test_rejects_overwrite_of_existing_operator_payload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            game = root / "game"
            game.mkdir()
            output = root / "existing.sav"
            output.write_bytes(b"keep")
            with self.assertRaisesRegex(producer.ProducerError, "refusing to overwrite"):
                producer.validate_operator_output_path(output, game)

    def test_rejects_artifact_aliasing_action_scenario(self) -> None:
        scenario = ROOT / "docs" / "experiments" / "_synthetic-actions.json"
        snapshot = ROOT / "docs" / "experiments" / "_synthetic-harness.py"
        with self.assertRaisesRegex(producer.ProducerError, "aliases immutable action scenario"):
            producer.validate_detached_output_paths(
                artifact=scenario,
                snapshot=snapshot,
                scenario=scenario,
                fixture_manifest=ROOT / "tools" / "retail-runtime-fixture.json",
                seed_save=Path("/tmp/operator-seed.sav"),
            )

    def test_rejects_artifact_aliasing_fixture_manifest(self) -> None:
        manifest = ROOT / "docs" / "experiments" / "_synthetic-manifest.json"
        snapshot = ROOT / "docs" / "experiments" / "_synthetic-harness.py"
        with self.assertRaisesRegex(producer.ProducerError, "aliases immutable fixture manifest"):
            producer.validate_detached_output_paths(
                artifact=manifest,
                snapshot=snapshot,
                scenario=ROOT / "tools" / "_synthetic-actions.json",
                fixture_manifest=manifest,
                seed_save=Path("/tmp/operator-seed.sav"),
            )


class ArtifactTests(unittest.TestCase):
    def test_preserves_complete_material_harness_source_closure(self) -> None:
        experiments = ROOT / "docs" / "experiments"
        with tempfile.TemporaryDirectory(dir=experiments) as td:
            snapshot = Path(td) / "producer.py"
            harness = producer.preserve_harness_snapshot(snapshot)
            expected_dependencies = {
                "run_t3_multi_planet_fixture.py",
                "run_re4_runtime_state.py",
                "run_re5_runtime_turn_path.py",
                "run_re5_override_witness.py",
                "le_image.py",
            }
            self.assertEqual(set(harness["dependencies"]), expected_dependencies)
            self.assertEqual(
                set(harness["source_snapshots"]),
                {"run_t3_target_written_fixture.py", *expected_dependencies},
            )
            for name, relative in harness["source_snapshots"].items():
                path = ROOT / relative
                self.assertTrue(path.is_file(), name)
                expected = harness["source_sha256"] if name == "run_t3_target_written_fixture.py" else harness["dependencies"][name]
                self.assertEqual(producer.sha256_file(path), expected)

    def test_builds_validator_compatible_identity_shape(self) -> None:
        scenario = {
            "name": "save-one",
            "ordinary_game_method": "ordinary Save Game to empty slot 1",
            "output_slot": 1,
            "max_runtime_seconds": 30.0,
        }
        scenario_path = ROOT / "tools" / "_synthetic-t3-scenario.json"
        original_sha = producer.sha256_file
        producer.sha256_file = lambda path: "a" * 64
        try:
            artifact = producer.build_artifact(
                fixture_id="target-written-test",
                output_name="01.SAV",
                payload=b"fixture-bytes",
                retail_fixture={
                    "id": "ascendancy-retail-en-canonical-antagonizer-runtime-fixture",
                    "manifest_sha256": "814c37ea8683e9c32ce494bcb9568d08a33d3ef8e6d91b99ac07f37958269852",
                    "verified_files": 17,
                },
                dosbox_identity={
                    "filename": "dosbox",
                    "size": 123,
                    "sha256": "b" * 64,
                    "version_output": "DOSBox version test",
                },
                scenario=scenario,
                scenario_path=scenario_path,
                harness={
                    "source": "scripts/run_t3_target_written_fixture.py",
                    "source_sha256": "c" * 64,
                    "source_snapshot": "docs/experiments/T3-target-written-producer-harness.py",
                    "dependencies": {"run_t3_multi_planet_fixture.py": "d" * 64},
                    "source_snapshots": {
                        "run_t3_target_written_fixture.py": "docs/experiments/T3-target-written-producer-harness.py",
                        "run_t3_multi_planet_fixture.py": "docs/experiments/T3-target-written-producer-harness-deps/run_t3_multi_planet_fixture.py",
                    },
                },
            )
        finally:
            producer.sha256_file = original_sha
        self.assertEqual(artifact["artifact_schema"], "ascendancy.validation-fixture-producer/v1")
        self.assertEqual(
            artifact["scenario_contract"],
            "validation-fixture/canonical-target-exact-byte-producer/v1",
        )
        self.assertTrue(artifact["fixture"]["target_written_exact_bytes"])
        self.assertTrue(artifact["oracle"]["exact_byte_match"])
        self.assertFalse(artifact["execution"]["diagnostic_guest_code_writes"])
        self.assertFalse(artifact["execution"]["diagnostic_guest_data_writes"])
        self.assertFalse(artifact["execution"]["source_inputs_modified"])
        self.assertIn("run_t3_multi_planet_fixture.py", artifact["harness"]["dependencies"])


if __name__ == "__main__":
    unittest.main()
