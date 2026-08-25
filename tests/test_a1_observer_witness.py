import hashlib
import unittest

from scripts.a1_observer_witness import (
    A1ObserverWitnessError,
    PLANET_RECORD_SIZE,
    PRESENTATION_NAME_OFFSET,
    qualify_selected_record,
    witness_contract,
)


class ObserverWitnessTests(unittest.TestCase):
    def manifest(self, label="Planet A", offset=0x10, payload=b"identity"):
        digest = hashlib.sha256(payload).hexdigest()
        return {
            "schema": "ascendancy.a1-sidecar-scenario-qualification/v2",
            "source": {},
            "planets": {label: digest},
            "witness_ranges": {
                label: {
                    "metadata_basis": "bounded-record-metadata",
                    "record_offset": offset,
                    "length": len(payload),
                    "sha256": digest,
                    "rationale": "synthetic non-name record metadata",
                }
            },
        }

    def record(self, offset=0x10, payload=b"identity"):
        value = bytearray(PLANET_RECORD_SIZE)
        value[offset:offset + len(payload)] = payload
        return bytes(value)

    def test_accepts_exact_predeclared_range_and_emits_no_bytes(self):
        result = qualify_selected_record(self.manifest(), "Planet A", self.record())
        self.assertTrue(result["matched"])
        self.assertEqual(result["record_offset"], 0x10)
        self.assertEqual(result["length"], len(b"identity"))
        self.assertNotIn("bytes", result)
        self.assertNotIn("record", result)

    def test_rejects_record_that_does_not_match_qualified_digest(self):
        with self.assertRaisesRegex(A1ObserverWitnessError, "does not match"):
            qualify_selected_record(self.manifest(), "Planet A", bytes(PLANET_RECORD_SIZE))

    def test_rejects_legacy_v1_manifest_for_exact_target_observer(self):
        manifest = self.manifest()
        manifest["schema"] = "ascendancy.a1-sidecar-scenario-qualification/v1"
        with self.assertRaisesRegex(A1ObserverWitnessError, "requires scenario qualification v2"):
            witness_contract(manifest, "Planet A")

    def test_rejects_range_outside_established_record(self):
        manifest = self.manifest(offset=PLANET_RECORD_SIZE - 2, payload=b"four")
        with self.assertRaisesRegex(A1ObserverWitnessError, "exceeds established"):
            witness_contract(manifest, "Planet A")

    def test_rejects_presentation_name_only_range_even_when_labeled_bounded_metadata(self):
        manifest = self.manifest(offset=PRESENTATION_NAME_OFFSET, payload=b"Planet A\0")
        with self.assertRaisesRegex(A1ObserverWitnessError, "overlaps established presentation-name window"):
            witness_contract(manifest, "Planet A")

    def test_rejects_range_partially_overlapping_presentation_name_window(self):
        manifest = self.manifest(offset=PRESENTATION_NAME_OFFSET - 2, payload=b"abcd")
        with self.assertRaisesRegex(A1ObserverWitnessError, "overlaps established presentation-name window"):
            witness_contract(manifest, "Planet A")

    def test_accepts_range_immediately_before_presentation_name_window(self):
        payload = b"xy"
        offset = PRESENTATION_NAME_OFFSET - len(payload)
        result = witness_contract(self.manifest(offset=offset, payload=payload), "Planet A")
        self.assertEqual(result["record_offset"], offset)
        self.assertEqual(result["length"], len(payload))

    def test_rejects_digest_disagreement_between_manifest_views(self):
        manifest = self.manifest()
        manifest["witness_ranges"]["Planet A"]["sha256"] = "00" * 32
        with self.assertRaisesRegex(A1ObserverWitnessError, "must match"):
            witness_contract(manifest, "Planet A")

    def test_labels_use_exact_decoded_string_identity(self):
        manifest = self.manifest(label=" Planet A")
        with self.assertRaisesRegex(A1ObserverWitnessError, "not independently qualified"):
            witness_contract(manifest, "Planet A")
        self.assertEqual(witness_contract(manifest, " Planet A")["logical_record"], " Planet A")

    def test_rejects_non_exact_record_snapshot_size(self):
        with self.assertRaisesRegex(A1ObserverWitnessError, "exactly 0x7b bytes"):
            qualify_selected_record(self.manifest(), "Planet A", bytes(PLANET_RECORD_SIZE - 1))


if __name__ == "__main__":
    unittest.main()
