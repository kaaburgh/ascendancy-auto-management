# Automatic planet-management turn path

## Targets and evidence boundary

Canonical M1 target:

- `ANTAG_EN.EXE` — SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` — 610863 bytes.

Corroboration inputs:

- `ANTAG_INTL.EXE` — SHA-256 `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c`;
- `PATCH_EN.EXE` — SHA-256 `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b`;
- `PATCH_INTL.EXE` — SHA-256 `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b`.

Blind-RE provenance: **clean**. All target-specific conclusions below come from the hash-pinned binaries, current supported repository evidence from T1/T2/RE1, and independently generated static analysis. No external target-specific recovered knowledge was used.

Evidence class is **static** for the RE3 sections unless stated otherwise; the RE5 confirmation section below is explicitly **runtime** evidence. Semantic names in this note describe candidate roles supported by data flow; they are not recovered source symbols.

## Result in one graph

The strongest current model on the canonical target is:

```text
0x20c94  turn-processing/orchestration candidate
  |
  |-- 0x20dac -> 0x352e0  for every planet, stride 0x7b
  |                    general per-planet turn update; not the automation policy seam
  |
  `-- per race, stride 0x1ee
      |-- 0x20df3 -> 0x3b220  for non-player races
      `-- 0x20e15 -> 0x3b220  explicitly for the current player race
                         |
                         `-- 0x3b31b -> 0x3b5b8
                                      |
                                      `-- final owned-planet loop
                                          owner candidate [planet+0x57] == race id
                                          |
                                          +-- non-player race ------------+
                                          |                               |
                                          `-- current player              |
                                              [planet+0x5a] != 0 ---------+
                                              OR global override != 0
                                                                          |
                                          [planet+0x54] == 0xff            |
                                          (no current action)              |
                                                                          v
                                      0x3c118 -> 0x3d8f0
                                                   automatic-policy candidate
                                                   EAX = race, EDX = planet
                                                   |
                                                   |-- selection/scoring helpers
                                                   |-- random/tie-breaking path
                                                   `-- -> 0x34b0c at several sites
                                                          action/queue mutation candidate
                                                          writes [planet+0x52]
                                                          writes [planet+0x54]
                                                          then recalculates via 0x34e70
