# A1 sidecar identity/lifetime — bounded runtime experiment design

Date: 2026-08-20  
Roadmap item: A1 / issue #26  
Blind-RE provenance: **clean**  
Planned evidence class: **runtime**

## Question

Can the exact canonical Antagonizer provide a reuse-safe current-session identity/lifetime contract for mod-owned per-planet sidecar state, without assuming raw-pointer stability, inventing a slot index from the known `0x7b` stride, or treating a presentation name as immutable identity?

This experiment addresses only the **planet identity/lifetime half** of A1. The separate requirement for a lossless boundary on original `planet_record+0x5a -> 0` Manual transitions remains independent and is not satisfied by this run.

## Evidence boundary

Use only the supported repository state, the exact canonical target, the verified maintainer-supplied retail fixture, and project-generated runtime observations. The M1 blind-research gate remains active. Do not consult target-specific external recovered knowledge or unsupported repository history.

Pin the existing runtime inputs before accepting any target observation:

- `ANTAG.EXE` SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`;
- retail runtime fixture accepted by `tools/retail-runtime-manifest.json`;
- the CF3 cloud runtime/debugger path and its fail-closed runtime mapping rather than host-address constants;
- a scenario/fixture identity whose logical planets can be distinguished during the bounded run.

The harness must operate on an isolated verified copy of the retail fixture and must emit only repo-safe detached metadata. No retail payload bytes, private host paths, or unrelated process memory belong in the artifact.

## Competing models

The experiment is designed to distinguish these models rather than confirm a preferred one.

### H1 — reusable pointer with an observable epoch/reset

A live record pointer may be reused, but a population/session epoch or equivalent reset event is observable **before** an address can represent a different logical planet. A sidecar key can therefore be `(epoch, record identity)` if the reset observation is lossless for the intended M1 session boundary.

### H2 — stable indexed population with an observable epoch/reset

An independently established array/indexing relationship exists at runtime and remains meaningful only within an observable population epoch. A sidecar key can therefore be `(epoch, index)` only if base/count/indexing are established by runtime evidence rather than inferred from `0x7b` arithmetic alone.

### H3 — immutable/reuse-detecting record identity

A bounded record-local or adjacent value changes when an address is repurposed and remains stable for the same logical planet across ordinary selection changes. It can participate in the key only if the experiment demonstrates the reuse-detection property; presentation name alone is explicitly excluded.

### H4 — no adequate identity/lifetime seam in the bounded transitions

The tested lifecycle transitions expose pointer/index reuse without a preceding detectable epoch/reuse signal, or no candidate signal is strong enough to distinguish continuity from replacement. This is a valid negative outcome. Preserve it and revisit the sidecar architecture rather than weakening the key requirement.

## Predeclared transitions and control

Run one bounded scenario that contains all of the following. If a transition cannot be made deterministic in the current cloud harness, fail closed and record that as an instrumentation/scenario limitation rather than substituting a weaker transition.

1. **Selection control** — in one unchanged game population, switch between two known player-owned planets and back. The harness must observe two distinct logical records and must classify this as ordinary selection change, not population replacement.
2. **In-session new-game/reset boundary** — start from a qualified game population, invoke the ordinary in-session path that replaces it with a newly initialized game population, then qualify a selected player-owned planet in the new population.
3. **Save/load population replacement** — from a qualified population, load a pinned save or equivalent already-reproducible population-replacement fixture, then qualify the selected player-owned planet after the load.

The new-game and save/load legs answer different questions and are both required unless the implementation demonstrates, before the target run, that one of them is not actually reproducible in the supported cloud harness. In that case the target run is insufficient for a positive identity contract and must report a bounded negative/incomplete result.

## Minimal observation set

At each pre-transition and post-transition qualification point capture only the smallest metadata needed to compare logical continuity and candidate lifetime signals:

- the selected-record runtime pointer resolved through the established runtime mapping;
- bounded record metadata sufficient to recognize the known scenario planet for this experiment, with name retained only as presentation/control evidence, never as the identity key;
- the already-established `+0x5a` field value as a consistency check, not as identity;
- any candidate population base/count/index or epoch/reset signal that is independently discovered by the instrumentation;
- if an index is claimed, the independently observed base/count relationship and the exact calculation that maps the selected pointer to that index;
- a bounded digest of explicitly selected record bytes only when needed to compare continuity, with the captured range and rationale declared in the run manifest.

Do not dump broad address-space regions merely to search retrospectively. Candidate signals must be named and bounded before the evidence is promoted.

## Oracles

### Harness/control oracle

The selection-control leg passes only when:

- two known player-owned planets produce distinct selected-record observations;
- returning to the first planet reproduces the observation expected for that same logical record within the unchanged population;
- no population-replacement event is reported during the control leg.

Failure means the harness cannot distinguish selection change from lifecycle replacement, so no target identity conclusion is allowed.

### Positive identity/lifetime oracle

A positive A1 identity/lifetime result requires one of these evidence-backed contracts:

- **epoch + pointer/reuse detector:** every observed replacement boundary changes or invalidates the epoch/reuse detector before a reused address could transfer stale sidecar state; or
- **epoch + stable index:** base/count/indexing are independently established, ordinary selection changes preserve their meaning, and every observed population replacement changes/invalidates the epoch before an index can refer to a different logical planet; or
- another bounded identity rule that demonstrably fails closed on the tested address/index reuse cases.

A positive result must state exactly which transition establishes invalidation and what implementation event A2/UI2 can observe without periodic best-effort sampling.

### Negative oracle

The bounded result is negative if any of the following occurs:

- the same selected-record address or claimed index is observed for a different logical planet without a preceding accepted epoch/reuse signal;
- candidate epoch/reset signals are only sampled after replacement and could have missed the stale-state window;
- an index depends only on the known `0x7b` stride without independently supported base/count semantics;
- the only distinguishing key is presentation name;
- lifecycle coverage is incomplete or ambiguous;
- runtime mapping, fixture identity, target identity, or control qualification fails.

Negative does not mean the sidecar is impossible. It means this bounded experiment did not establish the contract required to complete the identity half of A1.

## Termination and bounds

The runtime harness must declare and enforce all of these before launch:

- exact target/fixture identity verification;
- an overall timeout;
- a finite action script with no open-ended polling;
- bounded waits for each expected UI/runtime state;
- a maximum number of memory observations per transition;
- explicit process termination expectations;
- artifact emission on both PASS and FAIL/INCOMPLETE paths.

Any unexpected process exit, ambiguous selected-record mapping, missed scripted transition, or unsupported run-record schema is a failed/incomplete experiment, not evidence for H4.

## Detached run record

Use a versioned schema such as `ascendancy.a1-sidecar-runtime-lifetime/v1`. The record must include:

- repository checkout SHA and harness/script digest;
- exact target SHA-256 and verified retail-manifest identity;
- scenario/save identity and action-script digest;
- runtime environment facts material to the claim;
- per-step transition label and bounded observations;
- explicit control result;
- address/index reuse observations;
- candidate epoch/reset observations and their ordering relative to replacement;
- final outcome: `positive-epoch-pointer`, `positive-epoch-index`, `positive-other`, `negative-no-safe-seam`, or `incomplete-harness`;
- claim-boundary booleans for `array_base_established`, `array_count_established`, `stable_index_established`, `reuse_detector_established`, `epoch_boundary_established`, and `manual_transition_invalidation_established`.

For this experiment, `manual_transition_invalidation_established` must remain `false`; that requirement belongs to a separate A1 proof.

## Implementation sequence

1. Reuse the CF3/RE4 runtime fixture verification, isolated-copy handling, and process-memory mapping primitives rather than creating a second trust path.
2. Add a focused A1 runner that first proves the selection-control oracle.
3. Add deterministic scripted new-game/reset and save/load legs using already-supported UI/input mechanisms.
4. Instrument only the bounded selected-record/candidate lifecycle signals needed by this design.
5. Emit the detached run record even on failure.
6. Add synthetic tests for run-record validation and for rejecting false positives such as pointer reuse without epoch change, stride-only pseudo-indexing, and post-hoc/sampled reset observations.
7. Execute the real exact-target experiment only after the synthetic/control path passes.

## Decision after the run

- A positive result may update `docs/re/m1-profile-state-representation.md` and A1 roadmap state with the exact reuse-safe key/epoch contract, while keeping Manual-transition invalidation open.
- A negative result must be preserved under `docs/experiments/` and should trigger an explicit reconsideration of the provisional sidecar direction instead of inventing a heuristic key.
- An incomplete harness result changes no target model; fix the bounded harness/scenario and rerun in a later cycle.

This design intentionally does not choose A2's patch/integration mechanism and does not implement profile state, UI, save persistence, or differentiated automation policy.