import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts import a1_sidecar_evidence_bundle as bundle


class A1EvidenceBundleWitnessRangeTests(unittest.TestCase):
    def setUp(self):
        digest_a = hashlib.sha256(b"planet-a").hexdigest()
        digest_b = hashlib.sha256(b"planet-b").hexdigest()
        self.manifest = {
            "schema": "ascendancy.a1-sidecar-scenario-qualification/v2",
            "planets": {
                "scenario-planet-a": digest_a,
                "scenario-planet-b": digest_b,
            },
            "witness_ranges": {
                "scenario-planet-a": {
                    "metadata_basis": "bounded-record-metadata",
                    "record_offset": 0x10,
                    "length": 8,
                    "sha256": digest_a,
                    "rationale": "synthetic non-name witness",
                },
                "scenario-planet-b": {
                    "metadata_basis": "bounded-record-metadata",
                    "record_offset": 0x60,
                    "length": 8,
                    "sha256": digest_b,
                    "rationale": "synthetic non-name witness",
                },
            },
        }

    def record(self, *, offset=0x10, length=8):
        expected = self.manifest["witness_ranges"]["scenario-planet-a"]
        return {
            "outcome": "positive-epoch-index",
            "transitions": [
                {
                    "observations": {
                        "pre": {
                            "qualified_witness": {
                                "scenario_planet": "scenario-planet-a",
                                "metadata_basis": "bounded-record-metadata",
                                "record_offset": offset,
                                "length": length,
                                "metadata_sha256": expected["sha256"],
                            }
                        }
                    }
                }
            ],
        }

    def test_accepts_exact_predeclared_range(self):
        bundle._validate_v2_witness_range_binding(self.record(), self.manifest)

    def test_rejects_wrong_record_offset(self):
        with self.assertRaisesRegex(bundle.A1ScenarioQualificationError, "record_offset must match"):
            bundle._validate_v2_witness_range_binding(self.record(offset=0x11), self.manifest)

    def test_rejects_wrong_length(self):
        with self.assertRaisesRegex(bundle.A1ScenarioQualificationError, "length must match"):
            bundle._validate_v2_witness_range_binding(self.record(length=7), self.manifest)

    def test_rejects_missing_range_fields(self):
        record = self.record()
        del record["transitions"][0]["observations"]["pre"]["qualified_witness"]["record_offset"]
        with self.assertRaisesRegex(bundle.A1ScenarioQualificationError, "record_offset must be"):
            bundle._validate_v2_witness_range_binding(record, self.manifest)

    def test_legacy_or_nonpositive_records_remain_compatible(self):
        bundle._validate_v2_witness_range_binding(
            {"outcome": "incomplete-harness"}, self.manifest
        )
        bundle._validate_v2_witness_range_binding(
            self.record(), {"schema": "ascendancy.a1-sidecar-scenario-qualification/v1"}
        )

    def test_validate_bundle_rejects_wrong_v2_record_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata = bytes.fromhex("0102030405060708")
            qualification = {
                "schema": "ascendancy.a1-sidecar-scenario-qualification-input/v2",
                "source": {
                    "target_sha256": "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00",
                    "retail_manifest_identity": "fixture-v2",
                    "scenario_identity": "scenario-v2",
                },
                "planets": [
                    {
                        "logical_label": "scenario-planet-a",
                        "metadata_basis": "bounded-record-metadata",
                        "metadata_hex": metadata.hex(),
                        "record_offset": 0x10,
                        "metadata_rationale": "bounded non-name metadata witness",
                    }
                ],
            }
            raw = (json.dumps(qualification, sort_keys=True) + "\n").encode("utf-8")
            qualification_path = root / "qualification.json"
            qualification_path.write_bytes(raw)

            expected = {
                "schema": "ascendancy.a1-sidecar-expected-source/v1",
                "target_sha256": qualification["source"]["target_sha256"],
                "retail_manifest_identity": "fixture-v2",
                "scenario_identity": "scenario-v2",
                "qualification_source_sha256": hashlib.sha256(raw).hexdigest(),
            }
            expected_path = root / "expected.json"
            expected_path.write_text(json.dumps(expected), encoding="utf-8")

            record = {
                "outcome": "positive-epoch-index",
                "transitions": [
                    {
                        "observations": {
                            "pre": {
                                "qualified_witness": {
                                    "scenario_planet": "scenario-planet-a",
                                    "metadata_basis": "bounded-record-metadata",
                                    "record_offset": 0x11,
                                    "length": len(metadata),
                                    "metadata_sha256": hashlib.sha256(metadata).hexdigest(),
                                }
                            }
                        }
                    }
                ],
            }
            record_path = root / "record.json"
            record_path.write_text(json.dumps(record), encoding="utf-8")

            with self.assertRaisesRegex(
                bundle.A1ScenarioQualificationError,
                "record_offset must match predeclared v2 witness range",
            ):
                bundle.validate_bundle(qualification_path, expected_path, record_path)


if __name__ == "__main__":
    unittest.main()
