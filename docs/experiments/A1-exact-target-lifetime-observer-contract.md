# A1 exact-target lifetime observer — implementation contract

Date: 2026-08-24  
Roadmap item: A1 / issue #26  
Blind-RE provenance: **clean**  
Planned evidence class: **runtime**

## Purpose

Define the smallest exact-target observer that can consume the already-reviewed A1 scenario-qualification v2 witness contract and emit one detached lifetime record for the existing sidecar lifetime oracle. This is an implementation contract for the next bounded experiment; it does not itself establish a reuse-safe sidecar key, epoch, replacement boundary, or Manual-transition invalidation seam.

## Existing trusted boundaries

The observer must reuse, rather than replace, the current repository trust chain:

- scenario qualification is produced before target launch and supplied as `ascendancy.a1-sidecar-scenario-qualification/v2`;
- `scripts/a1_observer_witness.py` is the only permitted witness-range interpretation layer for selected-record qualification;
- the current A1 orchestration wrapper owns timeout/process-group cleanup, provenance hashing, detached-record collection, and invocation of the existing lifetime evidence bundle validator;
- canonical target identity, retail-runtime manifest identity, isolated writable copy handling, and runtime address translation come from the already-supported CF3/RE4 path;
- the existing sidecar lifetime oracle remains authoritative for whether the detached record supports a positive, negative, or incomplete identity/lifetime outcome.

The observer must not re-derive witness offsets, accept presentation names as identity, infer a stable index from `0x7b` stride arithmetic, or broaden memory capture to discover a convenient key after the run.

## Inputs

Before launch, the orchestration layer supplies immutable inputs:

1. exact scenario-qualification v2 manifest;
2. exact target and verified retail-runtime identities;
3. bounded action script describing the predeclared A → B → A selection control, new-game/reset replacement, and save/load replacement legs;
4. bounded logical labels expected at each qualification point;
5. a fresh detached output path.

The orchestration layer must treat the action script, and any other file-backed immutable observer argument, as first-class provenance input: hash it before launch, recheck that exact content immediately before target interaction, and record its path-independent identity/digest in the detached result alongside the already-bound qualification, expected-source, observer, and generated-manifest identities. `observer_args` alone are not sufficient provenance for file-backed inputs. Any missing, stale, schema-incompatible, changed, or digest-mismatched immutable input fails before target interaction.

## Observation primitive

At each scripted qualification point the observer must perform exactly this bounded sequence:

1. resolve the current selected-planet record through the existing runtime mapping path;
2. read exactly one `0x7b` selected-record snapshot;
3. call `qualify_selected_record()` from `scripts/a1_observer_witness.py` with the predeclared logical label;
4. record only repository-safe metadata: logical label, runtime record pointer, witness offset/length/digest, `+0x5a` value, step label, and any separately predeclared candidate lifecycle signal;
5. discard target bytes after qualification rather than serializing them into the detached record.

A read that is short, unmapped, multiply resolved, or fails the witness check terminates the run as `incomplete-harness`; it must not be treated as evidence for replacement or H4.

## Lifecycle ordering requirement

For any candidate epoch/reset/reuse detector to support a positive result, the observer must capture its transition ordering relative to population replacement. The detached record must distinguish at least:

- value/state immediately before the replacement action;
- first accepted lifecycle-signal change or invalidation event;
- first post-replacement selected-record qualification.

If the candidate signal is observed only after the new population is already addressable, or only by periodic sampling with a stale-state window, the observer must mark that leg insufficient for a positive contract.

The observer may record `no candidate signal` without failure. That is an admissible negative result for the oracle, not a reason to invent a weaker identity rule.

## Selection-control requirements

The A → B → A control is valid only when all of the following are observed in one unchanged population:

- A and B independently satisfy their predeclared witness contracts;
- A and B have distinct runtime record pointers;
- no replacement event is reported during the control;
- returning to A returns to the originally qualified A pointer and witness.

Failure of this control yields `incomplete-harness`. It does not establish pointer reuse or unsafe lifetime behavior.

