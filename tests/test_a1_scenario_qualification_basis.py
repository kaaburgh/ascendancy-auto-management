import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "a1_scenario_qualification", ROOT / "scripts" / "a1_scenario_qualification.py"
)
qual = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(qual)

TARGET_SHA256 = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
RETAIL_MANIFEST_IDENTITY = "tools/retail-runtime-manifest.json#canonical-retail-fixture"
SCENARIO_IDENTITY = "a1-synthetic-two-planet-scenario-v1"


def encode(document):
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def document(basis):
    return {
        "schema": qual.INPUT_SCHEMA,
        "source": {
            "target_sha256": TARGET_SHA256,
            "retail_manifest_identity": RETAIL_MANIFEST_IDENTITY,
            "scenario_identity": SCENARIO_IDENTITY,
        },
        "planets": [
            {
                "logical_label": "scenario-planet-a",
                "metadata_basis": basis,
                "metadata_hex": b"planet-a".hex(),
            }
        ],
    }


def expected_source(raw):
    return {
        "schema": qual.EXPECTED_SOURCE_SCHEMA,
        "target_sha256": TARGET_SHA256,
        "retail_manifest_identity": RETAIL_MANIFEST_IDENTITY,
        "scenario_identity": SCENARIO_IDENTITY,
        "qualification_source_sha256": hashlib.sha256(raw).hexdigest(),
    }


class A1ScenarioQualificationBasisTests(unittest.TestCase):
    def test_accepts_only_canonical_bounded_record_metadata_basis(self):
        raw = encode(document("bounded-record-metadata"))
        manifest = qual.build_manifest(raw, expected_source(raw))
        self.assertIn("scenario-planet-a", manifest["planets"])

    def test_rejects_noncanonical_or_unknown_metadata_basis(self):
        for basis in ("presentation-name", "presentation_name", "Presentation-Name", "arbitrary-metadata"):
            with self.subTest(basis=basis):
                raw = encode(document(basis))
                with self.assertRaisesRegex(qual.A1ScenarioQualificationError, "metadata_basis must be one of"):
                    qual.build_manifest(raw, expected_source(raw))


if __name__ == "__main__":
    unittest.main()
