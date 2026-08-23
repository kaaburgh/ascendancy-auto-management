import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.a1_sidecar_evidence_bundle import validate_bundle


class A1SidecarEvidenceBundleTests(unittest.TestCase):
    def test_builds_qualified_manifest_before_validating_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qualification = {
                "schema": "ascendancy.a1-sidecar-scenario-qualification-input/v1",
                "source": {
                    "target_sha256": "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00",
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
                "target_sha256": qualification["source"]["target_sha256"],
                "retail_manifest_identity": "fixture-v1",
                "scenario_identity": "scenario-v1",
                "qualification_source_sha256": hashlib.sha256(raw).hexdigest(),
            }
            expected_path = root / "expected.json"
            expected_path.write_text(json.dumps(expected), encoding="utf-8")

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
            record_path = root / "record.json"
            record_path.write_text(json.dumps(record), encoding="utf-8")
            manifest_path = root / "manifest.json"

            result = validate_bundle(
                qualification_path,
                expected_path,
                record_path,
                manifest_path,
            )

            self.assertEqual(result["outcome"], "incomplete-harness")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["planets"]["Planet A"],
                hashlib.sha256(bytes.fromhex("01020304")).hexdigest(),
            )

    def test_rejects_changed_qualification_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qualification_path = root / "qualification.json"
            qualification_path.write_text(
                json.dumps(
                    {
                        "schema": "ascendancy.a1-sidecar-scenario-qualification-input/v1",
                        "source": {
                            "target_sha256": "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00",
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
                ),
                encoding="utf-8",
            )
            expected_path = root / "expected.json"
            expected_path.write_text(
                json.dumps(
                    {
                        "schema": "ascendancy.a1-sidecar-expected-source/v1",
                        "target_sha256": "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00",
                        "retail_manifest_identity": "fixture-v1",
                        "scenario_identity": "scenario-v1",
                        "qualification_source_sha256": "0" * 64,
                    }
                ),
                encoding="utf-8",
            )
            record_path = root / "record.json"
            record_path.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "qualification input bytes"):
                validate_bundle(qualification_path, expected_path, record_path)


if __name__ == "__main__":
    unittest.main()
