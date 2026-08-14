# RE5 — read-only Manual override closure

Date: 2026-08-14  
Roadmap item: RE5  
Blind-RE provenance: **clean**  
Evidence class: **runtime**, with static relocation/direct-reference corroboration.

## Why this follow-up exists

The 2026-08-13 perturbation follow-up demonstrated that the process-wide action-marker probe materially suppresses normal simulation progress. Its strengthened Manual run was therefore correctly retained as **inconclusive** rather than promoted into a negative causal result.

This follow-up changes the observation method instead of extending the same perturbed run. It uses `scripts/run_re5_override_witness.py`, which performs **no guest code writes and no guest data writes**.

This document supersedes only the older conclusion that RE5 remained blocked on the perturbing Manual marker. The marker experiment itself remains a useful negative instrumentation result and is not deleted or reinterpreted as a clean performance measurement.

## Published evidence contract

The hardened v2 runner used for the acceptance runs is:

- Git revision: `b795235b34c4b7d739a18e5245f45e398383cfcc`;
- runner source SHA-256: `fccdbd5c4eb5de55c2a0662018258f69aa95d805fffaa9a8edd5fe51156f782f`;
- target SHA-256: `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`;
- fixture manifest SHA-256: `814c37ea8683e9c32ce494bcb9568d08a33d3ef8e6d91b99ac07f37958269852`;
- pinned `resume.gam` SHA-256: `fe7b29f63b685df3b098c0bd109a44e95c9a36a2116617b6c0363eb289a813d3`;
- artifact schema: `ascendancy.re5-override-witness/v2`;
- scenario contract: `re5/manual-override-witness/v2`.

Before runtime sampling, the runner fails closed unless the canonical gate relationship is reproduced from the target itself. The compare at static `0x3c102` has a 32-bit LE relocation at source page offset `0x104`; that relocation targets object 2 offset `0x10d00`. Object 2 has static relocation base `0x90000`, so the derived operand is `0xa0d00`. The runner also checks the gate instruction form, the raw immediate/relocation agreement, target object uniqueness and the final derived VA before using the dword as the override oracle.

The runtime data-object placement is then derived from five **disjoint** file-backed initialized-data signatures at `0x90895`, `0x90eb8`, `0x95078`, `0x987d0` and `0x998ba` (sizes 40, 40, 40, 32 and 15 bytes). They do not overlap; each must match exactly once in the runtime mapping, and all five must imply one uniform bias. Both acceptance runs derive `-0xd000`.

The stardate witness is now read through the same bias-derived `data_host` path as the override. Its data-model VA `0xa2f6c` must resolve to exactly the same host address as the previously established RE2-anchor-relative `+0x5e657` witness. A wrong bias therefore fails before sampling. The stardate then visibly advances during the run, providing liveness for the bias-corrected addressing path above the override VA.

The fixture guard for the startup condition is recursive: any file named `flash.pop`, at any depth under the verified fixture root, causes the runner to fail closed.

## Predeclared runtime oracle

Every coherent sample stops DOSBox, reads the override condition together with current-player identity, the Manual Xerxes record fields and stardate, then resumes. The acceptance oracle requires:

- a fixed seven-second observation window;
- at least 200 coherent samples;
- maximum observed sample gap at most 50 ms;
- stardate progress of at least four units;
- current-player identity and Xerxes ownership stable for the player;
- Manual state stable throughout;
- no automatic slot/action committed throughout;
- the statically identified override condition equal to zero in every coherent sample.

## Fresh exact-target v2 results

Two independent DOSBox processes passed the exact published contract:

| Run | Samples | Max gap | Stardate | Override values | Result |
| --- | ---: | ---: | ---: | --- | --- |
| [`run 1`](RE5-override-witness-b795-run1.json) | 272 | `40.349 ms` | `0 -> 235` (`+235`) | `[0]` | **PASS** |
| [`run 2`](RE5-override-witness-b795-run2.json) | 273 | `33.350 ms` | `0 -> 235` (`+235`) | `[0]` | **PASS** |

Both artifacts are repository-safe summaries. They contain target/fixture identity, relative mapping evidence, the statically derived gate relationship, before/after state and oracle results, but no process dump, host addresses or proprietary target byte payloads.

The normal `+235` / `+235` stardate progress is important: unlike the old process-wide marker experiment, the final Manual witness is not carrying the severe progression suppression that made the marker result inconclusive.

## Reliance chain and bounds

The final claim is intentionally a chain rather than a single all-zero observation:

1. **Static identity:** the hash-pinned target plus the `0x3c102` LE relocation derive the override operand as object 2 + `0x10d00` = static `0xa0d00`.
2. **Runtime mapping:** five disjoint initialized-data signatures independently reproduce one runtime data-object bias (`-0xd000`).
3. **Address-path liveness:** stardate is resolved through that same bias path, cross-checks the established anchor-relative witness, and advances `+235` in each run.
4. **Runtime state:** the derived override dword is zero at every coherent sample while the player/planet remain Manual and simulation progress is positive.
5. **Writer corroboration:** static direct-reference inspection finds turn-path reads/compares and one confirmed direct startup assignment on a path conditioned on `flash.pop`, which is absent from and recursively refused by the pinned fixture.

Sampling alone does **not** prove the value was zero at every instant between samples. The worst observed gap in the v2 runs is `40.349 ms`; a hypothetical flag set and cleared wholly inside such a gap could escape the runtime sampler. The direct-writer audit materially narrows that possibility for known direct references, but it does **not** rule out an unknown indirect-address writer. These two limitations are retained explicitly rather than collapsed into a stronger claim.

Accordingly, what is established is bounded: on the canonical target and pinned fixture, the statically identified override address is observed zero throughout two normally progressing Manual windows under a live, cross-checked data-object mapping, with direct-writer static corroboration. Broader gameplay semantics and hypothetical indirect writes remain unknown.

## RE5 conclusion for M1

The Manual/override ambiguity that reopened RE5 is closed to the confidence required for M1:

1. the Managed-side causal interventions already establish the existing policy/commit layering;
2. the final Manual discriminator observes the statically identified separate override condition as zero under normal progress without modifying guest code or action state;
3. the data-object address path is live and cross-checked rather than supported only by constant-zero reads;
4. the old perturbing marker is no longer load-bearing.

The compatibility handoff is therefore established for the pinned M1 target: preserve the existing automated behavior at the already documented pre-policy gate, and leave the existing downstream automatic-management policy and mutation path intact. A1 may now choose the three-profile in-session representation; A2 may choose the integration mechanism.

The old schema-3 six-scenario aggregate is intentionally **not reconstructed or retroactively stamped**. Its Manual component is the perturbing experiment that motivated this replacement, and rebuilding missing historical JSON from prose would violate the repository's evidence-integrity rules.

## Validation

For the hardened witness implementation:

- focused witness suite — **13 tests OK**;
- full unit suite — **310 tests OK** locally before publication of the documentation/evidence updates;
- exact-target static validator derives `0xa0d00` from the canonical gate relocation;
- two fresh exact-target v2 runtime runs passed with the published runner bytes and source hash above.

Final GitHub Actions status is recorded in the PR after the documentation/evidence commits land.
