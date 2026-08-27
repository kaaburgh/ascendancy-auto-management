from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_t3_multi_planet_fixture.py"
SPEC = importlib.util.spec_from_file_location("run_t3_multi_planet_fixture_snapshot_tree_guard", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
t3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(t3)


class T3SnapshotSourceTreeGuardTests(unittest.TestCase):
    def test_cli_rejects_harness_snapshot_inside_source_game_tree(self):
        experiments = Path(t3.ROOT) / "docs" / "experiments"
        with tempfile.TemporaryDirectory(dir=experiments) as td:
            root = Path(td)
            game = root / "game"
            game.mkdir()
            candidate = root / "candidate.gam"
            manifest = root / "manifest.json"
            artifact = root / "run.json"
            snapshot = game / "harness"
            candidate.write_bytes(b"save")
            manifest.write_text("{}", encoding="utf-8")

            successful_result = {
                "candidate_fixture": {"sha256": "00" * 32},
                "role_claim": {
                    "player_race_id": 0,
                    "player_owned_planet_count": 2,
                    "player_planet_names": ["A", "B"],
                },
            }
            with (
                mock.patch.object(t3, "resolve_executable", return_value=Path("/bin/true")),
                mock.patch.object(t3, "run", return_value=successful_result) as runtime_run,
            ):
                rc = t3.main([
                    "--game-dir", str(game),
                    "--dosbox", "dosbox",
                    "--fixture-manifest", str(manifest),
                    "--candidate-save", str(candidate),
                    "--candidate-sha256", "00" * 32,
                    "--fixture-id", "fixture",
                    "--artifact", str(artifact),
                    "--harness-snapshot-dir", str(snapshot),
                ])

            self.assertEqual(rc, 1)
            runtime_run.assert_not_called()
            self.assertFalse(artifact.exists())


if __name__ == "__main__":
    unittest.main()
