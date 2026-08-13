from pathlib import Path


def replace_tail(path: str, marker: str, staged: str) -> None:
    p = Path(path)
    text = p.read_text()
    i = text.index(marker)
    p.write_text(text[:i] + Path(staged).read_text())


replace_tail(
    "docs/experiments/RE5-runtime-turn-path.md",
    "## 2026-08-13 perturbation follow-up — current evidence\n",
    ".re5-docstage/experiment-tail.md",
)
replace_tail(
    "docs/re/auto-management-turn-path.md",
    "## RE5 runtime confirmation and reopened Manual-gate question\n",
    ".re5-docstage/re-tail.md",
)

roadmap = Path("ROADMAP.md")
text = roadmap.read_text()
old_front = """**Current front of the path:** CF1–CF4, T0–T2 and RE1–RE5 are complete. **A1 and A2 are now selectable as CLOUD**; they are the current architecture front and may proceed from the completed RE4/RE5 runtime contract.

RE4 runtime-confirmed the existing per-planet Managed field and immediate UI transition on two distinct planet records. RE5 runtime-confirmed its per-turn causal path into existing automatic management. A1 now owns the three-profile session-state representation; A2 owns the patch/integration mechanism."""
new_front = """**Current front of the path:** CF1–CF4, T0–T2 and RE1–RE4 are complete. **RE5 is reopened as `Investigation first` / CLOUD** because the strengthened Manual gate discriminator is inconclusive. A1 and A2 remain dependency-blocked on RE5.

RE5 still establishes the Managed policy/commit layering, but the Manual/override reachability discriminator is open. The next RE5 experiment must obtain a less perturbing player-loop reachability/override witness before A1/A2 may consume a completed runtime contract."""
if old_front not in text:
    raise SystemExit("ROADMAP front marker mismatch")
text = text.replace(old_front, new_front, 1)

start = "## RE5 — Runtime-confirm the per-turn self-management call path\n"
end = "\n---\n\n# Track A — Architecture decisions\n"
i = text.index(start)
j = text.index(end, i)
section = """## RE5 — Runtime-confirm the per-turn self-management call path

- **Status:** **Investigation first** — reopened by the 2026-08-13 perturbation follow-up. Managed policy/commit causality remains established, but the strengthened Manual gate/override discriminator is inconclusive; see [`docs/re/auto-management-turn-path.md`](./docs/re/auto-management-turn-path.md) and [`docs/experiments/RE5-runtime-turn-path.md`](./docs/experiments/RE5-runtime-turn-path.md).
- **Execution:** **CLOUD** — exact canonical target and pinned maintainer-supplied retail fixture are runnable with the existing RE4/RE5 harness.
- **Priority:** Critical
- **Category:** Reverse engineering / runtime turn processing
- **Origin:** High-level step 3
- **Depends on:** RE3 (complete), RE4 (complete), CF3 (complete)
- **Gates:** A1, A2 and later M1 work that relies on the completed Manual/automated gate contract
- **Question:** Which runtime path consumes the confirmed auto-management state during a turn, and how can Manual be distinguished from the separate RE3 override path without a strongly perturbing probe?

### Current outcome

`runtime`, clean blind-RE evidence on the canonical target:

- Managed reaches static `0x3c118`; the fresh fixed-window probe first observed reachability at `25.946 ms`.
- Suppressing the complete `0x3c118 -> 0x3d8f0` call prevents the tested Managed selection/action while stardate advances `0 -> 233` in `7009.080 ms`; the policy boundary remains necessary for the tested path.
- Fresh Managed control selects and commits; suppressing only the downstream `0x34df2` action commit preserves upstream selection while the action byte stays empty. The decision/commit layering remains established.
- The reachability probe is strongly perturbing: the clean Managed-vs-Managed comparison is `+233` with policy suppression versus `+1` with the reachability probe over essentially the same seven-second observation. Fresh Manual control reaches `+232`. This is an instrumentation progression artifact, not a game-performance result.
- The strengthened Manual probe ran `30017.889 ms`, never observed Xerxes reachability, and kept selection/action empty, but stardate advanced only `0 -> 1`, below the precommitted target `4`.
- No same-player two-sided witness exists in the pinned save. The structurally validated opposite-side owned records belong to other races, so their activity is supplemental telemetry only.
- Therefore the precommitted Manual outcome is **inconclusive** and the former claim that the separate override bypass is runtime-confirmed inactive is withdrawn.

Five of six fresh focused scenario artifacts pass; `manual-gate-probe` is `inconclusive`. The schema-3 aggregator fails closed and does not emit a causal `run-aggregate.json`. No historical JSON was reconstructed from prose.

### Next investigation

Obtain a **less perturbing player-loop reachability/override witness** that either preserves normal action-state semantics while observing player-loop reachability or directly establishes the separate override condition through a trustworthy runtime relationship. Do not strengthen the claim merely by extending the current mutating probe window.

### Deliverables

- [x] original runtime experiment record and durable RE findings;
- [x] original fail-closed low-level RE5 runner;
- [x] follow-up evidence/contract model and runner with per-scenario observation policies, exact runner provenance, ever-seen reachability semantics, and fail-closed aggregation;
- [x] focused synthetic coverage for the original runner and follow-up contracts/stop policies/inconclusive classification;
- [ ] minimally perturbing Manual gate/override witness satisfying the strengthened oracle;
- [ ] successful current-contract six-scenario causal aggregate after that witness exists.

### Acceptance criteria

**Not met.** Managed reachability, policy necessity, and decision/commit layering are runtime-established, but RE5 may return to **Completed and verified** only when the Manual/override ambiguity is closed with evidence that satisfies the declared contract without relying on the strongly perturbing reachability probe. Until then the candidate seam before `0x3c118` is not an unlocked A1/A2 architecture dependency.
"""
roadmap.write_text(text[:i] + section + text[j:])
