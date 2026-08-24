import unittest

from scripts.a1_lifetime_action_script import (
    ACTION_SCRIPT_SCHEMA,
    A1LifetimeActionScriptError,
    validate_action_script,
)


def _valid_script():
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
            {"id": "new-game-pre", "action": "qualify", "phase": "pre-replacement", "logical_label": "A"},
            {"id": "new-game", "action": "replace", "mechanism": "new-game-reset"},
            {"id": "new-game-post", "action": "qualify", "phase": "post-replacement", "logical_label": "C"},
            {"id": "save-load-pre", "action": "qualify", "phase": "pre-replacement", "logical_label": "C"},
            {"id": "save-load", "action": "replace", "mechanism": "save-load-replacement"},
            {"id": "save-load-post", "action": "qualify", "phase": "post-replacement", "logical_label": "D"},
        ],
    }


class A1LifetimeActionScriptTests(unittest.TestCase):
    def test_accepts_required_control_and_both_replacement_legs(self):
        result = validate_action_script(_valid_script())
        self.assertEqual(result["step_count"], 9)
        self.assertEqual(result["selection_control_labels"], ["A", "B", "A"])
        self.assertEqual(
            result["replacement_mechanisms"],
            ["new-game-reset", "save-load-replacement"],
        )

    def test_rejects_non_aba_selection_control(self):
        document = _valid_script()
        document["steps"][2]["logical_label"] = "C"
        with self.assertRaisesRegex(A1LifetimeActionScriptError, "A→B→A"):
            validate_action_script(document)

    def test_rejects_missing_replacement_leg(self):
        document = _valid_script()
        document["steps"] = document["steps"][:-3]
        document["bounds"]["max_action_count"] = 6
        with self.assertRaisesRegex(A1LifetimeActionScriptError, "both replacement legs"):
            validate_action_script(document)

    def test_rejects_reordered_replacement_mechanisms(self):
        document = _valid_script()
        document["steps"][4]["mechanism"] = "save-load-replacement"
        document["steps"][7]["mechanism"] = "new-game-reset"
        with self.assertRaisesRegex(A1LifetimeActionScriptError, "exactly once in order"):
            validate_action_script(document)

    def test_rejects_steps_over_declared_bound(self):
        document = _valid_script()
        document["bounds"]["max_action_count"] = 8
        with self.assertRaisesRegex(A1LifetimeActionScriptError, "max_action_count"):
            validate_action_script(document)

    def test_rejects_unbounded_time_relationship(self):
        document = _valid_script()
        document["bounds"]["per_step_timeout_seconds"] = 121
        with self.assertRaisesRegex(A1LifetimeActionScriptError, "must not exceed"):
            validate_action_script(document)


if __name__ == "__main__":
    unittest.main()
