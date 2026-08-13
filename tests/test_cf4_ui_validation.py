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


def oracle(sha="0" * 64):
    return {
        "type": "rgb_region_sha256",
        "x": 0,
        "y": 0,
        "width": 1,
        "height": 1,
        "sha256": sha,
    }


class ActionConfigTests(unittest.TestCase):
    def write_config(self, root: Path, value):
        p = root / "actions.json"
        p.write_text(json.dumps(value), encoding="utf-8")
        return p

    def base(self):
        return {
            "schema": 2,
            "name": "smoke",
            "max_runtime_seconds": 30,
            "steps": [
                {"action": "capture", "name": "before", "oracles": [oracle()]},
                {"action": "capture", "name": "after"},
            ],
        }

    def test_accepts_bounded_ui_actions(self):
        with tempfile.TemporaryDirectory() as td:
            p = self.write_config(Path(td), {
                "schema": 2,
                "name": "smoke",
                "max_runtime_seconds": 30,
                "pre_video_key_chords": [["Return"]],
                "steps": [
                    {"action": "capture", "name": "before", "oracles": [oracle()]},
                    {"action": "mouse_capture", "settle_seconds": 0.1},
                    {"action": "mouse_move", "dx": 1, "dy": -2, "settle_seconds": 0.1},
                    {"action": "click", "button": 1, "settle_seconds": 0.1},
                    {"action": "key_chord", "keys": ["Alt_L", "l"], "settle_seconds": 0.1},
                    {"action": "wait", "seconds": 0.1},
                    {"action": "capture", "name": "after", "min_change_ratio_from_previous": 0.01},
                ],
            })
            cfg = mod.load_actions(p)
            self.assertEqual(cfg["name"], "smoke")

    def test_rejects_unknown_action(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self.base()
            cfg["steps"].insert(1, {"action": "shell", "cmd": "rm"})
            with self.assertRaisesRegex(ValueError, "unknown action"):
                mod.load_actions(self.write_config(Path(td), cfg))

    def test_rejects_unsafe_capture_name(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self.base()
            cfg["steps"][0]["name"] = "../escape"
            with self.assertRaisesRegex(ValueError, "unsafe capture name"):
                mod.load_actions(self.write_config(Path(td), cfg))

    def test_rejects_duplicate_capture_names(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self.base()
            cfg["steps"][1]["name"] = "before"
            with self.assertRaisesRegex(ValueError, "duplicate capture name"):
                mod.load_actions(self.write_config(Path(td), cfg))

    def test_requires_two_capture_checkpoints(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self.base()
            cfg["steps"] = [cfg["steps"][0]]
            with self.assertRaisesRegex(ValueError, "at least two"):
                mod.load_actions(self.write_config(Path(td), cfg))

    def test_requires_screen_specific_oracle(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self.base()
            cfg["steps"][0].pop("oracles")
            with self.assertRaisesRegex(ValueError, "screen-specific capture oracle"):
                mod.load_actions(self.write_config(Path(td), cfg))

    def test_rejects_too_many_steps(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self.base()
            cfg["steps"] = [{"action": "wait", "seconds": 0}] * (mod.MAX_STEPS + 1)
            with self.assertRaisesRegex(ValueError, "too many steps"):
                mod.load_actions(self.write_config(Path(td), cfg))

    def test_rejects_too_many_captures(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self.base()
            cfg["steps"] = [
                {"action": "capture", "name": f"c{i}", "oracles": [oracle()] if i == 0 else []}
                for i in range(mod.MAX_CAPTURES + 1)
            ]
            with self.assertRaisesRegex(ValueError, "too many captures"):
                mod.load_actions(self.write_config(Path(td), cfg))

    def test_rejects_invalid_settle_seconds_for_all_settled_actions(self):
        for action_step in (
            {"action": "mouse_capture"},
            {"action": "mouse_move", "dx": 0, "dy": 0},
            {"action": "click"},
            {"action": "key_chord", "keys": ["Return"]},
        ):
            with self.subTest(action=action_step["action"]), tempfile.TemporaryDirectory() as td:
                cfg = self.base()
                action_step = dict(action_step, settle_seconds=999)
                cfg["steps"].insert(1, action_step)
                with self.assertRaisesRegex(ValueError, "settle_seconds"):
                    mod.load_actions(self.write_config(Path(td), cfg))

    def test_rejects_declared_sleeps_that_exhaust_runtime_budget(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self.base()
            cfg["max_runtime_seconds"] = 5
            cfg["startup_wait_seconds"] = 5
            with self.assertRaisesRegex(ValueError, "leave no runtime budget"):
                mod.load_actions(self.write_config(Path(td), cfg))

    def test_rejects_bad_oracle_region_and_hash(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self.base()
            cfg["steps"][0]["oracles"][0]["x"] = 639
            cfg["steps"][0]["oracles"][0]["width"] = 2
            with self.assertRaisesRegex(ValueError, "region exceeds"):
                mod.load_actions(self.write_config(Path(td), cfg))
        with tempfile.TemporaryDirectory() as td:
            cfg = self.base()
            cfg["steps"][0]["oracles"][0]["sha256"] = "ABC"
            with self.assertRaisesRegex(ValueError, "64 lowercase hex"):
                mod.load_actions(self.write_config(Path(td), cfg))

    def test_first_capture_cannot_require_transition_delta(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self.base()
            cfg["steps"][0]["min_change_ratio_from_previous"] = 0.01
            with self.assertRaisesRegex(ValueError, "first capture"):
                mod.load_actions(self.write_config(Path(td), cfg))


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


class PixelOracleTests(unittest.TestCase):
    def test_hashes_exact_rgb_region(self):
        raw = bytes(range(12))
        expected = hashlib.sha256(raw[3:6] + raw[9:12]).hexdigest()
        self.assertEqual(mod.hash_rgb_region(raw, 2, 2, 1, 0, 1, 2), expected)

    def test_rejects_wrong_rgb_byte_count(self):
        with self.assertRaisesRegex(ValueError, "RGB byte count mismatch"):
            mod.hash_rgb_region(b"short", 2, 2, 0, 0, 1, 1)


class PngTests(unittest.TestCase):
    def test_reads_png_dimensions_from_header(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.png"
            p.write_bytes(b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + (640).to_bytes(4, "big") + (480).to_bytes(4, "big"))
            self.assertEqual(mod.png_dimensions(p), (640, 480))


if __name__ == "__main__":
    unittest.main()
