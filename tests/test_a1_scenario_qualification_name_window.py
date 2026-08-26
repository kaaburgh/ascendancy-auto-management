"""The qualification input must be rejected by range geometry, not by its own basis label.

`test_a1_scenario_qualification_basis` already proves the declared `metadata_basis`
string is checked. That check alone cannot see where the bytes actually are: the
operator supplies both the range and the label, so a range covering the
presentation-name window qualifies as long as it is declared under an approved
basis. These cases pin the geometric constraint instead.
"""
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

NAME_START = qual.PRESENTATION_NAME_OFFSET
NAME_END = qual.PRESENTATION_NAME_OFFSET + qual.PRESENTATION_NAME_LENGTH


def encode(document):
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def document(record_offset, metadata=b"planet-a"):
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
                "metadata_basis": "bounded-record-metadata",
                "metadata_hex": metadata.hex(),
                "record_offset": record_offset,
                "metadata_rationale": "synthetic metadata range geometry test",
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


class A1QualificationNameWindowTests(unittest.TestCase):
    def build(self, record_offset, metadata=b"planet-a"):
        raw = encode(document(record_offset, metadata))
        return qual.build_manifest(raw, expected_source(raw))

    def assert_rejected(self, record_offset, metadata=b"planet-a"):
        raw = encode(document(record_offset, metadata))
        with self.assertRaisesRegex(
            qual.A1ScenarioQualificationError, "overlaps the established presentation-name window"
        ):
            qual.build_manifest(raw, expected_source(raw))

    def test_rejects_a_range_inside_the_presentation_name_window(self):
        self.assert_rejected(NAME_START + 4)

    def test_rejects_a_range_starting_at_the_presentation_name_field(self):
        self.assert_rejected(NAME_START)

    def test_rejects_a_range_straddling_the_start_of_the_name_window(self):
        # The exact shape this repository's own synthetic fixture used: 0x20..0x28
        # under the approved basis, with a rationale claiming distinctness from the
        # presentation name that the geometry contradicts.
        self.assert_rejected(NAME_START - 4)

    def test_rejects_a_range_straddling_the_end_of_the_name_window(self):
        self.assert_rejected(NAME_END - 4)

    def test_rejects_a_range_spanning_the_whole_name_window(self):
        self.assert_rejected(NAME_START - 2, b"x" * (qual.PRESENTATION_NAME_LENGTH + 4))

    def test_accepts_a_range_ending_exactly_where_the_name_window_begins(self):
        manifest = self.build(NAME_START - 8)
        self.assertEqual(
            manifest["witness_ranges"]["scenario-planet-a"]["record_offset"], NAME_START - 8
        )

    def test_accepts_a_range_starting_exactly_where_the_name_window_ends(self):
        manifest = self.build(NAME_END)
        self.assertEqual(
            manifest["witness_ranges"]["scenario-planet-a"]["record_offset"], NAME_END
        )

    def test_geometry_is_checked_independently_of_the_declared_basis(self):
        # The basis is the only approved value, so the label check passes and the
        # range is still refused. This is the property the label check cannot have.
        raw = encode(document(NAME_START))
        self.assertEqual(
            json.loads(raw)["planets"][0]["metadata_basis"], "bounded-record-metadata"
        )
        with self.assertRaisesRegex(
            qual.A1ScenarioQualificationError, "overlaps the established presentation-name window"
        ):
            qual.build_manifest(raw, expected_source(raw))

    def test_validate_manifest_rejects_an_overlapping_range_too(self):
        # validate_manifest rebuilds from the same input, so the producer and the
        # validator cannot disagree about which ranges are admissible.
        raw = encode(document(NAME_START))
        with self.assertRaisesRegex(
            qual.A1ScenarioQualificationError, "overlaps the established presentation-name window"
        ):
            qual.validate_manifest(raw, expected_source(raw), {"schema": qual.OUTPUT_SCHEMA})

    def test_window_matches_the_observer_witness_constants(self):
        # The two modules must agree, or a manifest accepted here is rejected later.
        spec = importlib.util.spec_from_file_location(
            "a1_observer_witness", ROOT / "scripts" / "a1_observer_witness.py"
        )
        observer = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(observer)
        self.assertEqual(qual.PRESENTATION_NAME_OFFSET, observer.PRESENTATION_NAME_OFFSET)
        self.assertEqual(qual.PRESENTATION_NAME_LENGTH, observer.PRESENTATION_NAME_LENGTH)


if __name__ == "__main__":
    unittest.main()
