# A1 observer record schema integration gap

Date: 2026-08-24  
Roadmap item: A1 / issue #26  
Blind-RE provenance: **clean**  
Evidence class in this slice: **tooling/schema inspection only**; no new target-runtime claim.

## Finding

The newly added bounded observer core and the existing lifetime evidence validator do not yet share one lossless positive-path witness representation.

`scripts/a1_lifetime_observer_core.py` intentionally serializes repository-safe witness metadata only: the predeclared record-relative range plus the observed SHA-256 digest. This matches the exact-target observer contract, which says selected `0x7b` record bytes are discarded after qualification rather than serialized.

The existing positive-path validator in `scripts/_a1_sidecar_lifetime_oracle_core.py`, however, still requires `qualified_witness.metadata_hex` and recomputes the digest from those bytes. `scripts/a1_sidecar_evidence_bundle.py` projects a v2 scenario manifest onto the legacy v1 lifetime-oracle manifest before calling that validator, so the v2 `witness_ranges` contract cannot currently substitute for `metadata_hex`.

Therefore a future exact-target adapter cannot faithfully convert the current observer-core transcript into a positive lifetime record without either reintroducing witness bytes that the reviewed observer contract intentionally excludes or changing the validator/schema boundary first.

## Why this matters

This is a tooling integration defect, not evidence that the sidecar design is unsafe and not a target-runtime result. Running the canonical target before closing it would create an avoidable ambiguity: a valid digest/range observation could not pass the existing positive oracle without changing the evidence shape after the run.

Do not work around the mismatch by inventing a digest preimage, weakening witness validation, treating a digest-only observation as implicitly equivalent to legacy `metadata_hex`, or broadening target-memory capture.

## Next bounded implementation slice

Version/extend the existing lifetime validation boundary so it can validate both contracts fail-closed:

1. preserve legacy v1 records containing bounded `metadata_hex`;
2. for scenario-qualification v2, permit a digest-only qualified witness only when `scenario_planet`, `record_offset`, `length`, and `metadata_sha256` exactly match the independently generated `witness_ranges` entry and the scenario `planets` digest;
3. reject mixed, missing, rewritten-label, range-mismatched, or digest-mismatched representations;
4. pass the v2 manifest through the evidence bundle instead of silently discarding its witness-range semantics on the positive path;
5. add focused synthetic tests proving legacy compatibility and fail-closed v2 digest-only behavior.

Only after that boundary is green should the exact-target adapter emit a positive candidate record and run the already-defined lifetime experiment. The separate Manual-transition invalidation requirement remains independent and open.

## Validation for this slice

Repository-source inspection only. No command was executed locally because this runner has no working checkout/network path to GitHub; repository CI on the exact PR head is the integration validation for this documentation-only change.
