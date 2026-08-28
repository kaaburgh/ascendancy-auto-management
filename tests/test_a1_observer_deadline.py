import hashlib
import unittest

from scripts.a1_lifetime_action_script import ACTION_SCRIPT_SCHEMA
from scripts.a1_lifetime_observer_core import execute_observer_plan
from scripts.a1_observer_witness import SCENARIO_SCHEMA


def _record() -> bytes:
    data = bytearray([1] * 0x7B)
    data[8:16] = b"AAAAAAAA"
    return bytes(data)


def _manifest(record: bytes) -> dict:
    digest = hashlib.sha256(record[8:16]).hexdigest()
    return {
        "schema": SCENARIO_SCHEMA,
        "planets": {"A": digest},
        "witness_ranges": {
            "A": {
                "metadata_basis": "bounded-record-metadata",
                "record_offset": 8,
                "length": 8,
                "sha256": digest,
                "rationale": "synthetic stable witness",
            }
        },
    }


def _actions() -> dict:
    return {
        "schema": ACTION_SCRIPT_SCHEMA,
        "bounds": {
            "max_action_count": 9,
            "max_qualification_attempts_per_step": 2,
            "per_step_timeout_seconds": 10,
            "total_timeout_seconds": 120,
        },
        "steps": [
            {
                "id": "control-a1",
                "action": "qualify",
                "phase": "selection-control",
                "logical_label": "A",
            },
            {
                "id": "control-b",
                "action": "qualify",
                "phase": "selection-control",
                "logical_label": "B",
            },
            {
                "id": "control-a2",
                "action": "qualify",
                "phase": "selection-control",
                "logical_label": "A",
            },
            {
                "id": "reset-pre",
                "action": "qualify",
                "phase": "pre-replacement",
                "logical_label": "A",
            },
            {
                "id": "reset",
                "action": "replace",
                "mechanism": "new-game-reset",
            },
            {
                "id": "reset-post",
                "action": "qualify",
                "phase": "post-replacement",
                "logical_label": "A",
            },
            {
                "id": "load-pre",
                "action": "qualify",
                "phase": "pre-replacement",
                "logical_label": "A",
            },
            {
                "id": "load",
                "action": "replace",
                "mechanism": "save-load-replacement",
            },
            {
                "id": "load-post",
                "action": "qualify",
                "phase": "post-replacement",
                "logical_label": "A",
            },
        ],
    }


class NeverCalledBackend:
    def qualify(self, *, step_id, logical_label, timeout_seconds):
        raise AssertionError("qualification backend must not run after total deadline expiry")

    def replace(self, *, step_id, mechanism, timeout_seconds):
        raise AssertionError("replacement backend is not used by this plan")


class Clock:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls <= 2:
            return 0.0
        return 121.0


class A1ObserverDeadlineTests(unittest.TestCase):
    def test_total_deadline_expiry_is_not_retried_as_qualification_failure(self):
        record = _record()
        result = execute_observer_plan(
            _manifest(record), _actions(), NeverCalledBackend(), clock=Clock()
        )
        self.assertEqual(result["status"], "incomplete-harness")
        self.assertEqual(result["error"], "observer exceeded total runtime bound")
        self.assertNotIn("failed after 2 attempt", result["error"])


if __name__ == "__main__":
    unittest.main()
