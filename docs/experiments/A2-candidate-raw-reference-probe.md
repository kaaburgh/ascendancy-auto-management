# A2 — independent raw-reference census for Stage-1 capacity leads

Date: 2026-08-23  
Roadmap item: A2  
Issue: #30  
Blind-RE provenance: **clean**  
Evidence class in this slice: **synthetic/tooling** only until the canonical target run is performed.

## Scope

This slice prepares the first independent static follow-up requested after the A2 Stage-1 capacity inventory. Stage 1 found two large fully file-backed zero/padding leads in object 2 at virtual addresses `0x96c10` (6,206 bytes) and `0x988dc` (3,052 bytes), but correctly left both `reusable: false` because zero content and absence of incoming direct control flow do not establish semantic inactivity.

The new producer is [`../../scripts/analyze_a2_candidate_raw_references.py`](../../scripts/analyze_a2_candidate_raw_references.py). It deliberately does not import the Stage-1 zero-run or GNU-objdump direct-control-flow oracle. Instead it scans the immutable executable bytes at one-byte stride for 32-bit little-endian values falling inside either candidate range under two representations already justified by the established LE layout:

- linear virtual address; and
- object-2-relative offset using the established object-2 base `0x90000`.

A match is only an investigation lead. It can identify a raw encoded reference that Stage 1 did not account for, but it does not by itself prove a live consumer. Conversely, no match does not establish that the range is unused: computed addresses, indirect access, narrower-width operands, relocation semantics, runtime-only initialization, and other consumers remain possible.

## Fail-closed boundary

The operator-facing CLI is pinned to canonical `ANTAG_EN.EXE` SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` and exposes no target-hash override. Output cannot alias the immutable target input. The report is bounded to 10,000 matches and every candidate remains explicitly `reusable: false` / `reuse_evidence: not established` regardless of the result.

Synthetic tests cover linear-VA and object-relative matches, range boundaries, target-hash rejection, CLI hash non-overridability, output-path safety, and the invariant that the producer never upgrades a candidate to reusable capacity.

## Canonical target run

Not performed in this cycle. The current runner has no outbound DNS/network path to the repository-approved Archive.org acquisition source, so no new exact-target static evidence is claimed here. This is an environment-specific acquisition limitation, not evidence about project feasibility: the repository already has a reproducible approved acquisition path in `tools/fetch_free_targets.py` and prior CI evidence that it works.

When target bytes are available through the normal approved path, run:

```sh
python tools/fetch_free_targets.py antagonizer-en
python scripts/analyze_a2_candidate_raw_references.py \
  binaries/ANTAG_EN.EXE \
  --output artifacts/a2-candidate-raw-references.json
```

The resulting report should be reviewed as an independent static signal only. If it finds raw references into either candidate, those sites become higher-priority investigation leads. If it finds none, A2 still requires a stronger independent structural/runtime observation before any existing mapped capacity can be accepted; otherwise proceed to the already-defined Stage-2 target-neutral LE-growth control.

## Roadmap impact

None yet. A2 remains `Investigation first`; Stage-1 capacity remains unestablished as reusable, no patch family is selected, and P1 remains blocked on A2. This slice prepares the next bounded evidence producer without changing status, dependencies, direction, compatibility, or acceptance criteria.
