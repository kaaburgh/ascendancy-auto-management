# A1 runtime observer orchestration boundary

Date: 2026-08-24  
Roadmap item: A1 / issue #26  
Blind-RE provenance: **clean**  
Evidence class in this slice: **tooling/synthetic only**; no new target-runtime claim.

## Purpose

The A1 lifetime oracle and scenario-qualification producer define the evidence contract for the next exact-target lifetime experiment. `scripts/run_a1_lifetime_observer.py` is the bounded execution boundary between those components and the future target-specific observer.

The runner builds the scenario manifest from independently supplied qualification bytes before starting the observer, gives the observer only that generated manifest plus a fresh record-output path, bounds execution with a timeout, and immediately validates the detached record with the existing A1 evidence bundle. The observer runs in a fresh POSIX process group; timeout cleanup kills that entire group so DOSBox/Xvfb descendants cannot outlive the bounded orchestration step.

The runner records SHA-256 identities for the observer, qualification input, expected-source document and generated scenario manifest, and rechecks all four after execution. The independently supplied qualification and expected-source paths are deliberately not passed to the observer.

## Qualified witness-location boundary

Scenario qualification v2 closes a prerequisite that the digest-only v1 manifest could not satisfy. A target observer must not guess which bytes of a selected `0x7b` record correspond to a trusted logical-label digest. For each logical label the v2 manifest therefore carries a `witness_ranges` entry with:

- `metadata_basis`;
- record-relative `record_offset`;
- bounded `length`;
- expected SHA-256;
- the predeclared rationale for the range.

The manifest does not contain the qualified proprietary bytes. The exact-target observer is expected to resolve the selected record through the established runtime mapping, read exactly the declared range, and emit only bounded repository-safe observation metadata. The v1 qualification path remains supported for existing synthetic/oracle compatibility but is not an acceptable input contract for the exact-target observer.

`scripts/a1_observer_witness.py` now provides the observer-side fail-closed boundary for that rule. It accepts only the v2 manifest, preserves exact decoded logical-label identity, verifies that the manifest's digest and range views agree, requires the declared range to remain inside the established `0x7b` record, and hashes exactly that predeclared slice of one exact-size selected-record snapshot. Its successful result contains the range and digest metadata but not the record bytes. This helper deliberately does not locate a record, choose a witness range, or infer a logical identity from target observations.

## Interface boundary

The observer process receives:

- `--scenario-manifest <path>`;
- `--record-output <fresh-path>`;
- optional observer-specific arguments after `--` on the orchestration command.

Successful exit without a record is an error; non-zero exit or timeout is an error. Timeout cleanup terminates the observer POSIX process group before orchestration returns, and environments without that cleanup capability fail closed. The record must satisfy `scripts/a1_sidecar_lifetime_oracle.py` through `scripts/a1_sidecar_evidence_bundle.py` before the orchestration command reports success.

A future exact-target observer remains responsible for verifying retail fixture/target identity, using an isolated writable runtime copy where required, driving the predeclared selection/new-game/save-load scenarios, resolving each selected `0x7b` record through the established runtime mapping, passing that bounded record to `scripts/a1_observer_witness.py`, collecting only bounded metadata, and emitting the runtime lifetime record. This layer does not infer or fabricate target observations.

## Validation in this slice

Synthetic coverage establishes that the observer-side helper accepts an exact v2-qualified witness and rejects a changed record, a legacy v1 manifest, an out-of-record range, disagreement between manifest digest views, label rewriting, and a non-exact record snapshot size. Existing orchestration tests continue to cover successful `incomplete-harness` flow, refusal to overwrite output, non-zero process failure, scenario-manifest mutation detection, and descendant cleanup on timeout.

These checks establish tooling behavior only. They do not establish a reuse-safe planet key, epoch/reset seam, pointer/index reuse behavior, lossless Manual-transition invalidation, or A1 completion.

## Next experiment

Implement the exact-target lifetime observer behind this interface, using the established runtime mapping and the new observer-side witness verifier, then run the already-defined `selection-control`, `new-game-reset`, and `save-load-replacement` experiment against the canonical target. Preserve a negative/no-safe-seam result if no valid epoch/reuse detector is observed rather than weakening the oracle.

The separate Manual-transition invalidation requirement remains independent and must still be closed with its own lossless evidence boundary.
