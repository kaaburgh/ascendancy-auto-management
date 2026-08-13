## 2026-08-13 perturbation follow-up — current evidence

### Phase -1 facts before code/runtime

No original focused RE5 JSON artifacts were physically available in the working environment, repository, or inspected GitHub Actions artifacts. The four historical result files were therefore **not reconstructed from prose or numbers in this document**. Per the precommitted plan, the follow-up budget became six fresh focused target runs.

The pinned `resume.gam` was also inspected structurally before any new DOSBox run. Relative to the unique `Xerxes I` record, the immediate `-0x7b`/`+0x7b` records are `Stavern IV` and `Xerxes II`, but both have owner byte `0xff` (unowned). RE3's static loop checks owner `+0x57` before the `0x3c118` gate, so those immediate neighbors cannot serve as same-player-loop marker witnesses. `Xerxes I` is the only owner-`0` record in the pinned save.

The nearest structurally validated **owned** records on opposite sides are:

- `Stavern I`, `Xerxes - 4 * 0x7b`, owner `0x01`;
- `Hurble I`, `Xerxes + 8 * 0x7b`, owner `0x05`.

They are useful cross-race loop-activity telemetry only. They are **not** promoted to a hard bracket for the player-race loop, and no `array_base` or `record_count` is inferred. Therefore the agreed Manual fallback requires four stardate increments if Xerxes remains unmarked; a two-sided marker observation on these other-race records cannot substitute for that target.

### Follow-up artifact/observation contract

Follow-up artifacts use `artifact_schema: 3` and separately record:

- `runner_revision`: exact 40-hex git SHA as provenance only; mixed revisions are allowed when scenario contracts remain compatible;
- `scenario_contract`: local to each scenario;
- `observation_policy`: `stop_policy`, `max_window_seconds`, and optional `progress_target`.

`managed-gate-probe` uses `fixed_window` for seven seconds and records the first marker while continuing to the deadline. `manual-gate-probe` uses `progress_target_or_timeout`, target `4`, hard ceiling `30 s`. Because no hard same-player bracket exists in this fixture, a Manual timeout below four increments is classified and preserved as **inconclusive**, not converted into a causal PASS. The already captured `managed-gate-probe/v2` artifact used a stricter supplemental-collateral start condition and is explicitly accepted by the current model; `runner_revision` alone is not a compatibility discriminator.

### Fresh exact-target observations

All rows below are fresh original JSON observations from the exact canonical target/fixture. Diagnostic code changes were process-memory-only, applied/restored while DOSBox was confirmed stopped, and restore verification succeeded for every patched scenario.

During the follow-up, several intermediate captures were explicitly discarded after a provenance audit found that the local base follow-up source did not byte-match the published GitHub blob named by their `runner_revision`. Those files are quarantined as provenance-invalid and are **not** used below. Before the retained reruns, the local model/base/capture sources were verified byte-for-byte by Git blob SHA against the published repository state; the retained artifacts record either `aba61e0f0b08f981f65d9b63d08944817913a752` (the earlier valid Managed fixed-window probe) or `587d2ed9ce58221be69fcbe7d47c5aca28bc244e` (the provenance-synchronized reruns). No invalidated measurement was copied into the retained evidence.

| Scenario | Status | Observation | Stardate | Key result |
| --- | --- | ---: | ---: | --- |
| `managed-gate-probe` | PASS | `7002.031 ms` fixed window | `0 -> 1` (`+1`) | Xerxes marker first seen at `25.946 ms`; both cross-race telemetry records were also marked |
| `manual-gate-probe` | **INCONCLUSIVE** | `30017.889 ms`, `stop_reason=timeout` | `0 -> 1` (`+1`), target `4` not met | Xerxes marker never seen; `+0x52/+0x54` stayed empty; both cross-race telemetry records were marked, but they are not a hard player-loop bracket |
| `managed-policy-suppressed` | PASS | `7009.080 ms` | `0 -> 233` (`+233`) | no selection/action mutation while the whole policy call is NOPed; restore verified |
| `manual-control` | PASS | `7015.295 ms` | `0 -> 232` (`+232`) | no selection/action mutation, no diagnostic code patch |
| `managed-control` | PASS | `3850.671 ms`, first-action stop | `0 -> 125` (`+125`) | `+0x52 -> 3400`, `+0x54 -> 00` at first mutation sample (`3850.656 ms`) |
| `managed-action-write-suppressed` | PASS | `7020.877 ms` | `0 -> 208` (`+208`) | selection survived (`+0x52 -> 3b00` first seen at `4031.758 ms`) while `+0x54` stayed `ff`; restore verified |

The selected-slot values vary between fresh runs (`0x0034`, `0x003b`); RE5 continues to treat them as opaque observed values, not reconstructed gameplay semantics.

### What the progression gap establishes

The strongest isolating comparison is **Managed versus Managed** with essentially the same seven-second wall-clock observation and the same `0x3c118` call removed:

- `managed-policy-suppressed`: replacement is five NOPs, stardate `+233` in `7009.080 ms`;
- `managed-gate-probe`: replacement writes `0x7e` to `[EDX+0x54]`, stardate `+1` in `7002.031 ms`.

`manual-control` independently reaches `+232` in `7015.295 ms`, and `managed-action-write-suppressed` reaches `+208` in `7020.877 ms`. The very large `+233` versus `+1` gap therefore strongly supports the marker write/process-wide state mutation as the source of the progression suppression. It does **not** establish a target-game performance defect: performance interpretation of the marker scenarios is heavily contaminated by instrumentation.

