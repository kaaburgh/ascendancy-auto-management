from pathlib import Path

p = Path('tests/test_run_re5_runtime_turn_path.py')
s = p.read_text(encoding='utf-8')

def r(old: str, new: str) -> None:
    global s
    if s.count(old) != 1:
        raise SystemExit(f'test anchor count {s.count(old)} for {old[:80]!r}')
    s = s.replace(old, new, 1)

r('        self.assertEqual(re5.POLICY_SUPPRESSION.expected.hex(), "e8d3170000")\n        self.assertEqual(len(re5.POLICY_SUPPRESSION.replacement), 5)\n',
  '        self.assertEqual(re5.POLICY_SUPPRESSION.expected.hex(), "e8d3170000")\n        self.assertEqual(len(re5.POLICY_SUPPRESSION.replacement), 5)\n        self.assertEqual(re5.GATE_REACHABILITY_PROBE.expected.hex(), "e8d3170000")\n        self.assertEqual(re5.GATE_REACHABILITY_PROBE.replacement.hex(), "c642547e90")\n')
r('    def _trace(self, slot=None, action=None, *, state="ffffffff", final_action="ff"):\n',
  '    def test_proc_state_parser_uses_code_after_label_only(self):\n        self.assertEqual(re5.parse_proc_state_code("State:\\tT (stopped)"), "T")\n        self.assertEqual(re5.parse_proc_state_code("State:\\tt (tracing stop)"), "t")\n        self.assertEqual(re5.parse_proc_state_code("State:\\tR (running)"), "R")\n        self.assertEqual(re5.parse_proc_state_code("State:\\tS (sleeping)"), "S")\n        self.assertEqual(re5.parse_proc_state_code("Name:\\tdosbox"), "")\n\n    def _trace(self, slot=None, action=None, *, state="ffffffff", final_action="ff"):\n')
r('    def test_managed_control_requires_selection_and_action_commit(self):\n',
  '    def test_gate_probe_distinguishes_manual_and_managed_reachability(self):\n        manual = next(s for s in re5.SCENARIOS if s.name == "manual-gate-probe")\n        managed = next(s for s in re5.SCENARIOS if s.name == "managed-gate-probe")\n        re5.validate_scenario(manual, self._trace(None, None, state="00000000"))\n        re5.validate_scenario(managed, self._trace(None, 65.0, final_action="7e"))\n        with self.assertRaises(re5.RE5Error):\n            re5.validate_scenario(manual, self._trace(None, 65.0, state="00000000", final_action="7e"))\n        with self.assertRaises(re5.RE5Error):\n            re5.validate_scenario(managed, self._trace(None, None))\n\n    def test_managed_control_requires_selection_and_action_commit(self):\n')
r('            if spec.name == "manual-control":\n                trace = self._trace(None, None, state="00000000")\n            elif spec.name == "managed-control":\n',
  '            if spec.name in {"manual-control", "manual-gate-probe"}:\n                trace = self._trace(None, None, state="00000000")\n            elif spec.name == "managed-gate-probe":\n                trace = self._trace(None, 65.0, final_action="7e")\n            elif spec.name == "managed-control":\n')
r('        self.assertTrue(summary["manual_stays_idle"])\n        self.assertTrue(summary["managed_commits_action"])\n',
  '        self.assertTrue(summary["manual_stays_idle"])\n        self.assertTrue(summary["manual_does_not_reach_gate_policy_call"])\n        self.assertTrue(summary["managed_reaches_gate_policy_call"])\n        self.assertTrue(summary["override_path_inactive_for_manual_probe"])\n        self.assertTrue(summary["managed_commits_action"])\n')
p.write_text(s, encoding='utf-8')
