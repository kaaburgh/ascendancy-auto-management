import hashlib
import json
import unittest

from scripts.a1_manual_transition_oracle import A1ManualInvalidationError, validate_record


TARGET = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
HARNESS = "1" * 64
QUALIFICATION = "3" * 64


def positive_record():
    return {
        "schema": "ascendancy.a1-manual-transition-invalidation/v1",
        "outcome": "positive-lossless-invalidation",
        "inputs": {
            "target_sha256": TARGET,
            "harness_sha256": HARNESS,
            "scenario_identity": "bounded-round-trip-v1",
        },
        "claims": {"manual_transition_invalidation_established": True},
        "transitions": [
            {
                "kind": "managed-manual-managed",
                "managed_before_seq": 10,
                "manual_write_seq": 20,
                "invalidation_seq": 20,
                "managed_after_seq": 30,
                "managed_before_value": 0xFFFFFFFF,
                "manual_value": 0,
                "managed_after_value": 0xFFFFFFFF,
                "write_source": {"mechanism": "lossless-observed-write-boundary", "lossless": True},
                "stale_profile_visible_after_manual": False,
            }
        ],
        "coverage": {
            "all_relevant_zero_write_paths_established": True,
            "equivalent_lossless_boundary_established": False,
            "periodic_sampling_only": False,
        },
    }


def coverage_evidence(basis="all-relevant-zero-write-paths"):
    return {
        "schema": "ascendancy.a1-manual-transition-coverage-evidence/v1",
        "target_sha256": TARGET,
        "harness_sha256": HARNESS,
        "scenario_identity": "bounded-round-trip-v1",
        "coverage_basis": basis,
        "write_source_mechanism": "lossless-observed-write-boundary",
        "qualification_artifact_sha256": QUALIFICATION,
        "qualification_method": "independent-qualified-write-boundary-manifest",
        "all_relevant_zero_write_paths_established": basis == "all-relevant-zero-write-paths",
        "equivalent_lossless_boundary_established": basis == "equivalent-lossless-boundary",
        "periodic_sampling_only": False,
    }


def evidence_digest(evidence):
    payload = json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def expected_coverage(evidence, basis="all-relevant-zero-write-paths"):
    return {
        "schema": "ascendancy.a1-manual-transition-expected-coverage/v1",
        "target_sha256": TARGET,
        "harness_sha256": HARNESS,
        "scenario_identity": "bounded-round-trip-v1",
        "coverage_evidence_sha256": evidence_digest(evidence),
        "coverage_basis": basis,
    }


