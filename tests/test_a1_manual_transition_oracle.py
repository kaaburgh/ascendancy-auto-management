import unittest

from scripts.a1_manual_transition_oracle import A1ManualInvalidationError, validate_record


TARGET = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
HARNESS = "1" * 64
EVIDENCE = "2" * 64


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


def expected_coverage(basis="all-relevant-zero-write-paths"):
    return {
        "schema": "ascendancy.a1-manual-transition-expected-coverage/v1",
        "target_sha256": TARGET,
        "harness_sha256": HARNESS,
        "scenario_identity": "bounded-round-trip-v1",
        "coverage_evidence_sha256": EVIDENCE,
        "coverage_basis": basis,
    }


class A1ManualTransitionOracleTests(unittest.TestCase):
    def test_accepts_lossless_round_trip_with_independent_coverage_binding(self):
        result = validate_record(positive_record(), expected_coverage())
        self.assertTrue(result["manual_transition_invalidation_established"])
        self.assertEqual(result["validated_round_trips"], 1)
        self.assertEqual(result["coverage_basis"], "all-relevant-zero-write-paths")

    def test_rejects_positive_without_independent_coverage_provenance(self):
        with self.assertRaisesRegex(A1ManualInvalidationError, "independently supplied expected coverage"):
            validate_record(positive_record())

    def test_rejects_self_asserted_coverage_when_expected_basis_differs(self):
        record = positive_record()
        record["coverage"]["all_relevant_zero_write_paths_established"] = False
        record["coverage"]["equivalent_lossless_boundary_established"] = True
        with self.assertRaisesRegex(A1ManualInvalidationError, "all-relevant-zero-write-path coverage"):
            validate_record(record, expected_coverage())

    def test_rejects_expected_coverage_bound_to_other_harness(self):
        expected = expected_coverage()
        expected["harness_sha256"] = "3" * 64
        with self.assertRaisesRegex(A1ManualInvalidationError, "must bind"):
            validate_record(positive_record(), expected)

    def test_accepts_equivalent_lossless_boundary_when_independently_expected(self):
        record = positive_record()
        record["coverage"]["all_relevant_zero_write_paths_established"] = False
        record["coverage"]["equivalent_lossless_boundary_established"] = True
        result = validate_record(record, expected_coverage("equivalent-lossless-boundary"))
        self.assertEqual(result["coverage_basis"], "equivalent-lossless-boundary")

    def test_rejects_periodic_sampling_as_positive_evidence(self):
        record = positive_record()
        record["coverage"]["periodic_sampling_only"] = True
        with self.assertRaisesRegex(A1ManualInvalidationError, "periodic sampling"):
            validate_record(record, expected_coverage())

    def test_rejects_invalidation_after_managed_reappears(self):
        record = positive_record()
        record["transitions"][0]["invalidation_seq"] = 31
        with self.assertRaisesRegex(A1ManualInvalidationError, "must order"):
            validate_record(record, expected_coverage())

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
