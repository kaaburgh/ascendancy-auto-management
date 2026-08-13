# RE5 — runtime automatic-management turn-path experiment

Date: 2026-08-13  
Roadmap item: RE5  
Blind-RE provenance: **clean**  
Evidence class: **runtime**, with RE3 static addresses used only as experiment boundaries.

## Question

Does the RE4-confirmed per-planet Managed state actually control the RE3 automatic-management path during turn processing, and where is the smallest established seam that M1 must preserve to keep the original automation behavior?

The experiment is deliberately causal rather than a whole-turn trace. It compares the same pinned saved planet in Manual and Managed modes, directly probes reachability of the RE3 gate-to-policy call site, and temporarily removes two whole-instruction boundaries from the **live DOSBox process only**:

1. reachability probe at `0x3c118`: replace the five-byte call with `mov byte [edx+0x54], 0x7e; nop`;
2. suppress the RE3 gate-to-policy call `0x3c118 -> 0x3d8f0`;
3. suppress the downstream action-byte commit `0x34df2: mov [planet+0x54], al` inside the `0x34b0c` mutation candidate.

## Inputs

Canonical target:

- `ANTAG.EXE` — 610863 bytes — SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`.

Runtime fixture:

- exact committed `tools/retail-runtime-manifest.json` — SHA-256 `814c37ea8683e9c32ce494bcb9568d08a33d3ef8e6d91b99ac07f37958269852`;
- immutable manifest entries: 17, all size/SHA-256 verified before execution;
- mutable input used by the scenario: `resume.gam`, SHA-256 `fe7b29f63b685df3b098c0bd109a44e95c9a36a2116617b6c0363eb289a813d3`.

Runtime/tooling:

- supplied DOSBox 0.74-3 Linux x86-64 runtime bundle; its `verify.sh` passed before the experiment;
- DOSBox CPU core forced to `normal` so live guest-code diagnostic writes are immediately observed and reversible;
- Xvfb + XTEST for bounded input;
- `/proc/<pid>/mem` for bounded guest-backing-memory reads/writes in the DOSBox process;
- `scripts/run_re5_runtime_turn_path.py` for the final fail-closed experiment.

The selected player planet is `Xerxes I`, independently established by RE4 as a structured `0x7b` runtime record with its name at `+0x24`. The pinned resume begins with:

- owner candidate `+0x57 = 0x00`;
- current selected slot `+0x52 = 0xffff`;
- current action `+0x54 = 0xff` (empty);
- Managed state `+0x5a = 0x00000000` (Manual).

No external target-specific recovered knowledge, unsupported repository history, cheat table, source reconstruction, or third-party mod internals were used.

## Instrumentation safety

The runner reuses RE4's exact fixture verification, unique relocation-tolerant runtime toggle signature, UI driver and bounded process-memory primitives.

It does **not** assume a DOS/4G selector/base mapping. RE2's uniquely matched runtime toggle sequence is used only as a mapping-local code anchor corresponding to static `0x37915`; RE5 resolves another static code site by the already established code-relative delta inside that same runtime mapping.

Before either live diagnostic patch, the runner requires the exact canonical instruction bytes:

| Purpose | Static VA | Expected whole instruction | Diagnostic bytes |
| --- | ---: | --- | --- |
| probe gate → policy reachability | `0x3c118` | `e8 d3 17 00 00` (`call 0x3d8f0`) | `c6 42 54 7e 90` (`mov byte [edx+0x54],0x7e; nop`) |
| suppress gate → policy | `0x3c118` | `e8 d3 17 00 00` (`call 0x3d8f0`) | five NOPs |
| suppress action commit | `0x34df2` | `88 46 54` (`mov [esi+0x54], al`) | three NOPs |

A zero/ambiguous runtime anchor, unexpected bytes, short process read/write, missing structured `Xerxes I` record, non-empty initial `+0x52/+0x54`, unexpected state transition, or failed patch restore fails closed. Each patched scenario runs in a fresh process and temporary copy of the retail tree. Original bytes are restored and byte-verified before process teardown; the repository or supplied retail tree is never modified.

Raw memory snapshots and host addresses are not written to artifacts. Scenario artifacts retain only hashes, mapping size/relative anchor offsets, object-relative state values, static patch sites/bytes, bounded timing observations, the bounded stardate progress witness, and pass/fail oracles. Focused runs write `run-<scenario>.json`; `--scenario all` writes `run.json`.

### Stable sampling under fast-forward

An early clean-run attempt exposed an instrumentation problem: concurrent `/proc/<pid>/mem` polling can stall while DOSBox is executing the `normal` core at fast-forward. This was treated as a diagnostic-tool failure rather than target evidence.

The final runner stops DOSBox with `SIGSTOP`, waits until `/proc/<pid>/status` reports an actual stopped-state code (`T` or `t`) **after** the `State:` colon, performs a bounded operation, and resumes with `SIGCONT`. Sampling reads the `Xerxes I` record window and the independent stardate witness in the same stopped interval. A review found that the first implementation searched for the letters `T`/`t` anywhere in the whole `State:` line; lowercase `t` in the label itself made that check vacuous. The parser now extracts the state code explicitly and focused tests cover `R`, `S`, `T`, and `t`.

The same stopped-process primitive now also wraps diagnostic code apply, exact-byte verification, restore, and restore verification. This prevents the guest interpreter from fetching a partially written 3- or 5-byte instruction. The required positive-control reruns below exercised that paused-write path for the gate marker and policy-suppression patches; no additional DOSBox run was made solely for this safety refactor.

### Independent turn-progress witness

The load-bearing negative oracles need to distinguish “this planet stayed idle” from “the game processed no turn/date progress during the observation window.” A bounded runtime search identified one exact-target, runtime-only witness at **RE2 anchor-relative `+0x5e657`**: a little-endian dword that tracks the upper-right five-digit stardate display. Stopped-process spot checks matched `35` with UI `00035` and `148` with UI `00148`; one sample read memory `80` while the rendered UI still showed `00079`, consistent with the display being one render behind at the stop boundary.

RE5 does **not** publish this as a guessed DOS/4G guest/static data address. It is scoped only to the uniquely resolved canonical runtime mapping and recorded as an anchor-relative relationship. The three negative-result scenarios now require this dword to increase (`delta > 0`) during their bounded windows. That is the positive control: at least one stardate progress unit was processed while the negative planet/path oracle remained negative.

These stopped samples produce coherent bounded observations. The observed millisecond values below are diagnostic sampling-window measurements, not instruction-level or gameplay-performance timings.

## Procedure

For every sub-scenario the runner starts from a fresh copy of the same pinned fixture and save:

1. start canonical `ANTAG.EXE` under DOSBox `core=normal`;
2. resume the pinned save and open `Xerxes I`;
3. require a unique RE4 runtime anchor and unique player-owned `Xerxes I` record;
4. require `+0x52 == 0xffff` and `+0x54 == 0xff`;
5. leave the planet Manual or toggle ordinary **M** to the RE4-confirmed `+0x5a == 0xffffffff` Managed state;
6. apply the scenario's optional live-process diagnostic patch while DOSBox is confirmed stopped, after exact-byte validation;
7. return to the main screen, enable fast-forward, and coherently sample `+0x52/+0x54/+0x5a` plus the anchor-relative stardate witness for a bounded 7-second window;
8. stop fast-forward, validate the scenario oracle (including positive turn progress for negative scenarios), restore/verify any diagnostic instruction bytes while stopped, and terminate the temporary process.

The original six-scenario confirmation was executed as focused invocations because the surrounding container tool imposes a shorter single-command wall-time than six fresh DOSBox startups combined. Focused runs preserve separate `run-<scenario>.json` files. Current artifacts use schema `2` and carry experiment contract `ascendancy.re5-runtime-turn-path/contract-v2`. When all six are present, the runner requires that exact contract and target/fixture identity, verifies scenario membership/window consistency, **re-runs the current `validate_scenario()` oracle on every loaded trace**, recomputes `summarize_causality`, and only then writes `run-aggregate.json` without starting DOSBox. Missing or older contract IDs fail closed; changing an incompatible instrumentation/oracle contract requires bumping this ID.

The earlier review aggregate was produced before this explicit contract binding and mixed three newly rerun negative artifacts with three preserved positive artifacts from an earlier corrected head. Those observations remain the documented target evidence, but that pre-contract aggregate is now treated as historical validation rather than as an input accepted by the current aggregator. The current tool deliberately does **not** retroactively stamp legacy artifacts with a new contract. No additional DOSBox launch was made for this artifact-integrity follow-up. Future focused target runs will emit contract-bound artifacts directly.

## Final observations

### 1. Manual control: no automatic selection or commit

Pinned start/armed state:

```text
+0x52 = ffff
+0x54 = ff
+0x5a = 00000000
```

Observed for `7015.588 ms` with coherent stopped-state sampling:

- no `+0x52` change;
- no `+0x54` change;
- `+0x5a` remained zero;
- independent stardate witness advanced `0 -> 219` (`delta = 219`);
- DOSBox remained alive.

The positive control therefore rules out “no turn/date progress occurred” for this negative result.

Result: **PASS**.

### 2. Manual gate-reachability probe: `0x3c118` is not reached

After exact-byte validation, the runner replaced the complete `0x3c118` call (`e8 d3 17 00 00`) with `c6 42 54 7e 90`, which writes marker byte `0x7e` to `[EDX+0x54]` and does not invoke the policy. RE3 independently established that `EDX` is the current planet pointer at this call site.

With `+0x5a == 0`, observed for `7005.156 ms`:

- `+0x52` remained `ffff`;
- `+0x54` remained `ff` — marker `7e` never appeared on `Xerxes I`;
- `+0x5a` remained `00000000`;
- independent stardate witness advanced `0 -> 1` (`delta = 1`);
- patch apply/verify and restore/re-verify occurred while DOSBox was confirmed stopped.

Result: **PASS**. The positive control establishes **at least one stardate progress unit** during which the pinned Manual planet did not reach the marker. It does not claim continuous seven-second turn throughput.

The marker replacement is process-wide at the shared call site: while installed, any other planet record that reaches `0x3c118` may also receive marker `0x7e` at its own `+0x54`. That is intentional bounded diagnostic mutation in a throwaway process, not persistent game state; the scenario oracle observes only the pinned `Xerxes I` record and the process is discarded after verified code restore.

### 3. Managed gate-reachability probe: the same `0x3c118` site is reached

The exact same marker replacement was applied in a fresh process after ordinary **M** produced `+0x5a == 0xffffffff`.

The first corrected coherent sample at `26.099 ms` observed:

```text
+0x52 = ffff
+0x54: ff -> 7e
+0x5a = ffffffff
```

No policy call was executed because the call instruction itself had been replaced by the marker write. Original call bytes were restored and byte-verified.

Result: **PASS**.

**Runtime conclusion:** for the same player-owned planet and empty-action preconditions, Manual does not reach `0x3c118` while Managed does. Static RE3 control flow permits Manual to reach this site only when the separate override is nonzero, so the paired probe establishes that the override bypass is **inactive in this pinned Manual scenario** without requiring an unverified DOS/4G data-address mapping.

### 4. Managed control: automatic selection reaches action commit

After ordinary **M**:

```text
+0x52 = ffff
+0x54 = ff
+0x5a = ffffffff
```

Observed at the first corrected mutation sample (`4511.810 ms`):

```text
+0x52: ffff -> 3400
+0x54: ff   -> 00
+0x5a: ffffffff (unchanged)
```

`0x0034` and `0x00` are recorded values only; RE5 does not assign gameplay semantics to those codes.

Result: **PASS**.

### 5. Managed + gate-to-policy call suppressed: no selection or commit

The runner verified `e8 d3 17 00 00` at static `0x3c118`, replaced the complete five-byte call with NOPs in the live process, then armed the same Managed state.

Observed for `7008.927 ms` with coherent stopped-state sampling:

- `+0x52` remained `ffff`;
- `+0x54` remained `ff`;
- `+0x5a` remained `ffffffff`;
- independent stardate witness advanced `0 -> 231` (`delta = 231`);
- patch apply/verify and restore/re-verify occurred while DOSBox was confirmed stopped;
- DOSBox remained alive.

The positive control therefore rules out “no turn/date progress occurred” as the explanation for the suppressed-path negative result.

Result: **PASS**.

**Runtime conclusion:** the RE3 `0x3c118 -> 0x3d8f0` boundary is necessary for the tested automatic selection/action path.

### 6. Managed + final action-byte write suppressed: selection survives, commit does not

The runner verified `88 46 54` at static `0x34df2` and replaced that complete three-byte instruction with NOPs in the live process.

The policy path still produced a selected slot at the first observed selection sample (`5174.806 ms`):

```text
+0x52: ffff -> 3400
+0x54: ff   -> ff
+0x5a: ffffffff (unchanged)
```

During the full `7005.001 ms` bounded window, `+0x54` never left `ff`. The original `88 46 54` bytes were restored and byte-verified; DOSBox remained alive.

Result: **PASS**.

**Runtime conclusion:** selection/decision output exists upstream of the `+0x54` write, while `0x34df2` is a concrete action-commit seam in the tested `0x34b0c` mutation path.

## Exploratory negative result retained

Before settling on the commit-write intervention, a clean exploratory run suppressed the RE3-highlighted internal call site `0x3df88 -> 0x34b0c` (`e8 7f 6b ff ff`) alone. The Managed planet still received an automatic action in that run (about 4.3 seconds after fast-forward began), and the original bytes were restored.

Therefore `0x3df88` is **not** established as the unique runtime policy-to-mutation call for the pinned `Xerxes I` scenario. RE3 already identified several static calls from the policy candidate into `0x34b0c`; RE5 deliberately does not guess which individual caller supplied this particular selected action. The downstream `0x34df2` write is the stronger runtime boundary because suppressing it preserved upstream selection while preventing commit.

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

All six fresh focused JSON files were captured and evaluated in the follow-up working set, but one scenario is intentionally `inconclusive`. The raw focused JSON files were not committed or uploaded and are not reconstructed here. The schema-3 aggregator therefore fails closed on the non-passed Manual artifact and **does not produce a causal `run-aggregate.json`**. No historical JSON is reconstructed or retroactively stamped to manufacture a complete set.

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
