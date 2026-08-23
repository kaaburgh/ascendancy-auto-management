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


class A1StandaloneSelectionControlIntegrationTests(unittest.TestCase):
    def test_positive_standalone_path_rejects_unobserved_selection_control(self):
        record = _cases.A1SidecarLifetimeOracleTests()._positive_index_record()
        record["transitions"][0] = {"label": "selection-control", "replacement": False}
        with self.assertRaisesRegex(_cases.mod.A1LifetimeError, "bounded observations for selection-control"):
            _cases.mod.validate_record(record, _cases.scenario_manifest())


if __name__ == "__main__":
    unittest.main()
