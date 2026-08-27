import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_cf4_ui_validation.py"
spec = importlib.util.spec_from_file_location("run_cf4_ui_validation", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class ExpectedExeHashGuardTests(unittest.TestCase):
    def test_cli_rejects_executable_hash_mismatch_before_tool_lookup(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            game = root / "game"
            game.mkdir()
            payload = b"synthetic executable"
            (game / "GAME.EXE").write_bytes(payload)

            fixture = root / "manifest.json"
            fixture.write_text(json.dumps({
                "schema": 1,
                "id": "hash-guard",
                "files": [{
                    "name": "GAME.EXE",
                    "size": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }],
            }), encoding="utf-8")

            actions = root / "actions.json"
            actions.write_text(json.dumps({
                "schema": 2,
                "name": "hash-guard",
                "max_runtime_seconds": 5,
                "steps": [
                    {
                        "action": "capture",
                        "name": "before",
                        "oracles": [{
                            "type": "rgb_region_sha256",
                            "x": 0,
                            "y": 0,
                            "width": 1,
                            "height": 1,
                            "sha256": "0" * 64,
                        }],
                    },
                    {"action": "capture", "name": "after"},
                ],
            }), encoding="utf-8")

            artifacts = root / "artifacts"
            stderr = io.StringIO()
            with mock.patch.object(
                mod.shutil,
                "which",
                side_effect=AssertionError(
                    "tool lookup should not run before executable identity rejection"
                ),
            ), contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as cm:
                    mod.main([
                        "--game-dir", str(game),
                        "--exe", "GAME.EXE",
                        "--expected-exe-sha256", "0" * 64,
                        "--fixture-manifest", str(fixture),
                        "--actions", str(actions),
                        "--artifacts", str(artifacts),
                    ])

            self.assertEqual(cm.exception.code, 2)
            self.assertIn("executable sha256 mismatch:", stderr.getvalue())
            self.assertFalse(artifacts.exists())


if __name__ == "__main__":
    unittest.main()
