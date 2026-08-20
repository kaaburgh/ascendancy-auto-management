# A1 sidecar identity/lifetime — next bounded evidence experiment

Date: 2026-08-20  
Roadmap item: A1 / issue #26  
Blind-RE provenance: **clean**  
Evidence class in this slice: **experiment design only**; no new target claim.

## Question

A1 has selected a two-layer M1 representation, but cannot complete until the sidecar has (1) a reuse-safe logical-planet identity/lifetime boundary and (2) a lossless invalidation boundary for original `planet_record+0x5a -> 0` Manual transitions.

The next bounded static experiment asks a narrower question: **where does the already-established `0x7b` planet-record population come from, and does the canonical binary expose a reviewable construction/reset seam that can provide an epoch or reuse detector without inventing array stability?**

This experiment deliberately does not try to choose A2's patch mechanism or declare a sidecar key before evidence exists.

## Existing supported anchors

On canonical `ANTAG_EN.EXE` (`sha256 8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`), current supported evidence provides these anchors:

- a `0x7b` runtime planet-record stride;
- selected-record pointer flow through `DS:0x43664`, including one path that loads an element pointer from `[container + index*4 + 0x42]` after reading the container from `DS:0x43660`;
- a supporting initializer-shaped routine at code VA `0x22400` whose write at `0x22421` clears record `+0x5a`;
- the original plain-M path that performs the reversible `+0x5a` write at `0x3791f`;
- no established planet-array base/count, no established pointer non-reuse guarantee, and no established session/population epoch.

These are investigation anchors, not symbol/type identities.

## Stage 1 — static producer/caller census

Add a fail-closed exact-target probe that reconstructs code object 1 with the existing LE parser and emits only compact derived metadata for:

1. every direct `CALL rel32` whose target is the uniquely re-established initializer-shaped routine containing the `+0x5a = 0` write;
2. bounded decoded instruction windows around those direct callers;
3. decoded references to the already-established selected-container / selected-record globals (`DS:0x43660`, `DS:0x43664`) and bounded windows around them;
4. occurrences of the established `0x7b` constant in decoded arithmetic/control-flow context, clearly marked as triage rather than proof of record indexing.

The probe must re-establish every anchor from byte/instruction invariants on the exact target instead of trusting the numeric address alone. Zero or ambiguous matches for an anchor fail closed.

### Required machine-readable provenance

The detached JSON result must carry:

- schema/version;
- exact target SHA-256;
- checkout SHA;
- LE parser identity/material-input hashes;
- decoder identity when GNU `objdump` is used;
- the invariant used to re-establish each anchor;
- caller/reference addresses and bounded normalized instruction text only;
- an explicit `identity_contract_established: false` unless a later reviewed analysis promotes independently supported facts.

Do not commit target bytes, raw disassembly dumps, or broad extracted data.

## Stage 2 — evidence decision

Review the compact census for one of three outcomes:

### A. Reuse-safe construction/reset seam found

Promote only if the evidence establishes a lifecycle event that necessarily precedes record reuse or population replacement and can be observed without guessing. Document the exact invariant and why a stale sidecar entry cannot survive the event.

This may satisfy the identity/epoch half of A1, but does **not** by itself satisfy Manual-transition invalidation.

### B. Stable indexed population established

Promote a slot/index key only if array base/count (or an equivalent indexing relationship) is independently established and the evidence also supplies a generation/reset boundary. `0x7b` stride plus alignment is insufficient.

### C. No adequate static seam

Record the negative result. The next A1 step becomes a bounded runtime experiment that watches population/selection changes across new-game/load/session transitions and tests candidate generation signals. Do not silently downgrade to raw-pointer or name-based identity.

## Manual-transition invalidation remains separate

Regardless of the identity result, A1 still needs a lossless boundary for original Manual transitions. The established plain-M write at `0x3791f` is a concrete candidate seam for later integration, but this experiment does not claim that it is the only writer or that observing it alone covers every possible `+0x5a -> 0` transition.

A later completion claim must either establish all relevant zero-write paths or establish an equivalent event/invariant that cannot miss a Manual transition before a later Managed state reuses sidecar identity.

## Success / failure oracle

This experiment succeeds as an **investigation step** when it produces a deterministic, exact-target-bound compact census that makes the next identity/lifetime decision reviewable without raw target material.

It succeeds as **A1 identity evidence** only if the reviewed result independently establishes a reuse-safe epoch/indexing invariant. Otherwise the correct result is a durable negative/ambiguous finding and a narrowed runtime follow-up.

It never by itself completes A1.

## Deliberately excluded

- selecting the A2 patch/integration mechanism;
- implementing the sidecar or UI state machine;
- assuming pointer, slot, index, or planet name stability;
- save-format persistence;
- target-specific external recovered knowledge while the M1 blind-research gate is active;
- broad disassembly publication or proprietary target bytes.