This also explains why simply extending the Manual marker window does not monotonically strengthen the gate claim. The new 30-second Manual probe still advances only one stardate unit. The marker is absent on `Xerxes I`, but with no hard same-player bracket and target `4` unmet, the precommitted outcome is **inconclusive**. Cross-race telemetry demonstrates that the shared call site is active elsewhere during the run, but it does not prove that the player-race loop traversed the Xerxes position under the same condition.

### Aggregation result

All six fresh focused JSON files exist, but one scenario is intentionally `inconclusive`. The schema-3 aggregator therefore fails closed on the non-passed Manual artifact and **does not produce a causal `run-aggregate.json`**. No historical JSON is reconstructed or retroactively stamped to manufacture a complete set.

The aggregate refusal is the correct durable outcome: five current scenario oracles pass, while the one load-bearing Manual gate oracle does not meet the agreed evidence-strength contract.

## Interpretation

### Established, runtime, clean

The follow-up preserves several RE5 findings:

1. Managed `Xerxes I` reaches the `0x3c118` call site: marker first observed at `25.946 ms`.
2. Suppressing the complete `0x3c118 -> 0x3d8f0` call prevents tested Managed selection/action while normal stardate progression continues (`+233` in `7009.080 ms` fresh run). The policy boundary remains runtime-necessary for the tested automatic action path.
3. Managed control still selects and commits an action; suppressing only the downstream `0x34df2` action-byte write preserves upstream selection while keeping `+0x54 == ff`. The decision/commit layering remains established.
4. The process-wide `0x7e` marker is strongly perturbing: it collapses stardate progression from approximately the fresh control range (`+208..+233` over seven seconds) to `+1` in the Managed probe. This is an instrumentation artifact/classification, not a game-performance result.
5. Short local Managed reachability remains trustworthy because the marker is observed before the large accumulated perturbation; long negative Manual absence is weaker because non-interference is not established.

### Reopened question

The follow-up **does not establish** that the separate RE3 override bypass is inactive in the pinned Manual scenario to the newly agreed strength. `Xerxes I` remained unmarked for 30 seconds and one stardate increment, but:

- no second player-owned record exists in the pinned save to form a hard same-player-loop bracket;
- the opposite-side owned records belong to other races and are supplemental telemetry only;
- the precommitted fallback target was four stardate increments; the marker-perturbed run reached only one.

Therefore the old statement “Manual does not reach `0x3c118`, so the override bypass is inactive” is no longer treated as completed runtime evidence. A next RE5 experiment must use a less perturbing reachability witness or directly establish the override condition without inventing an unverified DOS/4G data mapping.

### M1 handoff status

The candidate compatibility seam remains **before `0x3c118`** because the Managed policy/commit interventions still support preserving the existing downstream policy rather than reimplementing it. However it is now a **candidate pending RE5 completion**, not an unlocked architecture contract for A1/A2. Until the Manual/override reachability ambiguity is closed with adequate evidence, later roadmap items depending on RE5 remain blocked.

### Remaining unknowns

- The separate global override's gameplay semantics and trustworthy runtime value/address remain unknown.
- A minimally perturbing player-loop reachability witness has not yet been established.
- Non-player convergence remains high-confidence RE3 static evidence; the cross-race marker telemetry does not replace a same-player embedded control.
- The exact gameplay meanings of selected slot/action codes remain intentionally unreconstructed.

## Reproduction

Focused helper tests for the original runner and follow-up contract:

```sh
python -m unittest tests.test_run_re5_runtime_turn_path tests.test_re5_followup_contract -v
```

The current follow-up target runner is invoked with an explicit source revision. Gate probes use the policies embedded in their per-scenario contracts; do not override them with an ad-hoc common window:

```sh
python scripts/run_re5_runtime_turn_path_followup_capture.py \
  --game-dir /path/to/pinned/retail-tree \
  --dosbox /path/to/dosbox \
  --fixture-manifest tools/retail-runtime-manifest.json \
  --artifacts artifacts/re5-runtime-turn-path-followup \
  --runner-revision <exact-40-hex-source-sha> \
  --scenario managed-gate-probe
```

Use the same command for the other five scenario names. Do not reconstruct a missing focused JSON from the observations in this document. A causal aggregate is valid only when all six focused artifacts pass their declared current-compatible scenario contracts.

## Result

**RE5 acceptance is currently NOT met under the agreed follow-up evidence contract.**

The Managed side of the path remains well established: Managed reaches `0x3c118`; the existing `0x3d8f0` policy boundary is necessary for the tested selection/action; and `0x34df2` remains a concrete downstream commit seam. The new fixed-window probe also establishes that the `0x7e` marker intervention itself severely suppresses progression (`+1` versus fresh Managed NOP-control `+233 / 7009.080 ms`).

The Manual gate/override discriminator is the blocker. In the exact pinned scenario, a 30-second marker run produced no Xerxes marker but only one stardate increment, with no hard same-player bracket available. By the precommitted outcome table this is **inconclusive**, so the earlier runtime claim that the override bypass is inactive is reopened rather than defended with a longer contaminated run.

The next RE5 step is an investigation for a less perturbing player-loop reachability/override witness. A1/A2 must not consume the former completed-RE5 gate conclusion until that evidence exists.
