# RE5 — read-only Manual override closure

Date: 2026-08-14  
Roadmap item: RE5  
Blind-RE provenance: **clean**  
Evidence class: **runtime**, with static direct-reference corroboration.

## Why this follow-up exists

The 2026-08-13 perturbation follow-up demonstrated that the process-wide action-marker probe materially suppresses normal simulation progress. Its strengthened Manual run was therefore correctly retained as **inconclusive** rather than promoted into a negative causal result.

This follow-up changes the observation method instead of extending the same perturbed run. It uses `scripts/run_re5_override_witness.py`, which performs **no guest code writes and no guest data writes**.

This document supersedes only the older conclusion that RE5 remained blocked on the perturbing Manual marker. The marker experiment itself remains a useful negative instrumentation result and is not deleted or reinterpreted as a clean performance measurement.

## Published evidence contract

The published runner revision used for the acceptance runs is:

- Git revision: `a122801ebb0243d8f1d76151f2bbf8beb109bf54`;
- runner source SHA-256: `cfb86d3ce8914487bb23e36f3891a73c9b3a82d2a32dcfecc4aeecd8511ef99f`;
- target SHA-256: `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`;
- fixture manifest SHA-256: `814c37ea8683e9c32ce494bcb9568d08a33d3ef8e6d91b99ac07f37958269852`;
- pinned `resume.gam` SHA-256: `fe7b29f63b685df3b098c0bd109a44e95c9a36a2116617b6c0363eb289a813d3`.

Before reading the RE3 override condition, the runner derives the runtime placement of the LE data object from **five independent initialized-data signatures**. Every signature must match exactly once and all five must imply one uniform runtime bias; otherwise the run fails closed. The two acceptance runs independently derived the same bias, `-0xd000`.

Every coherent sample stops DOSBox, reads the override condition together with current-player identity, the Manual Xerxes record fields and the independent stardate progress witness, then resumes. The predeclared acceptance oracle requires:

- a fixed seven-second observation window;
- at least 200 coherent samples;
- maximum observed sample gap at most 50 ms;
- stardate progress of at least four units;
- current-player identity and Xerxes ownership stable for the player;
- Manual state stable throughout;
- no automatic slot/action committed throughout;
- the RE3 override condition equal to zero in every coherent sample.

## Fresh exact-target results

Two independent DOSBox processes passed the exact published contract:

| Run | Samples | Max gap | Stardate | Override values | Result |
| --- | ---: | ---: | ---: | --- | --- |
| [`run 1`](RE5-override-witness-a122-run1.json) | 273 | `31.015 ms` | `0 -> 234` (`+234`) | `[0]` | **PASS** |
| [`run 2`](RE5-override-witness-a122-run2.json) | 272 | `37.231 ms` | `0 -> 232` (`+232`) | `[0]` | **PASS** |

Both artifacts are repository-safe summaries: they contain target/fixture identity, relative mapping evidence, before/after state and oracle results, but no process dump or proprietary target bytes.

The normal `+234` / `+232` stardate progress is important: unlike the old process-wide marker experiment, the final Manual witness is not carrying the severe progression suppression that made the marker result inconclusive.

## Static corroboration and scope

Static relocation-backed direct-reference inspection is supporting evidence, not the load-bearing oracle. Direct turn-path references to the RE3 override global are reads/compares. One confirmed direct startup assignment can set it in a path conditioned on a file that is absent from the pinned canonical fixture; the runtime runner also refuses that unexpected fixture condition.

This direct-reference audit does **not** prove that no indirect-address writer exists. The final claim is deliberately bounded to the canonical target, pinned fixture, and the two normally progressing observation windows above. Broader gameplay semantics of the override condition remain unknown.

## RE5 conclusion for M1

The Manual/override ambiguity that reopened RE5 is closed to the confidence required for M1:

1. the Managed-side causal interventions already establish the existing policy/commit layering;
2. the final Manual discriminator directly observes the separate RE3 override condition as inactive under normal progress without modifying guest code or action state;
3. the old perturbing marker is no longer load-bearing.

The compatibility handoff is therefore established for the pinned M1 target: preserve the existing automated behavior at the already documented pre-policy gate, and leave the existing downstream automatic-management policy and mutation path intact. A1 may now choose the three-profile in-session representation; A2 may choose the integration mechanism.

The old schema-3 six-scenario aggregate is intentionally **not reconstructed or retroactively stamped**. Its Manual component is the perturbing experiment that motivated this replacement, and rebuilding missing historical JSON from prose would violate the repository's evidence-integrity rules.

## Validation

On published revision `a122801ebb0243d8f1d76151f2bbf8beb109bf54`:

- Documentation workflow `31749508284` — success;
- RE2 static seam workflow `31749508187` — success;
- Tests workflow `31749508194` — success;
- full unit suite — **305 tests OK**, including all eight read-only witness tests;
- CF2 real-target regression, RE1 real-target differential map, CF3 demo/debugger capability and CF4 UI automation capability — success.

The two target observations above were then captured from fresh exact-target processes using that published runner revision and source hash.
