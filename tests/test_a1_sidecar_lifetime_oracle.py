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


def replacement_step(
    label: str,
    invalidation_basis: str,
    *,
    include_observations: bool = True,
    outcome: str = "positive-epoch-index",
):
    step = {
        "label": label,
        "replacement": True,
        "invalidation_basis": invalidation_basis,
    }
    if include_observations:
        pre = {
            "seq": 10,
            "record_pointer": 0x10100,
            "array_base": 0x10000,
            "array_count": 8,
            "index": 1,
        }
        post = {
            "seq": 30,
            "record_pointer": 0x10100,
            "array_base": 0x10000,
            "array_count": 8,
            "index": 1,
        }
        if outcome == "positive-epoch-pointer":
            reuse_event = {
                "kind": "record-pointer-reuse",
                "seq": 25,
                "record_pointer": 0x10100,
                "before_logical_record": "scenario-planet-a",
                "after_logical_record": "scenario-planet-b",
            }
        elif outcome == "positive-other":
            reuse_event = {
                "kind": "other-identity-reuse",
                "seq": 25,
                "identity_subject": "candidate-key-slot-1",
                "before_logical_record": "scenario-planet-a",
                "after_logical_record": "scenario-planet-b",
            }
        else:
            reuse_event = {
                "kind": "index-reassignment",
                "seq": 25,
                "array_base": 0x10000,
                "index": 1,
                "before_logical_record": "scenario-planet-a",
                "after_logical_record": "scenario-planet-b",
            }
        step["observations"] = {
            "pre": pre,
            "post": post,
            "reuse_event": reuse_event,
            "epoch_signal": {"before": 7, "after": 8, "seq": 20},
            "reuse_detector_signal": {"before": "old", "after": "new", "seq": 20},
            "other_invalidation_signal": {"before": "old", "after": "new", "seq": 20},
        }
    return step


def complete_transitions(
    invalidation_basis: str,
    *,
    include_observations: bool = True,
    outcome: str = "positive-epoch-index",
):
    return [
        {"label": "selection-control"},
        replacement_step(
            "new-game-reset", invalidation_basis,
            include_observations=include_observations, outcome=outcome,
        ),
        replacement_step(
            "save-load-replacement", invalidation_basis,
            include_observations=include_observations, outcome=outcome,
        ),
    ]


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

    def test_positive_rejects_claims_only_transition_labels(self):
        record = base_record()
        record["outcome"] = "positive-epoch-pointer"
        record["control"]["passed"] = True
        record["claims"]["reuse_detector_established"] = True
        record["claims"]["epoch_boundary_established"] = True
        record["transitions"] = [
            {"label": "selection-control"},
            {"label": "new-game-reset"},
            {"label": "save-load-replacement"},
        ]
        with self.assertRaisesRegex(mod.A1LifetimeError, "observed replacement"):
            mod.validate_record(record)

    def test_positive_rejects_declarative_transition_without_observations(self):
        record = base_record()
        record["outcome"] = "positive-epoch-pointer"
        record["control"]["passed"] = True
        record["claims"]["reuse_detector_established"] = True
        record["claims"]["epoch_boundary_established"] = True
        record["transitions"] = complete_transitions(
            "epoch", include_observations=False, outcome="positive-epoch-pointer"
        )
        with self.assertRaisesRegex(mod.A1LifetimeError, "bounded observations"):
            mod.validate_record(record)

    def _positive_index_record(self):
        record = base_record()
        record["outcome"] = "positive-epoch-index"
        record["control"]["passed"] = True
        record["claims"].update({
            "array_base_established": True,
            "array_count_established": True,
            "stable_index_established": True,
            "epoch_boundary_established": True,
        })
        record["transitions"] = complete_transitions("epoch")
        return record

    def test_positive_rejects_unchanged_epoch_signal(self):
        record = self._positive_index_record()
        record["transitions"][1]["observations"]["epoch_signal"]["after"] = 7
        with self.assertRaisesRegex(mod.A1LifetimeError, "did not change"):
            mod.validate_record(record)

    def test_positive_rejects_missing_reuse_event(self):
        record = self._positive_index_record()
        del record["transitions"][1]["observations"]["reuse_event"]
        with self.assertRaisesRegex(mod.A1LifetimeError, "reuse_event"):
            mod.validate_record(record)

    def test_positive_rejects_signal_at_reuse_event(self):
        record = self._positive_index_record()
        record["transitions"][1]["observations"]["epoch_signal"]["seq"] = 25
        with self.assertRaisesRegex(mod.A1LifetimeError, "before observed reuse event"):
            mod.validate_record(record)

    def test_positive_rejects_signal_only_at_post_point(self):
        record = self._positive_index_record()
        record["transitions"][1]["observations"]["epoch_signal"]["seq"] = 30
        with self.assertRaisesRegex(mod.A1LifetimeError, "before observed reuse event"):
            mod.validate_record(record)

    def test_positive_rejects_unbound_index_reuse_event(self):
        record = self._positive_index_record()
        record["transitions"][1]["observations"]["reuse_event"]["index"] = 2
        with self.assertRaisesRegex(mod.A1LifetimeError, "bind to pre/post index"):
            mod.validate_record(record)

    def test_positive_rejects_reuse_event_without_logical_replacement(self):
        record = self._positive_index_record()
        event = record["transitions"][1]["observations"]["reuse_event"]
        event["after_logical_record"] = event["before_logical_record"]
        with self.assertRaisesRegex(mod.A1LifetimeError, "distinguish two logical records"):
            mod.validate_record(record)

    def test_positive_pointer_reuse_event_must_bind_to_pointer(self):
        record = base_record()
        record["outcome"] = "positive-epoch-pointer"
        record["control"]["passed"] = True
        record["claims"]["reuse_detector_established"] = True
        record["claims"]["epoch_boundary_established"] = True
        record["transitions"] = complete_transitions(
            "epoch+reuse-detector", outcome="positive-epoch-pointer"
        )
        record["transitions"][1]["observations"]["reuse_event"]["record_pointer"] = 0x20200
        with self.assertRaisesRegex(mod.A1LifetimeError, "bind to both pre/post record_pointer"):
            mod.validate_record(record)

    def test_positive_rejects_incompatible_invalidation_basis(self):
        record = self._positive_index_record()
        record["transitions"] = complete_transitions("reuse-detector")
        with self.assertRaisesRegex(mod.A1LifetimeError, "incompatible invalidation basis"):
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
        result = mod.validate_record(self._positive_index_record())
        self.assertTrue(result["positive_contract_accepted"])
        self.assertTrue(result["coverage_complete"])


if __name__ == "__main__":
    unittest.main()
