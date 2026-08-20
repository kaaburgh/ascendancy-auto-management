# A1 sidecar identity/lifetime — static census result

Date: 2026-08-20  
Roadmap item: A1 / issue #26  
Producer PR: #55, head `75f36345675d12be93b68da337c4f925e5946df9`  
Exact-target workflow run: `32375884873`  
Blind-RE provenance: **clean**  
Evidence class: **static**

## Question

Review the exact-target census defined by [`A1-sidecar-identity-lifetime-next-probe.md`](./A1-sidecar-identity-lifetime-next-probe.md) into one of its three allowed Stage 2 outcomes without promoting pointer, slot, name, or linear-sweep candidates beyond the evidence.

## Exact evidence binding

The `A1 exact-target static evidence bundle` workflow ran successfully on exact PR head `75f36345675d12be93b68da337c4f925e5946df9`, not on a merge ref. It fetched and verified canonical `ANTAG_EN.EXE` SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` and produced artifact `a1-static-evidence-bundle-75f36345675d12be93b68da337c4f925e5946df9`, artifact id `9408986123`, archive digest `sha256:75373513321e1e4f2984f39d0d396b4f53267966009b870d8d1681a1b8574769`.

The detached bundle manifest records:

- schema `ascendancy.a1-static-evidence-bundle/v1`;
- exact checkout SHA `75f36345675d12be93b68da337c4f925e5946df9`;
- exact canonical target hash;
- material input hashes for the workflow, both A1 producers, target acquisition manifest/script, and LE parser;
- claim boundaries explicitly false for array base, slot indexing, complete writer inventory, and lossless Manual-transition invalidation.

The planet identity census is schema `ascendancy.a1-planet-identity-static-census/v2` and re-established the initializer-shaped leaf at `0x22400` from decoded instruction invariants rather than accepting the address alone. The unique supported span contains the `+0x5a = 0` write at `0x22421` followed immediately by `ret`.

## Observed census

The compact exact-target census reports:

- **0 direct decoded callers** of the re-established initializer entry `0x22400`;
- **38 decoded references** to selected-container global `DS:0x43660`;
- **109 decoded references** to selected-record global `DS:0x43664`;
- **36 decoded `0x7b` contexts**, all explicitly classified as `triage-only`;
- `identity_contract_established: false`.

The zero direct-caller result is a negative static observation only. It does not establish that the initializer has no indirect caller, is not reached by fall-through or another decode boundary, or cannot participate in construction/reset through a relationship outside the producer's direct-call model.

Likewise, the selected-global references and `0x7b` contexts provide investigation leads but do not independently establish an array base/count, a stable slot index, a generation counter, or a lifecycle event that necessarily precedes record reuse.

The companion managed-field writer inventory observed 52 direct decoded `+0x5a` references and conservatively classified 19 as potential writes. That producer intentionally does not establish a complete writer inventory or a lossless Manual-transition invalidation boundary; linear-sweep false positives and indirect/unrecovered paths remain possible.

## Stage 2 decision: outcome C — no adequate static seam

The reviewed census does **not** satisfy outcome A or B from the experiment design:

- no evidence establishes a construction/reset event that necessarily precedes record reuse or population replacement;
- no evidence establishes an array base/count or equivalent stable indexing relationship together with a generation/reset boundary.

Therefore the bounded result is **Outcome C: no adequate static seam**.

This is a durable negative result, not evidence for raw-pointer stability and not permission to infer a slot key from `0x7b` arithmetic. A1 remains `Investigation first` and the selected two-layer sidecar representation remains provisional on the unresolved identity/lifetime contract.

## Next bounded A1 experiment

Move the identity half of A1 to runtime rather than broadening static inference. The next experiment should use the established CF3 runtime path on the exact canonical target and observe the smallest set of candidate population/selection signals across lifecycle transitions that can falsify unsafe key models.

The runtime experiment should be designed before instrumentation and must:

1. pin canonical target and fixture identity and reuse the repository's fail-closed runtime mapping rather than hard-coded host addresses;
2. capture the selected record pointer plus only bounded metadata needed to distinguish the same logical planet from a replacement, without treating presentation name as an immutable identity;
3. exercise at least an in-session new-game/reset boundary and a save/load or equivalent population-replacement boundary that is already reproducible in the cloud harness;
4. test whether record addresses/indices are reused and whether any independently observable population epoch/reset signal changes before reuse could transfer a stale sidecar entry;
5. include a control showing that the harness detects an ordinary selection change between two known player-owned records without confusing it with population replacement;
6. emit only repo-safe detached metadata and fail closed on ambiguous mapping, missing transitions, unexpected target/fixture identity, or insufficient coverage.

A successful runtime result may promote a reuse-safe epoch/reuse detector or an independently supported stable indexed population. If the bounded lifecycle transitions still expose no adequate signal, preserve that negative result and revisit the sidecar representation rather than weakening the key requirement.

## Manual-transition invalidation remains separate

This result closes only the static identity-census decision. A1 still separately requires a lossless boundary for original `planet_record+0x5a -> 0` Manual transitions. The plain-M write at `0x3791f` remains a concrete candidate seam, but neither this census nor the conservative potential-writer inventory proves it is the only relevant zero-write path.

No A1 completion claim is made here.
