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

ORACLE_SPEC = importlib.util.spec_from_file_location(
    "a1_sidecar_lifetime_oracle", ROOT / "scripts" / "a1_sidecar_lifetime_oracle.py"
)
oracle = importlib.util.module_from_spec(ORACLE_SPEC)
if ORACLE_SPEC.loader is not None and (ROOT / "scripts" / "a1_sidecar_lifetime_oracle.py").exists():
    ORACLE_SPEC.loader.exec_module(oracle)

TARGET_SHA256 = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
RETAIL_MANIFEST_IDENTITY = "tools/retail-runtime-manifest.json#canonical-retail-fixture"
SCENARIO_IDENTITY = "a1-synthetic-two-planet-scenario-v1"


def qualification_document(*, basis="bounded-record-metadata", metadata_a=b"planet-a", metadata_b=b"planet-b"):
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
                "metadata_hex": metadata_a.hex(),
                "record_offset": 0x10,
                "metadata_rationale": "synthetic stable metadata distinct from presentation name",
            },
            {
                "logical_label": "scenario-planet-b",
                "metadata_basis": "bounded-record-metadata",
                "metadata_hex": metadata_b.hex(),
                "record_offset": 0x20,
                "metadata_rationale": "synthetic stable metadata distinct from presentation name",
            },
        ],
    }


def encode(document):
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def expected_source(raw):
    return {
        "schema": qual.EXPECTED_SOURCE_SCHEMA,
        "target_sha256": TARGET_SHA256,
        "retail_manifest_identity": RETAIL_MANIFEST_IDENTITY,
        "scenario_identity": SCENARIO_IDENTITY,
        "qualification_source_sha256": hashlib.sha256(raw).hexdigest(),
    }


def witness(label, raw):
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "scenario_planet": label,
        "metadata_basis": "bounded-record-metadata",
        "metadata_hex": raw.hex(),
        "metadata_sha256": digest,
    }


