import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "_a1_sidecar_lifetime_oracle_cases.py"
SPEC = importlib.util.spec_from_file_location("a1_sidecar_lifetime_oracle_cases", CASES)
_cases = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(_cases)


def selection_control_step():
    return {
        "label": "selection-control",
        "replacement": False,
        "observations": {
            "first": {
                "seq": 1,
                "record_pointer": 0x10100,
                "logical_record": "scenario-planet-a",
                "qualified_witness": _cases.witness("scenario-planet-a"),
            },
            "second": {
                "seq": 2,
                "record_pointer": 0x10200,
                "logical_record": "scenario-planet-b",
                "qualified_witness": _cases.witness("scenario-planet-b"),
            },
            "return": {
                "seq": 3,
                "record_pointer": 0x10100,
                "logical_record": "scenario-planet-a",
                "qualified_witness": _cases.witness("scenario-planet-a"),
            },
        },
    }


def complete_transitions(
    invalidation_basis: str,
    *,
    include_observations: bool = True,
    outcome: str = "positive-epoch-index",
):
    return [
        selection_control_step(),
        _cases.replacement_step(
            "new-game-reset",
            invalidation_basis,
            include_observations=include_observations,
            outcome=outcome,
        ),
        _cases.replacement_step(
            "save-load-replacement",
            invalidation_basis,
            include_observations=include_observations,
            outcome=outcome,
        ),
    ]


_cases.complete_transitions = complete_transitions
A1SidecarLifetimeOracleTests = _cases.A1SidecarLifetimeOracleTests


def v2_manifest() -> dict:
    manifest = _cases.scenario_manifest()
    manifest["schema"] = "ascendancy.a1-sidecar-scenario-qualification/v2"
    manifest["witness_ranges"] = {
        "scenario-planet-a": {
            "metadata_basis": "bounded-record-metadata",
            "record_offset": 0x10,
            "length": len(bytes.fromhex(_cases.metadata_hex("scenario-planet-a"))),
            "sha256": _cases.metadata_digest("scenario-planet-a"),
            "rationale": "synthetic v2 witness",
        },
        "scenario-planet-b": {
            "metadata_basis": "bounded-record-metadata",
            "record_offset": 0x60,
            "length": len(bytes.fromhex(_cases.metadata_hex("scenario-planet-b"))),
            "sha256": _cases.metadata_digest("scenario-planet-b"),
            "rationale": "synthetic v2 witness",
        },
    }
    return manifest


def convert_record_to_v2_digest_witnesses(record: dict) -> None:
    offsets = {"scenario-planet-a": 0x10, "scenario-planet-b": 0x60}

    def visit(value):
        if isinstance(value, dict):
            witness = value.get("qualified_witness")
            if isinstance(witness, dict):
                planet = witness["scenario_planet"]
                raw = bytes.fromhex(witness.pop("metadata_hex"))
                witness["record_offset"] = offsets[planet]
                witness["length"] = len(raw)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(record)


class A1StandaloneSelectionControlIntegrationTests(unittest.TestCase):
    def test_positive_standalone_path_rejects_unobserved_selection_control(self):
        record = _cases.A1SidecarLifetimeOracleTests()._positive_index_record()
        record["transitions"][0] = {"label": "selection-control", "replacement": False}
        with self.assertRaisesRegex(_cases.mod.A1LifetimeError, "bounded observations for selection-control"):
            _cases.mod.validate_record(record, _cases.scenario_manifest())


class A1V2DigestOnlyWitnessIntegrationTests(unittest.TestCase):
    def positive_v2_record(self):
        record = _cases.A1SidecarLifetimeOracleTests()._positive_index_record()
        convert_record_to_v2_digest_witnesses(record)
        return record

    def test_accepts_digest_only_witnesses_bound_to_v2_ranges(self):
        result = _cases.mod.validate_record(self.positive_v2_record(), v2_manifest())
        self.assertTrue(result["positive_contract_accepted"])

    def test_rejects_mixed_v2_witness_with_metadata_hex(self):
        record = self.positive_v2_record()
        witness = record["transitions"][0]["observations"]["first"]["qualified_witness"]
        witness["metadata_hex"] = _cases.metadata_hex("scenario-planet-a")
        with self.assertRaisesRegex(_cases.mod.A1LifetimeError, "must not contain metadata_hex"):
            _cases.mod.validate_record(record, v2_manifest())

    def test_rejects_v2_record_offset_mismatch(self):
        record = self.positive_v2_record()
        witness = record["transitions"][1]["observations"]["pre"]["qualified_witness"]
        witness["record_offset"] += 1
        with self.assertRaisesRegex(_cases.mod.A1LifetimeError, "record_offset must match"):
            _cases.mod.validate_record(record, v2_manifest())

    def test_rejects_v2_digest_mismatch(self):
        record = self.positive_v2_record()
        witness = record["transitions"][1]["observations"]["pre"]["qualified_witness"]
        witness["metadata_sha256"] = "0" * 64
        with self.assertRaisesRegex(_cases.mod.A1LifetimeError, "metadata_sha256 must match"):
            _cases.mod.validate_record(record, v2_manifest())

    def test_rejects_v2_manifest_range_digest_disagreeing_with_planets(self):
        manifest = v2_manifest()
        manifest["witness_ranges"]["scenario-planet-a"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(_cases.mod.A1LifetimeError, "must match planets"):
            _cases.mod.validate_record(self.positive_v2_record(), manifest)


if __name__ == "__main__":
    unittest.main()
