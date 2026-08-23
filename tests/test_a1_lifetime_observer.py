import hashlib
import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from scripts.run_a1_lifetime_observer import A1RuntimeObserverError, run_observer

TARGET = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"


def _write_qualification(root: Path) -> tuple[Path, Path]:
    qualification = {
        "schema": "ascendancy.a1-sidecar-scenario-qualification-input/v1",
        "source": {
            "target_sha256": TARGET,
            "retail_manifest_identity": "fixture-v1",
            "scenario_identity": "scenario-v1",
        },
        "planets": [
            {
                "logical_label": "Planet A",
                "metadata_basis": "bounded-record-metadata",
                "metadata_hex": "01020304",
            }
        ],
    }
    qualification_path = root / "qualification.json"
    raw = (json.dumps(qualification, sort_keys=True) + "\n").encode("utf-8")
    qualification_path.write_bytes(raw)
    expected = {
        "schema": "ascendancy.a1-sidecar-expected-source/v1",
        "target_sha256": TARGET,
        "retail_manifest_identity": "fixture-v1",
        "scenario_identity": "scenario-v1",
        "qualification_source_sha256": hashlib.sha256(raw).hexdigest(),
    }
    expected_path = root / "expected.json"
    expected_path.write_text(json.dumps(expected), encoding="utf-8")
    return qualification_path, expected_path


def _write_observer(root: Path, body: str) -> Path:
    path = root / "observer.py"
    path.write_text("#!/usr/bin/env python3\n" + textwrap.dedent(body), encoding="utf-8")
    path.chmod(0o755)
    return path


class A1LifetimeObserverRunnerTests(unittest.TestCase):
    def test_runs_observer_and_validates_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qualification, expected = _write_qualification(root)
            observer = _write_observer(
                root,
                r'''
                import argparse
                import json
                from pathlib import Path

                p = argparse.ArgumentParser()
                p.add_argument("--scenario-manifest", type=Path, required=True)
                p.add_argument("--record-output", type=Path, required=True)
                args = p.parse_args()
                manifest = json.loads(args.scenario_manifest.read_text())
                record = {
                    "schema": "ascendancy.a1-sidecar-runtime-lifetime/v1",
                    "outcome": "incomplete-harness",
                    "claims": {
                        "array_base_established": False,
                        "array_count_established": False,
                        "stable_index_established": False,
                        "reuse_detector_established": False,
                        "epoch_boundary_established": False,
                        "manual_transition_invalidation_established": False,
                    },
                    "control": {"passed": False},
                    "transitions": [],
                }
                assert manifest["planets"]["Planet A"]
                args.record_output.write_text(json.dumps(record))
                ''',
            )
            record = root / "record.json"
            manifest = root / "manifest.json"

            result = run_observer(
                qualification, expected, observer, [], 5.0, record, manifest
            )

            self.assertEqual(result["oracle_result"]["outcome"], "incomplete-harness")
            self.assertEqual(result["observer_sha256"], hashlib.sha256(observer.read_bytes()).hexdigest())
            self.assertTrue(record.is_file())
            self.assertEqual(json.loads(manifest.read_text())["source"]["scenario_identity"], "scenario-v1")

    def test_rejects_preexisting_record_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qualification, expected = _write_qualification(root)
            observer = _write_observer(root, "raise SystemExit(0)\n")
            record = root / "record.json"
            record.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(A1RuntimeObserverError, "must not already exist"):
                run_observer(qualification, expected, observer, [], 5.0, record)

    def test_rejects_nonzero_observer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qualification, expected = _write_qualification(root)
            observer = _write_observer(root, "raise SystemExit(7)\n")
            with self.assertRaisesRegex(A1RuntimeObserverError, "observer exited with 7"):
                run_observer(qualification, expected, observer, [], 5.0, root / "record.json")

    def test_rejects_manifest_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qualification, expected = _write_qualification(root)
            observer = _write_observer(
                root,
                r'''
                import argparse
                import json
                from pathlib import Path

                p = argparse.ArgumentParser()
                p.add_argument("--scenario-manifest", type=Path, required=True)
                p.add_argument("--record-output", type=Path, required=True)
                args = p.parse_args()
                args.scenario_manifest.write_text("{}")
                record = {
                    "schema": "ascendancy.a1-sidecar-runtime-lifetime/v1",
                    "outcome": "incomplete-harness",
                    "claims": {
                        "array_base_established": False,
                        "array_count_established": False,
                        "stable_index_established": False,
                        "reuse_detector_established": False,
                        "epoch_boundary_established": False,
                        "manual_transition_invalidation_established": False,
                    },
                    "control": {"passed": False},
                    "transitions": [],
                }
                args.record_output.write_text(json.dumps(record))
                ''',
            )
            with self.assertRaisesRegex(A1RuntimeObserverError, "scenario manifest changed"):
                run_observer(qualification, expected, observer, [], 5.0, root / "record.json")


if __name__ == "__main__":
    unittest.main()
