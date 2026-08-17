from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_t3_multi_planet_fixture.py"
SPEC = importlib.util.spec_from_file_location("run_t3_multi_planet_fixture", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
t3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(t3)


class T3MultiPlanetFixtureTests(unittest.TestCase):
    def make_sequence(self, base: int = 0x1000, count: int = t3.EXPECTED_PLANET_RECORD_COUNT):
        size = base + count * t3.re4.RECORD_SIZE + 0x200
        blob = bytearray(size)
        for index in range(count):
            record = base + index * t3.re4.RECORD_SIZE
            name = f"Planet {index:03d}".encode("ascii") + b"\0"
            blob[record + t3.re4.NAME_OFFSET:record + t3.re4.NAME_OFFSET + len(name)] = name
            blob[record + t3.re5.OWNER_OFFSET] = 0xFF
            blob[record + t3.re5.SLOT_OFFSET:record + t3.re5.SLOT_OFFSET + 2] = b"\xff\xff"
            blob[record + t3.re5.ACTION_OFFSET] = 0xFF
        return blob, base

    def test_resolve_executable_preserves_path_lookup(self):
        with mock.patch.object(t3.shutil, "which", return_value="/opt/bin/dosbox"):
            self.assertEqual(t3.resolve_executable("dosbox"), Path("/opt/bin/dosbox"))

    def test_executable_identity_records_hash_and_version(self):
        with tempfile.TemporaryDirectory() as td:
            exe = Path(td) / "dosbox"
            exe.write_text("#!/bin/sh\necho 'DOSBox version 0.74-3'\n", encoding="utf-8")
            exe.chmod(0o755)
            identity = t3.executable_identity(exe)
            self.assertEqual(identity["filename"], "dosbox")
            self.assertEqual(identity["sha256"], t3.sha256_file(exe))
            self.assertIn("DOSBox version 0.74-3", identity["version_output"])

    def test_artifact_contract_requires_runtime_identity_v2(self):
        self.assertEqual(t3.ARTIFACT_SCHEMA, "ascendancy.t3-multi-planet-fixture/v2")
        self.assertEqual(t3.SCENARIO_CONTRACT, "t3/operator-save-runtime-verify/v2")
        self.assertTrue(Path(t3.re4.__file__).is_file())
        self.assertTrue(Path(t3.re5.__file__).is_file())
        self.assertTrue(Path(t3.override_witness.__file__).is_file())
        self.assertTrue(Path(t3.override_witness.le_image.__file__).is_file())

    def test_harness_provenance_materializes_complete_source_closure(self):
        experiments = Path(t3.ROOT) / "docs" / "experiments"
        with tempfile.TemporaryDirectory(dir=experiments) as td:
            snapshot_dir = Path(td)
            provenance = t3.harness_provenance(snapshot_dir)
            expected = {
                "run_t3_multi_planet_fixture.py",
                "run_re4_runtime_state.py",
                "run_re5_runtime_turn_path.py",
                "run_re5_override_witness.py",
                "le_image.py",
            }
            self.assertEqual(set(provenance["harness_source_snapshots"]), expected)
            self.assertEqual(
                set(provenance["harness_dependencies"]),
                expected - {"run_t3_multi_planet_fixture.py"},
            )
            for name, relative in provenance["harness_source_snapshots"].items():
                path = Path(t3.ROOT) / relative
                self.assertTrue(path.is_file())
                expected_hash = (
                    provenance["runner_source_sha256"]
                    if name == "run_t3_multi_planet_fixture.py"
                    else provenance["harness_dependencies"][name]
                )
                self.assertEqual(t3.sha256_file(path), expected_hash)

    def test_artifact_path_rejects_candidate_alias(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            game = root / "game"
            game.mkdir()
            candidate = root / "resume.gam"
            manifest = root / "manifest.json"
            candidate.write_bytes(b"save")
            manifest.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(t3.T3Error, "aliases"):
                t3.validate_output_paths(
                    artifact=candidate, candidate=candidate, fixture_manifest=manifest, game_dir=game
                )

    def test_artifact_path_rejects_manifest_alias(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            game = root / "game"
            game.mkdir()
            candidate = root / "resume.gam"
            manifest = root / "manifest.json"
            candidate.write_bytes(b"save")
            manifest.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(t3.T3Error, "aliases"):
                t3.validate_output_paths(
                    artifact=manifest, candidate=candidate, fixture_manifest=manifest, game_dir=game
                )

    def test_cli_rejects_alias_before_runtime_run(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            game = root / "game"
            game.mkdir()
            candidate = root / "resume.gam"
            manifest = root / "manifest.json"
            candidate.write_bytes(b"save")
            manifest.write_text("{}", encoding="utf-8")
            with mock.patch.object(t3, "run") as runtime_run:
                rc = t3.main([
                    "--game-dir", str(game),
                    "--dosbox", "dosbox",
                    "--fixture-manifest", str(manifest),
                    "--candidate-save", str(candidate),
                    "--candidate-sha256", "00" * 32,
                    "--fixture-id", "fixture",
                    "--runner-revision", "deadbeef",
                    "--artifact", str(candidate),
                ])
            self.assertEqual(rc, 1)
            runtime_run.assert_not_called()

    def test_artifact_path_rejects_source_game_tree(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            game = root / "game"
            game.mkdir()
            candidate = root / "resume.gam"
            manifest = root / "manifest.json"
            candidate.write_bytes(b"save")
            manifest.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(t3.T3Error, "source game tree"):
                t3.validate_output_paths(
                    artifact=game / "run.json", candidate=candidate, fixture_manifest=manifest, game_dir=game
                )

    def test_atomic_json_writer_replaces_complete_document(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            path.write_text("old", encoding="utf-8")
            t3.write_json_atomic(path, {"status": "passed", "value": 7})
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                json.dumps({"status": "passed", "value": 7}, indent=2, sort_keys=True) + "\n",
            )
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])

    def test_discovers_unique_305_record_runtime_sequence(self):
        blob, base = self.make_sequence()
        sequence = t3.discover_planet_record_sequence(bytes(blob))
        self.assertEqual(len(sequence), t3.EXPECTED_PLANET_RECORD_COUNT)
        self.assertEqual(sequence[0], (base, "Planet 000"))
        self.assertEqual(sequence[-1][1], "Planet 304")

    def test_discovery_fails_closed_on_second_full_sequence(self):
        blob1, base1 = self.make_sequence(0x1000)
        blob2, base2 = self.make_sequence(0xA000 + len(blob1))
        size = max(len(blob1), len(blob2))
        merged = bytearray(size)
        merged[:len(blob1)] = blob1
        for index in range(t3.EXPECTED_PLANET_RECORD_COUNT):
            record = base2 + index * t3.re4.RECORD_SIZE
            name = f"Other {index:03d}".encode("ascii") + b"\0"
            merged[record + t3.re4.NAME_OFFSET:record + t3.re4.NAME_OFFSET + len(name)] = name
            merged[record + t3.re5.OWNER_OFFSET] = 0xFF
            merged[record + t3.re5.SLOT_OFFSET:record + t3.re5.SLOT_OFFSET + 2] = b"\xff\xff"
            merged[record + t3.re5.ACTION_OFFSET] = 0xFF
        with self.assertRaisesRegex(t3.T3Error, "exactly one 305-record"):
            t3.discover_planet_record_sequence(bytes(merged))

    def test_discovery_fails_closed_on_duplicate_names(self):
        blob, base = self.make_sequence()
        second = base + t3.re4.RECORD_SIZE
        duplicate = b"Planet 000\0"
        blob[second + t3.re4.NAME_OFFSET:second + t3.re4.NAME_OFFSET + 32] = b"\0" * 32
        blob[second + t3.re4.NAME_OFFSET:second + t3.re4.NAME_OFFSET + len(duplicate)] = duplicate
        with self.assertRaisesRegex(t3.T3Error, "duplicate names"):
            t3.discover_planet_record_sequence(bytes(blob))

    @staticmethod
    def records(player_count: int = 3, empty_count: int = 3):
        rows = []
        for index in range(t3.EXPECTED_PLANET_RECORD_COUNT):
            player = index < player_count
            empty = index < empty_count
            rows.append(
                {
                    "name": f"Planet {index:03d}",
                    "owner_0x57": 0 if player else 0xFF,
                    "slot_0x52": "ffff" if empty else "0001",
                    "action_0x54": "ff" if empty else "01",
                    "managed_0x5a": "00000000",
                }
            )
        return rows

    def test_role_oracle_accepts_three_owned_empty_planets(self):
        result = t3.evaluate_fixture_records(self.records(), 0)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["player_owned_planet_count"], 3)
        self.assertEqual(len(result["planets_with_empty_current_action_at_load"]), 3)

    def test_role_oracle_rejects_single_owned_planet(self):
        result = t3.evaluate_fixture_records(self.records(player_count=1, empty_count=1), 0)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["checks"]["at_least_two_player_owned_planets"])

    def test_role_oracle_rejects_no_empty_player_action(self):
        result = t3.evaluate_fixture_records(self.records(player_count=3, empty_count=0), 0)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["checks"]["at_least_one_player_planet_has_empty_current_action"])

    def test_role_oracle_rejects_wrong_runtime_record_count(self):
        result = t3.evaluate_fixture_records(self.records()[:-1], 0)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["checks"]["runtime_record_count_matches_contract"])


if __name__ == "__main__":
    unittest.main()
