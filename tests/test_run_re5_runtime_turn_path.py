from __future__ import annotations

from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_re5_runtime_turn_path as re5


class RE5RuntimeTests(unittest.TestCase):
    def test_named_planet_record_requires_unique_player_owned_record(self):
        blob = bytearray(0x400)
        base = 0x120
        name_offset = re5.re4.NAME_OFFSET
        blob[base + name_offset:base + name_offset + 9] = b"Xerxes I\0"
        blob[base + re5.OWNER_OFFSET] = 0
        self.assertEqual(re5.find_named_planet_record(bytes(blob)), base)
        base2 = 0x240
        blob[base2 + name_offset:base2 + name_offset + 9] = b"Xerxes I\0"
        blob[base2 + re5.OWNER_OFFSET] = 0
        with self.assertRaises(re5.RE5Error):
            re5.find_named_planet_record(bytes(blob))

    def test_named_planet_record_rejects_non_player_owner(self):
        blob = bytearray(0x300)
        base = 0x100
        name_offset = re5.re4.NAME_OFFSET
        blob[base + name_offset:base + name_offset + 9] = b"Xerxes I\0"
        blob[base + re5.OWNER_OFFSET] = 3
        with self.assertRaises(re5.RE5Error):
            re5.find_named_planet_record(bytes(blob))

    def test_static_va_translation_is_anchor_relative_and_bounded(self):
        anchor = {"map_start": 0x100000, "map_end": 0x200000, "anchor_offset": 0x50000}
        expected = 0x100000 + 0x50000 + (re5.POLICY_CALL_VA - re5.ANCHOR_VA)
        self.assertEqual(re5.static_va_host(anchor, re5.POLICY_CALL_VA), expected)
        with self.assertRaises(re5.RE5Error):
            re5.static_va_host(anchor, 0x900000)

    def test_patch_plans_cover_whole_known_instruction_bytes(self):
        self.assertEqual(re5.POLICY_SUPPRESSION.expected.hex(), "e8d3170000")
        self.assertEqual(len(re5.POLICY_SUPPRESSION.replacement), 5)
        self.assertEqual(re5.GATE_REACHABILITY_PROBE.expected.hex(), "e8d3170000")
        self.assertEqual(re5.GATE_REACHABILITY_PROBE.replacement.hex(), "c642547e90")
        self.assertEqual(re5.ACTION_WRITE_SUPPRESSION.expected.hex(), "884654")
        self.assertEqual(len(re5.ACTION_WRITE_SUPPRESSION.replacement), 3)

    def test_proc_state_parser_uses_code_after_label_only(self):
        # Regression guard: never infer stopped state from letters in the literal "State:" label/body.
        self.assertEqual(re5.parse_proc_state_code("State:\tT (stopped)"), "T")
        self.assertEqual(re5.parse_proc_state_code("State:\tt (tracing stop)"), "t")
        self.assertEqual(re5.parse_proc_state_code("State:\tR (running)"), "R")
        self.assertEqual(re5.parse_proc_state_code("State:\tS (sleeping)"), "S")
        self.assertEqual(re5.parse_proc_state_code("Name:\tdosbox"), "")

    def _trace(self, slot=None, action=None, *, state="ffffffff", final_action="ff"):
        return {
            "first_slot_change_ms": slot,
            "first_action_change_ms": action,
            "final": {
                "owner_0x57": "00",
                "slot_0x52": "ffff" if slot is None else "3400",
                "action_0x54": final_action,
                "managed_0x5a": state,
            },
        }

    def test_gate_probe_distinguishes_manual_and_managed_reachability(self):
        manual = next(s for s in re5.SCENARIOS if s.name == "manual-gate-probe")
        managed = next(s for s in re5.SCENARIOS if s.name == "managed-gate-probe")
        re5.validate_scenario(manual, self._trace(None, None, state="00000000"))
        re5.validate_scenario(managed, self._trace(None, 65.0, final_action="7e"))
        with self.assertRaises(re5.RE5Error):
            re5.validate_scenario(manual, self._trace(None, 65.0, state="00000000", final_action="7e"))
        with self.assertRaises(re5.RE5Error):
            re5.validate_scenario(managed, self._trace(None, None))

    def test_managed_control_requires_selection_and_action_commit(self):
        spec = next(s for s in re5.SCENARIOS if s.name == "managed-control")
        re5.validate_scenario(spec, self._trace(4000.0, 4010.0, final_action="00"))
        with self.assertRaises(re5.RE5Error):
            re5.validate_scenario(spec, self._trace(None, None))

    def test_policy_suppression_requires_no_selection_or_action(self):
        spec = next(s for s in re5.SCENARIOS if s.name == "managed-policy-suppressed")
        re5.validate_scenario(spec, self._trace(None, None))
        with self.assertRaises(re5.RE5Error):
            re5.validate_scenario(spec, self._trace(2000.0, None))

    def test_action_write_suppression_requires_selection_but_no_action(self):
        spec = next(s for s in re5.SCENARIOS if s.name == "managed-action-write-suppressed")
        re5.validate_scenario(spec, self._trace(4800.0, None))
        with self.assertRaises(re5.RE5Error):
            re5.validate_scenario(spec, self._trace(None, None))
        with self.assertRaises(re5.RE5Error):
            re5.validate_scenario(spec, self._trace(4800.0, 4810.0, final_action="00"))

    def test_manual_control_requires_no_selection_or_action_and_manual_state(self):
        spec = next(s for s in re5.SCENARIOS if s.name == "manual-control")
        re5.validate_scenario(spec, self._trace(None, None, state="00000000"))
        with self.assertRaises(re5.RE5Error):
            re5.validate_scenario(spec, self._trace(None, None, state="ffffffff"))

    def test_summary_requires_complete_scenario_set(self):
        rows = []
        for spec in re5.SCENARIOS:
            if spec.name in {"manual-control", "manual-gate-probe"}:
                trace = self._trace(None, None, state="00000000")
            elif spec.name == "managed-gate-probe":
                trace = self._trace(None, 65.0, final_action="7e")
            elif spec.name == "managed-control":
                trace = self._trace(4000.0, 4010.0, final_action="00")
            elif spec.name == "managed-policy-suppressed":
                trace = self._trace(None, None)
            else:
                trace = self._trace(4800.0, None)
            rows.append({"name": spec.name, "status": "passed", "turn_trace": trace})
        summary = re5.summarize_causality(rows)
        self.assertTrue(summary["manual_stays_idle"])
        self.assertTrue(summary["manual_does_not_reach_gate_policy_call"])
        self.assertTrue(summary["managed_reaches_gate_policy_call"])
        self.assertTrue(summary["override_path_inactive_for_manual_probe"])
        self.assertTrue(summary["managed_commits_action"])
        self.assertTrue(summary["gate_policy_call_is_necessary"])
        self.assertTrue(summary["selection_survives_action_write_suppression"])
        self.assertTrue(summary["action_write_is_commit_seam"])
        with self.assertRaises(re5.RE5Error):
            re5.summarize_causality(rows[:-1])


if __name__ == "__main__":
    unittest.main()