class A1ManualTransitionOracleTests(unittest.TestCase):
    def test_accepts_lossless_round_trip_with_independent_coverage_binding(self):
        evidence = coverage_evidence()
        result = validate_record(positive_record(), expected_coverage(evidence), evidence)
        self.assertTrue(result["manual_transition_invalidation_established"])
        self.assertEqual(result["validated_round_trips"], 1)
        self.assertEqual(result["coverage_basis"], "all-relevant-zero-write-paths")
        self.assertEqual(result["coverage_evidence_sha256"], evidence_digest(evidence))

    def test_rejects_positive_without_independent_coverage_provenance(self):
        evidence = coverage_evidence()
        with self.assertRaisesRegex(A1ManualInvalidationError, "independently supplied expected coverage"):
            validate_record(positive_record(), coverage_evidence=evidence)

    def test_rejects_positive_without_coverage_evidence_manifest(self):
        evidence = coverage_evidence()
        with self.assertRaisesRegex(A1ManualInvalidationError, "coverage evidence manifest"):
            validate_record(positive_record(), expected_coverage(evidence))

    def test_rejects_arbitrary_expected_evidence_digest(self):
        evidence = coverage_evidence()
        expected = expected_coverage(evidence)
        expected["coverage_evidence_sha256"] = "2" * 64
        with self.assertRaisesRegex(A1ManualInvalidationError, "must match independently supplied expected digest"):
            validate_record(positive_record(), expected, evidence)

    def test_rejects_mutated_evidence_after_digest_was_pinned(self):
        evidence = coverage_evidence()
        expected = expected_coverage(evidence)
        evidence["qualification_method"] = "mutated-after-pin"
        with self.assertRaisesRegex(A1ManualInvalidationError, "must match independently supplied expected digest"):
            validate_record(positive_record(), expected, evidence)

    def test_rejects_self_asserted_coverage_when_expected_basis_differs(self):
        evidence = coverage_evidence()
        record = positive_record()
        record["coverage"]["all_relevant_zero_write_paths_established"] = False
        record["coverage"]["equivalent_lossless_boundary_established"] = True
        with self.assertRaisesRegex(A1ManualInvalidationError, "all-relevant-zero-write-path coverage"):
            validate_record(record, expected_coverage(evidence), evidence)

    def test_rejects_expected_coverage_bound_to_other_harness(self):
        evidence = coverage_evidence()
        expected = expected_coverage(evidence)
        expected["harness_sha256"] = "4" * 64
        with self.assertRaisesRegex(A1ManualInvalidationError, "must bind"):
            validate_record(positive_record(), expected, evidence)

    def test_accepts_equivalent_lossless_boundary_when_independently_expected(self):
        evidence = coverage_evidence("equivalent-lossless-boundary")
        record = positive_record()
        record["coverage"]["all_relevant_zero_write_paths_established"] = False
        record["coverage"]["equivalent_lossless_boundary_established"] = True
        result = validate_record(
            record,
            expected_coverage(evidence, "equivalent-lossless-boundary"),
            evidence,
        )
        self.assertEqual(result["coverage_basis"], "equivalent-lossless-boundary")

    def test_rejects_evidence_basis_that_differs_from_expected(self):
        evidence = coverage_evidence()
        expected = expected_coverage(evidence)
        evidence["coverage_basis"] = "equivalent-lossless-boundary"
        expected["coverage_evidence_sha256"] = evidence_digest(evidence)
        with self.assertRaisesRegex(A1ManualInvalidationError, "coverage_basis must match"):
            validate_record(positive_record(), expected, evidence)

    def test_rejects_unqualified_write_source_mechanism(self):
        evidence = coverage_evidence()
        record = positive_record()
        record["transitions"][0]["write_source"]["mechanism"] = "periodic-probe"
        with self.assertRaisesRegex(A1ManualInvalidationError, "must match qualified coverage evidence"):
            validate_record(record, expected_coverage(evidence), evidence)

    def test_rejects_periodic_sampling_as_positive_evidence(self):
        evidence = coverage_evidence()
        record = positive_record()
        record["coverage"]["periodic_sampling_only"] = True
        with self.assertRaisesRegex(A1ManualInvalidationError, "periodic sampling"):
            validate_record(record, expected_coverage(evidence), evidence)

    def test_rejects_invalidation_after_managed_reappears(self):
        evidence = coverage_evidence()
        record = positive_record()
        record["transitions"][0]["invalidation_seq"] = 31
        with self.assertRaisesRegex(A1ManualInvalidationError, "must order"):
            validate_record(record, expected_coverage(evidence), evidence)

    def test_negative_outcome_cannot_set_established_claim(self):
        record = positive_record()
        record["outcome"] = "negative-missed-transition"
        with self.assertRaisesRegex(A1ManualInvalidationError, "non-positive outcome"):
            validate_record(record)

    def test_incomplete_outcome_is_not_promoted(self):
        record = positive_record()
        record["outcome"] = "incomplete-harness"
        record["claims"]["manual_transition_invalidation_established"] = False
        record["transitions"] = []
        result = validate_record(record)
        self.assertFalse(result["manual_transition_invalidation_established"])


if __name__ == "__main__":
    unittest.main()