```

This is sufficient for M1 planning without reconstructing the whole AI: a new profile representation only needs to preserve whatever runtime condition RE4/RE5 confirms as the existing “automated” gate and continue into the existing `0x3d8f0` policy path.

## Established observations

### 1. The RE1 `0x352e0` lead is a general per-planet turn update

`0x20c94` contains a loop that calls `0x352e0` once per planet and advances the object pointer by `0x7b` bytes. Inside `0x352e0`, the same object pointer is retained in `ESI`; the routine consumes and updates fields including `+0x44`, `+0x50`, `+0x52`, `+0x54`, and `+0x57`, resolves completed/current actions, and calls the RE1 planet-cluster helpers.

This makes `0x352e0` a useful turn-processing anchor, but **not** the best self-management decision seam. It runs for every planet before the race-level automation gate and performs ordinary per-planet state progression whether or not the later automatic-policy path is taken.

This is a material negative/corrective result for RE1 H1: the RE1 structural lead was correctly close to turn processing, but its role should not be promoted to “automation policy.”

### 2. The same race-processing path is invoked for AI races and the player race

Later in `0x20c94`, a loop advances race records by `0x1ee` bytes. It calls `0x3b220` for every race except the current player, then separately computes the current-player race record and calls **the same** `0x3b220` at `0x20e15`.

`0x3b220` retains the incoming race pointer and calls `0x3b5b8` at `0x3b31b`. This establishes a shared race-management path rather than a wholly separate player automation implementation.

### 3. `0x3b5b8` contains the strongest candidate self-management gate

Near the end of `0x3b5b8`, a loop walks the planet array with the same `0x7b` stride. For each candidate planet it:

1. compares byte `[planet+0x57]` with byte `[race+0]` and skips non-owned planets;
2. compares the race id with the current-player id;
3. for a non-player race, proceeds without consulting `planet+0x5a`;
4. for the current player, requires `dword [planet+0x5a] != 0`, unless a separate global override is nonzero;
5. requires `byte [planet+0x54] == 0xff`;
6. loads the race pointer into `EAX`, leaves the planet pointer in `EDX`, and calls `0x3d8f0` at `0x3c118`.

The exact canonical code boundary for the discriminating part is `0x3c0eb..0x3c11c`; the `dword [planet+0x5a]` test itself is at `0x3c0fc`.

**Interpretation:** `+0x5a` is the strongest static candidate for the player-planet “allow existing AI/self-management” state consumed during a turn. This is not yet proof that the UI control writes that field; RE2/RE4 own that question. The independent global override means `+0x5a` must not be treated as the sole semantic condition until RE5 establishes the normal-runtime state of that global.

The owner interpretation of `+0x57` is strongly supported by this loop because the field is compared directly against the race record's identity byte before race-specific work is performed. It remains a structural/data-flow interpretation rather than a recovered type definition.

### 4. `0x3d8f0` is the automatic next-action policy candidate

`0x3d8f0` is reached from the gate above when an owned planet has no current action (`+0x54 == 0xff`). Its prologue stores the incoming `EAX` value and copies incoming `EDX` to `ESI`; downstream code repeatedly uses the latter as the planet-like object.

The body reads planet-relative production/resource/state fields, consults type tables, evaluates multiple candidate classes, uses a random/tie-breaking path, and then invokes lower-level mutation helpers. It calls `0x34b0c` at `0x3db17`, `0x3dbf7`, and `0x3df88` with selected type/index-like values.

This supports **high static confidence** that `0x3d8f0` is on the automatic decision/policy layer. It does not justify reconstructed source-level algorithm names or a claim that every branch has been understood.

### 5. `0x34b0c` is downstream action/queue mutation, not the policy gate

At entry `0x34b0c` captures:

- `EAX` as the planet-like pointer (`ESI`);
- `EDX` as an index-like input;
- `BL` as a type/action byte;
- `CL` is consumed as another mode/control input in the routine.

Its control flow manipulates the planet's slot array at `planet+0x10`. In the assignment path around `0x34db2..0x34df5`, it clears/replaces the previous selection, writes word `[planet+0x52]`, writes byte `[planet+0x54]`, and subsequently calls `0x34e70` to refresh derived planet state.

That distinguishes the layers required by RE3:

- `0x3c0fc` / surrounding block — candidate “is this player planet automated?” state consumption;
- `0x3d8f0` — decision/policy candidate;
- `0x34b0c` — action/build-selection mutation candidate;
- `0x352e0` / `0x34e70` — general per-turn/update/recalculation code surrounding the policy, not the policy entry itself.

## Calling-convention evidence

RE3 does **not** infer the ABI from Watcom defaults.

### Two-input call at `0x3c118 -> 0x3d8f0`

The caller establishes two independently traceable object inputs:

- `EDX` is the current planet pointer produced by `planet_base + index * 0x7b` and survives the gate;
- `EAX` is loaded from the current race pointer immediately before the call.

There are no argument pushes in the call preparation. At `0x3d8f0`, the callee immediately stores incoming `EAX` and copies incoming `EDX` into `ESI` before those registers are repurposed. The callee allocates `0x10c` bytes of local stack and all observed `[esp+...]` references stay within `+0x108`; it does not read caller-stack arguments above its local frame.

This is direct evidence for a register-passed internal call with `EAX` then `EDX` as the two live inputs.

### Four-register call into `0x34b0c`

At the canonical `0x3df88` call site, the caller explicitly prepares:

```text
ECX = 1
EBX = 0x15
EAX = planet
EDX = selected index
call 0x34b0c
```

The callee immediately preserves/consumes `EAX`, `EDX`, and `BL`, and its downstream branches consume `CL`. This ordering is consistent with Watcom's register convention `EAX, EDX, EBX, ECX`.

**Conclusion:** relevant internal game calls on this path use a register ABI consistent with `__watcall`. This conclusion is scoped to the observed internal call sites; it is not a claim that every runtime/library call in the executable uses the same convention.

## Cross-product and cross-locale corroboration

The gate is not an Antagonizer-only invention.

On the official English bug-patch baseline, the corresponding owned-planet loop checks the **same object-relative fields**:

- owner/race candidate at `+0x57`;
- current-player-only `dword +0x5a` gate;
- `byte +0x54 == 0xff` before entering policy.

The baseline gate calls its downstream policy candidate at `PATCH_EN 0x3a5a0`. On the canonical Antagonizer it calls `ANTAG_EN 0x3d8f0`.

The International pair independently reproduces the relationship with a stable `+0x40` code displacement inside each product family:

- `ANTAG_EN`: gate `0x3c0eb`, policy `0x3d8f0`;
- `ANTAG_INTL`: gate `0x3c12b`, policy `0x3d930`;
- `PATCH_EN`: gate `0x39f28`, policy `0x3a5a0`;
- `PATCH_INTL`: gate `0x39f68`, policy `0x3a5e0`.

The first 45 bytes of the Antagonizer policy entry are byte-identical across locales, as are the first 45 bytes of the patch policy entry across locales; the Antagonizer and patch policy prologues then materially differ in local-frame/layout and downstream code. This is consistent with T1/RE1's lineage model: the original automation gate is retained while Antagonizer changes downstream management logic.

This corroboration increases confidence that `+0x5a` is a pre-existing per-planet gate into generic AI behavior, but it still does not establish the UI write path. That remains deliberately independent RE2/RE4 work.

## RE3 pre-runtime hypotheses handed to RE5

> Historical static handoff: these falsifiers are retained to show what RE5 tested. The current runtime result is recorded in the RE5 confirmation section below.

### H1 — player automation state consumption

**High static confidence; runtime-unconfirmed.** In ordinary turn processing with the separate override global equal to zero, a current-player planet reaches `0x3d8f0` iff its owner matches the player race, `dword [planet+0x5a] != 0`, and `byte [planet+0x54] == 0xff`.

Falsifier: a manual planet confirmed by RE4 reaches `0x3d8f0` under the same override/empty-action conditions, or an automated planet confirmed by RE4 fails the `+0x5a` predicate.

### H2 — shared player/non-player policy

**High static confidence; runtime-unconfirmed.** Non-player owned planets and player-owned automated planets converge on the same `0x3d8f0` policy candidate; the player-specific distinction is made by the gate before the call.

Falsifier: runtime shows that non-player calls arrive with materially different hidden state/dispatch that changes the semantic entry, or that player automation reaches another policy path instead.

### H3 — policy-to-queue boundary

**High static confidence; runtime-unconfirmed.** `0x3d8f0` selects an automatic action and `0x34b0c` applies/queues it by updating the `+0x52/+0x54` current-selection fields.

Falsifier: breakpoints show `0x34b0c` calls on this path that do not produce the expected action-state transition, or a different helper is the actual commitment point.

### H4 — special override bypass

**Medium confidence on role, high confidence on control flow.** The separate global tested after `+0x5a == 0` is an exceptional mode that can force the current-player planet into the AI path. Its semantics are unknown.

RE5 should capture its value and establish a run where it is zero before using `+0x5a` as a causal discriminator.

## RE3 runtime plan executed by RE5

> Historical plan: RE5 kept the experiment bounded but used causal whole-instruction interventions instead of relying only on breakpoint hits. See the runtime confirmation below.

RE5 depends on RE4, so use RE4's runtime-confirmed manual/automated planet identities rather than guessing them from this static note.

Use the CF3 retail runtime harness and exact canonical hash. Resolve the static code VAs through the debugger/runtime mapping rather than assuming a DOS protected-mode selector maps 1:1 to file VAs.

A single bounded turn-advance capture should instrument only these boundaries:

1. gate block around static VA `0x3c0fc`;
2. call site `0x3c118` / policy entry `0x3d8f0`;
3. one policy-to-mutation call such as `0x3df88 -> 0x34b0c`;
4. the `+0x52/+0x54` write path around `0x34db2..0x34df5` if the debugger can break/watch it cheaply.

For each relevant hit, record a bounded row containing:

- race pointer/id and planet pointer;
- planet-relative `+0x57`, `+0x5a`, `+0x52`, `+0x54` values;
- the separate override-global value;
- whether the planet is RE4-confirmed manual or automated;
- whether the policy entry and queue mutation were reached;
- before/after `+0x52/+0x54` when a mutation occurs.

Minimum differentiating scenario:

- one RE4-confirmed manual player planet with no current action;
- one RE4-confirmed automated player planet with no current action;
- at least one non-player owned planet observed opportunistically from the same turn;
- if feasible, a second automated player planet with different resource/construction state.

Expected high-information result if H1-H3 are correct and the override is zero:

- manual player planet: owner match, `+0x5a == 0`, no `0x3d8f0` entry;
- automated player planet: owner match, `+0x5a != 0`, reaches `0x3d8f0` when `+0x54 == 0xff`;
- non-player planet: can reach the same `0x3d8f0` entry without the player-only `+0x5a` requirement;
- a selected automatic action eventually changes/sets `+0x52/+0x54` through the `0x34b0c` path.

This experiment rejects multiple competing models in one turn and does not require tracing the whole game loop.

## Negative findings and scope boundaries

- RE1's `0x352e0` structural lead is on the turn path, but static evidence now places it in general planet progression rather than the self-management policy decision.
- RE1's `0x34e70` changed cluster remains relevant downstream recalculation/state-update code, not the automation gate.
- No UI handler or write to `+0x5a` is claimed here. Parallel RE2/RE4 owns the UI/state transition and may confirm or reject the field interpretation independently.
- The separate override-global semantics are unknown; static control flow is established, semantic naming is not.
- The exact AI scoring algorithm inside `0x3d8f0` is intentionally not reconstructed. M1 does not need it.
- Static addresses are tied only to the named hashes. The cross-locale/product mapping is evidence, not permission to hard-code one address for multiple binaries.
- No target runtime behavior is claimed by RE3. Runtime causality and the smallest final M1 seam remain RE5 acceptance criteria.

## How this was established

See [`../experiments/RE3-static-turn-path.md`](../experiments/RE3-static-turn-path.md) for the exact static procedure, byte-level cross-checks, cross-product/cross-locale observations, and tool provenance.

## RE5 runtime confirmation and reopened Manual-gate question

Evidence class: **runtime**. Blind-RE provenance: **clean**. Full procedure, historical observations, and the 2026-08-13 perturbation follow-up are in [`../experiments/RE5-runtime-turn-path.md`](../experiments/RE5-runtime-turn-path.md).

### Runtime relationships that remain established

On the exact canonical target and pinned `resume.gam`, the same player planet `Xerxes I` starts with owner `+0x57 == 0`, empty selected/current action (`+0x52 == 0xffff`, `+0x54 == 0xff`), and RE4-confirmed Manual/Managed state in dword `+0x5a`. The follow-up preserves these causal relationships:

- **Managed reaches the RE3 gate-to-policy call site.** With `+0x5a == 0xffffffff`, the exact whole-call replacement at static `0x3c118` records the marker on `Xerxes I`; the fresh fixed-window run first observed it at `25.946 ms`.
- **`0x3c118 -> 0x3d8f0` remains necessary for the tested Managed automatic action.** Replacing the complete call (`e8 d3 17 00 00`) with five NOPs leaves Managed set while selection/action remain empty; the fresh independent stardate witness advances `0 -> 233` over `7009.080 ms`.
- **Managed control still selects and commits.** A fresh run reaches `+0x52 = 0x0034`, `+0x54 = 0x00` at the first mutation sample (`3850.656 ms`) while `+0x5a` stays `0xffffffff`.
- **`0x34df2` remains a current-action commit seam.** Suppressing the complete `88 46 54` write preserves upstream selection (`+0x52 = 0x003b` in the fresh run) while `+0x54` remains `ff`; stardate advances by `208` in `7020.877 ms`; the selection was first observed at `4031.758 ms`. The varying selected-slot values are opaque observations, not reconstructed semantics.
- Diagnostic instruction apply/verify and restore/re-verify occur only while DOSBox is confirmed stopped; all fresh patched scenarios restored and re-verified original bytes.

The original exploratory result also remains valid: suppressing only `0x3df88 -> 0x34b0c` did not prevent the tested action, so that single call site is not promoted to the unique policy-to-mutation edge.

### Stardate witness and marker perturbation

The runtime-only dword at RE2-anchor-relative `+0x5e657` remains an exact-target progress witness; it is not published as a guessed DOS/4G guest/static address. Fresh controls now show:

- `manual-control`: `0 -> 232` in `7015.295 ms`;
- `managed-policy-suppressed`: `0 -> 233` in `7009.080 ms`;
- `managed-action-write-suppressed`: `0 -> 208` in `7020.877 ms`;
- `managed-gate-probe`: `0 -> 1` in `7002.031 ms`;
- `manual-gate-probe`: `0 -> 1` in `30017.889 ms`.

The cleanest isolating pair is Managed↔Managed at the same `0x3c118` site: five NOPs produce `+233` stardate progress, while replacing the same call with the process-wide `mov [edx+0x54],0x7e` marker produces only `+1` over essentially the same seven-second window. This strongly establishes **instrumentation-induced progression suppression**. It must not be reported as a game-performance defect.

### Why the Manual/override conclusion is reopened

RE3 statically shows that a current-player Manual planet can bypass zero `+0x5a` only through the separate override branch. The earlier RE5 marker run saw no marker on Manual `Xerxes I` while stardate advanced one unit and therefore treated the override as inactive in that pinned run. The precommitted follow-up deliberately demanded stronger evidence because the marker perturbation was suspicious.

Before the follow-up, the pinned save was checked structurally around the unique Xerxes record:

- immediate `Xerxes ± 0x7b` records are `Stavern IV` and `Xerxes II`, both owner `0xff` (unowned), so they cannot serve as owner-gated `0x3c118` witnesses;
- `Xerxes I` is the only owner-`0` planet in the pinned save, so no two-sided same-player bracket is available;
- nearest structurally validated owned records on opposite sides are `Stavern I` (`-4 * 0x7b`, owner `1`) and `Hurble I` (`+8 * 0x7b`, owner `5`). Both were marked during the fresh Manual and Managed probe runs, but they belong to other race loops and are **supplemental cross-race telemetry only**. No array base/count is inferred.

The agreed fallback for Manual therefore required four stardate increments if Xerxes remained unmarked. The fresh Manual probe ran to its `30 s` hard ceiling, kept Xerxes `+0x52/+0x54` empty and never observed the marker, but reached only `delta = 1`; both cross-race telemetry records were marked. This outcome is **inconclusive by the precommitted oracle**: it shows the shared site is active elsewhere, but it does not establish that the player-race loop traversed the Xerxes position under a sufficiently strong non-perturbed control.

Consequently the stronger former statement “the override bypass is runtime-confirmed inactive in the pinned Manual scenario” is withdrawn. The override's broader semantics and trustworthy runtime value/address remain unknown.

### Evidence/artifact contract

The follow-up separates:

- `artifact_schema` — JSON structure;
- `runner_revision` — exact git SHA provenance, not an automatic compatibility discriminator;
- per-scenario `scenario_contract` — observation/oracle semantics.

Gate probes use explicit policies: Managed is a fixed seven-second window; Manual uses target `4` or timeout `30 s`. Marker reachability is represented as `marker_seen`/`first_marker_ms` rather than inferred from the final byte. Cross-race marker telemetry is accumulated as an ever-seen union so transient marker writes are not lost.

All six fresh focused JSON files were captured and evaluated in the follow-up working set, but the Manual gate artifact is `inconclusive`. The raw focused JSON files were not committed or uploaded and are not reconstructed here. The schema-3 aggregator therefore fails closed and does not emit a causal `run-aggregate.json`; no historical artifact is reconstructed from documentation.

### Current preservation-seam status

The runtime-established Managed decision/commit layering still makes **before `0x3c118`** the strongest candidate M1 compatibility seam: leave `0x3d8f0` and downstream selection/action mutation intact rather than reimplementing the existing AI. However this is no longer an unlocked architecture contract. The Manual/override reachability discriminator is still open, so RE5 requires another, less perturbing witness before dependent A1/A2 work may rely on the completed-gate claim.

A useful next experiment should maximize information gain without process-wide action-state stamping: either directly establish the override condition with a trustworthy runtime relationship or observe player-loop reachability using instrumentation that preserves normal `+0x54` semantics. Do not strengthen the current claim by merely extending the mutating marker window.


> **Status update — 2026-08-14:** the reopened Manual-gate discussion above is retained as historical evidence. RE5 is now closed for M1 by the read-only acceptance experiment documented in [`../experiments/RE5-read-only-override-closure.md`](../experiments/RE5-read-only-override-closure.md); broader override semantics remain unknown.