## Replacement legs

The observer must keep the two replacement mechanisms distinct in the record:

- `new-game-reset`;
- `save-load-replacement`.

Each leg must have its own pre-action qualification, bounded scripted action result, lifecycle-signal ordering record, and post-action qualification. One successful leg cannot substitute for the other in a positive identity/lifetime result.

If the supported cloud harness cannot deterministically execute one leg, the record must state that exact limitation and remain incomplete for positive A1 identity/lifetime completion.

## Detached record additions

The exact-target observer should populate the existing lifetime-record schema rather than create a second competing schema. Where the current schema permits extensible observation objects, each qualification point should include:

- `step`;
- `logical_record`;
- `runtime_record_pointer`;
- `witness` with offset, length, expected digest and observed digest;
- `managed_field_value` for `record+0x5a` as a consistency observation only;
- `population_replacement` classification;
- predeclared lifecycle-signal observations with explicit ordering.

The detached record must also carry the orchestration provenance identities for every file-backed immutable input, including the action script digest used for the run, without serializing proprietary target bytes or host-specific absolute paths.

If the current schema cannot represent the required ordering or immutable-input provenance without ambiguity, extend and version that existing schema in a separate bounded tooling change before running the target. Do not overload unrelated fields or encode ordering in prose strings.

## Transcript / lifetime-record relationship

The implementation uses `ascendancy.a1-lifetime-observer-transcript/v1` only as a bounded intermediate execution trace. It is not a second oracle-facing evidence record. `scripts/a1_lifetime_record_adapter.py` deterministically derives the existing `ascendancy.a1-sidecar-runtime-lifetime/v1` record from that transcript, and the lifetime oracle validates only the derived lifetime record.

`scripts/run_a1_lifetime_pipeline.py` is the committed integration boundary for this relationship: it builds or receives the plan inputs, calls `execute_observer_plan()`, adapts the resulting transcript exactly once, then calls `validate_record()` on the derived lifetime record. The committed `docs/experiments/A1-synthetic-lifetime-record.json` is generated through that path and is synthetic tooling evidence only. Its `incomplete-harness` outcome is intentional because the intermediate transcript omits the raw/oracle-shaped reuse evidence required for a positive lifetime claim.

The exact-target orchestration path may replace the synthetic backend, but it must preserve this one-way relationship rather than treating transcript and lifetime record as competing result formats.

## Fail-closed bounds

The observer must declare and enforce before launch:

- finite action count;
- maximum qualification attempts per scripted step;
- bounded per-step wait;
- bounded total runtime;
- one selected-record snapshot per accepted qualification attempt;
- no broad process-memory dump;
- detached record emission on PASS, FAIL, and INCOMPLETE paths;
- process-tree cleanup delegated to the existing orchestration layer.

Unexpected process exit, target/fixture mismatch, ambiguous runtime mapping, missing scripted UI transition, witness mismatch, unsupported schema, immutable-input provenance mismatch, or output-path mutation is `incomplete-harness`.

## Evidence and claim boundary

Synthetic tests for the observer may establish only tooling behavior. A positive A1 identity/lifetime claim requires CI- or runner-produced detached evidence from the exact canonical target and successful validation by the existing A1 lifetime evidence bundle.

Even a positive exact-target lifetime result leaves the separate lossless Manual-transition invalidation requirement open. This observer must not set `manual_transition_invalidation_established` to true.

## Next bounded implementation slice

The synthetic plan → execute → adapt → validate chain is now committed and produces a durable repository-safe record without a test harness supplying the middle. The next bounded slice is to place the exact-target backend/orchestration under that same integration boundary, preserving all existing target identity, immutable-input provenance, timeout, cleanup, action-ordering, witness, and detached-output requirements.

That target run must not change the predeclared witness contracts or action semantics merely to obtain a positive result. A target-produced result remains subject to the existing lifetime oracle and evidence bundle, and the separate Manual-transition invalidation requirement remains independent.