class A1ScenarioQualificationTests(unittest.TestCase):
    def test_generation_is_deterministic_and_hash_binds_exact_input(self):
        raw = encode(qualification_document())
        expected = expected_source(raw)
        first = qual.build_manifest(raw, expected)
        second = qual.build_manifest(raw, expected)
        self.assertEqual(first, second)
        self.assertEqual(first["source"]["qualification_source_sha256"], hashlib.sha256(raw).hexdigest())
        digest = hashlib.sha256(b"planet-a").hexdigest()
        self.assertEqual(first["planets"]["scenario-planet-a"], digest)
        self.assertEqual(
            first["witness_ranges"]["scenario-planet-a"],
            {
                "metadata_basis": "bounded-record-metadata",
                "record_offset": 0x10,
                "length": len(b"planet-a"),
                "sha256": digest,
                "rationale": "synthetic stable metadata distinct from presentation name",
            },
        )

    def test_rejects_expected_source_mismatch(self):
        raw = encode(qualification_document())
        expected = expected_source(raw)
        expected["scenario_identity"] = "different-scenario"
        with self.assertRaisesRegex(qual.A1ScenarioQualificationError, "scenario_identity must bind"):
            qual.build_manifest(raw, expected)

    def test_rejects_presentation_name_only_qualification(self):
        raw = encode(qualification_document(basis="presentation-name"))
        with self.assertRaisesRegex(qual.A1ScenarioQualificationError, "presentation-name-only"):
            qual.build_manifest(raw, expected_source(raw))

    def test_rejects_empty_and_oversized_metadata(self):
        empty = encode(qualification_document(metadata_a=b""))
        with self.assertRaisesRegex(qual.A1ScenarioQualificationError, "non-empty string|must not be empty"):
            qual.build_manifest(empty, expected_source(empty))

        oversized = encode(qualification_document(metadata_a=b"x" * (qual.MAX_METADATA_BYTES + 1)))
        with self.assertRaisesRegex(qual.A1ScenarioQualificationError, "exceeds 512 byte bound"):
            qual.build_manifest(oversized, expected_source(oversized))

    def test_rejects_missing_or_out_of_record_range(self):
        document = qualification_document()
        del document["planets"][0]["record_offset"]
        raw = encode(document)
        with self.assertRaisesRegex(qual.A1ScenarioQualificationError, "record_offset must be a non-negative integer"):
            qual.build_manifest(raw, expected_source(raw))

        document = qualification_document()
        document["planets"][0]["record_offset"] = qual.PLANET_RECORD_SIZE - 2
        raw = encode(document)
        with self.assertRaisesRegex(qual.A1ScenarioQualificationError, "must fit within"):
            qual.build_manifest(raw, expected_source(raw))

    def test_rejects_missing_metadata_rationale(self):
        document = qualification_document()
        del document["planets"][0]["metadata_rationale"]
        raw = encode(document)
        with self.assertRaisesRegex(qual.A1ScenarioQualificationError, "metadata_rationale must be a non-empty string"):
            qual.build_manifest(raw, expected_source(raw))

    def test_rejects_manifest_digest_not_matching_supplied_bytes(self):
        raw = encode(qualification_document())
        expected = expected_source(raw)
        manifest = qual.build_manifest(raw, expected)
        manifest["planets"]["scenario-planet-a"] = "c" * 64
        with self.assertRaisesRegex(qual.A1ScenarioQualificationError, "does not match supplied bounded metadata"):
            qual.validate_manifest(raw, expected, manifest)

    def test_exact_logical_labels_are_not_normalized(self):
        document = qualification_document()
        document["planets"][0]["logical_label"] = " Planet-A "
        document["planets"][1]["logical_label"] = "Planet-A"
        raw = encode(document)
        manifest = qual.build_manifest(raw, expected_source(raw))
        self.assertEqual(set(manifest["planets"]), {" Planet-A ", "Planet-A"})
        self.assertEqual(set(manifest["witness_ranges"]), {" Planet-A ", "Planet-A"})

    @unittest.skipUnless((ROOT / "scripts" / "a1_sidecar_lifetime_oracle.py").exists(), "oracle not present")
    def test_generated_manifest_projects_to_lifetime_oracle_contract(self):
        raw = encode(qualification_document())
        expected = expected_source(raw)
        manifest = qual.build_manifest(raw, expected)
        oracle_manifest = {
            "schema": oracle.SCENARIO_SCHEMA,
            "source": manifest["source"],
            "planets": manifest["planets"],
        }

        pre_raw = b"planet-a"
        post_raw = b"planet-b"
        pre_digest = hashlib.sha256(pre_raw).hexdigest()
        post_digest = hashlib.sha256(post_raw).hexdigest()

        def selection_point(seq, pointer, label, metadata):
            return {
                "seq": seq,
                "record_pointer": pointer,
                "logical_record": label,
                "qualified_witness": witness(label, metadata),
            }

        def selection_control():
            return {
                "label": "selection-control",
                "replacement": False,
                "observations": {
                    "first": selection_point(1, 0x10100, "scenario-planet-a", pre_raw),
                    "second": selection_point(2, 0x10200, "scenario-planet-b", post_raw),
                    "return": selection_point(3, 0x10100, "scenario-planet-a", pre_raw),
                },
            }

        def replacement(label):
            return {
                "label": label,
                "replacement": True,
                "invalidation_basis": "epoch",
                "observations": {
                    "pre": {
                        "seq": 10,
                        "record_pointer": 0x10100,
                        "logical_record": "scenario-planet-a",
                        "qualified_witness": witness("scenario-planet-a", pre_raw),
                        "array_base": 0x10000,
                        "array_count": 8,
                        "index": 1,
                    },
                    "post": {
                        "seq": 30,
                        "record_pointer": 0x10100,
                        "logical_record": "scenario-planet-b",
                        "qualified_witness": witness("scenario-planet-b", post_raw),
                        "array_base": 0x10000,
                        "array_count": 8,
                        "index": 1,
                    },
                    "reuse_event": {
                        "seq": 25,
                        "kind": "index-reassignment",
                        "before_logical_record": "scenario-planet-a",
                        "after_logical_record": "scenario-planet-b",
                        "before_metadata_sha256": pre_digest,
                        "after_metadata_sha256": post_digest,
                        "array_base": 0x10000,
                        "index": 1,
                    },
                    "epoch_signal": {"before": 7, "after": 8, "seq": 20},
                },
            }

        record = {
            "schema": oracle.SCHEMA,
            "outcome": "positive-epoch-index",
            "inputs": {
                "target_sha256": TARGET_SHA256,
                "retail_manifest_identity": RETAIL_MANIFEST_IDENTITY,
                "scenario_identity": SCENARIO_IDENTITY,
                "qualification_source_sha256": expected["qualification_source_sha256"],
            },
            "claims": {
                "array_base_established": True,
                "array_count_established": True,
                "stable_index_established": True,
                "reuse_detector_established": False,
                "epoch_boundary_established": True,
                "manual_transition_invalidation_established": False,
            },
            "control": {"passed": True},
            "transitions": [
                selection_control(),
                replacement("new-game-reset"),
                replacement("save-load-replacement"),
            ],
        }
        result = oracle.validate_record(record, oracle_manifest, expected)
        self.assertTrue(result["positive_contract_accepted"])


if __name__ == "__main__":
    unittest.main()
