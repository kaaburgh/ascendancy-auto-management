import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "a1_sidecar_lifetime_oracle", ROOT / "scripts" / "a1_sidecar_lifetime_oracle.py"
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


def base_record():
    return {
        "schema": mod.SCHEMA,
        "outcome": "incomplete-harness",
        "claims": {
            "array_base_established": False,
            "array_count_established": False,
            "stable_index_established": False,
            "reuse_detector_established": False,
            "epoch_boundary_established": False,
            "manual_transition_invalidation_established": False,
        },
        "control": {"passed": False},
        "transitions": [],
    }


class A1SidecarLifetimeOracleTests(unittest.TestCase):
    def test_incomplete_record_is_valid_without_positive_claims(self):
        result = mod.validate_record(base_record())
        self.assertFalse(result["positive_contract_accepted"])
        self.assertFalse(result["coverage_complete"])

    def test_positive_epoch_pointer_requires_full_coverage(self):
        record = base_record()
        record["outcome"] = "positive-epoch-pointer"
        record["control"]["passed"] = True
        record["claims"]["reuse_detector_established"] = True
        record["claims"]["epoch_boundary_established"] = True
        with self.assertRaisesRegex(mod.A1LifetimeError, "all predeclared transitions"):
            mod.validate_record(record)

    def test_rejects_pointer_reuse_with_post_hoc_signal(self):
        record = base_record()
        record["transitions"] = [
            {"label": "selection-control"},
            {"label": "new-game-reset", "replacement": True, "signal_order": "post-hoc"},
            {"label": "save-load-replacement"},
        ]
        with self.assertRaisesRegex(mod.A1LifetimeError, "post-hoc"):
            mod.validate_record(record)

    def test_rejects_stride_only_index(self):
        record = base_record()
        record["transitions"] = [{"label": "selection-control", "index_basis": "stride-only"}]
        with self.assertRaisesRegex(mod.A1LifetimeError, "stride"):
            mod.validate_record(record)

    def test_stable_index_requires_base_and_count(self):
        record = base_record()
        record["claims"]["stable_index_established"] = True
        with self.assertRaisesRegex(mod.A1LifetimeError, "array base and count"):
            mod.validate_record(record)

    def test_rejects_presentation_name_as_identity(self):
        record = base_record()
        record["transitions"] = [{"label": "selection-control", "identity_basis": "presentation-name"}]
        with self.assertRaisesRegex(mod.A1LifetimeError, "presentation name"):
            mod.validate_record(record)

    def test_accepts_positive_epoch_index_when_evidence_contract_is_complete(self):
        record = base_record()
        record["outcome"] = "positive-epoch-index"
        record["control"]["passed"] = True
        record["claims"].update({
            "array_base_established": True,
            "array_count_established": True,
            "stable_index_established": True,
            "epoch_boundary_established": True,
        })
        record["transitions"] = [
            {"label": "selection-control", "index_basis": "runtime-base-count"},
            {"label": "new-game-reset", "replacement": True, "signal_order": "before-reuse"},
            {"label": "save-load-replacement", "replacement": True, "signal_order": "before-reuse"},
        ]
        result = mod.validate_record(record)
        self.assertTrue(result["positive_contract_accepted"])
        self.assertTrue(result["coverage_complete"])


if __name__ == "__main__":
    unittest.main()
