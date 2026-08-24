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


class A1LifetimeObserverProvenanceTests(unittest.TestCase):
    def test_binds_file_backed_immutable_input_into_detached_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qualification, expected = _write_qualification(root)
            action_script = root / "actions.json"
            action_script.write_text('{"steps":["A","B","A"]}\n', encoding="utf-8")
            observer = _write_observer(
                root,
                r'''
                import argparse
                import json
                from pathlib import Path

                p = argparse.ArgumentParser()
                p.add_argument("--scenario-manifest", type=Path, required=True)
                p.add_argument("--record-output", type=Path, required=True)
                p.add_argument("--action-script", type=Path, required=True)
                args = p.parse_args()
                assert args.action_script.read_text()
                args.record_output.write_text(json.dumps({
                    "schema": "ascendancy.a1-sidecar-runtime-lifetime/v1",
                    "outcome": "incomplete-harness",
                    "claims": {
                        "array_base_established": False,
                        "array_count_established": False,
                        "stable_index_established": False,
                        "reuse_detector_established": False,
                        "epoch_boundary_established": False,
                        "manual_transition_invalidation_established": False
                    },
                    "control": {"passed": False},
                    "transitions": []
                }))
                ''',
            )
            record = root / "record.json"

            result = run_observer(
                qualification,
                expected,
                observer,
                ["--action-script", str(action_script)],
                5.0,
                record,
                immutable_inputs={"action-script": action_script},
            )

            digest = hashlib.sha256(action_script.read_bytes()).hexdigest()
            self.assertEqual(result["immutable_inputs"], {"action-script": digest})
            provenance = json.loads(record.read_text())["orchestration_provenance"]
            self.assertEqual(
                provenance["schema"],
                "ascendancy.a1-observer-orchestration-provenance/v1",
            )
            self.assertEqual(provenance["immutable_inputs"], {"action-script": digest})
            self.assertNotIn(str(root), json.dumps(provenance))

    def test_rejects_immutable_input_mutated_during_observer_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qualification, expected = _write_qualification(root)
            action_script = root / "actions.json"
            action_script.write_text('{"steps":["A"]}\n', encoding="utf-8")
            observer = _write_observer(
                root,
                r'''
                import argparse
                import json
                from pathlib import Path

                p = argparse.ArgumentParser()
                p.add_argument("--scenario-manifest", type=Path, required=True)
                p.add_argument("--record-output", type=Path, required=True)
                p.add_argument("--action-script", type=Path, required=True)
                args = p.parse_args()
                args.action_script.write_text('{"steps":["mutated"]}\n')
                args.record_output.write_text(json.dumps({
                    "schema": "ascendancy.a1-sidecar-runtime-lifetime/v1",
                    "outcome": "incomplete-harness",
                    "claims": {
                        "array_base_established": False,
                        "array_count_established": False,
                        "stable_index_established": False,
                        "reuse_detector_established": False,
                        "epoch_boundary_established": False,
                        "manual_transition_invalidation_established": False
                    },
                    "control": {"passed": False},
                    "transitions": []
                }))
                ''',
            )

            with self.assertRaisesRegex(
                A1RuntimeObserverError,
                "immutable input 'action-script' changed during observer execution",
            ):
                run_observer(
                    qualification,
                    expected,
                    observer,
                    ["--action-script", str(action_script)],
                    5.0,
                    root / "record.json",
                    immutable_inputs={"action-script": action_script},
                )

    def test_rejects_observer_supplied_orchestration_provenance(self):
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
                record = {
                    "schema": "ascendancy.a1-sidecar-runtime-lifetime/v1",
                    "outcome": "incomplete-harness",
                    "claims": {
                        "array_base_established": False,
                        "array_count_established": False,
                        "stable_index_established": False,
                        "reuse_detector_established": False,
                        "epoch_boundary_established": False,
                        "manual_transition_invalidation_established": False
                    },
                    "control": {"passed": False},
                    "transitions": [],
                    "orchestration_provenance": {"forged": True}
                }
                args.record_output.write_text(json.dumps(record))
                ''',
            )

            with self.assertRaisesRegex(
                A1RuntimeObserverError,
                "must not pre-populate orchestration_provenance",
            ):
                run_observer(
                    qualification,
                    expected,
                    observer,
                    [],
                    5.0,
                    root / "record.json",
                )


if __name__ == "__main__":
    unittest.main()
