# A1 runtime observer orchestration boundary

Date: 2026-08-23  
Roadmap item: A1 / issue #26  
Blind-RE provenance: **clean**  
Evidence class in this slice: **tooling/synthetic only**; no new target-runtime claim.

## Purpose

The A1 lifetime oracle and scenario-qualification producer already define the evidence contract for the next exact-target lifetime experiment. This slice adds the bounded execution boundary between those components and the future target-specific observer.

`scripts/run_a1_lifetime_observer.py` builds the scenario manifest from independently supplied qualification bytes before starting the observer, gives the observer only that manifest plus a fresh record-output path, bounds observer execution with a timeout, and immediately validates the detached record with the existing A1 evidence bundle. The observer runs in a fresh POSIX process group; if the timeout expires, the runner kills that entire process group before reporting failure so future target-runtime descendants such as DOSBox/Xvfb cannot outlive the bounded orchestration step.

The runner records SHA-256 identities for the observer, qualification input, expected-source document and generated scenario manifest. It rechecks all four after observer execution and fails closed if any changed. The independently supplied qualification and expected-source paths are deliberately not passed to the observer.

## Interface boundary

The observer contract is intentionally small:

- input: `--scenario-manifest <path>`;
- output: `--record-output <fresh-path>`;
- optional observer-specific arguments follow `--` on the orchestration command;
- successful process exit without a record is an error;
- non-zero exit or timeout is an error;
- timeout cleanup terminates the observer's POSIX process group before orchestration returns; an environment without POSIX process-group cleanup is rejected rather than silently weakening this bound;
- the record must satisfy `scripts/a1_sidecar_lifetime_oracle.py` through `scripts/a1_sidecar_evidence_bundle.py` before the orchestration command reports success.

A future exact-target observer remains responsible for verifying the retail fixture/target identity, using an isolated writable runtime copy where required, driving the predeclared selection/new-game/save-load scenarios, collecting only bounded metadata, and emitting the runtime lifetime record. This orchestration layer does not infer or fabricate any target observation.

## Validation in this slice

Synthetic tests exercise:

1. one successful `incomplete-harness` observer record flowing through scenario qualification and the lifetime oracle;
2. refusal to overwrite an existing record output;
3. fail-closed handling of a non-zero observer exit;
4. detection of observer mutation of the generated scenario manifest;
5. timeout cleanup that kills a spawned observer descendant before it can survive the bounded run.

These checks establish orchestration behavior only. They do not establish a reuse-safe planet key, an epoch/reset seam, pointer/index reuse behavior, lossless Manual-transition invalidation, or A1 completion.

## Next experiment

Implement the exact-target lifetime observer behind this interface and run the already-defined bounded `selection-control`, `new-game-reset`, and `save-load-replacement` experiment against the canonical target. Preserve a negative/no-safe-seam result if no valid epoch/reuse detector is observed rather than weakening the oracle.

The separate Manual-transition invalidation requirement remains independent and must still be closed with its own lossless evidence boundary.
