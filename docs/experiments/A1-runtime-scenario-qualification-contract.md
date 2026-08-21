# A1 runtime scenario qualification contract

Date: 2026-08-21  
Roadmap item: A1 / issue #26  
Blind-RE provenance: **clean**  
Evidence class in this slice: **experiment/tooling contract only**; no new target-runtime claim.

## Purpose

The A1 sidecar lifetime oracle now deliberately refuses to promote a positive identity/lifetime result unless each logical-record witness is bound to an independently supplied scenario qualification and that qualification is itself bound to independently supplied expected source identity.

This note defines the next bounded producer boundary needed before the real runtime experiment can be executed. It keeps scenario qualification separate from the lifetime run so the runtime observer cannot manufacture both the observation and the expected identity it is supposed to match.

## Inputs that must be pinned independently

Before the A1 lifetime runner starts, the qualification producer must receive and verify these values from outside the runtime-observation record:

- canonical target SHA-256;
- retail runtime manifest identity;
- scenario identity;
- qualification-source SHA-256 identifying the exact operator/repository-supplied scenario qualification input;
- a finite set of logical planet labels used only for the bounded experiment.

The lifetime runner may consume these values but must not derive or rewrite them from its own observations.

## Qualification output

Produce a detached JSON document with schema `ascendancy.a1-sidecar-scenario-qualification/v1` containing:

```json
{
  "schema": "ascendancy.a1-sidecar-scenario-qualification/v1",
  "source": {
    "target_sha256": "<64 hex>",
    "retail_manifest_identity": "<non-empty stable identity>",
    "scenario_identity": "<non-empty stable identity>",
    "qualification_source_sha256": "<64 hex>"
  },
  "planets": {
    "<logical-label>": "<sha256 of bounded qualified metadata bytes>"
  }
}
```

The corresponding independently supplied expected-source document uses schema `ascendancy.a1-sidecar-expected-source/v1` and contains the same four source fields. It is an input to validation, not output copied from the runtime run record.

## Bounded witness rule

Each planet digest must cover a deliberately selected, bounded metadata byte range that is sufficient to distinguish the scenario's known logical records during this experiment. The range and rationale must be declared before the target run. Presentation name may be present as control/presentation evidence but may not be the sole metadata basis.

The qualification step does **not** claim that these metadata bytes are an immutable planet identity. Their only role is to independently bind the bounded experiment's labels to the runtime observations so pointer/index reuse can be detected without circularly trusting labels emitted by the observer itself.

## Fail-closed requirements

The producer/validator must reject:

- unsupported schema versions;
- missing or malformed source identities;
- duplicate logical labels after normalization;
- empty metadata ranges;
- metadata larger than the lifetime oracle's 512-byte witness bound;
- presentation-name-only qualification;
- any digest not matching the exact bounded bytes supplied for qualification;
- source identity that differs from the expected-source document or later lifetime-run inputs.

No positive A1 identity outcome is valid when qualification is missing, ambiguous, or generated from the same runtime observations being judged.

## Repository-safe boundary

Commit only the schema/producer/validator, synthetic fixtures and compact digests. Do not commit retail save data, target executables, broad memory dumps, private paths, usernames, or unrelated process memory.

If the qualification input itself contains proprietary bytes, consume it from the operator-supplied artifact path and emit only the bounded digests required by the experiment.

## Validation slice

The implementation PR for this producer should include synthetic tests proving at least:

1. deterministic generation for the same bounded input;
2. rejection of a source-identity mismatch;
3. rejection of presentation-name-only qualification;
4. rejection of oversized or empty metadata;
5. rejection when a declared digest does not match supplied bytes;
6. successful consumption by `scripts/a1_sidecar_lifetime_oracle.py` for a synthetic positive fixture without weakening any of the oracle's replacement/invalidation checks.

These are `reconstructed-local` validation claims only. They do not establish target identity/lifetime behavior.

## Decision boundary

This slice does not complete either half of A1. It only closes the evidence-input contract needed to make the already-designed runtime experiment non-circular and reviewable. The next executable work is to implement this bounded qualification producer/validator and then wire it into the focused A1 runtime runner. The real exact-target lifecycle run remains a later evidence-producing step.
