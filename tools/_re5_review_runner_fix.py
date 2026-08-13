from pathlib import Path

p = Path('scripts/run_re5_runtime_turn_path.py')
s = p.read_text(encoding='utf-8')

def r(old: str, new: str) -> None:
    global s
    if s.count(old) != 1:
        raise SystemExit(f'runner anchor count {s.count(old)} for {old[:80]!r}')
    s = s.replace(old, new, 1)

r('POLICY_CALL_BYTES = bytes.fromhex("e8d3170000")  # call 0x3d8f0\nACTION_WRITE_VA',
  'POLICY_CALL_BYTES = bytes.fromhex("e8d3170000")  # call 0x3d8f0\nGATE_MARKER_BYTES = bytes.fromhex("c642547e90")  # mov byte [edx+0x54],0x7e; nop\nGATE_MARKER_ACTION = 0x7E\nACTION_WRITE_VA')
r('ACTION_WRITE_SUPPRESSION = PatchPlan(\n',
  'GATE_REACHABILITY_PROBE = PatchPlan(\n    "probe-gate-policy-reachability",\n    POLICY_CALL_VA,\n    POLICY_CALL_BYTES,\n    GATE_MARKER_BYTES,\n)\nACTION_WRITE_SUPPRESSION = PatchPlan(\n')
r('SCENARIOS = (\n    ScenarioSpec("manual-control", False, None),\n    ScenarioSpec("managed-control", True, None),\n',
  'SCENARIOS = (\n    ScenarioSpec("manual-control", False, None),\n    ScenarioSpec("manual-gate-probe", False, GATE_REACHABILITY_PROBE),\n    ScenarioSpec("managed-gate-probe", True, GATE_REACHABILITY_PROBE),\n    ScenarioSpec("managed-control", True, None),\n')
r('def paused_read_process(pid: int, address: int, size: int) -> bytes:\n',
  'def parse_proc_state_code(state_line: str) -> str:\n    """Return the one-letter /proc State code, never text from the label/body."""\n    if not state_line.startswith("State:"):\n        return ""\n    payload = state_line.split(":", 1)[1].strip()\n    if not payload:\n        return ""\n    return payload.split(None, 1)[0]\n\n\ndef paused_read_process(pid: int, address: int, size: int) -> bytes:\n')
r('            state_line = next((line for line in status.splitlines() if line.startswith("State:")), "")\n            if "T" in state_line or "t" in state_line:\n                return re4.read_process(pid, address, size)\n',
  '            state_line = next((line for line in status.splitlines() if line.startswith("State:")), "")\n            state_code = parse_proc_state_code(state_line)\n            if state_code in {"T", "t"}:\n                return re4.read_process(pid, address, size)\n')
r('def sample_record(pid: int, record_host: int) -> dict[str, str]:\n    return {\n        "owner_0x57": re4.read_process(pid, record_host + OWNER_OFFSET, 1).hex(),\n        "slot_0x52": re4.read_process(pid, record_host + SLOT_OFFSET, 2).hex(),\n        "action_0x54": re4.read_process(pid, record_host + ACTION_OFFSET, 1).hex(),\n        "managed_0x5a": re4.read_process(pid, record_host + re4.STATE_OFFSET, 4).hex(),\n    }\n',
  'def sample_record(pid: int, record_host: int) -> dict[str, str]:\n    window_offset = 0x50\n    window = paused_read_process(pid, record_host + window_offset, 0x0E)\n    return {\n        "owner_0x57": window[OWNER_OFFSET - window_offset:OWNER_OFFSET - window_offset + 1].hex(),\n        "slot_0x52": window[SLOT_OFFSET - window_offset:SLOT_OFFSET - window_offset + 2].hex(),\n        "action_0x54": window[ACTION_OFFSET - window_offset:ACTION_OFFSET - window_offset + 1].hex(),\n        "managed_0x5a": window[re4.STATE_OFFSET - window_offset:re4.STATE_OFFSET - window_offset + 4].hex(),\n    }\n')
r('            "owner_0x57": re4.read_process(pid, record_host + OWNER_OFFSET, 1).hex(),\n',
  '            "owner_0x57": final_window[OWNER_OFFSET - window_offset:OWNER_OFFSET - window_offset + 1].hex(),\n')
r('    if spec.name == "manual-control":\n        if first_slot is not None or first_action is not None:\n            raise RE5Error("manual-control unexpectedly selected or committed an automatic action")\n    elif spec.name == "managed-control":\n',
  '    if spec.name == "manual-control":\n        if first_slot is not None or first_action is not None:\n            raise RE5Error("manual-control unexpectedly selected or committed an automatic action")\n    elif spec.name == "manual-gate-probe":\n        if first_slot is not None or first_action is not None or final["action_0x54"] != "ff":\n            raise RE5Error("manual gate probe reached 0x3c118 despite +0x5a == 0")\n    elif spec.name == "managed-gate-probe":\n        if first_slot is not None:\n            raise RE5Error("managed gate probe unexpectedly changed +0x52")\n        if first_action is None or final["action_0x54"] != f"{GATE_MARKER_ACTION:02x}":\n            raise RE5Error("managed gate probe did not reach 0x3c118 marker write")\n    elif spec.name == "managed-control":\n')
r('        "manual_stays_idle": by_name["manual-control"]["turn_trace"]["first_action_change_ms"] is None,\n        "managed_commits_action": by_name["managed-control"]["turn_trace"]["first_action_change_ms"] is not None,\n',
  '        "manual_stays_idle": by_name["manual-control"]["turn_trace"]["first_action_change_ms"] is None,\n        "manual_does_not_reach_gate_policy_call": by_name["manual-gate-probe"]["turn_trace"]["first_action_change_ms"] is None,\n        "managed_reaches_gate_policy_call": (\n            by_name["managed-gate-probe"]["turn_trace"]["final"]["action_0x54"] == f"{GATE_MARKER_ACTION:02x}"\n        ),\n        "override_path_inactive_for_manual_probe": (\n            by_name["manual-gate-probe"]["turn_trace"]["first_action_change_ms"] is None\n            and by_name["managed-gate-probe"]["turn_trace"]["final"]["action_0x54"] == f"{GATE_MARKER_ACTION:02x}"\n        ),\n        "managed_commits_action": by_name["managed-control"]["turn_trace"]["first_action_change_ms"] is not None,\n')
r('Complete four-scenario set by default; focused modes are for diagnosis/retry.',
  'Complete six-scenario set by default; focused modes are for diagnosis/retry.')
p.write_text(s, encoding='utf-8')
