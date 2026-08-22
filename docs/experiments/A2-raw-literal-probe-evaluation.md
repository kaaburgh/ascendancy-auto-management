# A2 — exact-target raw-literal capacity probe evaluation

Date: 2026-08-22  
Roadmap item: A2 / issue #30  
Blind-RE provenance: **clean**  
Evidence class in this initial slice: **experiment/evaluation contract only**; the exact-target result is produced separately by the dedicated evidence workflow.

## Purpose

Stage 1 found two large fully file-backed zero/padding leads in object 2 at `0x96c10` (6206 bytes) and `0x988dc` (3052 bytes), but deliberately established no reusable capacity. The repository now has an independent raw-literal producer that scans mapped file-backed bytes without consuming the Stage 1 zero-run inventory, and the dedicated A2 real-target workflow can execute both producers against the hash-pinned canonical target.

This note predeclares how that detached exact-target result is to be interpreted. It prevents a convenient negative literal scan from being promoted into a code/data-cave claim.

## Exact inputs and producer boundary

The evidence run must be bound to:

- canonical `ANTAG_EN.EXE` SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`;
- the exact checkout SHA that contains the workflow and producer implementations;
- SHA-256 identities of the acquisition manifest/tool, LE parser, workflow and material producer inputs recorded by `.github/workflows/a2-real-target.yml`.

The raw-literal producer is independent of the Stage 1 zero-run/direct-control-flow derivation only in its scanning oracle: it searches overlapping little-endian 32-bit words in mapped file-backed bytes for values falling inside the two predeclared candidate ranges. It does not prove absence of computed, indirect, narrower/wider, relocated, encoded, runtime-generated, or semantic references.

## Allowed outcomes

### Outcome A — literal hits exist

Any exact-target literal hit into either candidate is evidence of a possible consumer and therefore blocks declaring the touched region wholly reusable. Record the hit sites and retain both candidates as `reusable: false` unless later bounded analysis proves the references irrelevant to the proposed subrange.

A hit is a triage lead, not semantic identity. Do not infer the accessed type, width, lifetime or purpose from the literal value alone.

### Outcome B — no literal hits

Zero literal hits narrows one consumer class only. Both candidates remain `reusable: false` because computed/indirect addressing, runtime initialization, scratch use, sentinel semantics and other non-literal consumers remain unresolved.

A negative result does **not** select mechanism A. The next step must add an orthogonal consumer/lifetime observation or, if sufficiently defensible reuse evidence remains impractical, advance to the target-neutral LE-growth control already defined as A2 Stage 2.

### Outcome C — producer/run invalid

Wrong target identity, checkout/provenance mismatch, malformed detached output, acquisition failure, or producer failure yields no target-specific conclusion. Preserve the concrete failure and rerun only after the evidence path is repaired; do not reinterpret missing output as a negative scan.

## Review requirements

Before incorporating the detached result into roadmap state:

1. verify target and checkout identities from the detached provenance;
2. verify the candidate ranges are exactly the predeclared A2 leads;
3. distinguish the Stage 1 inventory result from the raw-literal result rather than treating them as independent confirmation of reuse safety;
4. keep every candidate `reusable: false` unless separate evidence establishes a safe bounded subrange;
5. state all unresolved consumer classes explicitly;
6. preserve the decision boundary: mechanism A remains unselected from this probe alone.

## Status impact

This evaluation contract alone does not change A2 status, dependencies, or the selected mechanism. A2 remains `Investigation first` until detached exact-target evidence is reviewed and either establishes a defensible next capacity experiment or moves the project to Stage 2.
