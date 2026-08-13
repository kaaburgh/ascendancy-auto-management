import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_cf4_ui_validation.py"
spec = importlib.util.spec_from_file_location("run_cf4_ui_validation", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class ActionConfigTests(unittest.TestCase):
    def write_config(self, root: Path, value):
        p = root / "actions.json"
        p.write_text(json.dumps(value), encoding="utf-8")
        return p

    def test_accepts_bounded_ui_actions(self):
        with tempfile.TemporaryDirectory() as td:
            p = self.write_config(Path(td), {
                "schema": 1,
                "name": "smoke",
                "pre_video_key_chords": [["Return"]],
                "steps": [
                    {"action": "capture", "name": "before"},
                    {"action": "mouse_capture"},
                    {"action": "mouse_move", "dx": 1, "dy": -2},
                    {"action": "click", "button": 1},
                    {"action": "key_chord", "keys": ["Alt_L", "l"]},
                    {"action": "wait", "seconds": 0.1},
                    {"action": "capture", "name": "after"},
                ],
            })
            cfg = mod.load_actions(p)
            self.assertEqual(cfg["name"], "smoke")

    def test_rejects_unknown_action(self):
        with tempfile.TemporaryDirectory() as td:
            p = self.write_config(Path(td), {
                "schema": 1, "name": "bad",
                "steps": [{"action": "capture", "name": "a"}, {"action": "shell", "cmd": "rm"}, {"action": "capture", "name": "b"}],
            })
            with self.assertRaisesRegex(ValueError, "unknown action"):
                mod.load_actions(p)

    def test_rejects_unsafe_capture_name(self):
        with tempfile.TemporaryDirectory() as td:
            p = self.write_config(Path(td), {
                "schema": 1, "name": "bad",
                "steps": [{"action": "capture", "name": "../escape"}, {"action": "capture", "name": "b"}],
            })
            with self.assertRaisesRegex(ValueError, "unsafe capture name"):
                mod.load_actions(p)

    def test_requires_two_capture_checkpoints(self):
        with tempfile.TemporaryDirectory() as td:
            p = self.write_config(Path(td), {"schema": 1, "name": "bad", "steps": [{"action": "capture", "name": "only"}]})
            with self.assertRaisesRegex(ValueError, "at least two"):
                mod.load_actions(p)


class FixtureVerificationTests(unittest.TestCase):
    def test_verifies_case_insensitively_without_modifying_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = root / "antag.exe"
            payload.write_bytes(b"abc")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema": 1,
                "id": "fixture",
                "files": [{"name": "ANTAG.EXE", "size": 3, "sha256": hashlib.sha256(b"abc").hexdigest()}],
            }), encoding="utf-8")
            result = mod.verify_fixture(root, manifest)
            self.assertEqual(result["id"], "fixture")
            self.assertEqual(payload.read_bytes(), b"abc")

    def test_rejects_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "ANTAG.EXE").write_bytes(b"abc")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema": 1,
                "id": "fixture",
                "files": [{"name": "ANTAG.EXE", "size": 3, "sha256": "0" * 64}],
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                mod.verify_fixture(root, manifest)

    def test_rejects_casefold_collision(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "A.EXE").write_bytes(b"a")
            (root / "a.exe").write_bytes(b"b")
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                mod._casefold_index(root)


class PngTests(unittest.TestCase):
    def test_reads_png_dimensions_from_header(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.png"
            p.write_bytes(b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + (640).to_bytes(4, "big") + (480).to_bytes(4, "big"))
            self.assertEqual(mod.png_dimensions(p), (640, 480))


if __name__ == "__main__":
    unittest.main()
