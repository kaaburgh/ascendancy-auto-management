import hashlib
import unittest

from scripts.a1_lifetime_action_script import ACTION_SCRIPT_SCHEMA
from scripts.a1_lifetime_observer_core import TRANSCRIPT_SCHEMA, execute_observer_plan
from scripts.a1_observer_witness import SCENARIO_SCHEMA


def _record(fill: int, witness: bytes) -> bytes:
    data = bytearray([fill] * 0x7B)
    data[8:8 + len(witness)] = witness
    return bytes(data)


def _manifest(records):
    planets = {}
    ranges = {}
    for label, record in records.items():
        witness = record[8:16]
        digest = hashlib.sha256(witness).hexdigest()
        planets[label] = digest
        ranges[label] = {
            "metadata_basis": "bounded-record-metadata",
            "record_offset": 8,
            "length": 8,
            "sha256": digest,
            "rationale": "synthetic stable witness",
        }
    return {"schema": SCENARIO_SCHEMA, "planets": planets, "witness_ranges": ranges}


def _actions():
    return {
        "schema": ACTION_SCRIPT_SCHEMA,
        "bounds": {
            "max_action_count": 9,
            "max_qualification_attempts_per_step": 2,
            "per_step_timeout_seconds": 10,
            "total_timeout_seconds": 120,
        },
        "steps": [
            {"id": "control-a1", "action": "qualify", "phase": "selection-control", "logical_label": "A"},
            {"id": "control-b", "action": "qualify", "phase": "selection-control", "logical_label": "B"},
            {"id": "control-a2", "action": "qualify", "phase": "selection-control", "logical_label": "A"},
            {"id": "ng-pre", "action": "qualify", "phase": "pre-replacement", "logical_label": "A"},
            {"id": "ng", "action": "replace", "mechanism": "new-game-reset"},
            {"id": "ng-post", "action": "qualify", "phase": "post-replacement", "logical_label": "C"},
            {"id": "sl-pre", "action": "qualify", "phase": "pre-replacement", "logical_label": "C"},
            {"id": "sl", "action": "replace", "mechanism": "save-load-replacement"},
            {"id": "sl-post", "action": "qualify", "phase": "post-replacement", "logical_label": "D"},
        ],
    }


class Backend:
    def __init__(self, records, pointers=None, signals=None):
        self.records = records
        self.pointers = pointers or {"A": 100, "B": 200, "C": 300, "D": 400}
        self.signals = signals or {
            "new-game-reset": {"name": "epoch", "before": 1, "after": 2, "changed_before_post_qualification": True},
            "save-load-replacement": {"name": "epoch", "before": 2, "after": 3, "changed_before_post_qualification": True},
        }

    def qualify(self, *, step_id, logical_label, timeout_seconds):
        return {
            "record_pointer": self.pointers[logical_label],
            "record": self.records[logical_label],
            "population_replacement": False,
        }

    def replace(self, *, step_id, mechanism, timeout_seconds):
        return {"completed": True, "lifecycle_signal": self.signals.get(mechanism)}


class A1LifetimeObserverCoreTests(unittest.TestCase):
    def setUp(self):
        self.records = {
            "A": _record(1, b"AAAAAAAA"),
            "B": _record(2, b"BBBBBBBB"),
            "C": _record(3, b"CCCCCCCC"),
            "D": _record(4, b"DDDDDDDD"),
        }
        self.manifest = _manifest(self.records)

    def test_executes_bounded_plan_without_serializing_record_bytes(self):
        result = execute_observer_plan(self.manifest, _actions(), Backend(self.records))
        self.assertEqual(result["schema"], TRANSCRIPT_SCHEMA)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(result["replacement_legs"]), 2)
        self.assertNotIn("record", repr(result))
        self.assertEqual(result["steps"][0]["record_pointer"], 100)

    def test_witness_mismatch_is_incomplete(self):
        backend = Backend(dict(self.records))
        backend.records["B"] = _record(9, b"XXXXXXXX")
        result = execute_observer_plan(self.manifest, _actions(), backend)
        self.assertEqual(result["status"], "incomplete-harness")
        self.assertIn("failed after 2 attempt", result["error"])

    def test_short_record_is_incomplete(self):
        backend = Backend(dict(self.records))
        backend.records["B"] = b"short"
        result = execute_observer_plan(self.manifest, _actions(), backend)
        self.assertEqual(result["status"], "incomplete-harness")
        self.assertIn("selected record must be exactly", result["error"])

    def test_selection_control_requires_distinct_a_b_pointers(self):
        backend = Backend(self.records, pointers={"A": 100, "B": 100, "C": 300, "D": 400})
        result = execute_observer_plan(self.manifest, _actions(), backend)
        self.assertEqual(result["status"], "incomplete-harness")
        self.assertIn("distinct record pointers", result["error"])

    def test_pointer_reuse_requires_preceding_signal(self):
        pointers = {"A": 100, "B": 200, "C": 100, "D": 400}
        signals = {
            "new-game-reset": None,
            "save-load-replacement": {"name": "epoch", "before": 2, "after": 3, "changed_before_post_qualification": True},
        }
        result = execute_observer_plan(self.manifest, _actions(), Backend(self.records, pointers, signals))
        self.assertEqual(result["status"], "incomplete-harness")
        self.assertIn("without a lifecycle signal", result["error"])

    def test_late_signal_cannot_guard_pointer_reuse(self):
        pointers = {"A": 100, "B": 200, "C": 100, "D": 400}
        signals = {
            "new-game-reset": {"name": "epoch", "before": 1, "after": 2, "changed_before_post_qualification": False},
            "save-load-replacement": {"name": "epoch", "before": 2, "after": 3, "changed_before_post_qualification": True},
        }
        result = execute_observer_plan(self.manifest, _actions(), Backend(self.records, pointers, signals))
        self.assertEqual(result["status"], "incomplete-harness")
        self.assertIn("too late", result["error"])


if __name__ == "__main__":
    unittest.main()
