import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "a1_sidecar_evidence_bundle", ROOT / "scripts" / "a1_sidecar_evidence_bundle.py"
)
bundle = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(bundle)


class A1EvidenceBundleWitnessRangeTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "schema": "ascendancy.a1-sidecar-scenario-qualification/v2",
            "witness_ranges": {
                "scenario-planet-a": {"record_offset": 0x10, "length": 8},
                "scenario-planet-b": {"record_offset": 0x20, "length": 8},
            },
        }

    def record(self, *, offset=0x10, length=8):
        return {
            "outcome": "positive-epoch-index",
            "transitions": [
                {
                    "observations": {
                        "pre": {
                            "qualified_witness": {
                                "scenario_planet": "scenario-planet-a",
                                "record_offset": offset,
                                "length": length,
                            }
                        }
                    }
                }
            ],
        }

    def test_accepts_exact_predeclared_range(self):
        bundle._validate_v2_witness_range_binding(self.record(), self.manifest)

    def test_rejects_wrong_record_offset(self):
        with self.assertRaisesRegex(bundle.A1ScenarioQualificationError, "record_offset does not match"):
            bundle._validate_v2_witness_range_binding(self.record(offset=0x11), self.manifest)

    def test_rejects_wrong_length(self):
        with self.assertRaisesRegex(bundle.A1ScenarioQualificationError, "length does not match"):
            bundle._validate_v2_witness_range_binding(self.record(length=7), self.manifest)

    def test_rejects_missing_range_fields(self):
        record = self.record()
        del record["transitions"][0]["observations"]["pre"]["qualified_witness"]["record_offset"]
        with self.assertRaisesRegex(bundle.A1ScenarioQualificationError, "record_offset does not match"):
            bundle._validate_v2_witness_range_binding(record, self.manifest)

    def test_legacy_or_nonpositive_records_remain_compatible(self):
        bundle._validate_v2_witness_range_binding(
            {"outcome": "incomplete-harness"}, self.manifest
        )
        bundle._validate_v2_witness_range_binding(
            self.record(), {"schema": "ascendancy.a1-sidecar-scenario-qualification/v1"}
        )


if __name__ == "__main__":
    unittest.main()
