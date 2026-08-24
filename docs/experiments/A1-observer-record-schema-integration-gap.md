# A1 observer record schema integration gap

Date: 2026-08-24  
Roadmap item: A1 / issue #26  
Blind-RE provenance: **clean**  
Evidence class in this slice: **tooling/schema inspection and synthetic validation only**; no new target-runtime claim.

## Finding

The bounded observer core and the lifetime evidence validator originally did not share one lossless positive-path witness representation.

`scripts/a1_lifetime_observer_core.py` intentionally serializes repository-safe witness metadata only: the predeclared record-relative range plus the observed SHA-256 digest. This matches the exact-target observer contract, which says selected `0x7b` record bytes are discarded after qualification rather than serialized.

The legacy positive-path validator in `scripts/_a1_sidecar_lifetime_oracle_core.py`, however, requires `qualified_witness.metadata_hex` and recomputes the digest from those bytes. The previous `scripts/a1_sidecar_evidence_bundle.py` path projected a v2 scenario manifest onto the legacy v1 lifetime-oracle manifest before calling that validator, so the v2 `witness_ranges` contract could not substitute for `metadata_hex`.

## Resolution

The public lifetime validation boundary now preserves legacy v1 behavior while adding a fail-closed v2 witness path:

1. legacy v1 records continue to require bounded `metadata_hex` and recompute its SHA-256;
2. scenario-qualification v2 accepts digest-only qualified witnesses only when `scenario_planet`, `metadata_basis`, `record_offset`, `length`, and `metadata_sha256` exactly match the independently generated `witness_ranges` entry;
3. the v2 range digest must also equal the independently generated `planets` digest for that logical record;
4. a v2 qualified witness containing `metadata_hex` is rejected as a mixed representation rather than silently choosing one interpretation;
5. the A→B→A selection-control validator applies the same v2 binding rules;
6. `scripts/a1_sidecar_evidence_bundle.py` now passes the full v2 scenario manifest through the lifetime and selection-control validators instead of discarding witness-range semantics on the positive path.

Synthetic coverage exercises the accepted v2 digest-only path plus mixed-representation, range-mismatch, witness-digest mismatch, and manifest-range-digest mismatch failures. Existing legacy lifetime/selection-control coverage remains the compatibility regression.

This closes the tooling integration defect only. It is not evidence that the sidecar design is safe and it adds no target-runtime result.

## Next bounded implementation slice

The exact-target adapter may now emit a positive candidate lifetime record using the already-reviewed digest/range-only observer transcript and run the predeclared lifetime experiment. The adapter must retain all existing bounded action, target-identity, provenance, selection-control, replacement-ordering, and fail-closed requirements.

The separate Manual-transition invalidation requirement remains independent and open, and A1 remains investigatory until both the reuse-safe identity/lifetime contract and that lossless invalidation boundary are established.
