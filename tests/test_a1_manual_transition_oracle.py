import unittest

from scripts.a1_manual_transition_oracle import A1ManualInvalidationError, validate_record


TARGET = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
HARNESS = "1" * 64


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


class A1ManualTransitionOracleTests(unittest.TestCase):
    def test_accepts_lossless_round_trip(self):
        result = validate_record(positive_record())
        self.assertTrue(result["manual_transition_invalidation_established"])
        self.assertEqual(result["validated_round_trips"], 1)

    def test_rejects_periodic_sampling_as_positive_evidence(self):
        record = positive_record()
        record["coverage"]["periodic_sampling_only"] = True
        with self.assertRaisesRegex(A1ManualInvalidationError, "periodic sampling"):
            validate_record(record)

    def test_rejects_invalidation_after_managed_reappears(self):
        record = positive_record()
        record["transitions"][0]["invalidation_seq"] = 31
        with self.assertRaisesRegex(A1ManualInvalidationError, "must order"):
            validate_record(record)

    def test_rejects_positive_without_complete_or_equivalent_coverage(self):
        record = positive_record()
        record["coverage"]["all_relevant_zero_write_paths_established"] = False
        with self.assertRaisesRegex(A1ManualInvalidationError, "all relevant zero-write paths"):
            validate_record(record)

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
