from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fetch_demo", ROOT / "tools" / "fetch_demo.py")
fetch_demo = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(fetch_demo)


class DemoFetchTests(unittest.TestCase):
    def fixture(self, directory: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
        files = {"ASCEND.EXE": b"MZ synthetic demo", "README": b"fixture only\n"}
        archive = directory / "demo.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for name, data in files.items():
                zf.writestr(f"DEMO/{name}", data)
        raw = archive.read_bytes()
        manifest = {
            "schema": 1,
            "id": "synthetic",
            "archive": {
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "sources": [{"url": "https://invalid.example/fixture.zip"}],
            },
            "files": [
                {"name": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                for name, data in files.items()
            ],
        }
        manifest_path = directory / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return archive, manifest_path

    def test_local_archive_extracts_only_after_full_verification(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = pathlib.Path(name)
            archive, manifest = self.fixture(root)
            dest = root / "out"
            rc = fetch_demo.main(["--archive", str(archive), "--dest", str(dest)], manifest)
            self.assertEqual(rc, 0)
            self.assertEqual((dest / "ASCEND.EXE").read_bytes(), b"MZ synthetic demo")
            self.assertEqual(fetch_demo.main(["--verify", "--dest", str(dest)], manifest), 0)

    def test_tampered_archive_fails_without_destination(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = pathlib.Path(name)
            archive, manifest = self.fixture(root)
            archive.write_bytes(archive.read_bytes() + b"tamper")
            dest = root / "out"
            self.assertEqual(fetch_demo.main(["--archive", str(archive), "--dest", str(dest)], manifest), 1)
            self.assertFalse(dest.exists())

    def test_duplicate_casefolded_member_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = pathlib.Path(name)
            archive = root / "demo.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("ASCEND.EXE", b"one")
                zf.writestr("ascend.exe", b"one")
            raw = archive.read_bytes()
            manifest_data = {
                "schema": 1,
                "id": "synthetic",
                "archive": {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "sources": [{"url": "https://invalid.example"}]},
                "files": [{"name": "ASCEND.EXE", "size": 3, "sha256": hashlib.sha256(b"one").hexdigest()}],
            }
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(manifest_data), encoding="utf-8")
            dest = root / "out"
            self.assertEqual(fetch_demo.main(["--archive", str(archive), "--dest", str(dest)], manifest), 1)
            self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
