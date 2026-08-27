from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_t3_multi_planet_fixture.py"
SPEC = importlib.util.spec_from_file_location("run_t3_multi_planet_fixture", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
t3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(t3)


class T3SnapshotCollisionGuardTests(unittest.TestCase):
    def test_harness_provenance_rejects_reused_snapshot_with_different_bytes(self):
        experiments = Path(t3.ROOT) / "docs" / "experiments"
        with tempfile.TemporaryDirectory() as source_td, tempfile.TemporaryDirectory(dir=experiments) as snapshot_td:
            source = Path(source_td) / "runner.py"
            source.write_text("first\n", encoding="utf-8")
            snapshot_dir = Path(snapshot_td)

            with mock.patch.object(t3, "harness_source_paths", return_value={"run_t3_multi_planet_fixture.py": source}):
                t3.harness_provenance(snapshot_dir)
                source.write_text("second\n", encoding="utf-8")
                with self.assertRaisesRegex(t3.T3Error, "already exists with different bytes"):
                    t3.harness_provenance(snapshot_dir)


if __name__ == "__main__":
    unittest.main()
