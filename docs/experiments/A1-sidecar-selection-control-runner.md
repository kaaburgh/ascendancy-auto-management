# A1 sidecar lifetime — selection-control runner

Date: 2026-08-23  
Roadmap item: A1 / issue #26  
Blind-RE provenance: **clean**  
Evidence class in this slice: **runtime harness/tooling only until an exact-target artifact is reviewed**.

## Bounded goal

Implement only the first executable leg of `A1-sidecar-runtime-lifetime-experiment.md`: prove that the focused runtime harness can select two independently qualified logical planet records and return to the first record within one unchanged game population.

This slice deliberately does **not** implement the new-game/reset or save/load replacement legs and therefore cannot establish a reuse-safe identity/lifetime contract. Its run record must remain `outcome: incomplete-harness` with every identity/lifetime claim boolean false.

## Independent scenario binding

Before launching the target, the runner validates all three qualification inputs produced by the already-reviewed A1 qualification boundary:

- the operator/repository-supplied qualification input;
- the independently supplied expected-source document;
- the detached scenario-qualification manifest.

The two control labels are opaque exact strings supplied on the command line. The runtime observer does not derive or normalize them from presentation names.

For this control leg the predeclared witness range is the first `0x52` bytes of the established `0x7b` planet record. This bounded prefix ends immediately before the already-established current-slot/action/owner/Managed cluster beginning at `+0x52`. It intentionally contains more than the presentation name and assigns no new semantics to the remaining opaque bytes. A positive control requires the exact runtime prefix digest to match the independently qualified digest for each label.

This range is a control witness only. It is not promoted to an immutable planet identity and must not be reused as such without separate evidence.

## Runtime action sequence

Use the existing verified retail/T3 runtime path and an isolated copy of the candidate save. After the ordinary Resume path reaches the planet list:

1. select visible row 0 and identify the selected record;
2. select visible row 1 and identify the selected record;
3. select visible row 0 again and identify the selected record.

Identification uses the game's ordinary `M` toggle followed immediately by the restoring `M` toggle, then the established RE4 `0 -> ffffffff -> 0` transition oracle. The source save and retail tree remain immutable; no diagnostic guest-code patch is used. A run fails if the selected record does not return to Manual after identification.

The control passes only when:

- the two logical labels resolve to distinct record pointers;
- returning to the first logical label reproduces the first pointer;
- each runtime witness matches its independent qualification;
- returning to the first logical label reproduces the first witness digest;
- the two independently qualified witnesses are distinct;
- no population-replacement claim is made.

Presentation names are emitted only as control/debugging evidence and are never the identity basis.

## Detached record boundary

The runner emits `ascendancy.a1-sidecar-runtime-lifetime/v1` so the existing lifetime oracle can reject accidental promotion. For this slice:

- `outcome` is always `incomplete-harness` on success;
- only the `selection-control` transition is present;
- all six claim booleans remain false, including Manual-transition invalidation;
- the record binds the exact checkout SHA, runner digest, action-script digest, target/retail/scenario qualification identities, candidate-save hash, and bounded runtime environment facts;
- the runner invokes the lifetime oracle before emitting success and fails if the record is ever classified as coverage-complete or positive.

Failure artifacts remain fail-closed and contain no positive claim.

## Validation and next boundary

Synthetic unit coverage exercises A→B→A stability, pointer alias rejection, first-record pointer drift, non-distinguishing witnesses, and exact bounded witness hashing. Repository CI remains the integration authority for sibling-module imports and the full unit suite.

An exact-target run is still required before this slice becomes runtime evidence. Even after that control passes, A1 remains open: the next implementation slice is one bounded population-replacement leg with a predeclared candidate epoch/reuse signal. The separate lossless Manual-transition invalidation proof also remains open.
