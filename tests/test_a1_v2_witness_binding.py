import hashlib
import unittest
from unittest.mock import patch

from scripts import a1_observer_witness as observer
from scripts import a1_selection_control_oracle as selection
from scripts import a1_sidecar_evidence_bundle as bundle
from scripts import a1_sidecar_lifetime_oracle as lifetime
from scripts.a1_v2_witness_binding import A1V2WitnessBindingError, witness_contract


def contract_parts():
    digest = hashlib.sha256(b"witness-a").hexdigest()
    planets = {"planet-a": digest}
    ranges = {
        "planet-a": {
            "metadata_basis": "bounded-record-metadata",
            "record_offset": 0x10,
            "length": 9,
            "sha256": digest,
            "rationale": "synthetic non-name witness",
        }
    }
    witness = {
        "scenario_planet": "planet-a",
        "metadata_basis": "bounded-record-metadata",
        "record_offset": 0x10,
        "length": 9,
        "metadata_sha256": digest,
    }
    return planets, ranges, witness


class A1V2WitnessBindingTests(unittest.TestCase):
    def test_shared_contract_requires_rationale(self):
        planets, ranges, _ = contract_parts()
        del ranges["planet-a"]["rationale"]
        with self.assertRaisesRegex(A1V2WitnessBindingError, "rationale"):
            witness_contract(planets, ranges, "planet-a")

    def test_shared_contract_rejects_presentation_name_geometry(self):
        planets, ranges, _ = contract_parts()
        ranges["planet-a"]["record_offset"] = 0x24
        with self.assertRaisesRegex(A1V2WitnessBindingError, "presentation-name window"):
            witness_contract(planets, ranges, "planet-a")

    def test_observer_path_delegates_to_shared_contract(self):
        planets, ranges, _ = contract_parts()
        manifest = {
            "schema": "ascendancy.a1-sidecar-scenario-qualification/v2",
            "planets": planets,
            "witness_ranges": ranges,
        }
        with patch.object(observer, "_shared_witness_contract", wraps=observer._shared_witness_contract) as shared:
            observer.witness_contract(manifest, "planet-a")
        shared.assert_called_once()

    def test_selection_path_delegates_to_shared_binding(self):
        planets, ranges, witness = contract_parts()
        observations = {
            "first": {
                "seq": 1,
                "record_pointer": 0x100,
                "logical_record": "planet-a",
                "qualified_witness": witness,
            }
        }
        with patch.object(selection, "validate_qualified_witness", wraps=selection.validate_qualified_witness) as shared:
            selection._point(observations, "first", planets, ranges)
        shared.assert_called_once()

    def test_lifetime_path_delegates_to_shared_binding(self):
        planets, ranges, witness = contract_parts()
        scenario_planets = lifetime._ScenarioPlanets(planets, ranges)
        observations = {
            "pre": {
                "seq": 1,
                "record_pointer": 0x100,
                "logical_record": "planet-a",
                "qualified_witness": witness,
            }
        }
        with patch.object(lifetime, "validate_qualified_witness", wraps=lifetime.validate_qualified_witness) as shared:
            lifetime._require_point(observations, "pre", "new-game-reset", scenario_planets)
        shared.assert_called_once()

    def test_bundle_path_delegates_to_shared_binding(self):
        planets, ranges, witness = contract_parts()
        manifest = {
            "schema": "ascendancy.a1-sidecar-scenario-qualification/v2",
            "planets": planets,
            "witness_ranges": ranges,
        }
        record = {
            "outcome": "positive-epoch-pointer",
            "transitions": [{"qualified_witness": witness}],
        }
        with patch.object(bundle, "validate_qualified_witness", wraps=bundle.validate_qualified_witness) as shared:
            bundle._validate_v2_witness_range_binding(record, manifest)
        shared.assert_called_once()


if __name__ == "__main__":
    unittest.main()
